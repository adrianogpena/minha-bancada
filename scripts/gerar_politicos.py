"""
Monta o índice de todos os políticos (vereador a presidente) que o site usa:

  site/dados/indice/<UF>.json   lista leve, para busca e filtros (BR = Presidência)
  site/dados/p/<arquivo>.json   fichas completas, agrupadas por município ou estado. Nos arquivos do TSE (t/<ano>/…), a chave
                                `_disputas` traz uma vez só o que os eleitos do mesmo cargo e local têm em comum (comparecimento e
                                vagas, votos por partido, coligações); a página monta `disputa`, `partidoVotos` e `alianca` de
                                cada ficha a partir dela (`completarEleicao`, em site/assets/js/ficha.js)

Fontes: dados/tse/ (eleitos 2022, 2024 e 2026), dados/senado.json e os
deputados federais em exercício já coletados da Câmara.
Chamado pelo scripts/gerar.py; não acessa a internet.
"""

import json
import statistics
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from coletar_prefeituras import TODAS as CAPITAIS_COM_DADOS

RAIZ = Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "dados"
SAIDA = RAIZ / "site" / "dados"

# cargo do TSE -> (masculino, feminino, ordem de exibição)
CARGOS = {
    "PRESIDENTE": ("Presidente", "Presidenta", 1),
    "VICE-PRESIDENTE": ("Vice-presidente", "Vice-presidenta", 2),
    "SENADOR": ("Senador", "Senadora", 3),
    "DEPUTADO FEDERAL": ("Deputado federal", "Deputada federal", 4),
    "GOVERNADOR": ("Governador", "Governadora", 5),
    "VICE-GOVERNADOR": ("Vice-governador", "Vice-governadora", 6),
    "DEPUTADO ESTADUAL": ("Deputado estadual", "Deputada estadual", 7),
    "DEPUTADO DISTRITAL": ("Deputado distrital", "Deputada distrital", 7),
    "PREFEITO": ("Prefeito", "Prefeita", 8),
    "VICE-PREFEITO": ("Vice-prefeito", "Vice-prefeita", 9),
    "VEREADOR": ("Vereador", "Vereadora", 10),
}
# de qual eleição vem quem está no cargo hoje (deputados federais e
# senadores vêm das APIs da Câmara e do Senado, que já refletem substituições)
MANDATO_ATUAL = {
    2022: {"PRESIDENTE", "VICE-PRESIDENTE", "GOVERNADOR", "VICE-GOVERNADOR",
           "DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL"},
    2024: {"PREFEITO", "VICE-PREFEITO", "VEREADOR"},
}
ELEICAO_NOVA = 2026
MUNICIPAIS = {"PREFEITO", "VICE-PREFEITO", "VEREADOR"}
# (início, fim) do mandato por eleição e cargo. Presidente e governadores tomam posse em 5 e 6 de
# janeiro desde a EC 111/2021 (a partir de 2027); o mandato acaba um dia antes da posse seguinte.
MANDATOS = {
    2018: {"SENADOR": ("2019-02-01", "2027-01-31")},
    2022: {"PRESIDENTE": ("2023-01-01", "2027-01-04"), "VICE-PRESIDENTE": ("2023-01-01", "2027-01-04"),
           "GOVERNADOR": ("2023-01-01", "2027-01-05"), "VICE-GOVERNADOR": ("2023-01-01", "2027-01-05"),
           "SENADOR": ("2023-02-01", "2031-01-31"),
           **dict.fromkeys(("DEPUTADO FEDERAL", "DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL"), ("2023-02-01", "2027-01-31"))},
    2024: dict.fromkeys(("PREFEITO", "VICE-PREFEITO", "VEREADOR"), ("2025-01-01", "2028-12-31")),
    2026: {"PRESIDENTE": ("2027-01-05", "2031-01-04"), "VICE-PRESIDENTE": ("2027-01-05", "2031-01-04"),
           "GOVERNADOR": ("2027-01-06", "2031-01-05"), "VICE-GOVERNADOR": ("2027-01-06", "2031-01-05"),
           "SENADOR": ("2027-02-01", "2035-01-31"),
           **dict.fromkeys(("DEPUTADO FEDERAL", "DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL"), ("2027-02-01", "2031-01-31"))},
}


