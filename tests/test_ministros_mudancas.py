"""Mudanças entre duas coletas de ministros e de pedidos a eles (ministros_mudancas.py)."""
import ministros_mudancas as mm


def lista(*pares):
    return {"atuais": [{"cargo": c, "nome": n} for c, n in pares]}


def test_trocas_sem_coleta_anterior_ou_atual_nao_tem_mudanca():
    assert mm.trocas(None, lista(("Ministro de Estado da Saúde", "A"))) == []
    assert mm.trocas(lista(("Ministro de Estado da Saúde", "A")), {}) == []


def test_trocas_ignora_cargo_sem_mudanca():
    d = lista(("Ministro de Estado da Saúde", "A"))
    assert mm.trocas(d, d) == []


def test_trocas_de_ministro_entrada_e_saida_sem_substituto():
    antes = lista(("Ministro de Estado da Saúde", "A"), ("Ministro de Estado do Turismo", "B"), ("Ministro de Estado da Educação", "C"))
    depois = lista(("Ministro de Estado da Saúde", "D"), ("Ministro de Estado do Turismo", "B"), ("Ministro de Estado da Cultura", "E"))
    por_cargo = {t["titulo"]: t for t in mm.trocas(antes, depois)}
    assert set(por_cargo) == {"Ministro de Estado da Saúde", "Ministro de Estado da Educação", "Ministro de Estado da Cultura"}
    saude = por_cargo["Ministro de Estado da Saúde"]
    assert saude["tipo"] == "troca" and saude["pasta"] == "saude" and saude["pastaNome"] == "Saúde"
    assert saude["mudanca"] == ["A", "D"] and saude["resumo"] == "Troca de ministro" and saude["relevancia"] == 3
    assert por_cargo["Ministro de Estado da Cultura"]["mudanca"] == ["—", "E"]
    assert por_cargo["Ministro de Estado da Cultura"]["resumo"] == "Novo ministro"
    assert por_cargo["Ministro de Estado da Educação"]["mudanca"] == ["C", "—"]
    assert por_cargo["Ministro de Estado da Educação"]["resumo"] == "Cargo sem ministro na lista"


def test_trocas_cargo_sem_pasta_conhecida():
    (t,) = mm.trocas(lista(("Cargo Inventado", "A")), lista(("Cargo Inventado", "B")))
    assert t["pasta"] is None and t["pastaNome"] is None


def pedido_camara(tipo="REQ", ementa="Solicita informações ao Sr. Ministro da Saúde sobre vacinas.", **extra):
    return {"tipo": tipo, "numero": 10, "ano": 2026, "ementa": ementa, **extra}


def test_pedidos_camara_novo_com_e_sem_pasta():
    depois = {"1": pedido_camara(dataApresentacao="2026-05-01"), "2": pedido_camara(ementa="Requer audiência pública")}
    por_id = {p["id"]: p for p in mm.pedidos_camara({}, depois, "2026-06-10", "2026-06-09")}
    assert por_id["1"]["tipo"] == "novo" and por_id["1"]["pasta"] == "saude" and por_id["1"]["fonte"] == "camara"
    assert por_id["1"]["resumo"] == "Pedido ao ministério: Saúde" and por_id["1"]["dataDoAto"] == "2026-05-01"
    assert por_id["1"]["titulo"] == "REQ 10/2026" and por_id["1"]["relevancia"] == 1
    assert por_id["2"]["pasta"] is None and por_id["2"]["resumo"] == "Pedido a ministro"


def test_pedidos_camara_resposta_no_prazo_e_fora_do_prazo():
    antes = {"1": pedido_camara("RIC", prazoFim="2026-06-01"), "2": pedido_camara("RIC", prazoFim="2026-06-01")}
    depois = {"1": pedido_camara("RIC", prazoFim="2026-06-01", resposta="2026-05-30"),
              "2": pedido_camara("RIC", prazoFim="2026-06-01", resposta="2026-06-05")}
    por_id = {p["id"]: p for p in mm.pedidos_camara(antes, depois, "2026-06-10", "2026-06-09")}
    assert por_id["1"]["tipo"] == "resposta" and por_id["1"]["mudanca"] == ["Sem resposta", "Respondido no prazo"]
    assert por_id["1"]["resumo"] == "Resposta recebida (Saúde)" and por_id["1"]["dataDoAto"] == "2026-05-30"
    assert por_id["2"]["mudanca"] == ["Sem resposta", "Respondido fora do prazo"]


