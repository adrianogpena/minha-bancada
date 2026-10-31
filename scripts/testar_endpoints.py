"""
Testa todos os endpoints listados em ENDPOINTS.md e grava o resultado (Status, Verificado em, Detalhe) na própria tabela.

Cada URL é consultada com GET; só o cabeçalho (e o início do corpo) é lido, então os ZIPs grandes do TSE não são baixados.
Sucesso = HTTP 2xx. JSON deve ser válido (conferido quando a resposta é pequena). Fonte fora do ar ou 4xx/5xx = ERRO.

Uso:
    python scripts/testar_endpoints.py              # testa tudo e atualiza ENDPOINTS.md
    python scripts/testar_endpoints.py nome ...     # só os endpoints indicados
    python scripts/testar_endpoints.py --listar     # mostra a tabela sem consultar
    python scripts/testar_endpoints.py --sem-tabela # testa tudo e só atualiza dados/status_apis.json (usado no CI diário)
O histórico de cada endpoint (último checkup, último sucesso, se nunca funcionou) fica em dados/status_apis.json,
que o gerar.py copia para o site (página "Sobre os dados").
Código de saída 1 se algum endpoint estiver com erro.
"""

import argparse
import datetime as dt
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "ENDPOINTS.md"
STATUS = RAIZ / "dados" / "status_apis.json"
UA = "Mozilla/5.0 (compatible; minha-bancada; projeto de transparencia; teste de endpoints)"
LIMITE_JSON = 2_000_000   # só confere o JSON se couber nisso
HOSTS_XHR = ("transparencia.assembleia.pr.leg.br",)   # o /api/ do portal responde 403 sem o cabeçalho de chamada AJAX
OK, ERRO = "✅ OK", "❌ ERRO"


def ler_tabela(linhas: list[str]) -> list[tuple[int, list[str]]]:
    """(índice da linha, células) de cada endpoint da tabela."""
    saida = []
    for i, lin in enumerate(linhas):
        if lin.startswith("| ") and not lin.startswith("| Nome") and not lin.startswith("|---"):
            saida.append((i, [c.strip() for c in lin.strip().strip("|").split(" | ")]))
    return saida


def bundle_extra() -> str:
    """CAs do sistema + cadeia extra de scripts/certs (alguns sites, como o SUAP de Goiânia, não mandam a cadeia completa)."""
    import certifi
    import tempfile
    cadeia = "\n".join(p.read_text(encoding="ascii") for p in sorted((RAIZ / "scripts" / "certs").glob("*.pem")))
    arq = Path(tempfile.gettempdir()) / "minha_bancada_ca_endpoints.pem"
    arq.write_text(Path(certifi.where()).read_text(encoding="ascii") + "\n" + cadeia, encoding="ascii")
    return str(arq)


def testar(url: str, verify=True, tentativa: int = 0) -> tuple[bool, str]:
    try:
        cabecalhos = {"User-Agent": UA, "Accept": "*/*"}
        if any(h in url for h in HOSTS_XHR):
            cabecalhos.update({"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"})
        with requests.get(url, stream=True, timeout=60, verify=verify, headers=cabecalhos) as r:
            tipo = r.headers.get("Content-Type", "").split(";")[0]
            if not r.ok:
                return False, f"HTTP {r.status_code}"
            detalhe = f"HTTP {r.status_code}, {tipo}"
            tam = int(r.headers.get("Content-Length") or 0)
            if "json" in tipo and tam < LIMITE_JSON:
                try:
                    r.json()
                except ValueError:
                    return False, f"HTTP {r.status_code}, JSON inválido"
            if tam:
                detalhe += f", {tam / 1e6:.1f} MB" if tam > 1e6 else f", {tam // 1024} KB"
            return True, detalhe + ("; só com a cadeia extra de scripts/certs" if verify is not True else "")
    except requests.exceptions.SSLError as e:
        if verify is True:
            return testar(url, bundle_extra(), tentativa)
        return False, f"SSLError: {str(e)[:100]}".replace("|", "/")
    except requests.RequestException as e:
        if tentativa == 0 and not isinstance(e, requests.Timeout):   # reinício de conexão é comum; repete uma vez
            return testar(url, verify, 1)
        return False, f"{type(e).__name__}: {str(e)[:100]}".replace("|", "/").replace("\n", " ")


def atualizar_status(alvo, resultados, agora: str) -> None:
    """Grava em dados/status_apis.json o resultado de agora e o que já se sabia (último sucesso, primeira verificação)."""
    antigo = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}
    novo = dict(antigo)
    for (_, c), (ok, detalhe) in zip(alvo, resultados, strict=True):
        h = antigo.get(c[0], {})
        novo[c[0]] = {
            "grupo": c[1], "url": c[2], "ok": ok, "detalhe": detalhe, "verificadoEm": agora,
            "primeiraVerificacao": h.get("primeiraVerificacao", agora),
            "ultimoOk": agora if ok else h.get("ultimoOk"),
        }
    vivos = {c[0] for _, c in ler_tabela(ARQUIVO.read_text(encoding="utf-8").splitlines())}
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({n: v for n, v in novo.items() if n in vivos}, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("nomes", nargs="*")
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--sem-tabela", action="store_true", help="não reescreve ENDPOINTS.md")
    a = ap.parse_args()

    linhas = ARQUIVO.read_text(encoding="utf-8").split("\n")
    tabela = ler_tabela(linhas)
    if a.listar:
        for _, c in tabela:
            print(f"{c[0]:32} {c[4]:8} {c[2]}")
        return 0
    desconhecidos = set(a.nomes) - {c[0] for _, c in tabela}
    if desconhecidos:
        sys.exit(f"não está no ENDPOINTS.md: {', '.join(sorted(desconhecidos))}")
    alvo = [(i, c) for i, c in tabela if not a.nomes or c[0] in a.nomes]

    with ThreadPoolExecutor(8) as ex:
        resultados = list(ex.map(lambda x: testar(x[1][2]), alvo))

    agora = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hoje = dt.date.today().isoformat()
    erros = []
    for (i, c), (ok, detalhe) in zip(alvo, resultados, strict=True):
        c[4:7] = [OK if ok else ERRO, hoje, detalhe]
        linhas[i] = "| " + " | ".join(c) + " |"
        print(f"{'OK  ' if ok else 'ERRO'} {c[0]:32} {detalhe}")
        if not ok:
            erros.append(c[0])
    if not a.sem_tabela:
        ARQUIVO.write_text("\n".join(linhas), encoding="utf-8")
    atualizar_status(alvo, resultados, agora)
    print(f"\n{len(alvo) - len(erros)}/{len(alvo)} funcionando" + (f"; com erro: {', '.join(erros)}" if erros else ""))
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
