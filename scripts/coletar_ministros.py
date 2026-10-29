"""
Coleta dos ministros de Estado (primeira etapa; o que fica para depois está em FUTURAS_IMPLEMENTACOES.md, 4.3).
Grava em dados/ministros/ (vai para o git; o histórico de quem passou pela pasta cresce aos poucos):

  planalto.json  {coletadoEm, fonte, atualizadoEm, atuais:[{cargo, nome, vistoDesde}], anteriores:[{cargo, nome, vistoDesde, vistoAte}]}
      lista da página "Ministros e Ministras" do Planalto, que não tem datas: `vistoDesde`/`vistoAte` são os dias da coleta
      em que o par cargo+nome apareceu e sumiu (na primeira coleta, o próprio dia). `atualizadoEm` é o "Atualizado em" da página.
  camara_<ano>.json  {coletadoEm, fonte, itens:{id:{tipo, numero, ano, ementa, dataApresentacao, inteiroTeor, situacao,
      tramitacao, dataStatus, orgao, autores:[[idDeputado, nome]], remessa?, prazoFim?, resposta?, lidoEm?}}}
      requerimentos de informação (RIC) a ministro e requerimentos de convocação/convite de ministro (REQ), do arquivo
      anual da Câmara. Nos RIC, `remessa` (ofício ao ministério), `prazoFim` e `resposta` saem da tramitação, relida só
      quando o último status muda (`lidoEm` guarda a data do status lido) e até chegar a resposta.
  senado_<ano>.json  {coletadoEm, fonte, itens:{id:{identificacao, tipoConteudo, ementa, autoria, dataApresentacao,
      tramitando, deliberacao, dataDeliberacao, documento}}}
      requerimentos do Senado de informações e de convocação de autoridades que citam ministro.
  licencas.json  {coletadoEm, camara:{idDeputado:{nome, historico:[{data, situacao, condicao, descricao}]}},
      senado:{codigo:{nome, afastamentos:[{inicio, fim, cargo, uf}]}}}
      deputados da legislatura fora de exercício que se licenciaram para ser ministro (os em exercício já têm o histórico
      em dados/deputados/) e senadores afastados para ocupar cargo de ministro ou secretário.

A ligação de cada requerimento ao ministro da pasta na data e dos nomes às pessoas fica em `identidades.py`, no `gerar`.

Uso:
    python scripts/coletar_ministros.py
"""

import datetime as dt
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import estaduais_comum as comum
from coletar import API, LEGISLATURA, S, avisar, get, get_todos

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "dados" / "ministros"
PLANALTO = "https://www.gov.br/planalto/pt-br/conheca-a-presidencia/ministros-e-ministras"
ARQUIVOS = "https://dadosabertos.camara.leg.br/arquivos"
SENADO = "https://legis.senado.leg.br/dadosabertos"
ANO_INICIAL = 2023          # governo atual começa em 1º de janeiro de 2023
MINIMO_PLANALTO = 20        # menos que isso na página é mudança de layout, não reforma ministerial
TRABALHADORES = 6
PRAZO_SEG = float(os.environ.get("MINISTROS_PRAZO_MIN", "20")) * 60   # leitura de tramitações para aqui; o resto fica para amanhã
TIPOS_SENADO = ("Informações", "Convocação de autoridades")


def ministro(texto: str | None) -> bool:
    return "ministr" in comum.sem_acento(texto or "")


def convocacao(texto: str | None) -> bool:
    return ministro(texto) and re.search(r"convoca|convite|convida", comum.sem_acento(texto or "")) is not None


# ---------------------------------------------------------------- Planalto