def test_pedidos_camara_resposta_ja_conhecida_nao_repete():
    x = pedido_camara("RIC", prazoFim="2026-06-01", resposta="2026-05-30")
    assert mm.pedidos_camara({"1": x}, {"1": dict(x)}, "2026-06-10", "2026-06-09") == []


def test_pedidos_camara_prazo_vencido_so_no_dia_em_que_vence():
    x = pedido_camara("RIC", prazoFim="2026-06-09")
    (p,) = mm.pedidos_camara({"1": x}, {"1": dict(x)}, "2026-06-10", "2026-06-09")
    assert p["tipo"] == "prazo" and p["mudanca"] == ["Aguardando resposta", "Prazo vencido sem resposta"]
    assert p["resumo"] == "Prazo até 2026-06-09, Saúde" and p["dataDoAto"] == "2026-06-09"
    assert mm.pedidos_camara({"1": x}, {"1": dict(x)}, "2026-06-12", "2026-06-11") == []
    assert mm.pedidos_camara({"1": x}, {"1": dict(x)}, "2026-06-09", "2026-06-08") == []


def test_pedidos_camara_convocacao_aprovada():
    antes = {"1": pedido_camara("REQ", situacao="Aguardando Apreciação"), "2": pedido_camara("REQ", situacao="Aprovado"),
             "3": pedido_camara("REQ", situacao="Aguardando Apreciação")}
    depois = {"1": pedido_camara("REQ", situacao="Aprovado", dataStatus="2026-06-02"), "2": pedido_camara("REQ", situacao="Aprovado"),
              "3": pedido_camara("REQ", situacao="Rejeitado")}
    (p,) = mm.pedidos_camara(antes, depois, "2026-06-10", "2026-06-09")
    assert p["id"] == "1" and p["tipo"] == "convocacao" and p["mudanca"] == ["Aguardando Apreciação", "Aprovado"]
    assert p["resumo"] == "Convocação ou convite a ministro aprovado" and p["dataDoAto"] == "2026-06-02" and p["relevancia"] == 3


def pedido_senado(**extra):
    return {"identificacao": "REQ 5/2026", "ementa": "Convoca o Ministro da Saúde para explicações.", "tipoConteudo": "Convocação", **extra}


def test_pedidos_senado_novo():
    (p,) = mm.pedidos_senado({}, {"9": pedido_senado(dataApresentacao="2026-04-01")})
    assert p["tipo"] == "novo" and p["fonte"] == "senado" and p["titulo"] == "REQ 5/2026" and p["pasta"] == "saude"
    assert p["resumo"] == "Pedido ao ministério: Saúde" and p["dataDoAto"] == "2026-04-01"


def test_pedidos_senado_convocacao_aprovada_e_informacoes_ignoradas():
    antes = {"1": pedido_senado(), "2": pedido_senado(tipoConteudo="Informações"), "3": pedido_senado(deliberacao="Aprovado")}
    depois = {"1": pedido_senado(deliberacao="Aprovado", dataDeliberacao="2026-06-03"),
              "2": pedido_senado(tipoConteudo="Informações", deliberacao="Aprovado"),
              "3": pedido_senado(deliberacao="Aprovado")}
    (p,) = mm.pedidos_senado(antes, depois)
    assert p["id"] == "1" and p["tipo"] == "convocacao" and p["mudanca"] == ["—", "Aprovado"]
    assert p["resumo"] == "Convocação de ministro aprovada" and p["dataDoAto"] == "2026-06-03"
