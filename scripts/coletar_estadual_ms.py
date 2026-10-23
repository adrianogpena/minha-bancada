"""
Deputados estaduais de Mato Grosso do Sul (ALEMS). Grava em dados/estaduais/MS/ (contrato em estaduais_comum.py).

Fontes lidas aqui:
  - lista de deputados: eleitos de 2022 do TSE (dados/tse/2022/MS.json); al.ms.gov.br não publica a lista em formato aberto;
  - CEAP (cota do exercício da atividade parlamentar), CSV por ano, 2012 em diante (aqui desde 2023):
    https://transparencia2.al.ms.gov.br/ceap/notas/exportar-csv?ano=2026; o comprovante (PDF da nota) é a fonte de cada item;
  - diárias: https://transparencia2.al.ms.gov.br/consulta-diarias/exportar-csv?ano=2026 (2021 a 2026: "Não houve despesa", sem itens).

Não coletado: remuneração (só PDF mensal, portal antigo gerdocumento/1201), proposições e votações (sistema sgpl atrás de captcha,
não contornado), presença e emendas (não encontradas).
"""

import csv
import io
import re
from datetime import date

import estaduais_comum as comum

UF = "MS"
PASTA = comum.DADOS / UF
TRANSP = "https://transparencia2.al.ms.gov.br"
CEAP_PAGINA = f"{TRANSP}/ceap"
CEAP_CSV = f"{TRANSP}/ceap/notas/exportar-csv?ano={{ano}}"
DIARIAS_PAGINA = f"{TRANSP}/consulta-diarias"
DIARIAS_CSV = f"{TRANSP}/consulta-diarias/exportar-csv?ano={{ano}}"
TSE_ARQUIVO = comum.arquivo_tse(UF)
TSE_FICHA = comum.ficha_tse(UF)
ANO_INICIAL = 2023
TIMEOUT = 90
APELIDOS = {"hashioka": "Roberto Hashioka", "cel david": "Coronel David", "professor rinaldo": "Professor Rinaldo Modesto",
            "lucas de lima": "Lucas de Lima do Amor Sem Fim", "zeca do pt": "Zeca do Pt"}


def deputados_do_tse() -> list[dict]:
    return comum.deputados_do_tse(TSE_ARQUIVO, TSE_FICHA)


def linhas_csv(texto: str, cabecalho_em: str) -> list[dict]:
    """Linhas do CSV com ';' como dicts de cabeçalho sem acento; ignora o que vem antes da linha com `cabecalho_em`."""
    todas = list(csv.reader(io.StringIO(texto.lstrip("﻿")), delimiter=";"))
    inicio = next((i for i, linha in enumerate(todas) if cabecalho_em in [comum.sem_acento(c).upper() for c in linha]), None)
    if inicio is None:
        return []
    cab = [comum.sem_acento(c).upper() for c in todas[inicio]]
    return [dict(zip(cab, linha, strict=False)) for linha in todas[inicio + 1:] if any(c.strip() for c in linha)]


def ligar(nomes, deputados: list[dict]) -> dict:
    """Como comum.ligar_nomes, aceitando "Dep.Fulano" sem espaço, "Cel." por "Coronel" e os apelidos de APELIDOS."""
    def normal(n):
        n = comum.sem_acento(comum.nome_limpo(re.sub(r"^\s*dep\.(?=\S)", "dep. ", n or "", flags=re.I)))
        n = n.replace(".", "")
        return comum.sem_acento(APELIDOS.get(n, n))

    achados = comum.ligar_nomes({normal(n) for n in nomes}, deputados)
    return {n: achados[normal(n)] for n in nomes if normal(n) in achados}


def itens_ceap(linhas: list[dict], ligacao: dict, fonte: str) -> tuple[list[dict], set]:
    itens, sem_par = [], set()
    for linha in linhas:
        nome = linha.get("DEPUTADO", "")
        pid = ligacao.get(nome)
        if not pid:
            sem_par.add(comum.nome_limpo(nome))
            continue
        cnpj = "".join(c for c in (linha.get("CPF/CNPJ") or "") if c.isdigit())
        itens.append({"idDeputado": pid, "mes": comum.mes_numero(linha.get("MES")), "categoria": " ".join((linha.get("CATEGORIA") or "").split()) or None,
                      "fornecedor": " ".join((linha.get("FORNECEDOR") or "").split()) or None, "cnpj": cnpj or None,
                      "valor": comum.valor_br(linha.get("VALOR (R$)")), "documento": linha.get("DOCUMENTO") or None,
                      "emissao": emissao_iso(linha.get("EMISSAO")), "fonte": (linha.get("COMPROVANTE") or "").strip() or fonte})
    return itens, sem_par