def periodo(ano: int, cargo_tse: str) -> tuple[str | None, str | None]:
    return MANDATOS.get(ano, {}).get(cargo_tse, (None, None))


CAMPOS_ELEICAO = ("ano", "sequencial", "eleicao", "unidadeEleitoral", "uf", "cargoTse", "resultado", "votos", "titular")


_RESUMOS = {}


def resumo_tse(pasta: str, ano: int, uf: str) -> dict:
    chave = (pasta, ano, uf)
    if chave not in _RESUMOS:
        _RESUMOS[chave] = ler(BRUTO / "tse" / pasta / str(ano) / f"{uf}.json", {})
    return _RESUMOS[chave]


MIN_COMPARACAO = 5   # eleitos mínimos no mesmo cargo (ou cargo e partido) para comparar o custo do voto


def _contas_brutas(ano: int, e: dict):
    return resumo_tse("contas", ano, e["uf"]).get(e.get("sequencialChapa") or e["sequencial"])


def custo_do_voto(e: dict, contas: dict | None) -> float | None:
    """Receita de campanha por voto recebido (soma dos turnos), ou None sem receita ou sem votos."""
    votos = sum(v.get("votos") or 0 for v in e.get("votos") or [])
    if not contas or not contas.get("receitas") or votos <= 0:
        return None
    return contas["receitas"] / votos


_CUSTOS = {}


def medianas_custo_voto() -> dict:
    """Mediana do custo do voto dos eleitos, por (ano, cargo) e por (ano, cargo, partido), em todo o país.
    Vice não entra: a prestação de contas é a da chapa."""
    if not _CUSTOS:
        grupos = defaultdict(list)
        for pasta in sorted((BRUTO / "tse").glob("[0-9]*")):
            if not pasta.is_dir():
                continue
            ano = int(pasta.name)
            for arq in sorted(pasta.glob("[A-Z][A-Z].json")):
                for e in ler(arq, []):
                    if e["cargo"].startswith("VICE-") or e.get("situacao") != "eleito":
                        continue
                    c = custo_do_voto(e, _contas_brutas(ano, e))
                    if c is not None:
                        grupos[(ano, e["cargo"])].append(c)
                        grupos[(ano, e["cargo"], e.get("partido"))].append(c)
        _CUSTOS["m"] = {k: (statistics.median(v), len(v)) for k, v in grupos.items() if len(v) >= MIN_COMPARACAO}
    return _CUSTOS["m"]


def contas_de(ano: int, e: dict):
    """Resumo da prestação de contas de campanha (dados/tse/contas/<ano>/<UF>.json), ou None.
    Acrescenta `custoVoto`: reais de receita por voto do eleito e a mediana dos eleitos do mesmo cargo e do mesmo cargo e partido."""
    contas = _contas_brutas(ano, e)
    custo = custo_do_voto(e, contas)
    if custo is None:
        return contas
    medianas = medianas_custo_voto()
    extra = {"valor": round(custo, 2)}
    for nome, chave in (("cargo", (ano, e["cargo"])), ("partido", (ano, e["cargo"], e.get("partido")))):
        if chave in medianas and not e["cargo"].startswith("VICE-"):
            extra[nome] = {"mediana": round(medianas[chave][0], 2), "n": medianas[chave][1]}
    return {**contas, "custoVoto": extra}


def historico_patrimonio() -> dict:
    """(nome, nascimento) -> {ano: [cargoTse, totalBens]} de todas as eleições coletadas. O TSE não publica mais o CPF,
    então a ligação entre eleições é por nome e data de nascimento."""
    if "p" not in _CUSTOS:
        achados = defaultdict(dict)
        for pasta in sorted((BRUTO / "tse").glob("[0-9]*")):
            if not pasta.is_dir():
                continue
            ano = int(pasta.name)
            for arq in sorted(pasta.glob("[A-Z][A-Z].json")):
                for e in ler(arq, []):
                    if e.get("totalBens") is None or not e.get("nascimento"):
                        continue
                    achados[(chave_nome(e.get("nome"), None), e["nascimento"])].setdefault(ano, [e["cargo"], e["totalBens"]])
        _CUSTOS["p"] = achados
    return _CUSTOS["p"]


