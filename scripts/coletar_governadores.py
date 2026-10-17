"""
Coleta o que cada governador enviou à Assembleia Legislativa (projetos de lei,
leis complementares, emendas à Constituição, medidas provisórias, mensagens e
vetos), nas Assembleias que usam o SAPL. O governador consta como autor das
matérias, então basta achar esse autor. Guarda em dados/estaduais/<UF>/governo_<ano>.json.

Uso:
    python scripts/coletar_governadores.py          # todas as Assembleias configuradas
    python scripts/coletar_governadores.py PB AM
"""

import datetime as dt
import re
import sys

from coletar_estaduais import (ASSEMBLEIAS, DADOS, RENOVAR_ANO_ANTIGO_DIAS, avisar, compactar_materia,
                               ler, paginar, salvar, sem_acento, tipos_materia)

ANO_INICIAL = 2023  # mandato atual começa em 1º de janeiro de 2023
# projetos, vetos e mensagens do governador; autógrafos, requerimentos e indicações ficam de fora
TIPO_GOVERNO = re.compile(r"^(projeto|proposta de emenda|medida provis|veto|mensagem)", re.I)


def autor_governo(host: str) -> int:
    for a in paginar(host, "base/autor"):
        nome = sem_acento(a.get("nome"))
        if "governador" in nome or "poder executivo" in nome:
            return a["id"]
    raise RuntimeError("autor do governador não encontrado")


def coletar(uf: str, host: str) -> None:
    print(f"{uf} ({host})")
    autor = autor_governo(host)
    tipos = {i: t for i, t in tipos_materia(host).items() if TIPO_GOVERNO.match(t["d"].strip())}
    hoje = dt.date.today()
    for ano in range(ANO_INICIAL, hoje.year + 1):
        arq = DADOS / uf / f"governo_{ano}.json"
        antigo = ler(arq)
        if antigo and ano < hoje.year and (hoje - dt.date.fromisoformat(antigo["coletadoEm"])).days < RENOVAR_ANO_ANTIGO_DIAS:
            continue
        itens = {}
        for tid, t in tipos.items():
            for m in paginar(host, "materia/materialegislativa", ano=ano, tipo=tid):
                if autor in (m.get("autores") or []):
                    itens[str(m["id"])] = compactar_materia(m, {tid: {"s": t["s"], "d": t["d"]}})
        salvar(arq, {"coletadoEm": hoje.isoformat(), "materias": itens})
        print(f"  {uf} governo {ano}: {len(itens)}")


def main() -> None:
    for uf in [a.upper() for a in sys.argv[1:]] or list(ASSEMBLEIAS):
        try:
            coletar(uf, ASSEMBLEIAS[uf])
        except Exception as e:
            avisar(f"{uf}: governo: {e}")


if __name__ == "__main__":
    main()
