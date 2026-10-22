"""Copia site/ para a pasta dada e gera dados mínimos em <pasta>/dados (nunca toca em site/dados do repositório).

Uso: python tests/e2e/preparar_site.py <pasta>
"""
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ / "scripts"), str(RAIZ / "tests")]

import dados_minimos  # noqa: E402


def main(destino: Path) -> None:
    shutil.copytree(RAIZ / "site", destino, ignore=shutil.ignore_patterns("dados", "fotos"), dirs_exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        saida = dados_minimos.gerar_tudo(Path(tmp))
        shutil.copytree(saida, destino / "dados", dirs_exist_ok=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