def patrimonio_de(e: dict) -> list | None:
    """Total de bens declarado em cada eleição do mesmo político, do mais antigo ao mais recente: [[ano, cargoTse, total]].
    None se só há uma eleição (nada a comparar)."""
    if not e.get("nascimento"):
        return None
    por_ano = historico_patrimonio().get((chave_nome(e.get("nome"), None), e["nascimento"]), {})
    return [[ano, *por_ano[ano]] for ano in sorted(por_ano)] if len(por_ano) > 1 else None


def secoes_de(ano: int, e: dict):
    """Onde o eleito foi votado (dados/tse/secoes/<ano>/<UF>.json), ou None."""
    return resumo_tse("secoes", ano, e["uf"]).get(e.get("sequencialChapa") or e["sequencial"])


def disputa_de(ano: int, e: dict):
    """Comparecimento e vagas do cargo e local da eleição (dados/tse/disputa/<ano>/<UF>.json), ou None."""
    return resumo_tse("disputa", ano, e["uf"]).get(f"{e['cargo'].replace('VICE-', '')}|{e['unidadeEleitoral']}")


def partido_de(ano: int, e: dict):
    """Votos do partido (e da federação) no cargo e local da eleição (dados/tse/partidos/<ano>/<UF>.json), ou None.
    Devolve votosLegenda, votosNominais e totalVotosPartidos (votos válidos de todos os partidos do local); com federação,
    também federacao, votosLegendaFederacao e votosNominaisFederacao."""
    local = resumo_tse("partidos", ano, e["uf"]).get(f"{e['cargo']}|{e['unidadeEleitoral']}")
    p = local and local["partidos"].get(e.get("partido"))
    if not p:
        return None
    r = {"votosLegenda": p[0], "votosNominais": p[1], "totalVotosPartidos": local["totalVotos"]}
    if p[2]:
        membros = [v for v in local["partidos"].values() if v[2] == p[2]]
        r.update(federacao=p[2], votosLegendaFederacao=sum(v[0] for v in membros), votosNominaisFederacao=sum(v[1] for v in membros))
    return r


def alianca_de(ano: int, e: dict):
    """tipo (C coligação, F federação, I isolado), nome, composicao e situacao da legenda do partido do eleito
    (dados/tse/coligacoes/<ano>/<UF>.json), ou None."""
    local = resumo_tse("coligacoes", ano, e["uf"]).get(f"{e['cargo']}|{e['unidadeEleitoral']}")
    i = local and local["coligacaoDoPartido"].get(e.get("partido"))
    return dict(zip(("tipo", "nome", "composicao", "situacao"), local["coligacoes"][i], strict=False)) if i is not None else None


COMUNS = "_disputas"


def comuns_de(e: dict) -> dict:
    """Chaves, nos arquivos disputa, partidos e coligacoes do TSE, do que o eleito tem em comum com os outros do mesmo cargo e local.
    O vice disputa com o titular (disputa); votos por partido e coligações usam o cargo como está."""
    local = e["unidadeEleitoral"]
    return {"disputa": f"{e['cargo'].replace('VICE-', '')}|{local}", "partidos": f"{e['cargo']}|{local}", "coligacoes": f"{e['cargo']}|{local}"}


def eleitos_por_nome(cargo_tse: str) -> dict:
    """Eleitos de 2018 e 2022 a um cargo federal, por nome e UF, para ligar com a Câmara e o Senado."""
    achados = defaultdict(list)
    for ano in (2018, 2022):
        for arq in sorted((BRUTO / "tse" / str(ano)).glob("[A-Z][A-Z].json")):
            for e in ler(arq, []):
                if e["cargo"] != cargo_tse:
                    continue
                bloco = {**{k: e.get(k) for k in CAMPOS_ELEICAO if k != "ano"}, "ano": ano, "cargoTse": cargo_tse}
                bloco["inicioMandato"], bloco["fimMandato"] = periodo(ano, cargo_tse)
                bloco["contas"] = contas_de(ano, e)
                bloco["secoes"] = secoes_de(ano, e)
                bloco["disputa"] = disputa_de(ano, e)
                bloco["partidoVotos"] = partido_de(ano, e)
                bloco["alianca"] = alianca_de(ano, e)
                for n in (e.get("nome"), e.get("urna")):
                    achados[chave_nome(n, e["uf"])].append(bloco)
    return achados