def ler_planalto(html: str) -> tuple[list[dict], str | None]:
    """[{cargo, nome}] e o "Atualizado em" (ISO) da página: cada cargo vem em negrito e o nome no parágrafo seguinte."""
    corpo = html[html.find('id="parent-fieldname-text"'):] if 'id="parent-fieldname-text"' in html else html
    pares = re.findall(r"<p[^>]*>\s*<strong>(.*?)</strong>\s*</p>\s*<p[^>]*>(.*?)</p>", corpo, re.S)
    lista = [{"cargo": comum.limpar(c), "nome": comum.limpar(n)} for c, n in pares]
    m = re.search(r'documentModified">.*?class="value">\s*(\d\d/\d\d/\d{4})', html, re.S)
    return [x for x in lista if x["cargo"] and x["nome"]], comum.data_br_iso(m.group(1)) if m else None


def atualizar_planalto(anterior: dict | None, lidos: list[dict], hoje: str) -> dict:
    """Mantém `vistoDesde` de quem continua, abre quem entrou e fecha (`vistoAte`) quem saiu."""
    def chave(x):
        return comum.sem_acento(x["cargo"]), comum.sem_acento(x["nome"])

    antes = {chave(x): x for x in (anterior or {}).get("atuais", [])}
    atuais = [{**x, "vistoDesde": antes.get(chave(x), {}).get("vistoDesde") or hoje} for x in lidos]
    agora = {chave(x) for x in lidos}
    saidas = [{**x, "vistoAte": hoje} for k, x in antes.items() if k not in agora]
    return {"atuais": atuais, "anteriores": (anterior or {}).get("anteriores", []) + saidas}


def coletar_planalto(hoje: str) -> None:
    lidos, atualizado = ler_planalto(comum.get(comum.sessao(), PLANALTO, headers={"Accept": "text/html"}).text)   # sem Accept HTML o gov.br responde 401/404
    if len(lidos) < MINIMO_PLANALTO:
        raise RuntimeError(f"só {len(lidos)} ministros reconhecidos na página; mantendo a lista anterior")
    arq = PASTA / "planalto.json"
    novo = atualizar_planalto(comum.ler(arq), lidos, hoje)
    comum.salvar(arq, {"coletadoEm": hoje, "fonte": PLANALTO, "atualizadoEm": atualizado, **novo})
    print(f"Planalto: {len(novo['atuais'])} ministros")


# ---------------------------------------------------------------- Câmara

def baixar_arquivo(nome: str, ano: int) -> list:
    """Arquivo anual da Câmara (o de proposições passa de 70 MB e às vezes chega cortado: tenta de novo)."""
    url = f"{ARQUIVOS}/{nome}/json/{nome}-{ano}.json"
    for tentativa in range(3):
        try:
            return comum.get(S, url, timeout=300).json()["dados"]
        except Exception:
            if tentativa == 2:
                raise
            time.sleep(5)


def filtrar_camara(props: list, autores: list) -> dict:
    """{id: item} dos RIC a ministro e REQ de convocação/convite de ministro, com os autores como vieram."""
    por_prop: dict[int, list] = {}
    for a in sorted(autores, key=lambda a: int(a.get("ordemAssinatura") or 0)):
        por_prop.setdefault(a["idProposicao"], []).append([a.get("idDeputadoAutor") or None, a.get("nomeAutor")])
    itens = {}
    for p in props:
        if not ((p["siglaTipo"] == "RIC" and ministro(p.get("ementa"))) or (p["siglaTipo"] == "REQ" and convocacao(p.get("ementa")))):
            continue
        st = p.get("ultimoStatus") or {}
        itens[str(p["id"])] = {
            "tipo": p["siglaTipo"], "numero": p["numero"], "ano": p["ano"], "ementa": comum.compactar(p.get("ementa")),
            "dataApresentacao": comum.data_iso(p.get("dataApresentacao")), "inteiroTeor": p.get("urlInteiroTeor") or None,
            "situacao": st.get("descricaoSituacao"), "tramitacao": st.get("descricaoTramitacao"),
            "dataStatus": comum.data_iso(st.get("data")), "orgao": st.get("siglaOrgao"), "autores": por_prop.get(p["id"], []),
        }
    return itens


