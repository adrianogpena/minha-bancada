"""
O que mudou nos ministros e nos pedidos a eles entre duas coletas de `dados/ministros/`. Sem git e sem internet: quem chama lê os
arquivos (histórico diário em `historico.py`; e-mail e RSS em `resumo_email.py`) e este módulo decide o que é novidade, para os três
dizerem a mesma coisa.

Cada mudança: {tipo, pasta (chave de ministerios.PASTAS ou None), titulo, ementa, resumo, mudanca ([antes, depois] ou None),
dataDoAto, relevancia, item (o registro da fonte)}. Tipos: troca (lista do Planalto), novo, resposta, prazo, convocacao.
"""

import re
from collections import defaultdict

import ministerios


def _pasta_do_texto(ementa) -> str | None:
    achadas = ministerios.pastas_do_texto(ementa)
    return achadas[0] if achadas else None


def _nome_pasta(pasta: str | None) -> str | None:
    return ministerios.PASTAS[pasta][0] if pasta else None



def trocas(antes: dict | None, depois: dict | None) -> list[dict]:
    """Troca de ministro: quem entrou ou saiu da lista do Planalto, por cargo. O Planalto não dá data: vale o dia da coleta."""
    if not antes or not depois:
        return []
    por_cargo = lambda d: defaultdict(set, {c: {x["nome"] for x in d["atuais"] if x["cargo"] == c} for c in {x["cargo"] for x in d["atuais"]}})  # noqa: E731
    ant, atual = por_cargo(antes), por_cargo(depois)
    saida = []
    for cargo in sorted(set(ant) | set(atual)):
        saiu, entrou = sorted(ant[cargo] - atual[cargo]), sorted(atual[cargo] - ant[cargo])
        if not saiu and not entrou:
            continue
        pasta = ministerios.pasta_do_cargo(cargo)
        saida.append({"tipo": "troca", "pasta": pasta, "pastaNome": _nome_pasta(pasta), "titulo": cargo, "mudanca": [", ".join(saiu) or "—", ", ".join(entrou) or "—"],
                      "resumo": "Troca de ministro" if saiu and entrou else "Novo ministro" if entrou else "Cargo sem ministro na lista", "ementa": None,
                      "dataDoAto": None, "relevancia": 3, "item": None})
    return saida


def pedidos_camara(antes: dict, depois: dict, hoje: str, ontem: str) -> list[dict]:
    """`antes`/`depois`: o campo "itens" de camara_<ano>.json. Novos, resposta recebida, prazo que acabou de vencer sem resposta e convocação ou convite aprovado."""
    saida = []
    for pid, y in depois.items():
        x = antes.get(pid)
        pasta = _pasta_do_texto(y["ementa"])
        base = dict(pasta=pasta, pastaNome=_nome_pasta(pasta), id=pid, fonte="camara", titulo=f"{y['tipo']} {y['numero']}/{y['ano']}", ementa=y["ementa"], item=y)
        if x is None:
            saida.append({**base, "tipo": "novo", "mudanca": None, "resumo": f"Pedido ao ministério: {base['pastaNome']}" if pasta else "Pedido a ministro",
                          "dataDoAto": y.get("dataApresentacao"), "relevancia": 1})
        elif y["tipo"] == "RIC":
            if y.get("resposta") and not x.get("resposta"):
                no_prazo = not y.get("prazoFim") or y["resposta"] <= y["prazoFim"]
                saida.append({**base, "tipo": "resposta", "mudanca": ["Sem resposta", "Respondido" + (" no prazo" if no_prazo else " fora do prazo")],
                              "resumo": f"Resposta recebida ({base['pastaNome']})" if pasta else "Resposta recebida", "dataDoAto": y["resposta"], "relevancia": 2})
            elif not y.get("resposta") and y.get("prazoFim") and ontem <= y["prazoFim"] < hoje:
                saida.append({**base, "tipo": "prazo", "mudanca": ["Aguardando resposta", "Prazo vencido sem resposta"],
                              "resumo": f"Prazo até {y['prazoFim']}" + (f", {base['pastaNome']}" if pasta else ""), "dataDoAto": y["prazoFim"], "relevancia": 2})
        elif (x.get("situacao") or "") != (y.get("situacao") or "") and re.search(r"aprovad", y.get("situacao") or "", re.I):
            saida.append({**base, "tipo": "convocacao", "mudanca": [x.get("situacao") or "—", y.get("situacao")],
                          "resumo": "Convocação ou convite a ministro aprovado", "dataDoAto": y.get("dataStatus"), "relevancia": 3})
    return saida


def pedidos_senado(antes: dict, depois: dict) -> list[dict]:
    """`antes`/`depois`: o campo "itens" de senado_<ano>.json. Novos e convocação ou convite aprovado."""
    saida = []
    for pid, y in depois.items():
        x = antes.get(pid)
        pasta = _pasta_do_texto(y["ementa"])
        base = dict(pasta=pasta, pastaNome=_nome_pasta(pasta), id=pid, fonte="senado", titulo=y["identificacao"], ementa=y["ementa"], item=y)
        if x is None:
            saida.append({**base, "tipo": "novo", "mudanca": None, "resumo": f"Pedido ao ministério: {base['pastaNome']}" if pasta else "Pedido a ministro",
                          "dataDoAto": y.get("dataApresentacao"), "relevancia": 1})
        elif (y.get("tipoConteudo") != "Informações" and (x.get("deliberacao") or "") != (y.get("deliberacao") or "")
              and re.search(r"aprovad", y.get("deliberacao") or "", re.I)):
            saida.append({**base, "tipo": "convocacao", "mudanca": [x.get("deliberacao") or "—", y["deliberacao"]],
                          "resumo": "Convocação de ministro aprovada", "dataDoAto": y.get("dataDeliberacao"), "relevancia": 3})
    return saida
