"""
Coleta o que o prefeito de Salvador enviou à Câmara Municipal. A Câmara de Salvador não usa SAPL: o
acompanhamento de proposições (https://cmsalvador.sys.inf.br/cl/prop_interna/) é uma grade Scriptcase, em que
a busca por autor ("Executivo Municipal") e a paginação são chamadas AJAX presas à sessão.
Guarda em dados/municipais/BA/prefeitura_<ano>.json, no mesmo formato das Câmaras SAPL
(ver coletar_prefeituras.py), para o gerar_prefeituras.py tratar tudo igual.

A grade só mostra a data da última movimentação; a data de apresentação e a situação vêm do histórico de
cada projeto (janela de tramitação), consultado só dos projetos de 2025 em diante. Os links da grade e da
janela valem só dentro da sessão, então o link por projeto é o do texto integral (PDF), quando existe.
"""

import datetime as dt
import html
import re

from coletar_estaduais import RENOVAR_ANO_ANTIGO_DIAS, avisar, ler, salvar, sessao
from coletar_estaduais import DADOS as DADOS_ESTADUAIS

DADOS = DADOS_ESTADUAIS.parent / "municipais"
HOST = "cmsalvador.sys.inf.br/cl/prop_interna/"
BASE = f"https://{HOST}"
TRAM = "https://cmsalvador.sys.inf.br/cl/prop_interna_tram/"
ANO_INICIAL = 2025  # mandato atual começa em 1º de janeiro de 2025
AUTOR = "Executivo Municipal"
# prefixo do número -> (tipo, descrição)
TIPOS = {"PLE": ("PL", "Projeto de Lei"), "PLC": ("PLC", "Projeto de Lei Complementar"),
         "PEL": ("PEL", "Projeto de Emenda à Lei Orgânica"), "VTO": ("VET", "Veto")}
POR_PAGINA = 50
S = sessao()


def ajax(url: str, sci: str, opc: str, parm: str) -> dict:
    r = S.post(url + "index.php", data={"nmgp_opcao": "ajax_navigate", "script_case_init": sci, "opc": opc, "parm": parm}, timeout=120)
    r.raise_for_status()
    return r.json()


def corpo(resp: dict) -> str:
    return next(v["value"] for v in resp["setValue"] if v["field"] == "sc_grid_body")


