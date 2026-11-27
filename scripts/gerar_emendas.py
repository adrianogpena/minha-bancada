"""
Emendas parlamentares de cada deputado e senador: site/dados/emendas/<pessoa>.json, a partir de `nucleo["emendas"]`
(identidades.ligar_emendas, que lê dados/emendas/<ano>.json do coletar_emendas.py). Sem internet.

Arquivo da pessoa: {anos:[{ano, n, empenhado, liquidado, pago}] (mais recente primeiro),
funcoes:[{nome, n, empenhado, pago}] (totais por área, a função orçamentária como o Portal publica; do maior empenhado ao menor),
municipios:[{nome, uf, ibge, empenhado, pago, n, pixEmpenhado, pixPago, pixN}] (todos os destinos, do maior valor empenhado ao menor; `ibge` só
quando o nome casa com o município, e é o que o mapa do site usa; os campos pix* só nas emendas Pix), itens:[{codigo, ano, tipo, numero, local,
funcao, subfuncao, empenhado, liquidado, pago}]}. Valores em reais; o link da fonte de cada ano é montado no site.

Emenda Pix é a emenda individual de "Transferências Especiais" (a verba vai direto ao caixa do município, sem convênio).
O código IBGE vem de dados/municipios_nomes.json (gerar_municipios_ibge.py --nomes).

O plano só entra em emenda do tipo Pix: o Transferegov traz plano de algumas emendas que o Portal classifica como "Finalidade Definida"
(60 itens em 2026-11-27), e esses ficam de fora (contados em `conferir_planos`, `planosDeOutroTipo`).

Plano de ação do Transferegov (coletar_transferegov_especiais.py, dados/transferegov/especiais/<ano>.json): o plano liga à emenda pelo
`codigoEmenda` do Portal (12 dígitos), sem comparar nomes. O item da emenda guarda só `planos:[id]`; os dados do plano (situação, objeto,
valores, executores com CNPJ) ficam uma vez no arquivo da pessoa, em `planos:{id: {codigo, ano, situacao, objeto, custeio, investimento,
executores:[{cnpj, nome, objeto, custeio, investimento}], gestao}}`, só dos planos das emendas dela.
`gestao` (relatórios de gestão: prestação de contas do que o município pagou com a verba; dados/transferegov/gestao/<ano>.json), quando o plano
tem relatório: {relatorios, situacao e data do mais recente, executado, pendente, pago (soma dos pagamentos), favorecidos:[{cnpj, nome, valor, n,
fornecedor}] (maiores recebedores por CNPJ; `fornecedor` é o id de nucleo/fornecedores quando a empresa já está lá), outros:{n, valor} (recebedores
fora dos maiores, inclusive sem CNPJ), pessoasFisicas:{n, valor} (CPF: a fonte não é reproduzida, só a soma)}. `pessoa["planos"]` some quando nenhum casa.
"""

from collections import defaultdict
from pathlib import Path

import coletar_emendas
import estaduais_comum as comum
import gerar_municipios_ibge as ibge_nomes

NOMES = comum.RAIZ / "dados" / "municipios_nomes.json"
TRANSFEREGOV = comum.RAIZ / "dados" / "transferegov"
CAMPOS_PLANO = ("codigo", "ano", "situacao", "aceite", "custeio", "investimento", "areas", "objeto", "executores")
FAVORECIDOS_EXIBIDOS = 10   # maiores recebedores (CNPJ) por plano; o resto entra em `outros`
CAMPOS_ITEM = ("codigo", "ano", "tipo", "numero", "local", "funcao", "subfuncao", "empenhado", "liquidado", "pago")


# (UF, nome como o Portal da Transparência escreve, sem acento) -> nome do TSE (sem acento), para o que o IBGE e o TSE grafam diferente
GRAFIAS_PORTAL = {
    ("SP", "embu"): "embu das artes", ("RJ", "trajano de morais"): "trajano de moraes", ("RS", "santana do livramento"): "sant ana do livramento",
    ("PE", "iguaraci"): "iguaracy", ("BA", "muquem de sao francisco"): "muquem do sao francisco", ("MT", "poxoreo"): "poxoreu",
    ("BA", "santa teresinha"): "santa terezinha", ("CE", "itapage"): "itapaje", ("RN", "ares"): "arez", ("RN", "acu"): "assu",
    ("SE", "gracho cardoso"): "graccho cardoso", ("SP", "florinia"): "florinea", ("RN", "presidente juscelino"): "serra caiada",
    ("RN", "augusto severo"): "campo grande", ("TO", "fortaleza do tabocao"): "tabocao",
}


