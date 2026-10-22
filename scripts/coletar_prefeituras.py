"""
Coleta o que cada prefeito de capital enviou à Câmara Municipal (projetos de lei,
leis complementares, emendas à Lei Orgânica, medidas provisórias, mensagens e
vetos), nas Câmaras que usam o SAPL. O Executivo consta como autor das matérias,
então basta achar esse autor. Guarda em dados/municipais/<UF>/prefeitura_<ano>.json.

Uso:
    python scripts/coletar_prefeituras.py          # todas as Câmaras configuradas
    python scripts/coletar_prefeituras.py PB RN
"""

import datetime as dt
import importlib
import re
import sys

from coletar_estaduais import (RENOVAR_ANO_ANTIGO_DIAS, compactar_materia, em_paralelo, ler, paginar, salvar,
                               sem_acento, tipos_materia)
from coletar_estaduais import DADOS as DADOS_ESTADUAIS

DADOS = DADOS_ESTADUAIS.parent / "municipais"
ANO_INICIAL = 2025  # mandato atual começa em 1º de janeiro de 2025

# UF da capital -> (código TSE do município, host do SAPL da Câmara Municipal).
# Câmaras de capitais com API aberta, dados atuais e o Executivo registrado como autor, verificadas em 2026-10.
# Ficaram de fora Porto Velho e Fortaleza (matérias do Executivo sem autor), Manaus e Palmas (sem dados atuais).
# Sem coletor, verificadas em 2026-10 (motivos em dados/municipais/capitais_sem_dados.md): Curitiba (CAPTCHA), Campo Grande
# e Florianópolis (reCAPTCHA), Cuiabá, São Luís e Vitória (site bloqueia scripts), Teresina (senha), Belém (sem projetos do
# Executivo), Maceió (dados incompletos), Macapá (sem API), Aracaju (SAPL antigo com 503); Recife tem SAPL, mas ficou em
# manutenção (503); Rio de Janeiro, Belo Horizonte e Porto Alegre não responderam.
CAMARAS = {
    "AC": ("01392", "sapl.riobranco.ac.leg.br"),
    "RR": ("03018", "sapl.boavista.rr.leg.br"),
    "RN": ("17612", "sapl.natal.rn.leg.br"),
    "PB": ("20516", "sapl.joaopessoa.pb.leg.br"),
}
# Câmaras com sistema próprio, cada uma com seu coletor em scripts/coletar_prefeitura_<uf>.py
OUTRAS = {"SP": ("71072", "splegisconsulta.saopaulo.sp.leg.br"),
          "BA": ("38490", "cmsalvador.sys.inf.br/cl/prop_interna/"),
          "GO": ("93734", "suap.camaragyn.go.gov.br")}
TODAS = {**CAMARAS, **OUTRAS}
# projetos, vetos e mensagens do prefeito; emendas, pareceres e requerimentos ficam de fora
TIPO_PREFEITO = re.compile(r"^(projeto de lei|lei ordin|proposta de emenda|projeto de emenda|medida provis|veto|mensagem)", re.I)
NAO_PREFEITO = re.compile(r"legislativo|substitutivo", re.I)


def autores_prefeitura(host: str) -> set[int]:
    ids = {a["id"] for a in paginar(host, "base/autor")
           if re.search(r"prefeit|executivo", sem_acento(f"{a.get('nome')} {a.get('cargo')}"))}
    if not ids:
        raise RuntimeError("autor do prefeito não encontrado")
    return ids


def coletar(uf: str, host: str) -> None:
    print(f"{uf} ({host})")
    autores = autores_prefeitura(host)
    tipos = {i: t for i, t in tipos_materia(host).items()
             if TIPO_PREFEITO.match(t["descricao"].strip()) and not NAO_PREFEITO.search(t["descricao"])}
    hoje = dt.date.today()
    for ano in range(ANO_INICIAL, hoje.year + 1):
        arq = DADOS / uf / f"prefeitura_{ano}.json"
        antigo = ler(arq)
        if antigo and ano < hoje.year and (hoje - dt.date.fromisoformat(antigo["coletadoEm"])).days < RENOVAR_ANO_ANTIGO_DIAS:
            continue
        itens = {}
        for tid, t in tipos.items():
            for m in paginar(host, "materia/materialegislativa", ano=ano, tipo=tid):
                if autores & set(m.get("autores") or []):
                    itens[str(m["id"])] = compactar_materia(m, {tid: t})
        salvar(arq, {"coletadoEm": hoje.isoformat(), "host": host, "materias": itens})
        print(f"  {uf} prefeitura {ano}: {len(itens)}")


def main() -> None:
    def uma(uf):
        if uf in OUTRAS:
            importlib.import_module(f"coletar_prefeitura_{uf.lower()}").coletar()
        else:
            coletar(uf, CAMARAS[uf][1])

    em_paralelo([a.upper() for a in sys.argv[1:]] or list(TODAS), uma, "prefeitura")


if __name__ == "__main__":
    main()
