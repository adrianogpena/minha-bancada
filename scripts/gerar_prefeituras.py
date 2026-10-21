"""
Monta, a partir de dados/municipais/<UF>/ (coletar_prefeituras.py), o arquivo que o
site lê para o prefeito de cada capital:

  site/dados/prefeitura/<código TSE do município>.json   o que o prefeito enviou à Câmara, do mais novo ao mais antigo

Não acessa a internet.
"""

import re
from pathlib import Path

from coletar_prefeituras import TODAS
from gerar_estaduais import ler, salvar

RAIZ = Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "dados" / "municipais"
SAIDA = RAIZ / "site" / "dados"


def gerar() -> None:
    for uf, (ue, host) in TODAS.items():
        itens = []
        for arq in sorted((BRUTO / uf).glob("prefeitura_[0-9]*.json")):
            for mid, m in ler(arq, {}).get("materias", {}).items():
                veto = re.search(r"veto", m["tipoDescricao"], re.I)
                itens.append({"id": mid, "tipo": "VET" if veto else m["tipo"], "tipoDescricao": m["tipoDescricao"],
                              "numero": m["numero"], "ano": m["ano"], "dataApresentacao": m.get("dataApresentacao"),
                              "ementa": re.sub(r"\s+", " ", m["ementa"]).strip(), "situacao": m["situacao"], "linkTexto": m.get("linkTexto")})
        if not itens:
            continue
        itens.sort(key=lambda x: (x["dataApresentacao"] or "", x["id"]), reverse=True)
        salvar(SAIDA / "prefeitura" / f"{ue}.json", {"host": host, "materias": itens})
        print(f"Gerado: prefeitura de {uf}, {len(itens)} matérias")
