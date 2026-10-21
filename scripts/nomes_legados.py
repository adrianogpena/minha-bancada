"""
Nomes antigos (abreviados) dos campos dos JSON de dados/ -> nomes atuais.

Só serve ao histórico e ao resumo por e-mail, que comparam versões antigas do git com as novas: um commit anterior
à renomeação ainda tem os campos abreviados. Passou o primeiro dia comparado com os nomes novos, este módulo pode sair.
`atualizar(caminho, dados)` devolve os dados daquele arquivo com os nomes atuais (ou os mesmos dados, se já estão).
"""

import re

MATERIA = {"t": "tipo", "td": "tipoDescricao", "n": "numero", "a": "ano", "ap": "dataApresentacao", "e": "ementa",
           "sit": "situacao", "tr": "emTramitacao", "pdf": "linkTexto", "au": "idsAutores", "dep": "idsDeputados"}
VOTACAO = {"d": "data", "m": "idMateria", "ok": "aprovada", "res": "resultado", "abs": "abstencoes", "v": "votos"}
DETALHE = {"apres": "dataApresentacao", "sit": "situacao", "tram": "tramitacao", "desp": "despacho", "org": "orgao",
           "data": "dataSituacao", "detalhada": "ementaDetalhada", "palavras": "palavrasChave", "em": "consultadoEm",
           "fim": "finalizada"}
EXECUTIVO = {"apres": "dataApresentacao", "sit": "situacao", "data": "dataSituacao", "t": "tramitacaoLida",
             "edicao": "dataEdicao", "razoes": "razoesVeto", "msc": "mensagemVeto"}
SENADO = {"sit": "situacao", "data": "dataSituacao", "ap": "dataApresentacao", "proc": "processo"}


def renomear(obj: dict, mapa: dict) -> dict:
    return {mapa.get(k, k): v for k, v in obj.items()}


def atualizar(caminho: str, dados):
    if re.search(r"dados/(estaduais|municipais)/[A-Z]{2}/(materias|governo|prefeitura)_\d{4}\.json$", caminho) and isinstance(dados, dict):
        return {**dados, "materias": {k: renomear(m, MATERIA) for k, m in (dados.get("materias") or {}).items()}}
    if caminho.endswith("/materias_votadas.json") and isinstance(dados, dict):
        return {k: renomear(m, MATERIA) for k, m in dados.items()}
    if caminho.endswith("/votacoes.json") and "/estaduais/" in caminho and isinstance(dados, dict):
        return {**dados, "votacoes": {k: renomear(v, VOTACAO) for k, v in (dados.get("votacoes") or {}).items()}}
    if caminho == "dados/proposicoes_detalhe.json" and isinstance(dados, dict):
        return {k: renomear(v, DETALHE) for k, v in dados.items()}
    if caminho == "dados/executivo.json" and isinstance(dados, list):
        return [renomear(i, EXECUTIVO) for i in dados]
    if caminho == "dados/senado_materias.json" and isinstance(dados, dict):
        return {k: renomear(v, SENADO) for k, v in dados.items()}
    return dados
