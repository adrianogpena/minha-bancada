"""ENDPOINTS.md precisa listar todos os hosts externos que o código consulta."""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# hosts só citados em texto, links de rodapé/licença ou exemplos
IGNORAR = {"github.com", "adrianogpena.github.io", "www.w3.org", "www.openstreetmap.org", "fonts.gstatic.com", "exemplo",
           "localhost", "seu_usuario.github.io", "www.", "script.google.com",
           # placeholders/regex em comentários e namespaces XML, não são consultas
           "...", "al", "schemas.openxmlformats.org"}


def hosts(texto: str) -> set[str]:
    return {m.lower() for m in re.findall(r"https?://(?:[^/@\s]*@)?([a-zA-Z0-9_.-]+)", texto)}


def test_todo_host_usado_esta_em_endpoints_md():
    listados = hosts((RAIZ / "ENDPOINTS.md").read_text(encoding="utf-8"))
    codigo = [*RAIZ.glob("scripts/*.py"), *RAIZ.glob("site/assets/*.js"), *RAIZ.glob("site/*.html")]
    faltando = {}
    for arq in codigo:
        if arq.name in ("testar_endpoints.py",):
            continue
        for h in hosts(arq.read_text(encoding="utf-8")) - listados - IGNORAR:
            faltando.setdefault(h, arq.relative_to(RAIZ).as_posix())
    assert not faltando, f"hosts fora do ENDPOINTS.md (adicione uma linha para cada): {faltando}"


def test_tabela_bem_formada():
    sys.path.insert(0, str(RAIZ / "scripts"))
    import testar_endpoints as t
    linhas = (RAIZ / "ENDPOINTS.md").read_text(encoding="utf-8").split("\n")
    nomes = []
    for _, c in t.ler_tabela(linhas):
        assert len(c) == 7, c
        assert c[2].startswith("https://"), c
        nomes.append(c[0])
    assert len(nomes) == len(set(nomes))