def achar_eleicao(achados: dict, nomes: list, uf: str, fim: str | None = None):
    for n in nomes:
        for b in sorted(achados.get(chave_nome(n, uf), []), key=lambda b: -b["ano"]):
            if not fim or b["fimMandato"][:4] == fim[:4]:
                return b
    return None


def eleicao_deputados(deputados: dict) -> dict:
    """id do deputado federal -> como foi eleito em 2022 (None se for suplente que assumiu)."""
    achados = eleitos_por_nome("DEPUTADO FEDERAL")
    return {did: achar_eleicao(achados, [d.get("nomeCivil"), d.get("nome")], d["uf"]) for did, d in deputados.items()}


def ler(caminho: Path, padrao=None):
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return padrao


def salvar(caminho: Path, obj) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def chave_nome(nome: str | None, uf: str | None) -> str:
    n = unicodedata.normalize("NFD", (nome or "").lower())
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return f"{' '.join(n.split())}|{(uf or '').upper()}"


def rotulo(cargo: str, genero: str | None) -> tuple[str, int]:
    m, f, ordem = CARGOS.get(cargo, (cargo.title(), cargo.title(), 99))
    return (f if (genero or "").upper().startswith("F") else m), ordem


FAIXAS_IDADE = [(16, 17), (18, 24), (25, 34), (35, 44), (45, 54), (55, 64), (65, 74), (75, 200)]   # mesmas faixas do perfil do eleitorado
NIVEIS_INSTRUCAO = ["analfabeto", "le e escreve", "fundamental incompleto", "fundamental completo", "medio incompleto", "medio completo",
                    "superior incompleto", "superior completo"]   # mesma ordem do perfil do eleitorado
OCUPACOES_POR_CASA = 5


def nivel_instrucao(texto: str | None) -> int | None:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").replace("ensino ", "").replace("-", " ")
    t = " ".join(t.split())
    for i, nivel in enumerate(NIVEIS_INSTRUCAO):
        if t == nivel:
            return i
    return None


def perfil_eleitos(eleitos: list, ano: int) -> dict:
    """Perfil de quem foi eleito para uma Casa (dados do TSE no registro da candidatura), no formato do perfil do eleitorado:
    `genero` [homens, mulheres], `faixas` e `instrucao` (8 posições), mais `raca` e `ocupacoes`. Idade na eleição (`ano`)."""
    genero, faixas, instrucao = [0, 0], [0] * len(FAIXAS_IDADE), [0] * len(NIVEIS_INSTRUCAO)
    raca, ocupacoes = Counter(), Counter()
    for e in eleitos:
        g = (e.get("genero") or "").upper()
        if g:
            genero[1 if g.startswith("F") else 0] += 1
        if e.get("nascimento"):
            idade = ano - int(e["nascimento"][:4])
            for i, (de, ate) in enumerate(FAIXAS_IDADE):
                if de <= idade <= ate:
                    faixas[i] += 1
        n = nivel_instrucao(e.get("instrucao"))
        if n is not None:
            instrucao[n] += 1
        if e.get("corRaca"):
            raca[e["corRaca"]] += 1
        if e.get("ocupacao"):
            ocupacoes[e["ocupacao"].strip().capitalize()] += 1
    return {"ano": ano, "total": len(eleitos), "genero": genero, "faixas": faixas, "instrucao": instrucao,
            "raca": raca.most_common(), "ocupacoes": ocupacoes.most_common(OCUPACOES_POR_CASA)}