PRAZO = re.compile(r"a (\d\d/\d\d/\d{4})\)")


def ler_tramitacao(id_: str) -> dict:
    """remessa (ofício ao ministério), fim do prazo de resposta e dia em que a resposta chegou, da tramitação do RIC."""
    saida = {}
    for t in get(f"/proposicoes/{id_}/tramitacoes").get("dados", []):
        desc, dia = comum.sem_acento(t.get("descricaoTramitacao")), comum.data_iso(t.get("dataHora"))
        if desc.startswith("remessa a ministerio"):
            saida["remessa"] = dia
        elif desc.startswith("abertura de prazo") and (m := PRAZO.search(t.get("despacho") or "")):
            saida["prazoFim"] = comum.data_br_iso(m.group(1))
        elif desc.startswith("recebimento de resposta") and "resposta" not in saida:
            saida["resposta"] = dia
    return saida


def pendente(novo: dict, velho: dict | None) -> bool:
    """RIC cuja tramitação precisa ser lida: sem resposta registrada e com status diferente do lido."""
    return novo["tipo"] == "RIC" and not (velho or {}).get("resposta") and (velho or {}).get("lidoEm") != novo["dataStatus"]


def coletar_camara(ano: int, hoje: str, fim: float) -> None:
    arq = PASTA / f"camara_{ano}.json"
    antigo = (comum.ler(arq) or {}).get("itens", {})
    if comum.ano_encerrado(ano, dt.date.fromisoformat(hoje), arq) and all(i["tipo"] != "RIC" or i.get("lidoEm") for i in antigo.values()):
        return   # ano encerrado só para de ser lido depois que todas as tramitações foram lidas uma vez
    itens = filtrar_camara(baixar_arquivo("proposicoes", ano), baixar_arquivo("proposicoesAutores", ano))
    leitura = ("remessa", "prazoFim", "resposta", "lidoEm")
    fila = []
    for id_, item in itens.items():
        velho = antigo.get(id_) or {}
        item.update({k: velho[k] for k in leitura if k in velho})
        if pendente(item, velho):
            fila.append(id_)

    def ler(id_):
        if time.monotonic() > fim:
            return id_, None
        try:
            return id_, ler_tramitacao(id_)
        except Exception as e:
            avisar(f"ministros: tramitação do RIC {id_}: {e}")
            return id_, None

    lidos = 0
    with ThreadPoolExecutor(TRABALHADORES) as ex:
        for id_, r in ex.map(ler, fila):
            if r is not None:
                itens[id_].update({**r, "lidoEm": itens[id_]["dataStatus"]})
                lidos += 1
    comum.salvar(arq, {"coletadoEm": hoje, "fonte": f"{ARQUIVOS}/proposicoes/json/proposicoes-{ano}.json", "itens": itens})
    print(f"Câmara {ano}: {len(itens)} requerimentos a ministro; tramitação lida em {lidos} de {len(fila)} pendentes")
    if lidos < len(fila):
        avisar(f"ministros: Câmara {ano}: {len(fila) - lidos} tramitações ficaram para a próxima coleta")


# ---------------------------------------------------------------- Senado

def filtrar_senado(processos: list) -> dict:
    itens = {}
    for p in processos:
        if (p.get("tipoConteudo") or "").strip() not in TIPOS_SENADO or not ministro(p.get("ementa")):
            continue
        itens[str(p["id"])] = {
            "identificacao": p.get("identificacao"), "tipoConteudo": p["tipoConteudo"].strip(), "ementa": comum.compactar(p.get("ementa")),
            "autoria": p.get("autoria"), "dataApresentacao": comum.data_iso(p.get("dataApresentacao")), "tramitando": p.get("tramitando") == "Sim",
            "deliberacao": p.get("siglaTipoDeliberacao"), "dataDeliberacao": comum.data_iso(p.get("dataDeliberacao")),
            "documento": p.get("urlDocumento"),
        }
    return itens