def indice_municipios(nomes: dict) -> dict:
    """{(UF, nome sem acento): código IBGE}, com as grafias do TSE, as do IBGE (ibge_nomes.AJUSTES) e as do Portal (GRAFIAS_PORTAL)."""
    indice = {(uf, ibge_nomes.chave(nome)): cod for cod, (uf, nome) in nomes.items()}
    for (uf, tse), ibge in ibge_nomes.AJUSTES.items():
        if (uf, tse) in indice:
            indice.setdefault((uf, ibge), indice[(uf, tse)])
    for (uf, portal), tse in GRAFIAS_PORTAL.items():
        if (uf, tse) in indice:
            indice.setdefault((uf, portal), indice[(uf, tse)])
    return indice


def por_funcao(itens: list[dict]) -> list[dict]:
    """Totais por função orçamentária (Saúde, Educação...). Sem função, o rótulo é "Sem área informada"."""
    grupos = defaultdict(list)
    for i in itens:
        grupos[i.get("funcao") or "Sem área informada"].append(i)
    return sorted(({"nome": f, "n": len(x), "empenhado": soma(x, "empenhado"), "pago": soma(x, "pago")} for f, x in grupos.items()),
                  key=lambda f: (-f["empenhado"], f["nome"]))


def eh_pix(tipo: str) -> bool:
    return "transferencias especiais" in ibge_nomes.chave(tipo or "")


def soma(itens: list[dict], campo: str) -> float:
    return round(sum(i.get(campo) or 0 for i in itens), 2)


def carregar_planos(raiz: Path = TRANSFEREGOV) -> dict[str, list[dict]]:
    """{codigoEmenda: [plano]} de dados/transferegov/especiais/<ano>.json; vazio quando o Transferegov ainda não foi coletado."""
    planos = defaultdict(list)
    for arq in sorted((raiz / "especiais").glob("*.json")):
        for p in (comum.ler(arq, {}) or {}).get("planos") or []:
            if p.get("emenda"):
                planos[p["emenda"]].append(p)
    return dict(planos)


def carregar_gestao(raiz: Path = TRANSFEREGOV) -> dict[int, list[dict]]:
    """{id do plano: [relatório de gestão com pagamentos]} de dados/transferegov/gestao/<ano>.json."""
    gestao = defaultdict(list)
    for arq in sorted((raiz / "gestao").glob("*.json")):
        for r in (comum.ler(arq, {}) or {}).get("relatorios") or []:
            gestao[r["plano"]].append(r)
    return dict(gestao)


def resumo_gestao(relatorios: list[dict], fornecedores: set[str] | None = None) -> dict:
    """Prestação de contas de um plano: o que foi executado e para quem o município pagou."""
    recente = max(relatorios, key=lambda r: (r.get("data") or "", r["id"]))
    por_cnpj, outros, pf = {}, [0, 0.0], [0, 0.0]
    for r in relatorios:
        for x in r.get("pagamentos") or []:
            valor = x.get("valor") or 0.0
            if x.get("pf"):
                pf[0] += 1
                pf[1] += valor
            elif x.get("cnpj"):
                f = por_cnpj.setdefault(x["cnpj"], {"cnpj": x["cnpj"], "nome": x.get("nome") or "", "valor": 0.0, "n": 0})
                f["valor"] += valor
                f["n"] += 1
            else:
                outros[0] += 1
                outros[1] += valor
    ordenados = sorted(por_cnpj.values(), key=lambda f: (-f["valor"], f["cnpj"]))
    for f in ordenados[FAVORECIDOS_EXIBIDOS:]:
        outros[0] += f["n"]
        outros[1] += f["valor"]
    favorecidos = []
    for f in ordenados[:FAVORECIDOS_EXIBIDOS]:
        favorecidos.append({**f, "valor": round(f["valor"], 2), **({"fornecedor": "for_" + f["cnpj"][:8]} if "for_" + f["cnpj"][:8] in (fornecedores or ()) else {})})
    saida = {"relatorios": len(relatorios), "situacao": recente.get("situacao"), "data": recente.get("data"),
             "executado": round(sum(r.get("executado") or 0 for r in relatorios), 2), "pendente": recente.get("pendente") or 0.0,
             "pago": round(sum(x.get("valor") or 0 for r in relatorios for x in r.get("pagamentos") or []), 2), "favorecidos": favorecidos}
    if outros[0]:
        saida["outros"] = {"n": outros[0], "valor": round(outros[1], 2)}
    if pf[0]:
        saida["pessoasFisicas"] = {"n": pf[0], "valor": round(pf[1], 2)}
    return {k: v for k, v in saida.items() if v not in (None, "")}


def conferir_planos(emendas: list[dict], planos: dict[str, list[dict]]) -> dict:
    """Quantos planos do Transferegov casam com uma emenda coletada do Portal (e quantas Emendas Pix ficaram sem plano)."""
    codigos = {e["codigo"] for e in emendas}
    todos = [p for lista in planos.values() for p in lista]
    pix = {e["codigo"] for e in emendas if eh_pix(e.get("tipo"))}
    return {"planos": len(todos), "semEmenda": sum(1 for p in todos if p["emenda"] not in codigos),
            "emendasPix": len(pix), "pixSemPlano": len(pix - set(planos)),
            "planosDeOutroTipo": sum(len(l) for c, l in planos.items() if c in codigos and c not in pix)}


