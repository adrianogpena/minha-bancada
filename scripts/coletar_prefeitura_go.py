"""
Coleta o que o prefeito de Goiânia enviou à Câmara Municipal. A Câmara de Goiânia não usa SAPL: a
consulta pública de processos eletrônicos do SUAP (https://suap.camaragyn.go.gov.br/camara/consulta_publica/)
lista os processos legislativos por interessado (o prefeito) e ano, e cada processo tem página pública.
Guarda em dados/municipais/GO/prefeitura_<ano>.json, no mesmo formato das Câmaras SAPL
(ver coletar_prefeituras.py), para o gerar_prefeituras.py tratar tudo igual.

O servidor do SUAP não envia o certificado intermediário da Let's Encrypt (YR2), então o Python não fecha a
cadeia. Sem desligar a verificação, o script junta os certificados públicos de scripts/certs/letsencrypt_yr.pem
(YR2 e Root YR, este assinado pela ISRG Root X1) aos do certifi. Se a Let's Encrypt trocar de intermediário,
a coleta falha com aviso e o arquivo precisa ser atualizado.

A situação é a do processo na Câmara (em trâmite, finalizado, anexado): o SUAP não diz se o projeto virou lei.
Vetos não aparecem como processos próprios do prefeito, então ficam de fora.
"""

import datetime as dt
import html
import re
import tempfile
from pathlib import Path

import certifi

from coletar_estaduais import RENOVAR_ANO_ANTIGO_DIAS, avisar, ler, salvar, sessao
from coletar_estaduais import DADOS as DADOS_ESTADUAIS

DADOS = DADOS_ESTADUAIS.parent / "municipais"
HOST = "suap.camaragyn.go.gov.br"
CONSULTA = f"https://{HOST}/camara/consulta_publica/"
PROCESSO = f"https://{HOST}/processo_eletronico/visualizar_processo/"
ANO_INICIAL = 2025  # mandato atual começa em 1º de janeiro de 2025
INTERESSADO = "Prefeito de Goiânia"
# "Projeto de Lei nº 463/2026 - ementa"; o mais longo primeiro
ASSUNTO = re.compile(r"^(Projeto de Lei Complementar|Projeto de Lei|Projeto de Emenda à Lei Orgânica)\s+n[ºo°.]*\s*(\d+)/(\d{2}|\d{4})\s*-\s*(.+)$", re.I | re.S)
TIPOS = {"projeto de lei complementar": ("PLC", "Projeto de Lei Complementar"), "projeto de lei": ("PL", "Projeto de Lei"),
         "projeto de emenda à lei orgânica": ("PEL", "Projeto de Emenda à Lei Orgânica")}
S = sessao()


def confiar() -> None:
    cadeia = (Path(__file__).parent / "certs" / "letsencrypt_yr.pem").read_text(encoding="ascii")
    arq = Path(tempfile.gettempdir()) / "minha_bancada_ca_suap.pem"
    arq.write_text(Path(certifi.where()).read_text(encoding="ascii") + "\n" + cadeia, encoding="ascii")
    S.verify = str(arq)


def pagina(ano: int, n: int) -> tuple[int, list[dict]]:
    r = S.get(CONSULTA, params={"classificacao": "PL", "interessado": "Prefeito", "ano": ano, "page": n}, timeout=120,
              headers={"Accept": "text/html"})
    r.raise_for_status()
    h = r.text
    m = re.search(r"Total de (\d+) ite", h)
    total = int(m.group(1)) if m else 0
    itens = []
    for b in re.split(r'<div class="general-box">', h)[1:]:
        def g(p: str, b: str = b) -> str:
            x = re.search(p, b, re.S)
            return html.unescape(re.sub(r"<[^>]+>", "", x.group(1))).strip() if x else ""
        uuid = re.search(r"visualizar_processo/([0-9a-f-]+)/", b)
        itens.append({"uuid": uuid.group(1) if uuid else None, "assunto": re.sub(r"\s+", " ", g(r"<dt>Assunto:</dt><dd>(.*?)</dd>")),
                      "interessados": g(r"Interessados:</dt><dd>(.*?)</dd>"), "criado": g(r"cria..o:</dt><dd>(.*?)</dd>"),
                      "situacao": g(r'<span class="status status-(?!publico)[^"]*">([^<]*)')})
    return total, itens


def situacao(s: str) -> str:
    return {"Finalizado": "Processo finalizado na Câmara", "Anexado": "Anexado a outro processo"}.get(s, s or "Em trâmite")


def coletar() -> None:
    print(f"GO ({HOST})")
    confiar()
    hoje = dt.date.today()
    for ano in range(ANO_INICIAL, hoje.year + 1):
        arq = DADOS / "GO" / f"prefeitura_{ano}.json"
        antigo = ler(arq, {})
        if antigo and ano < hoje.year and (hoje - dt.date.fromisoformat(antigo["coletadoEm"])).days < RENOVAR_ANO_ANTIGO_DIAS:
            continue
        itens: dict[str, dict] = {}
        lidos, n = 0, 1
        while True:
            total, pg = pagina(ano, n)
            lidos += len(pg)
            for x in pg:
                m = ASSUNTO.match(x["assunto"])
                if not m or INTERESSADO not in x["interessados"] or not x["uuid"]:
                    continue
                t, td = TIPOS[m.group(1).lower()]
                ano_p = int(m.group(3)) + (2000 if len(m.group(3)) == 2 else 0)
                mid = f"{t}-{int(m.group(2))}-{ano_p}"
                criado = dt.datetime.strptime(x["criado"][:10], "%d/%m/%Y").date().isoformat()
                if mid in itens and itens[mid]["dataApresentacao"] <= criado:
                    continue
                itens[mid] = {"tipo": t, "tipoDescricao": td, "numero": int(m.group(2)), "ano": ano_p, "dataApresentacao": criado,
                              "ementa": m.group(4).strip(), "situacao": situacao(x["situacao"]),
                              "emTramitacao": x["situacao"] != "Finalizado", "linkTexto": PROCESSO + x["uuid"] + "/"}
            if not pg or lidos >= total:
                break
            n += 1
        if lidos != total:
            raise RuntimeError(f"{ano}: lidos {lidos} de {total} processos")
        salvar(arq, {"coletadoEm": hoje.isoformat(), "host": HOST, "materias": itens})
        print(f"  GO prefeitura {ano}: {len(itens)}")


if __name__ == "__main__":
    try:
        coletar()
    except Exception as e:
        avisar(f"GO: prefeitura: {e}")