def limpar(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def campo(tr: str, nome: str) -> str:
    m = re.search(rf'id="id_sc_field_{nome}_\d+"[^>]*>(.*?)</span>', tr, re.S)
    return limpar(m.group(1)) if m else ""


def linhas(resp: dict) -> list[dict]:
    res = []
    for tr in re.split(r'<TR\s+class="scGridField(?:Odd|Even)"', corpo(resp))[1:]:
        par = re.search(r"nm_gp_submit5\('/cl/prop_interna_tram/', '/cl/prop_interna/', '([^']*)'", tr)
        res.append({"prop": campo(tr, "proposicao"), "ementa": campo(tr, "pro_ementa"), "situacao": campo(tr, "sit_nome_futuro"),
                    "parametros": par.group(1) if par else None})
    return res


def historico(par: str) -> list[dict]:
    """Movimentos do projeto, do mais novo ao mais antigo: data, situação, observação e link do anexo."""
    h = S.get(f"{TRAM}?&nmgp_outra_jan=true&nmgp_url_saida=modal&SC_lig_apl_orig=prop_interna&nmgp_opcao=grid&nmgp_parms={par}", timeout=120).text
    sci = re.search(r'name="script_case_init" value="(\d+)"', h)
    if not sci:
        raise RuntimeError("janela de tramitação não abriu")
    movs = []
    for tr in re.split(r'<TR\s+class="scGridField(?:Odd|Even)"', corpo(ajax(TRAM, sci.group(1), "muda_qt_linhas", str(POR_PAGINA))))[1:]:
        cel = re.search(r'css_situacao_grid_line[^>]*>(.*?)</TD>', tr, re.S)
        link = re.search(r"nm_gp_submit5\('(https?://[^']*)'", tr)
        movs.append({"data": campo(tr, "tra_dt_movimentacao"), "situacao": limpar(cel.group(1)) if cel else "", "observacao": campo(tr, "tra_observacao"),
                     "link": link.group(1) if link else None})
    return movs


def iso(d: str) -> str:
    return dt.datetime.strptime(d, "%d/%m/%Y").date().isoformat()


def situacao(tipo: str, movs: list[dict], da_grade: str) -> str:
    """Situação do projeto: "Armazenado" na grade só diz que o processo foi guardado, o desfecho está no histórico."""
    if tipo != "VET":
        passos = {m["situacao"].lower() for m in movs}
        if "sancionado" in passos:
            for m in movs:
                lei = re.match(r"\s*LEI\s*N\D{0,3}\s*([\d.]+)/(\d+).*PUBLICADO", m["observacao"], re.I)
                if lei:
                    return f"Sancionado (Lei {int(lei.group(1).replace('.', '')):,}/{lei.group(2)})".replace(",", ".")
            return "Sancionado"
        if "retirado pelo autor" in passos:
            return "Retirado pelo prefeito"
        if "arquivado" in passos:
            return "Arquivado"
    return da_grade or (movs[0]["situacao"] if movs else "")


def coletar() -> None:
    print(f"BA ({HOST})")
    hoje = dt.date.today()
    h = S.get(BASE, timeout=120).text
    sci = re.search(r'name="script_case_init" value="(\d+)"', h).group(1)
    ajax(BASE, sci, "interativ_search", f"autorproposicao__DL__Autor__DL__tx__DL__{AUTOR}##@@{AUTOR}__DL__S__DL__N")
    resp = ajax(BASE, sci, "muda_qt_linhas", str(POR_PAGINA))
    total = int(re.search(r"sm_counter_total'>(\d+)<", next(v["value"] for v in resp["setValue"] if v["field"] == "sc_grid_toobar_bot")).group(1))
    anos: dict[int, dict] = {}
    vistas = 0
    while True:
        pagina = linhas(resp)
        for x in pagina:
            vistas += 1
            m = re.match(r"([A-Z]+)-(\d+)/(\d{4})$", x["prop"])
            if not m or m.group(1) not in TIPOS or int(m.group(3)) < ANO_INICIAL:
                continue
            if not x["parametros"]:
                raise RuntimeError(f"{x['prop']}: sem histórico")
            t, td = TIPOS[m.group(1)]
            movs = historico(x["parametros"])
            prot = [mv for mv in movs if mv["situacao"].lower().startswith("protocolado")]
            integra = next((mv["link"] for mv in reversed(movs) if mv["situacao"].lower().startswith("anexado integra") and mv["link"]), None)
            sit = situacao(t, movs, x["situacao"])
            anos.setdefault(int(m.group(3)), {})[x["prop"]] = {
                "tipo": t, "tipoDescricao": td, "numero": int(m.group(2)), "ano": int(m.group(3)),
                "dataApresentacao": iso(prot[-1]["data"]) if prot else None,
                "ementa": x["ementa"], "situacao": sit, "emTramitacao": x["situacao"] not in ("Armazenado", ""), "linkTexto": integra}
        if vistas >= total or not pagina:
            break
        resp = ajax(BASE, sci, "rec", str(vistas + 1))
    if vistas != total:
        raise RuntimeError(f"lidos {vistas} de {total} projetos")
    for ano in range(ANO_INICIAL, hoje.year + 1):
        arq = DADOS / "BA" / f"prefeitura_{ano}.json"
        antigo = ler(arq, {})
        if antigo and ano < hoje.year and (hoje - dt.date.fromisoformat(antigo["coletadoEm"])).days < RENOVAR_ANO_ANTIGO_DIAS:
            continue
        itens = anos.get(ano, {})
        salvar(arq, {"coletadoEm": hoje.isoformat(), "host": HOST, "materias": itens})
        print(f"  BA prefeitura {ano}: {len(itens)}")


if __name__ == "__main__":
    try:
        coletar()
    except Exception as e:
        avisar(f"BA: prefeitura: {e}")
