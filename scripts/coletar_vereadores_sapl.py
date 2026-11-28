"""
Vereadores da legislatura 2025-2028 pelo SAPL de cada Câmara Municipal (sistema do Interlegis).

Descoberta: diretório oficial do Interlegis (`orgaosatendidos?servico=SAPL&uf=<UF>&tipocasa=CM&p=<n>`): Câmara, CNPJ, município e URL do
SAPL (a paginação repete casas; a leitura vai até a página sem cards). Leitura por Câmara, no próprio SAPL:
  /api/parlamentares/legislatura/            -> a legislatura que contém 2025-01-01 (o id muda por instância)
  /api/parlamentares/mandato/?legislatura=ID -> titular x suplente, início e fim do mandato (sem partido)
  /api/parlamentares/parlamentar/            -> nome civil e nome parlamentar (sem CPF)
Limites do SAPL: o suplente aparece com o início da legislatura (não registra a posse real); `ativo` não serve.

Grava em `dados/municipais/<UF>/`: `camaras_sapl.json` (descoberta, relida a cada DESCOBERTA_DIAS) e `vereadores_sapl.json` (uma
entrada por Câmara; cada uma só é relida depois de REVISITA_DIAS, escalonada por crc32 da URL, e as sem SAPL em uso a cada
REVISITA_VAZIA_DIAS). Uma Câmara que falha não derruba as outras: guarda o erro e mantém os itens anteriores.
Uso: `python scripts/coletar_vereadores_sapl.py [UF ...]` (sem argumento: MG e PR).
Ligação com a pessoa (TSE) e partido: identidades.py, não aqui.
"""

import re
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

import estaduais_comum as comum
from coletar_vereadores import DADOS, INICIO_LEGISLATURA, iso, municipio_da_camara

INTERLEGIS = "https://www12.senado.leg.br/interlegis/orgaosatendidos"
UFS_PADRAO = ["MG", "PR"]
DESCOBERTA_DIAS = 30
REVISITA_DIAS = 7
REVISITA_VAZIA_DIAS = 30
PAGINAS_MAX = 150
TRABALHADORES = 8        # um host por Câmara: 8 Câmaras ao mesmo tempo, no máximo 2 conexões em cada
PAGINA = 100


# ------------------------------------------------------------------ descoberta

