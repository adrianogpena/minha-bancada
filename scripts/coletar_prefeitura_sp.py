"""
Coleta o que o prefeito de São Paulo enviou à Câmara Municipal. A Câmara de São Paulo não usa SAPL:
o SPLegis tem um webservice próprio (https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx, operações *JSON).
Guarda em dados/municipais/SP/prefeitura_<ano>.json, no mesmo formato das Câmaras SAPL
(ver coletar_prefeituras.py), para o gerar_prefeituras.py tratar tudo igual.

O webservice lista os projetos de cada ano sem dizer quem os enviou; o autor só aparece no resumo de cada
projeto. Por isso o script consulta o resumo de cada PL e PLO do ano e guarda os números já vistos
("vistos"), para as próximas execuções olharem só os projetos novos. Situação: em tramitação, vetado
e lei aprovada vêm das listas por promovente; o que não está em nenhuma delas saiu da tramitação.
"""

import datetime as dt
from concurrent.futures import ThreadPoolExecutor

from coletar_estaduais import RENOVAR_ANO_ANTIGO_DIAS, avisar, ler, salvar, sessao
from coletar_estaduais import DADOS as DADOS_ESTADUAIS

DADOS = DADOS_ESTADUAIS.parent / "municipais"
WS = "https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx"
HOST = "splegisconsulta.saopaulo.sp.leg.br"
ANO_INICIAL = 2025  # mandato atual começa em 1º de janeiro de 2025
PREFEITO = "ricardo nunes"  # nome do promovente na lista PromoventesCMSP (tipo EXECUTIVO)
# projetos que o Executivo envia; o código é o "_tipo" do SPLegis, usado no link da consulta pública
TIPOS = {"PL": ("Projeto de Lei", 1), "PLO": ("Emenda à Lei Orgânica", None)}
S = sessao()


def ws(operacao: str, **params):
    r = S.get(f"{WS}/{operacao}", params=params or None, timeout=180)
    r.raise_for_status()
    return r.json()


def chave(x: dict) -> tuple:
    return (x["tipo"], x["numero"], x["ano"])


def link(tipo: str, numero: int, ano: int, cod: int | None) -> str | None:
    """Página do projeto na consulta pública do SPLegis (a busca aceita o tipo, o número e o ano na URL)."""
    return f"https://{HOST}/Pesquisa/IndexDetalhado?tipo={cod}&numero={numero}&ano={ano}" if cod else None


def promovente_id() -> int:
    ids = [p["chave"] for p in ws("PromoventesCMSPJSON")
           if (p.get("tipo") or {}).get("nome") == "EXECUTIVO" and p["nome"].lower() == PREFEITO]
    if not ids:
        raise RuntimeError("promovente do prefeito não encontrado")
    return ids[0]


def e_do_prefeito(tipo: str, numero: int, ano: int, pid: int) -> bool:
    r = ws("ProjetoResumoJSON", Tipo=tipo, Numero=numero, Ano=ano)
    return any(a.get("Chave") == pid for a in (r or {}).get("Autores") or [])


def coletar() -> None:
    print(f"SP ({HOST})")
    pid = promovente_id()
    hoje = dt.date.today()
    tramitando = {chave(x) for x in ws("ProjetosEmTramitacaoPorPromoventeJSON", Codigo=pid)}
    vetos = {chave(x): x["veto"]["nome"] for x in ws("ProjetosVetadosPorPromoventeJSON", Codigo=pid)}
    leis = {chave(x["projeto"]): x for x in ws("LeisAprovadasPorPromoventeJSON", Codigo=pid)}
    for ano in range(ANO_INICIAL, hoje.year + 1):
        arq = DADOS / "SP" / f"prefeitura_{ano}.json"
        antigo = ler(arq, {})
        itens_ant = antigo.get("enviados", {})
        if antigo and ano < hoje.year and (hoje - dt.date.fromisoformat(antigo["coletadoEm"])).days < RENOVAR_ANO_ANTIGO_DIAS:
            continue
        vistos = set(map(tuple, antigo.get("vistos", [])))
        projetos = [p for p in ws("ProjetosPorAnoJSON", Ano=ano) if p["tipo"] in TIPOS]
        novos = [p for p in projetos if chave(p) not in vistos]
        with ThreadPoolExecutor(8) as ex:
            do_prefeito = list(ex.map(lambda p: e_do_prefeito(p["tipo"], p["numero"], p["ano"], pid), novos))
        for p, sim in zip(novos, do_prefeito):
            vistos.add(chave(p))
            if sim:
                itens_ant[f"{p['tipo']}-{p['numero']}-{p['ano']}"] = {"tipo": p["tipo"], "numero": p["numero"], "ano": p["ano"],
                                                                      "ap": p["data"][:10], "ementa": p["ementa"].strip()}
        itens = {}
        for mid, m in itens_ant.items():
            k = (m["tipo"], m["numero"], m["ano"])
            td, cod = TIPOS[m["tipo"]]
            lei = leis.get(k)
            if lei:
                sit = f"Virou lei (Lei {lei['numero']:,}".replace(",", ".") + (f", publicada em {lei['publicacao'][:10]})" if lei.get("publicacao") else ")")
            elif k in tramitando:
                sit = "Em tramitação"
            elif k in vetos:
                sit = vetos[k]
            else:
                sit = "Fora de tramitação (arquivado, retirado ou rejeitado)"
            itens[mid] = {"t": m["tipo"], "td": td, "n": m["numero"], "a": m["ano"], "ap": m["ap"], "e": m["ementa"],
                          "sit": sit, "tr": k in tramitando, "pdf": link(m["tipo"], m["numero"], m["ano"], cod)}
            if k in vetos:
                itens[f"VET-{mid}"] = {**itens[mid], "t": "VET", "td": vetos[k], "sit": f"{vetos[k]} do prefeito"}
        salvar(arq, {"coletadoEm": hoje.isoformat(), "host": HOST, "materias": itens, "vistos": sorted(vistos), "enviados": itens_ant})
        print(f"  SP prefeitura {ano}: {len(itens)}")


if __name__ == "__main__":
    try:
        coletar()
    except Exception as e:
        avisar(f"SP: prefeitura: {e}")
