"""
Monta, a partir de dados/municipais/<UF>/ (coletar_prefeituras.py), o arquivo que o
site lê para o prefeito de cada capital:

  site/dados/prefeitura/<código TSE do município>.json   o que o prefeito enviou à Câmara, do mais novo ao mais antigo

Não acessa a internet.
"""

import re
from pathlib import Path

from coletar_prefeituras import CAMARAS
from gerar_estaduais import ler, salvar

RAIZ = Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "dados" / "municipais"
SAIDA = RAIZ / "site" / "dados"


def gerar() -> None:
    for uf, (ue, host) in CAMARAS.items():
        itens = []
        for arq in sorted((BRUTO / uf).glob("prefeitura_[0-9]*.json")):
            for mid, m in ler(arq, {}).get("materias", {}).items():
                veto = re.search(r"veto", m["td"], re.I)
                itens.append({"id": mid, "tipo": "VET" if veto else m["t"], "td": m["td"], "numero": m["n"], "ano": m["a"],
                              "ap": m.get("ap"), "ementa": re.sub(r"\s+", " ", m["e"]).strip(), "sit": m["sit"], "pdf": m.get("pdf")})
        if not itens:
            continue
        itens.sort(key=lambda x: (x["ap"] or "", x["id"]), reverse=True)
        salvar(SAIDA / "prefeitura" / f"{ue}.json", {"host": host, "materias": itens})
        print(f"Gerado: prefeitura de {uf}, {len(itens)} matérias")
