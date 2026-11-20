import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))


import pytest


@pytest.fixture(autouse=True)
def _log_de_ligacoes_isolado():
    import identidades
    identidades._LOG.clear()
    yield
    identidades._LOG.clear()
