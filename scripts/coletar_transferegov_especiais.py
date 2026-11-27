"""
Emendas Pix (Transferências Especiais) pelo Transferegov: plano de ação, beneficiário (o ente que recebe) e executores (quem
aplica a verba, com CNPJ, objeto e valores), pela API de dados abertos nova do módulo.

Fonte: https://api-publica.transferegov.gestao.gov.br/especiais (FastAPI, sem chave, esquema em /especiais/openapi.json). O host
antigo (api.transferegov.gestao.gov.br) foi desativado na migração e devolve bloqueio do Cloudflare. A API pagina com `pagina` (a
partir de 1) e `tamanho_da_pagina` (máximo 200) e responde {data, total_pages, total_items}; `/data-atualizacao` diz quando a
carga foi renovada pela última vez.

A ligação com a emenda do Portal da Transparência é pelo código: `numero_emenda_parlamentar_plano_acao` (12 dígitos, ex.
202027070006) é o `codigoEmenda` de dados/emendas/<ano>.json. O nome do parlamentar não é guardado aqui (vive em
dados/emendas/ e no núcleo); a ligação a pessoa é de identidades.py, nunca daqui.

Grava em dados/transferegov/:
  especiais/<ano>.json  {coletadoEm, fonte, planos:[{id, codigo, emenda, ano, situacao, aceite, beneficiario, custeio, investimento,
                        areas, objeto, executores:[{id, cnpj, nome, objeto, custeio, investimento}]}]}  (ano do plano de ação)
  beneficiarios.json    {coletadoEm, fonte, itens:{<id_beneficiario>: {nome, uf, cnpj}}}
  atualizacao.json      {atualizadoEm, coletadoEm}; gravado por último. Se a data da API não mudou desde a última coleta, nada é baixado.
Valores em reais (float), datas em ISO, CNPJ só dígitos e válido (fornecedores.documento).

Uso:
    python scripts/coletar_transferegov_especiais.py            # coleta (pula se a API não foi renovada)
    python scripts/coletar_transferegov_especiais.py --forcar   # coleta mesmo sem renovação
    python scripts/coletar_transferegov_especiais.py --amostra  # regrava tests/fixtures/contratos/transferegov_especiais.json
"""

import datetime as dt
import sys
import time
from collections import defaultdict
from pathlib import Path

import estaduais_comum as comum
import fornecedores

DADOS = comum.RAIZ / "dados" / "transferegov"
URL = "https://api-publica.transferegov.gestao.gov.br/especiais"
FONTE = "https://www.gov.br/transferegov/pt-br/ferramentas-gestao/api-de-dados-abertos-transferegov.br"
AMOSTRA = comum.RAIZ / "tests" / "fixtures" / "contratos" / "transferegov_especiais.json"
TAMANHO = 200
PAUSA = 0.3   # s entre páginas; a API não publica limite, ~300 páginas por tabela
LIMITE_PAGINAS = 2000   # ~59 mil planos / 200 = 295; mais que isso é laço na paginação
RECURSOS = {"planos": "planos-acao-especiais", "beneficiarios": "beneficiarios-especiais", "executores": "executores-especiais"}


def texto(v) -> str:
    return " ".join(str(v or "").split())


def limpar(item: dict) -> dict:
    return {k: v for k, v in item.items() if v not in (None, "", [])}


def cnpj(bruto) -> str | None:
    doc = fornecedores.documento(bruto)
    return doc[1] if doc and doc[0] == "cnpj" else None


def compactar_plano(p: dict) -> dict | None:
    if p.get("id_plano_acao") is None:
        return None
    return limpar({
        "id": p["id_plano_acao"], "codigo": texto(p.get("codigo_plano_acao")), "emenda": texto(p.get("numero_emenda_parlamentar_plano_acao")),
        "ano": p.get("ano_plano_acao"), "situacao": texto(p.get("situacao_plano_acao")), "aceite": p.get("data_aceite_plano_acao"),
        "beneficiario": p.get("id_beneficiario"), "custeio": comum.valor_br(p.get("valor_custeio_plano_acao")),
        "investimento": comum.valor_br(p.get("valor_investimento_plano_acao")),
        "areas": texto(p.get("codigo_descricao_areas_politicas_publicas_plano_acao")), "objeto": texto(p.get("nome_objeto")),
    })


def compactar_executor(e: dict) -> dict | None:
    if e.get("id_executor") is None or e.get("id_plano_acao") is None:
        return None
    return limpar({
        "id": e["id_executor"], "plano": e["id_plano_acao"], "cnpj": cnpj(e.get("cnpj_executor")), "nome": texto(e.get("nome_executor")),
        "objeto": texto(e.get("objeto_executor")), "custeio": comum.valor_br(e.get("vl_custeio_executor")),
        "investimento": comum.valor_br(e.get("vl_investimento_executor")),
    })