def construir(emendas: list[dict], nomes: dict | None = None, planos: dict[str, list[dict]] | None = None,
              gestao: dict[int, list[dict]] | None = None, fornecedores: set[str] | None = None) -> dict[str, dict]:
    """{pessoa: arquivo}. `emendas`: itens ligados, cada um com `pessoa`; `nomes`: {código IBGE: [UF, nome]};
    `planos`: {codigoEmenda: [plano do Transferegov]} (carregar_planos)."""
    indice = indice_municipios(nomes or {})
    por_pessoa = defaultdict(list)
    for e in emendas:
        # o município sai do `local` aqui, não do que o coletor gravou: os anos encerrados não são baixados de novo
        # e os arquivos antigos têm "SANTOS - SP" sem município e "SÃO PAULO (UF)" como se fosse município
        e = {**e, **dict(zip(("municipio", "uf"), coletar_emendas.destino(e.get("local"))))} if "local" in e else e
        por_pessoa[e["pessoa"]].append(e)
    saida = {}
    for pid, itens in por_pessoa.items():
        por_ano, por_local = defaultdict(list), defaultdict(list)
        for i in itens:
            por_ano[i["ano"]].append(i)
            if i.get("municipio"):
                por_local[(i["municipio"], i["uf"])].append(i)
        municipios = sorted((municipio(m, uf, x, indice) for (m, uf), x in por_local.items()), key=lambda m: (-m["empenhado"], m["nome"], m["uf"]))
        usados = {}
        for i in itens:
            for p in (planos or {}).get(i["codigo"], []) if eh_pix(i.get("tipo")) else []:
                usados[p["id"]] = {k: p[k] for k in CAMPOS_PLANO if k in p}
                if (gestao or {}).get(p["id"]):
                    usados[p["id"]]["gestao"] = resumo_gestao(gestao[p["id"]], fornecedores)
        saida[pid] = {
            "anos": [{"ano": a, "n": len(x), "empenhado": soma(x, "empenhado"), "liquidado": soma(x, "liquidado"), "pago": soma(x, "pago")}
                     for a, x in sorted(por_ano.items(), reverse=True)],
            "funcoes": por_funcao(itens),
            "municipios": municipios,
            "itens": [{**{k: i[k] for k in CAMPOS_ITEM if k in i}, **({"planos": sorted(p["id"] for p in planos[i["codigo"]])} if eh_pix(i.get("tipo")) and i["codigo"] in (planos or {}) else {})}
                      for i in sorted(itens, key=lambda i: (-i["ano"], -(i.get("empenhado") or 0), i["codigo"]))],
        }
        if usados:
            saida[pid]["planos"] = {str(k): v for k, v in sorted(usados.items())}
    return saida


def totais(emendas: list[dict]) -> dict[str, dict]:
    """{pessoa: {n, empenhado, pago}} somando todos os anos coletados, para as listas de deputados e senadores."""
    saida: dict[str, dict] = {}
    for e in emendas:
        t = saida.setdefault(e["pessoa"], {"n": 0, "empenhado": 0.0, "pago": 0.0})
        t["n"] += 1
        t["empenhado"] += e.get("empenhado") or 0
        t["pago"] += e.get("pago") or 0
    return {p: {"n": t["n"], "empenhado": round(t["empenhado"], 2), "pago": round(t["pago"], 2)} for p, t in saida.items()}


def municipio(nome: str, uf: str, itens: list[dict], indice: dict) -> dict:
    m = {"nome": nome, "uf": uf, "empenhado": soma(itens, "empenhado"), "pago": soma(itens, "pago"), "n": len(itens)}
    if (uf, ibge_nomes.chave(nome)) in indice:
        m["ibge"] = indice[(uf, ibge_nomes.chave(nome))]
    pix = [i for i in itens if eh_pix(i.get("tipo"))]
    if pix:
        m.update(pixEmpenhado=soma(pix, "empenhado"), pixPago=soma(pix, "pago"), pixN=len(pix))
    return m


def salvar(emendas: list[dict], saida: Path, nomes: dict | None = None, planos: dict[str, list[dict]] | None = None,
           gestao: dict[int, list[dict]] | None = None, fornecedores: set[str] | None = None) -> int:
    nomes = comum.ler(NOMES, {}) if nomes is None else nomes
    planos = carregar_planos() if planos is None else planos
    gestao = carregar_gestao() if gestao is None else gestao
    arquivos = construir(emendas, nomes, planos, gestao, fornecedores)
    for pid, arq in arquivos.items():
        comum.salvar(saida / "emendas" / f"{pid}.json", arq)
    return len(arquivos)