def _texto(trecho: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", trecho)).strip()


def camaras_da_pagina(html: str) -> tuple[list[dict], int]:
    """Cards do Interlegis com serviço SAPL: nome, cnpj, município, url (https, sem barra final)."""
    achadas = []
    cards = html.split('<div class="orgao-atendido">')[1:]
    for card in cards:
        nome = re.search(r'font-weight:bold;margin-bottom:3px;">([^<]+)</div>', card)
        cnpj = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", card)
        local = re.search(r"\d{5}-\d{3} - ([^<,]+), ([A-Z]{2})</div>", card)
        sapl = next((linha for linha in re.findall(r"<tr[^>]*>(.*?)</tr>", card, re.S)
                     if _texto(linha).startswith("SAPL ") and "http" in linha), None)
        if not (nome and cnpj and sapl):
            continue
        url = re.search(r'https?://[^"\'<\s]+', sapl)
        if not url:
            continue
        base = urlsplit(url[0])
        achadas.append({"nome": _texto(nome[1]), "cnpj": cnpj[1], "municipio": local[1].strip() if local else municipio_da_camara(_texto(nome[1])),
                        "url": f"https://{base.netloc}"})
    return achadas, len(cards)


def descobrir(s, uf: str) -> list[dict]:
    achadas: dict = {}
    for pagina in range(1, PAGINAS_MAX + 1):
        r = comum.get(s, INTERLEGIS, 60, params={"servico": "SAPL", "uf": uf, "tipocasa": "CM", "p": pagina})
        da_pagina, total_cards = camaras_da_pagina(r.text)
        if not total_cards:
            break
        achadas.update({c["cnpj"]: c for c in da_pagina})
    return sorted(achadas.values(), key=lambda c: (c["municipio"] or "", c["cnpj"]))


# ------------------------------------------------------------------ leitura de uma Câmara

def paginas(s, url: str, params: dict) -> list[dict]:
    resultados, pagina = [], 1
    while True:
        dados = comum.get(s, url, 60, params={**params, "page_size": PAGINA, "page": pagina}).json()
        resultados += dados.get("results", [])
        if not dados.get("pagination", {}).get("next_page"):
            return resultados
        pagina += 1


def legislatura_atual(legislaturas: list[dict]) -> dict | None:
    for leg in legislaturas:
        if (iso(leg.get("data_inicio")) or "9") <= INICIO_LEGISLATURA <= (iso(leg.get("data_fim")) or ""):
            return leg
    return None


def itens_camara(camara: dict, legislatura: dict, mandatos: list[dict], parlamentares: list[dict]) -> list[dict]:
    """Um item por mandato. `afastamento`: fim do mandato quando é anterior ao fim da legislatura ou há causa de fim registrada."""
    por_id = {p["id"]: p for p in parlamentares}
    fim_legislatura = iso(legislatura.get("data_fim"))
    itens = []
    for m in mandatos:
        p = por_id.get(m.get("parlamentar")) or {}
        nome = (p.get("nome_completo") or p.get("nome_parlamentar") or "").strip()
        if not nome:
            continue
        fim = iso(m.get("data_fim_mandato"))
        saiu = bool(m.get("tipo_causa_fim_mandato")) or bool(fim and fim_legislatura and fim < fim_legislatura)
        itens.append({"municipio": camara["municipio"], "camara": camara["url"], "nome": nome,
                      "nomeParlamentar": (p.get("nome_parlamentar") or "").strip() or None, "cargo": "VEREADOR",
                      "idParlamentar": m.get("parlamentar"), "titular": bool(m.get("titular")),
                      "ingresso": iso(m.get("data_inicio_mandato")), "afastamento": fim if saiu else None})
    return sorted(itens, key=lambda i: (i["ingresso"] or "", i["nome"], i["idParlamentar"] or 0))


def ler_camara(s, camara: dict) -> list[dict] | None:
    """Itens da legislatura atual; None quando o SAPL não tem a legislatura (instância vazia ou sem uso)."""
    base = camara["url"] + "/api/parlamentares/"
    legislatura = legislatura_atual(paginas(s, base + "legislatura/", {}))
    if not legislatura:
        return None
    mandatos = paginas(s, base + "mandato/", {"legislatura": legislatura["id"]})
    if not mandatos:
        return None
    return itens_camara(camara, legislatura, mandatos, paginas(s, base + "parlamentar/", {}))


# ------------------------------------------------------------------ coleta por UF

def vencida(entrada: dict | None, url: str, hoje: date) -> bool:
    """Relê quando nunca lida, ou depois de REVISITA_DIAS (REVISITA_VAZIA_DIAS se vazia; no dia seguinte se deu erro), escalonado por crc32 da URL."""
    if not entrada or not entrada.get("lidoEm"):
        return True
    if entrada.get("erro"):
        return entrada["lidoEm"] < hoje.isoformat()
    dias = REVISITA_DIAS if entrada.get("itens") else REVISITA_VAZIA_DIAS
    dias = max(1, dias - zlib.crc32(url.encode()) % dias)
    return hoje - date.fromisoformat(entrada["lidoEm"]) >= timedelta(days=dias)


def coletar_uf(uf: str, s=None, hoje: date | None = None) -> None:
    hoje = hoje or date.today()
    s = s or comum.sessao()
    pasta = DADOS / uf
    cadastro = comum.ler(pasta / "camaras_sapl.json", {})
    if not cadastro.get("coletadoEm") or hoje - date.fromisoformat(cadastro["coletadoEm"]) >= timedelta(days=DESCOBERTA_DIAS):
        camaras = descobrir(s, uf)
        comum.salvar(pasta / "camaras_sapl.json", {"coletadoEm": hoje.isoformat(), "fonte": INTERLEGIS, "camaras": camaras})
    else:
        camaras = cadastro["camaras"]
    arquivo = pasta / "vereadores_sapl.json"
    guardado = comum.ler(arquivo, {}).get("camaras", {})
    pendentes = [c for c in camaras if vencida(guardado.get(c["url"]), c["url"], hoje)]

    def uma(camara):
        try:
            return camara, ler_camara(s, camara), None
        except comum.PrazoEsgotado:
            raise
        except Exception as e:  # noqa: BLE001
            return camara, None, f"{type(e).__name__}: {e}"[:200]

    novos = {c["url"]: guardado[c["url"]] for c in camaras if c["url"] in guardado}
    erros = prazo = 0
    try:
        with ThreadPoolExecutor(TRABALHADORES) as pool:
            for camara, itens, erro in pool.map(uma, pendentes):
                antigo = guardado.get(camara["url"]) or {}
                if erro:
                    erros += 1
                novos[camara["url"]] = {"municipio": camara["municipio"], "nome": camara["nome"], "cnpj": camara["cnpj"], "lidoEm": hoje.isoformat(),
                                        "itens": antigo.get("itens", []) if erro else (itens or []), **({"erro": erro} if erro else {})}
    except comum.PrazoEsgotado:
        prazo = 1
        comum.avisar(f"{uf}: prazo esgotado; as Câmaras já lidas ficam guardadas")
    comum.salvar(arquivo, {"coletadoEm": hoje.isoformat(), "fonte": INTERLEGIS, "camaras": novos})
    com_itens = [c for c in novos.values() if c["itens"]]
    print(f"{uf}: {len(camaras)} Câmaras com SAPL, {len(pendentes)} lidas agora, {len(com_itens)} com vereadores "
          f"({sum(len(c['itens']) for c in com_itens)} mandatos), {erros} com erro{', prazo esgotado' if prazo else ''}")


def coletar(ufs: list[str] | None = None) -> None:
    comum.rodar_etapas("Vereadores SAPL", [(uf, lambda uf=uf: coletar_uf(uf)) for uf in (ufs or UFS_PADRAO)])


if __name__ == "__main__":
    coletar([a.upper() for a in sys.argv[1:]] or None)
    sys.exit(0)