def emissao_iso(texto) -> str | None:
    p = (texto or "").strip().split("/")
    if len(p) == 3 and all(x.isdigit() for x in p):
        return f"{p[2]}-{p[1]}-{p[0]}"
    return None


def baixar(s, url: str) -> str:
    return comum.baixar(s, url, timeout=TIMEOUT).decode("utf-8-sig", errors="replace")


def coletar_ceap(s, deputados: list[dict]) -> None:
    hoje = date.today()
    sem_par = set()
    for ano in range(ANO_INICIAL, hoje.year + 1):
        destino = PASTA / f"verbas_{ano}.json"
        if ano < hoje.year and destino.exists():
            continue
        url = CEAP_CSV.format(ano=ano)
        linhas = linhas_csv(baixar(s, url), "DEPUTADO")
        ligacao = ligar({linha["DEPUTADO"] for linha in linhas}, deputados)
        itens, sp = itens_ceap(linhas, ligacao, f"{CEAP_PAGINA}")
        sem_par |= sp
        if itens or ano == hoje.year:
            comum.salvar(destino, {"coletadoEm": hoje.isoformat(), "fonte": CEAP_PAGINA, "itens": itens})
            print(f"MS: CEAP {ano}: {len(itens)} itens de {len(linhas)} linhas")
    if sem_par:
        comum.avisar(f"MS: CEAP sem deputado eleito em 2022 ({len(sem_par)}): {sorted(sem_par)[:12]}")


def linhas_diarias(texto: str) -> list[dict]:
    """Linhas de diárias com dados; o portal devolve uma linha "Não houve despesa" por mês quando não há."""
    return [linha for linha in linhas_csv(texto, "MES") if "nao houve" not in comum.sem_acento(linha.get("INFORMACAO", ""))]


def coletar_diarias(s) -> None:
    hoje = date.today()
    for ano in range(max(ANO_INICIAL, hoje.year - 1), hoje.year + 1):  # só conta e avisa, nada é gravado: anos encerrados não precisam
        n = len(linhas_diarias(baixar(s, DIARIAS_CSV.format(ano=ano))))
        print(f"MS: diárias {ano}: {n} lançamentos" + (" (portal: sem despesa)" if not n else ""))
        if n:
            comum.avisar(f"MS: diárias {ano} têm {n} linhas, formato com dados ainda não tratado")


def coletar() -> None:
    s = comum.sessao()
    deputados = deputados_do_tse()
    if not deputados:
        comum.avisar("MS: sem eleitos de 2022 em dados/tse/2022/MS.json")
        return
    comum.salvar(PASTA / "deputados.json", {"fonte": "https://divulgacandcontas.tse.jus.br/divulga/#/home", "host": None,
                                            "legislatura": "2023-2027", "deputados": deputados})
    print(f"MS: {len(deputados)} deputados")
    comum.rodar_etapas(UF, [("CEAP", lambda: coletar_ceap(s, deputados)), ("diárias", lambda: coletar_diarias(s))])


def _contrato_ceap(ctx):
    texto = baixar(comum.sessao(), CEAP_CSV.format(ano=date.today().year))
    return {"csv": "\n".join(texto.splitlines()[:12])}


def _conferir_ceap(registro):
    linhas = linhas_csv(registro["csv"], "DEPUTADO")
    if not linhas:
        return ["CSV da CEAP sem cabeçalho Deputado ou sem linhas"], []
    falhas = []
    falhas += comum.faltando(linhas[0], ("ANO", "MES", "CATEGORIA", "CPF/CNPJ", "FORNECEDOR", "DOCUMENTO", "EMISSAO", "VALOR (R$)", "COMPROVANTE"), "CSV da CEAP")
    if comum.valor_br(linhas[0].get("VALOR (R$)")) is None:
        falhas.append("valor da CEAP ilegível")
    if comum.mes_numero(linhas[0].get("MES")) is None:
        falhas.append("mês da CEAP não reconhecido")
    return falhas, []


def _contrato_diarias(ctx):
    texto = baixar(comum.sessao(), DIARIAS_CSV.format(ano=date.today().year))
    return {"csv": "\n".join(texto.splitlines()[:8])}


def _conferir_diarias(registro):
    linhas = linhas_csv(registro["csv"], "MES")
    if not linhas:
        return ["CSV de diárias sem cabeçalho Mês ou sem linhas"], []
    return [], []


CONTRATOS = [
    {"nome": "estadual_ms_ceap", "fonte": CEAP_PAGINA, "buscar": _contrato_ceap, "html": _conferir_ceap},
    {"nome": "estadual_ms_diarias", "fonte": DIARIAS_PAGINA, "buscar": _contrato_diarias, "html": _conferir_diarias},
]


if __name__ == "__main__":
    comum.principal(coletar)