def compactar_beneficiario(b: dict) -> dict | None:
    if b.get("id_beneficiario") is None:
        return None
    return limpar({"nome": texto(b.get("nome_beneficiario")), "uf": texto(b.get("uf_beneficiario")), "cnpj": cnpj(b.get("cnpj_beneficiario"))})


def paginas(s, recurso: str, pausa: float = PAUSA):
    """Itens crus de todas as páginas de um recurso, até `total_pages`."""
    total = 1
    for pagina in range(1, LIMITE_PAGINAS + 1):
        r = comum.get(s, f"{URL}/{recurso}", params={"pagina": pagina, "tamanho_da_pagina": TAMANHO}, timeout=60).json()
        total = r.get("total_pages") or 1
        yield from r.get("data") or []
        if pagina >= total:
            return
        time.sleep(pausa)
    raise RuntimeError(f"paginação de {recurso} não terminou")


def atualizacao_da_api(s) -> str:
    return texto(comum.get(s, f"{URL}/data-atualizacao", timeout=60).json().get("data_ultima_atualizacao"))


def montar(planos: list[dict], executores: list[dict]) -> dict[int, list[dict]]:
    """{ano: [plano com seus executores]}; plano sem ano vai para ano 0 não é gravado; executor sem plano é descartado."""
    por_plano = defaultdict(list)
    for e in executores:
        por_plano[e.pop("plano")].append(e)
    anos = defaultdict(list)
    for p in planos:
        ex = sorted(por_plano.get(p["id"], []), key=lambda e: e["id"])
        anos[p.get("ano") or 0].append({**p, **({"executores": ex} if ex else {})})
    return {a: sorted(v, key=lambda p: p["id"]) for a, v in anos.items() if a}


def coletar(forcar: bool = False, hoje: dt.date | None = None, s=None, pausa: float = PAUSA) -> bool:
    hoje = hoje or dt.date.today()
    s = s or comum.sessao(1)
    try:
        atual = atualizacao_da_api(s)
    except Exception as e:  # noqa: BLE001
        comum.avisar(f"transferegov especiais: data de atualização: {e}")
        return False
    anterior = (comum.ler(DADOS / "atualizacao.json", {}) or {}).get("atualizadoEm")
    if atual and atual == anterior and not forcar:
        print(f"Transferegov especiais: API sem renovação desde {atual}; nada a baixar")
        return False
    try:
        beneficiarios = {b["id_beneficiario"]: c for b in paginas(s, RECURSOS["beneficiarios"], pausa) if (c := compactar_beneficiario(b))}
        planos = [c for c in map(compactar_plano, paginas(s, RECURSOS["planos"], pausa)) if c]
        executores = [c for c in map(compactar_executor, paginas(s, RECURSOS["executores"], pausa)) if c]
    except Exception as e:  # noqa: BLE001
        comum.avisar(f"transferegov especiais: {e}; arquivos anteriores mantidos")
        return False
    if not planos:
        comum.avisar("transferegov especiais: a API não devolveu planos; arquivos anteriores mantidos")
        return False
    for ano, itens in montar(planos, executores).items():
        comum.salvar(DADOS / "especiais" / f"{ano}.json", {"coletadoEm": hoje.isoformat(), "fonte": f"{URL}/planos-acao-especiais", "planos": itens})
    comum.salvar(DADOS / "beneficiarios.json", {"coletadoEm": hoje.isoformat(), "fonte": f"{URL}/beneficiarios-especiais",
                                                "itens": {str(k): v for k, v in sorted(beneficiarios.items())}})
    comum.salvar(DADOS / "atualizacao.json", {"atualizadoEm": atual, "coletadoEm": hoje.isoformat()})
    print(f"Transferegov especiais: {len(planos)} planos, {len(executores)} executores, {len(beneficiarios)} beneficiários (API de {atual})")
    return True


def gravar_amostra(hoje: dt.date | None = None, s=None, itens: int = 3) -> None:
    """Grava a resposta crua da API (primeiros itens de cada recurso, sem compactar) como amostra de contrato dos testes."""
    hoje = hoje or dt.date.today()
    s = s or comum.sessao(1)
    amostra = {"dataAtualizacao": atualizacao_da_api(s)}
    for nome, recurso in RECURSOS.items():
        r = comum.get(s, f"{URL}/{recurso}", params={"pagina": 1, "tamanho_da_pagina": itens}, timeout=60).json()
        if not r.get("data"):
            raise RuntimeError(f"a API não devolveu {recurso} para a amostra")
        amostra[nome] = r["data"][:itens]
    comum.salvar(AMOSTRA, {"fonte": f"{URL}/<recurso>?pagina=1&tamanho_da_pagina={itens}", "capturadoEm": hoje.isoformat(), "amostra": amostra})
    print(f"Amostra gravada em {AMOSTRA}")


def main() -> None:
    args = sys.argv[1:]
    if args == ["--amostra"]:
        gravar_amostra()
    else:
        coletar(forcar="--forcar" in args)


if __name__ == "__main__":
    main()