def bancada_federal_atual(uf: str, deputados: dict) -> tuple[list, int]:
    """Registros de 2022 (TSE) dos deputados federais em exercício pela UF, inclusive suplentes que assumiram, ligados por nome.
    Devolve (registros achados, deputados em exercício); quem não tem registro de 2022 não entra no perfil."""
    candidatos = defaultdict(list)
    for e in ler(BRUTO / "tse" / "2022" / f"{uf}.json", []):
        if e["cargo"] == "DEPUTADO FEDERAL":
            for n in (e.get("nome"), e.get("urna")):
                candidatos[chave_nome(n, uf)].append(e)
    atuais = [d for d in deputados.values() if d["uf"] == uf]
    achados = []
    for d in atuais:
        for n in (d.get("nomeCivil"), d.get("nome")):
            lista = candidatos.get(chave_nome(n, uf), [])
            if lista:
                achados.append(next((e for e in lista if e.get("situacao") == "eleito"), lista[0]))
                break
    return achados, len(atuais)


def custo_assembleia(uf: str, cadeiras: int) -> dict:
    """Despesa liquidada da subfunção Ação Legislativa (DCA do SICONFI) do último ano publicado dividida pelas cadeiras.
    Vazio sem DCA ou sem cadeiras. É o gasto da Casa inteira (pessoal, gabinetes, estrutura), não de cada deputado."""
    anos = ler(BRUTO / "siconfi" / f"{uf}.json", {}).get("anos", {})
    for ano in sorted(anos, reverse=True):
        leg = anos[ano].get("legislativa") or {}
        liquidada = (leg.get("acaoLegislativa") or {}).get("liquidada")
        if liquidada and cadeiras:
            return {"ano": int(ano), "despesaLiquidada": liquidada, "cadeiras": cadeiras,
                    "porParlamentar": round(liquidada / cadeiras, 2), "fonte": leg.get("fonte")}
    return {}


def custo_camara_municipal(ibge: str | None, cadeiras: int, dca: dict) -> dict:
    """Ação Legislativa liquidada (DCA da prefeitura) dividida pelas cadeiras da Câmara Municipal. `dca` é o arquivo de
    dados/siconfi_municipios/<UF>.json. Vazio sem DCA do município ou sem cadeiras."""
    reg = (dca.get("municipios") or {}).get(ibge) or {}
    if not reg.get("liquidada") or not cadeiras:
        return {}
    return {"ano": dca["ano"], "despesaLiquidada": reg["liquidada"], "cadeiras": cadeiras,
            "porParlamentar": round(reg["liquidada"] / cadeiras, 2), "fonte": reg.get("fonte")}


def gerar_perfil_casas(deputados: dict | None = None) -> None:
    """site/dados/perfil_casas/<UF>.json: perfil dos eleitos de cada Casa, para comparar com o eleitorado.
    Chaves: estadual (Assembleia ou Câmara Legislativa, 2022), federal (bancada em exercício na Câmara, com os dados da candidatura
    de 2022; sem `deputados`, os eleitos de 2022), senado (senadores eleitos em 2018 e 2022) e municipal
    (<código TSE do município> -> vereadores de 2024)."""
    ibge_do_tse = ler(BRUTO / "municipios_ibge.json", {})
    for arq in sorted((BRUTO / "tse" / "2022").glob("[A-Z][A-Z].json")):
        uf = arq.stem
        if uf == "BR":
            continue
        def eleitos(ano: int, cargos: set, uf: str = uf) -> list:
            return [e for e in ler(BRUTO / "tse" / str(ano) / f"{uf}.json", []) if e["cargo"] in cargos and e.get("situacao") == "eleito"]

        vereadores = defaultdict(list)
        for e in eleitos(2024, {"VEREADOR"}):
            vereadores[e["unidadeEleitoral"]].append(e)
        federal = perfil_eleitos(eleitos(2022, {"DEPUTADO FEDERAL"}), 2022)
        if deputados:
            achados, em_exercicio = bancada_federal_atual(uf, deputados)
            if achados:
                federal = {**perfil_eleitos(achados, 2022), "composicao": "atual", "emExercicio": em_exercicio}
        estadual = perfil_eleitos(eleitos(2022, {"DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL"}), 2022)
        if estadual:
            custo = custo_assembleia(uf, estadual.get("total"))
            if custo:
                estadual["custo"] = custo
        dca = ler(BRUTO / "siconfi_municipios" / f"{uf}.json", {})
        municipal = {}
        for cod, lista in vereadores.items():
            perfil = perfil_eleitos(lista, 2024)
            custo = custo_camara_municipal(ibge_do_tse.get(cod), perfil.get("total"), dca)
            municipal[cod] = {**perfil, "custo": custo} if custo else perfil
        casas = {
            "estadual": estadual,
            "federal": federal,
            "senado": perfil_eleitos(eleitos(2018, {"SENADOR"}) + eleitos(2022, {"SENADOR"}), 2022),
            "municipal": municipal,
        }
        salvar(SAIDA / "perfil_casas" / f"{uf}.json", {k: v for k, v in casas.items() if v})


