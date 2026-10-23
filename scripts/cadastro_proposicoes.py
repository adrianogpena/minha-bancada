"""
Cadastro das proposições da Câmara: cada proposição (tipo, número, ementa) guardada uma vez só.

  dados/proposicoes_cadastro/<ano>.json   {id: [siglaTipo, numero, ementa]}  (ano = ano da proposição)
  dados/proposicoes/<idDeputado>.json     {ate, ids: [id, ...]}              (só a relação deputado -> proposição)

Antes, cada arquivo de deputado repetia tipo, número e ementa; um projeto de 100 coautores ocupava 100 vezes o espaço.
O formato antigo (`itens`: lista de objetos) ainda é lido: `ids_de` aceita os dois, e `Cadastro.registrar` absorve os
objetos do arquivo antigo na primeira coleta depois da mudança.
"""

import json
import threading
from pathlib import Path

LIMITE_PARA_GRAVAR = 20000   # entradas novas acumuladas antes de regravar os anos tocados (cada ano tem uns 15 MB)


def ids_de(arquivo: dict | None) -> list:
    """Ids das proposições de um arquivo de deputado, no formato novo (`ids`) ou no antigo (`itens`, objetos)."""
    arquivo = arquivo or {}
    if "ids" in arquivo:
        return list(arquivo["ids"])
    return [i["id"] if isinstance(i, dict) else i for i in arquivo.get("itens", [])]


def itens_legados(arquivo: dict | None) -> list:
    """Objetos completos do formato antigo de um arquivo de deputado (vazio no formato novo)."""
    return [i for i in (arquivo or {}).get("itens", []) if isinstance(i, dict)]


def para_objeto(pid: int, linha: list, ano: int | None) -> dict:
    return {"id": pid, "siglaTipo": linha[0], "numero": linha[1], "ano": ano, "ementa": linha[2]}


def ler_anos(anos: dict) -> dict:
    """{ano: conteúdo do arquivo} -> {id: objeto da proposição}. Serve ao histórico, que lê os arquivos do git."""
    saida = {}
    for ano, conteudo in anos.items():
        for pid, linha in (conteudo or {}).items():
            saida[int(pid)] = para_objeto(int(pid), linha, ano)
    return saida


class Cadastro:
    """Cadastro em memória, carregado uma vez e gravado por ano. Seguro para as threads da coleta."""

    def __init__(self, pasta: Path):
        self.pasta = pasta
        self.lock = threading.RLock()
        self.por_ano: dict = {}      # ano -> {str(id): [tipo, numero, ementa]}
        self.ano_de: dict = {}       # id -> ano
        self.sujos: set = set()
        self.novas = 0
        for arq in sorted(pasta.glob("*.json")):
            ano = int(arq.stem) if arq.stem.isdigit() else None
            conteudo = json.loads(arq.read_text(encoding="utf-8"))
            self.por_ano[ano] = conteudo
            for pid in conteudo:
                self.ano_de[int(pid)] = ano

    def get(self, pid) -> dict | None:
        if int(pid) not in self.ano_de:
            return None
        ano = self.ano_de[int(pid)]
        return para_objeto(int(pid), self.por_ano[ano][str(pid)], ano)

    def todos(self):
        for pid in self.ano_de:
            yield self.get(pid)

    def registrar(self, p: dict) -> None:
        """Guarda (ou atualiza) uma proposição {id, siglaTipo, numero, ano, ementa}."""
        pid, ano = int(p["id"]), p.get("ano")
        linha = [p.get("siglaTipo"), p.get("numero"), (p.get("ementa") or "").strip()]
        with self.lock:
            antigo = self.ano_de.get(pid, False)
            if antigo is not False and self.por_ano[antigo].get(str(pid)) == linha and antigo == ano:
                return
            if antigo is not False and antigo != ano:
                del self.por_ano[antigo][str(pid)]
                self.sujos.add(antigo)
            self.por_ano.setdefault(ano, {})[str(pid)] = linha
            self.ano_de[pid] = ano
            self.sujos.add(ano)
            self.novas += 1

    def gravar(self, forcar: bool = False) -> None:
        """Regrava os anos alterados quando passou do limite de entradas novas (ou sempre, com `forcar`)."""
        with self.lock:
            if not self.sujos or not (forcar or self.novas >= LIMITE_PARA_GRAVAR):
                return
            self.pasta.mkdir(parents=True, exist_ok=True)
            for ano in sorted(self.sujos, key=lambda a: a or 0):
                arq = self.pasta / f"{ano if ano is not None else 'sem_ano'}.json"
                tmp = arq.with_suffix(".tmp")
                tmp.write_text(json.dumps(dict(sorted(self.por_ano[ano].items(), key=lambda kv: int(kv[0]), reverse=True)),
                                          ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                tmp.replace(arq)
            self.sujos.clear()
            self.novas = 0
