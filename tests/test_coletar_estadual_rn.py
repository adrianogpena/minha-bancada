import json

import coletar_estadual_rn as rn
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_contratos_registrados():
    assert [c["nome"] for c in rn.CONTRATOS] == [f"estadual_rn_{x}" for x in ("deputados", "projetos", "presenca", "votacao")]
    for c in rn.CONTRATOS:
        falhas, _ = c["html"](amostra(c["nome"]))
        assert falhas == [], c["nome"]


def test_titulo():
    assert rn.titulo("FRANCISCO DE ASSIS DO PT") == "Francisco de Assis do PT"
    assert rn.titulo("DR. BERNARDO") == "Dr. Bernardo"


def test_deputado():
    d = rn.deputado(amostra("estadual_rn_deputados")["parlamentar"][0])
    assert d["id"] == "8" and d["nome"] == "Cristiane Dantas" and d["nomeCivil"] == "Cristiane Bezerra de Souza Dantas"
    assert d["partido"] == "PSDB" and d["iniciativas"] == [3] and d["fonte"].endswith("/parlamentar/8")
    assert d["foto"].endswith("/parlamentar/fotografia/8") and "cpf" not in d


def test_so_projetos():
    processos = amostra("estadual_rn_projetos")["processos"]
    assert {p["propositura"]["tipo"]["sigla"] for p in processos if rn.eh_projeto(p)} <= {"PL", "PLC", "PEC", "PRES", "PDL", "PRTH"}
    assert any(not rn.eh_projeto(p) for p in processos)


def test_materias_juntam_autores():
    projeto = next(p for p in amostra("estadual_rn_projetos")["processos"] if rn.eh_projeto(p))
    por_ano = rn.montar_materias({"8": [projeto], "9": [projeto]})
    chave, m = next(iter(por_ano[projeto["propositura"]["ano"]].items()))
    assert m["idsAutores"] == ["8", "9"] and m["idsDeputados"] == ["8", "9"]
    assert chave == f"{m['tipo']}-{m['numero']}-{m['ano']}" and m["fonte"].endswith(f"/projeto/{projeto['id']}")
    assert m["emTramitacao"] is True and m["dataApresentacao"] == projeto["dataEntrada"][:10]


def test_presenca_somada_por_ano():
    registros = amostra("estadual_rn_presenca")["presenca"]
    soma = rn.somar_presenca([("2026-03-01", registros), ("2026-03-02", registros), ("2025-12-01", registros)])
    um = registros[0]
    assert soma[(str(um["id"]), "2026")]["totalSessoes"] == 2 and soma[(str(um["id"]), "2025")]["totalSessoes"] == 1
    total = sum(c["presente"] + c["ausente"] + c["licenca"] for c in soma.values())
    assert total == 3 * len(registros)


def test_situacao_presenca():
    assert rn.situacao_presenca({"chave": "presenca"}) == "presente"
    assert rn.situacao_presenca({"chave": "ausencia-justificada"}) == "licenca"
    assert rn.situacao_presenca(None) == "ausente"


def test_votacao_do_contrato():
    a = amostra("estadual_rn_votacao")
    ids = {str(v["parlamentar"]["id"]) for v in a["detalhe"]["votacao"]["dados"]}
    v, m = rn.votacao(a["processo"], a["detalhe"], ids)
    assert v["data"] == "2026-10-20" and v["aprovada"] is True and v["resultado"] == "Aprovado" and v["sim"] == 5
    assert all(voto == "Sim" for _, voto in v["votos"]) and len(v["votos"]) == 5
    assert v["fonte"].endswith("/evento-legislativo/3029") and v["idMateria"] == "PL-394-2026"
    assert m["tipo"] == "PL" and m["numero"] == 394 and m["ementa"]


def test_votos_codificados_e_secretos():
    processo = {"propositura": {"tipo": {"sigla": "PL", "descricao": "PROJETO DE LEI"}, "numero": 1, "ano": 2025}, "ementa": "X",
                "resultadoVotacao": {"dataSituacaoAbertura": "2025-05-06T10:00:00.000Z", "resultadoVotacao": "R", "reuniao": {"id": 7}}}
    detalhe = {"votacao": {"resumo": {"sim": 1, "nao": 1, "abstencao": 1},
                           "dados": [{"voto": 1, "parlamentar": {"id": 1}}, {"voto": 0, "parlamentar": {"id": 2}},
                                     {"voto": 2, "parlamentar": {"id": 3}}, {"voto": "votou", "parlamentar": {"id": 4}},
                                     {"voto": 1, "parlamentar": {"id": 99}}]}}
    v, _ = rn.votacao(processo, detalhe, {"1", "2", "3", "4"})
    assert v["votos"] == [["1", "Sim"], ["2", "Não"], ["3", "Abstenção"]] and v["aprovada"] is False and v["resultado"] == "Rejeitado"
    detalhe["votacao"]["dados"] = [{"voto": "votou", "parlamentar": {"id": 1}}]
    assert rn.votacao(processo, detalhe, {"1"}) is None