def gerar(deputados: dict, estaduais: dict | None = None, pessoas: dict | None = None) -> dict:
    """`pessoas` (identidades.construir()["chaves"]) acrescenta `pessoa`, o id do núcleo, às fichas do TSE e do Senado."""
    estaduais = estaduais or {}
    pessoas = pessoas or {}
    indice = defaultdict(list)       # UF -> entradas
    fichas = defaultdict(dict)       # arquivo -> {id: ficha}
    comuns = defaultdict(lambda: defaultdict(dict))   # arquivo -> {disputa|partidos|coligacoes: {cargo|local: dado do TSE}}

    # páginas atuais de deputados federais e senadores, para ligar com o TSE
    paginas_atuais = {}
    for d in deputados.values():
        href = f"deputado.html?id={d['id']}"
        paginas_atuais[chave_nome(d.get("nomeCivil"), d["uf"])] = href
        paginas_atuais[chave_nome(d.get("nome"), d["uf"])] = href

    # --- deputados federais em exercício (Câmara)
    for d in deputados.values():
        indice[d["uf"]].append({
            "id": d["id"], "nome": d["nome"], "cargo": "Deputado federal", "ordemCargo": 4,
            "partido": d["partido"], "estado": "atual", "foto": d.get("foto"),
            "pagina": f"deputado.html?id={d['id']}", "codigoFeed": f"dep:{d['id']}",
        })

    # --- senadores em exercício (Senado)
    eleitos_senado = eleitos_por_nome("SENADOR")
    for s in ler(BRUTO / "senado.json", []) or []:
        cargo, ordem = rotulo("SENADOR", s.get("genero"))
        sid = str(s["id"])
        fichas["senado"][sid] = {**s, "pessoa": pessoas.get(("senado", sid)), "cargo": cargo, "fonte": "senado", "estado": "atual",
                                 "eleicao": achar_eleicao(eleitos_senado, [s.get("titular")] if s.get("titular") else [s.get("nomeCivil"), s.get("nome")],
                                                          s["uf"], s.get("fimMandato"))}
        paginas_atuais[chave_nome(s.get("nomeCivil"), s["uf"])] = f"politico.html?f=senado&i={sid}"
        paginas_atuais[chave_nome(s.get("nome"), s["uf"])] = f"politico.html?f=senado&i={sid}"
        indice[s["uf"]].append({
            "id": sid, "arquivoFicha": "senado", "nome": s["nome"], "cargo": cargo, "ordemCargo": ordem,
            "partido": s.get("partido"), "estado": "atual", "foto": s.get("foto"),
        })

    # --- TSE: mandatos atuais e eleitos de 2026
    anos = sorted(int(p.name) for p in (BRUTO / "tse").glob("*") if p.is_dir() and p.name.isdigit())
    for ano in anos:
        for arq in sorted((BRUTO / "tse" / str(ano)).glob("[A-Z][A-Z].json")):
            for e in ler(arq, []):
                cargo_tse = e["cargo"]
                if ano == ELEICAO_NOVA:
                    estado = e["situacao"]                     # "eleito" ou "2turno"
                elif cargo_tse in MANDATO_ATUAL.get(ano, set()):
                    estado = "atual"
                else:
                    continue
                cargo, ordem = rotulo(cargo_tse, e.get("genero"))
                uf = "BR" if e["uf"] in ("BR", "BRASIL") else e["uf"]
                arquivo = f"t/{ano}/{e['unidadeEleitoral']}" if cargo_tse in MUNICIPAIS else f"t/{ano}/{uf}"
                atual_href = None
                if estado != "atual":
                    atual_href = paginas_atuais.get(chave_nome(e.get("nome"), uf)) or \
                        paginas_atuais.get(chave_nome(e.get("urna"), uf))
                estadual = None
                if estado == "atual" and cargo_tse in ("DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL"):
                    achado = estaduais.get(chave_nome(e.get("urna"), uf)) or estaduais.get(chave_nome(e.get("nome"), uf))
                    estadual = {"uf": achado[0], "id": achado[1]} if achado else None
                for grupo, chave in comuns_de(e).items():
                    achado = resumo_tse(grupo, ano, e["uf"]).get(chave)
                    if achado is not None:
                        comuns[arquivo][grupo][chave] = achado
                fichas[arquivo][e["sequencial"]] = {
                    **e, "pessoa": pessoas.get(("tse", ano, e["sequencial"])), "cargo": cargo, "cargoTse": cargo_tse, "ano": ano, "fonte": "tse",
                    "estado": estado, "inicioMandato": periodo(ano, cargo_tse)[0], "fimMandato": periodo(ano, cargo_tse)[1],
                    "paginaAtual": atual_href,
                    "contas": contas_de(ano, e),
                    "secoes": secoes_de(ano, e),
                    **({"patrimonio": patrimonio_de(e)} if patrimonio_de(e) else {}),
                    **({"estadual": estadual} if estadual else {}),
                }
                alvo = None   # código dos feeds da página Fique informado; só para quem tem dados acompanháveis (ver scripts/feeds.py)
                if estado == "atual":
                    if cargo_tse == "PRESIDENTE":
                        alvo = "pres"
                    elif cargo_tse == "GOVERNADOR":
                        alvo = f"gov:{uf}"
                    elif estadual:
                        alvo = f"est:{estadual['uf']}:{estadual['id']}"
                    elif cargo_tse == "PREFEITO" and CAPITAIS_COM_DADOS.get(uf, ("",))[0] == e["unidadeEleitoral"]:
                        alvo = f"pref:{uf}"
                indice[uf].append({
                    "codigoFeed": alvo, "id": e["sequencial"], "arquivoFicha": arquivo, "nome": e["urna"], "cargo": cargo, "ordemCargo": ordem,
                    "partido": e.get("partido"), "municipio": e.get("municipio"),
                    "codigoMunicipio": e["unidadeEleitoral"] if cargo_tse in MUNICIPAIS else None,
                    "estado": estado, "totalBens": e.get("totalBens") or None,
                    "foto": e.get("foto"),
                })

    # cargos federais do Brasil todo, para a visão nacional da página inicial (uf = estado de quem aparece)
    indice["BR"] += [{**x, "uf": uf} for uf, lista in indice.items() if uf != "BR" for x in lista if x["ordemCargo"] in (3, 4)]

    # --- grava
    for uf, lista in indice.items():
        lista.sort(key=lambda x: (x["ordemCargo"], x.get("municipio") or "", x["nome"] or ""))
        salvar(SAIDA / "indice" / f"{uf}.json", [{k: v for k, v in x.items() if v is not None} for x in lista])
    for arquivo, mapa in fichas.items():
        salvar(SAIDA / "p" / f"{arquivo}.json", {**mapa, **({COMUNS: dict(comuns[arquivo])} if comuns.get(arquivo) else {})})

    resumo = {}
    for uf, lista in indice.items():
        cont = defaultdict(int)
        for x in lista:
            cont[x["estado"]] += 1
        resumo[uf] = dict(cont)
    salvar(SAIDA / "indice" / "_resumo.json", resumo)
    # o que a página Fique informado oferece: estados com Assembleia coletada e capitais com a Câmara Municipal coletada
    capitais = {}
    for uf, lista in indice.items():
        for x in lista:
            if x.get("codigoFeed") == f"pref:{uf}":
                capitais[uf] = x.get("municipio") or uf
    salvar(SAIDA / "cobertura.json", {
        "estados": sorted(p.parent.name for p in (BRUTO / "estaduais").glob("*/deputados.json")),
        "capitais": dict(sorted(capitais.items())),
    })
    gerar_perfil_casas(deputados)
    total = sum(len(v) for v in indice.values())
    print(f"Políticos no índice: {total} em {len(indice)} UFs; {len(fichas)} arquivos de fichas")
    return resumo
