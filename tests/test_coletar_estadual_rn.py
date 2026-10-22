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


def test_presenca_guarda_sessoes_lidas_e_nao_repete(tmp_path, monkeypatch):
    from datetime import date, timedelta
    monkeypatch.setattr(rn, "PASTA", tmp_path)
    hoje = date.today()
    antiga, recente, quebrada = "2024-05-01", (hoje - timedelta(days=1)).isoformat(), "2024-06-01"
    sessoes = [{"id": 1, "dataInicio": antiga}, {"id": 2, "dataInicio": recente}, {"id": 3, "dataInicio": quebrada}]
    chamadas = []

    def pegar(s, caminho, **kw):
        chamadas.append(caminho)
        if caminho.endswith("/3"):
            raise RuntimeError("HTTP 500")
        return {"dados": [{"id": 8, "evento": {"chave": "presenca"}}]}

    monkeypatch.setattr(rn, "pegar", pegar)
    deputados = [{"id": "8"}]
    rn.coletar_presenca(None, deputados, sessoes)
    assert sorted(chamadas) == ["reuniao/presenca/1", "reuniao/presenca/2", "reuniao/presenca/3"]
    # segunda execução: a antiga fica no cache, a falha espera a renovação; só a sessão recente é lida de novo
    chamadas.clear()
    rn.coletar_presenca(None, deputados, sessoes)
    assert chamadas == ["reuniao/presenca/2"]
    itens = json.loads((tmp_path / "presenca.json").read_text(encoding="utf-8"))["itens"]
    assert sum(i["presente"] for i in itens) == 2  # sessões 1 e 2; a 3 ficou de fora


def test_coletar_projetos_incremental_le_so_o_novo_e_soma_autores(monkeypatch, tmp_path):
    from datetime import date, timedelta

    projeto = next(p for p in amostra("estadual_rn_projetos")["processos"] if rn.eh_projeto(p))
    ano = projeto["propositura"]["ano"]
    chave, antigo = next(iter(rn.montar_materias({"9": [projeto]})[ano].items()))
    hoje = date.today()
    monkeypatch.setattr(rn.comum, "DADOS", tmp_path)
    monkeypatch.setattr(rn, "PASTA", tmp_path)
    for a in range(rn.ANO_INICIAL, hoje.year + 1):
        rn.comum.salvar(tmp_path / f"materias_{a}.json", {"coletadoEm": hoje.isoformat(), "completaEm": hoje.isoformat(), "fonte": "x",
                                                         "materias": {chave: antigo} if a == ano else {}})
    lidas = []

    def falso(s, d, desde=rn.DESDE):
        lidas.append(desde)
        return [projeto]

    monkeypatch.setattr(rn, "projetos_do_deputado", falso)
    rn.coletar_projetos(None, [{"id": "8", "nome": "A", "iniciativas": []}])
    assert lidas == [(hoje - timedelta(days=1)).isoformat()]
    salvo = rn.comum.ler(tmp_path / f"materias_{ano}.json")
    assert salvo["materias"][chave]["idsDeputados"] == ["8", "9"] and salvo["completaEm"] == hoje.isoformat()

    rn.comum.salvar(tmp_path / f"materias_{hoje.year}.json", {"coletadoEm": "2020-01-01", "completaEm": "2020-01-01", "fonte": "x", "materias": {}})
    lidas.clear()
    rn.coletar_projetos(None, [{"id": "8", "nome": "A", "iniciativas": []}])
    assert lidas == [rn.DESDE]   # completa velha: lê tudo