def coletar_senado(ano: int, hoje: str) -> None:
    arq = PASTA / f"senado_{ano}.json"
    if comum.ano_encerrado(ano, dt.date.fromisoformat(hoje), arq):
        return
    url = f"{SENADO}/processo?sigla=RQS&ano={ano}"
    itens = filtrar_senado(comum.get(S, url, timeout=120).json())
    comum.salvar(arq, {"coletadoEm": hoje, "fonte": url, "itens": itens})
    print(f"Senado {ano}: {len(itens)} requerimentos a ministro")


# ---------------------------------------------------------------- licenças

def historico_deputado(did: int) -> list:
    return [{"data": comum.data_iso(x.get("dataHora")), "situacao": x.get("situacao"), "condicao": x.get("condicaoEleitoral"),
             "descricao": (x.get("descricaoStatus") or "").strip() or None}
            for x in get(f"/deputados/{did}/historico").get("dados", []) if x.get("idLegislatura") == LEGISLATURA]


def licencas_camara() -> dict:
    """Deputados da legislatura fora de exercício que se licenciaram para ser ministro, com o histórico da legislatura."""
    atuais = {d["id"] for d in get_todos("/deputados")}
    fora = {d["id"]: d["nome"] for d in get_todos("/deputados", idLegislatura=LEGISLATURA) if d["id"] not in atuais}
    with ThreadPoolExecutor(4) as ex:
        hist = dict(zip(fora, ex.map(historico_deputado, fora)))
    return {str(did): {"nome": fora[did], "historico": h} for did, h in hist.items() if any(ministro(x["descricao"]) for x in h)}


def afastamentos_senado(lista: dict) -> dict:
    """{codigo: {nome, afastamentos}} dos exercícios encerrados para ocupar cargo de ministro/secretário."""
    raiz = next(iter(lista.values()))
    saida = {}
    for p in raiz["Parlamentares"]["Parlamentar"]:
        ex = ((p.get("Mandato") or {}).get("Exercicios") or {}).get("Exercicio") or []
        afast = [{"inicio": comum.data_iso(e.get("DataInicio")), "fim": comum.data_iso(e.get("DataFim")),
                  "cargo": e.get("DescricaoCargoAssumido"), "uf": e.get("UFCargoAssumido")}
                 for e in (ex if isinstance(ex, list) else [ex]) if ministro(e.get("DescricaoCausaAfastamento"))]
        if afast:
            ident = p["IdentificacaoParlamentar"]
            saida[ident["CodigoParlamentar"]] = {"nome": ident["NomeParlamentar"], "afastamentos": afast}
    return saida


def coletar_licencas(hoje: str) -> None:
    senado = {}
    for lista in ("atual", "afastados"):
        senado.update(afastamentos_senado(comum.get(S, f"{SENADO}/senador/lista/{lista}.json", timeout=120).json()))
    camara = licencas_camara()
    comum.salvar(PASTA / "licencas.json", {"coletadoEm": hoje, "fonte": {"camara": f"{API}/deputados/{{id}}/historico",
                                                                         "senado": f"{SENADO}/senador/lista/afastados.json"},
                                            "camara": camara, "senado": senado})
    print(f"Licenças: {len(camara)} deputados e {len(senado)} senadores afastados para ser ministro")


def main() -> None:
    hoje = dt.date.today()
    dia, fim = hoje.isoformat(), time.monotonic() + PRAZO_SEG
    etapas = [("Planalto", lambda: coletar_planalto(dia)), ("licenças", lambda: coletar_licencas(dia))]
    for ano in range(hoje.year, ANO_INICIAL - 1, -1):   # do ano corrente para trás: o prazo corta os anos velhos primeiro
        etapas += [(f"Câmara {ano}", lambda a=ano: coletar_camara(a, dia, fim)), (f"Senado {ano}", lambda a=ano: coletar_senado(a, dia))]
    comum.rodar_etapas("ministros", etapas)


if __name__ == "__main__":
    main()
