"""
Cruzamento de doadores de campanha com fornecedores das cotas: "empresa que doou e depois foi paga pela cota".

  site/dados/doadores_fornecedores.json   por fornecedor, as doações de campanha que ele fez (ou que vieram por repasse) a eleitos e
                                          quanto o mesmo político lhe pagou da cota no ano
  site/dados/nucleo/ligacoes.json         chave `doadores`: como cada doador foi ligado a um fornecedor (método e confiança)

Fontes: prestação de contas dos eleitos (dados/tse/contas/<ano>/<UF>.json, do TSE) e os fornecedores de scripts/fornecedores.py (cota da
Câmara, CEAPS do Senado e verbas das Assembleias). Não acessa a internet; chamado pelo scripts/gerar.py.

Só empresa (CNPJ) e só correspondência exata: o doador liga ao fornecedor pelo CNPJ (raiz de 8 dígitos) ou, nas contas coletadas antes de
o CNPJ ser guardado, pelo nome padronizado igual ao de um único fornecedor com CNPJ. A regra de ligação fica em `identidades.ligar_doadores`.
Pessoa física não entra: o nome sozinho confunde homônimos e o CPF do doador não é guardado. Não afirma irregularidade: mostra que as duas
fontes citam a mesma empresa.
"""

from collections import Counter, defaultdict
from pathlib import Path

import candidaturas
import identidades
from gerar_politicos import ler, salvar

REPASSES = ("partido", "outros candidatos", "próprios")   # origens que não são doação direta de terceiro
FONTES = {
    "doacoes": {"nome": "TSE, prestação de contas eleitorais dos candidatos", "url": "https://dadosabertos.tse.jus.br"},
    "pagamentos": {
        "camara": {"nome": "Cota parlamentar da Câmara", "url": "https://www.camara.leg.br/cotas/"},
        "senado": {"nome": "CEAPS do Senado", "url": "https://adm.senado.gov.br/adm-dadosabertos"},
        "estadual": {"nome": "Verbas indenizatórias das Assembleias (portal de cada Casa, citado na ficha do deputado)", "url": None},
    },
}


def _doadores(bruto: Path, chaves: dict):
    """Doações de pessoa jurídica das contas dos eleitos: [(chave do registro, nome, cnpj ou None, dados da doação)]."""
    saida = []
    for pasta in sorted(p for p in (bruto / "tse" / "contas").glob("*") if p.is_dir() and p.name.isdigit()):
        ano = int(pasta.name)
        for arq in sorted(pasta.glob("[A-Z][A-Z].json")):
            for sq, c in (ler(arq, {}) or {}).items():
                base = {"candidatura": candidaturas.id_candidatura(ano, sq), "pessoa": chaves.get(("tse", ano, sq)), "eleicao": ano,
                        "uf": arq.stem, "sequencial": sq}
                if "doadoresPJ" in c:   # coleta com CNPJ: todos os doadores empresa, não só os cinco maiores
                    diretos = [(cnpj, nome, cnpj, origem, valor) for cnpj, nome, origem, valor in c["doadoresPJ"]]
                    repasses = [(cnpj, nome, cnpj, None, valor) for cnpj, nome, valor in c.get("originariosPJ", ())]
                else:   # coleta antiga: só os maiores e sem documento; o cruzamento é pelo nome
                    diretos = [(nome, nome, None, origem, valor) for nome, origem, valor in c.get("principaisDoadores", ())
                               if not any(r in origem.lower() for r in REPASSES)]
                    repasses = [(nome, nome, None, None, valor) for nome, valor in c.get("doadoresOriginarios", ())]
                for via, lista in (("direto", diretos), ("repasse", repasses)):
                    for ident, nome, cnpj, origem, valor in lista:
                        saida.append((f"{ano}|{sq}|{via}|{ident}", nome, cnpj, {**base, "valor": valor, "origem": origem, "via": via}))
    return saida


def construir(bruto: Path, nucleo: dict, fornecedores: dict) -> dict:
    """Devolve {ligacoes, cruzamentos}. `nucleo` é o de identidades.construir(); `fornecedores`, o de fornecedores.construir()."""
    doadores = _doadores(bruto, nucleo["chaves"])
    ligados, ambiguos = identidades.ligar_doadores([(k, n, c) for k, n, c, _ in doadores], fornecedores["entidades"])
    recebimentos = fornecedores["recebimentos"]
    por_fornecedor = defaultdict(list)
    for chave, _, _, doacao in doadores:
        if chave not in ligados:
            continue
        fid, metodo, confianca = ligados[chave]
        pagos = sorted(({"casa": casa, "uf": uf, "id": did, "valor": valor} for casa, uf, did, pessoa, valor in recebimentos.get(fid, ())
                        if pessoa and pessoa == doacao["pessoa"]), key=lambda p: -p["valor"])
        por_fornecedor[fid].append({k: v for k, v in {**doacao, "ligacao": [metodo, confianca], "pagoPeloMesmoPolitico": pagos or None}.items()
                                    if v is not None})
    cruzamentos = []
    for fid, doacoes in por_fornecedor.items():
        doacoes.sort(key=lambda d: (-d["eleicao"], -d["valor"], d["candidatura"]))
        cruzamentos.append({"fornecedor": fid, "doacoes": doacoes})
    cruzamentos.sort(key=lambda c: (not any(d.get("pagoPeloMesmoPolitico") for d in c["doacoes"]), -sum(d["valor"] for d in c["doacoes"]),
                                    c["fornecedor"]))
    metodos = Counter(m for _, m, _ in ligados.values())
    resumo = {"doadoresPJ": sum(1 for _, _, c, _ in doadores if c), "doadoresSemCnpj": sum(1 for _, _, c, _ in doadores if not c),
              "ligados": dict(metodos), "ambiguos": len(ambiguos), "fornecedores": len(cruzamentos),
              "comPagamentoAoMesmoPolitico": sum(1 for c in cruzamentos if any(d.get("pagoPeloMesmoPolitico") for d in c["doacoes"]))}
    return {"ligacoes": {"resumo": resumo, "registros": ligados, "ambiguos": ambiguos},
            "cruzamentos": cruzamentos, "anoPagamentos": fornecedores["ranking"]["ano"], "resumo": resumo}


def salvar_doadores(res: dict, saida: Path) -> None:
    salvar(saida / "doadores_fornecedores.json", {
        "fontes": FONTES, "anoPagamentos": res["anoPagamentos"], "resumo": res["resumo"], "cruzamentos": res["cruzamentos"]})
    r = res["resumo"]
    print(f"Doadores x fornecedores: {r['fornecedores']} empresas em comum ({r['comPagamentoAoMesmoPolitico']} pagas pelo mesmo político que "
          f"recebeu a doação); ambíguos: {r['ambiguos']}")
