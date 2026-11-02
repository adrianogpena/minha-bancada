import json

import pytest

import coletar_estadual_rn as rn
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_contratos_registrados():
    assert [c["nome"] for c in rn.CONTRATOS] == [f"estadual_rn_{x}" for x in ("deputados", "projetos", "presenca", "votacao", "orgao", "pauta", "atas", "normas")]
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


class Resp:
    def __init__(self, dados=None, status=200):
        self.dados = dados
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.dados


def test_itens_do_orgao_pncp():
    a = amostra("estadual_rn_orgao")
    itens = rn.itens_do_orgao(a["contratos"], a["atas"])
    por_tipo = {}
    for i in itens.values():
        por_tipo.setdefault(i["tipo"], []).append(i)
    assert set(por_tipo) == {"contrato", "ata_registro"} and all(k.startswith("ctr_") for k in itens)
    assert itens == rn.itens_do_orgao(a["contratos"], a["atas"])
    c = por_tipo["contrato"][0]
    assert c["cnpj"] and c["valor"] and c["inicio"] and c["fonte"].startswith(f"{rn.PNCP_SITE}/contratos/{rn.CNPJ_ORGAO}/")
    assert c["arquivos"][0]["url"] == c["fonte"]
    ata = por_tipo["ata_registro"][0]
    assert ata["fornecedor"] is None and ata["valor"] is None and ata["fonte"].startswith(f"{rn.PNCP_SITE}/atas/{rn.CNPJ_ORGAO}/")
    assert rn._conferir_orgao(a) == ([], [])


def test_links_do_pncp():
    assert rn.link_contrato({"numeroControlePNCP": "08493371000164-2-000168/2025"}) == f"{rn.PNCP_SITE}/contratos/08493371000164/2025/168"
    assert rn.link_ata({"numeroControlePNCPAta": "08493371000164-1-000144/2024-000001"}) == f"{rn.PNCP_SITE}/atas/08493371000164/2024/144/1"
    assert rn.link_contrato({}) is None and rn.link_ata({"numeroControlePNCPAta": "x"}) is None


def sessao_pncp_falsa(contratos, atas, chamadas, limite_429=0):
    class Sessao:
        def get(self, url, params=None, timeout=None):
            recurso = url.replace(rn.PNCP + "/", "")
            chamadas.append((recurso, params["pagina"]))
            if limite_429 and chamadas.count((recurso, params["pagina"])) <= limite_429:
                return Resp(status=429)
            registros = contratos if recurso == "contratos" else atas
            if not registros:
                return Resp(status=204)
            return Resp({"data": registros[params["pagina"] - 1], "totalPaginas": len(registros)})
    return Sessao()


def test_orgao_do_ano_pagina_espera_429_e_pula_ano_encerrado(tmp_path, monkeypatch):
    a = amostra("estadual_rn_orgao")
    esperas = []
    monkeypatch.setattr(rn.time, "sleep", esperas.append)
    chamadas = []
    s = sessao_pncp_falsa([a["contratos"][:1], a["contratos"][1:]], [a["atas"]], chamadas, limite_429=1)
    hoje = rn.date(2026, 11, 2)
    rn.orgao_do_ano(s, tmp_path, 2026, hoje)
    env = json.loads((tmp_path / "orgao_2026.json").read_text(encoding="utf-8"))
    assert len(env["itens"]) == len(a["contratos"]) + len(a["atas"])
    assert ("contratos", 2) in chamadas and rn.ESPERA_429 in esperas

    chamadas.clear()
    (tmp_path / "orgao_2023.json").write_text("{}", encoding="utf-8")
    rn.orgao_do_ano(s, tmp_path, 2023, hoje)
    assert chamadas == []


def test_orgao_do_ano_sem_registro_mantem_arquivo_anterior(tmp_path, monkeypatch):
    monkeypatch.setattr(rn.time, "sleep", lambda x: None)
    (tmp_path / "orgao_2026.json").write_text(json.dumps({"itens": {"ctr_x": {"tipo": "contrato"}}}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="mantém o arquivo anterior"):
        rn.orgao_do_ano(sessao_pncp_falsa([], [], []), tmp_path, 2026, rn.date(2026, 11, 2))
    assert "ctr_x" in json.loads((tmp_path / "orgao_2026.json").read_text(encoding="utf-8"))["itens"]


def test_pncp_desiste_depois_de_429_repetido(monkeypatch):
    monkeypatch.setattr(rn.time, "sleep", lambda x: None)
    with pytest.raises(RuntimeError, match="429"):
        rn.pncp_pagina(sessao_pncp_falsa([], [], [], limite_429=99), "atas", pagina=1)


def test_pauta_liga_deputado_por_id():
    a = amostra("estadual_rn_pauta")
    ids = sorted({str(p["iniciativa"]["parlamentar"]["id"]) for lista in a["fases"].values() for p in lista})
    processos = rn.processos_da_pauta({int(f): lista for f, lista in a["fases"].items()}, {ids[0]})
    assert {p["fase"] for p in processos} == {1, 2}
    assert {p["idDeputado"] for p in processos} == ({ids[0], None} if len(ids) > 1 else {ids[0]})
    item = rn.item_pauta(a["reuniao"], processos)
    assert item["tipo"] == "ordem-do-dia" and item["data"] == "2026-10-28" and item["fonte"].endswith("/evento-legislativo/3048")
    assert item["arquivos"][0]["url"] == item["fonte"] and item["idsDeputados"] == [ids[0]]
    assert rn.item_pauta(a["reuniao"], []) is None
    assert rn._conferir_pauta(a) == ([], [])


def test_dia_local_usa_fuso_do_rn():
    assert rn.dia_local("2026-10-29T02:30:00.000Z") == "2026-10-28"
    assert rn.dia_local(None) is None


def test_ata_so_com_texto_publicado():
    a = amostra("estadual_rn_atas")
    itens = rn.itens_ata(a["reuniao"], a["videos"] + [{**a["videos"][0], "id": 1, "ata": None}])
    assert len(itens) == 1 and itens[0]["tipo"] == "atas"
    assert itens[0]["arquivos"][0]["url"] == f"{rn.ATAS_SITE}/video/ata/{a['videos'][0]['hash']}" and "ata" not in itens[0]
    assert rn._conferir_atas(a) == ([], [])


def test_pautas_e_atas_incremental(tmp_path, monkeypatch):
    a = amostra("estadual_rn_pauta")
    hoje = rn.date.today()
    recente = f"{(hoje - rn.timedelta(days=1)).isoformat()}T13:00:00.000Z"
    tipo = {"nome": "Sessão"}
    sessoes = [{"id": 1, "numero": 1, "dataInicio": f"{rn.ANO_INICIAL}-05-02T13:00:00.000Z", "tipoReuniao": tipo},
               {"id": 2, "numero": 2, "dataInicio": recente, "tipoReuniao": tipo},
               {"id": 3, "numero": 3, "dataInicio": f"{rn.ANO_INICIAL}-06-02T13:00:00.000Z", "tipoReuniao": tipo}]
    monkeypatch.setattr(rn, "PASTA", tmp_path)
    chamadas = []

    def pegar(s, caminho, **kw):
        chamadas.append((caminho, kw.get("reuniao"), kw.get("faseReuniao")))
        if kw.get("reuniao") == 3 or caminho.endswith("/3"):
            raise RuntimeError("HTTP 500")
        if caminho == "processo":
            return {"dados": a["fases"][str(kw["faseReuniao"])]}
        return {"dados": [{"id": 90 + int(caminho.rsplit("/", 1)[1]), "hash": "abc", "titulo": "Sessão", "ata": "<p>x</p>"}]}

    monkeypatch.setattr(rn, "pegar", pegar)
    rn.coletar_pautas_atas(None, [{"id": "16"}], sessoes)
    antigo = json.loads((tmp_path / f"pautas_{rn.ANO_INICIAL}.json").read_text(encoding="utf-8"))
    assert set(antigo["itens"]) == {"ordem-do-dia|1", "atas|91"}
    assert list(antigo["falhas"]) == ["3"] and list(antigo["lidas"]) == ["1"]

    chamadas.clear()
    rn.coletar_pautas_atas(None, [{"id": "16"}], sessoes)
    assert {c[1] for c in chamadas if c[0] == "processo"} == {2}
    atual = json.loads((tmp_path / f"pautas_{hoje.year}.json").read_text(encoding="utf-8"))
    assert [i["reuniao"] for i in atual["itens"].values() if i["tipo"] == "atas"] == [2]


def test_norma_pela_tramitacao():
    a = amostra("estadual_rn_normas")
    sit = rn.situacao_da_norma(a["tramitacao"])
    assert sit["id"] in rn.SITUACOES_NORMA and sit["data"]
    chave, n = rn.norma(a["processo"], sit)
    assert chave == "PL-508-2023" and n["tipo"] == "Projeto de Lei sancionado" and n["numero"] == 508 and n["ano"] == 2023
    assert n["idsDeputados"] == [str(a["processo"]["iniciativa"]["parlamentar"]["id"])] and n["fonte"]
    assert rn.situacao_da_norma([{"situacaoProcesso": {"id": 13}}]) is None
    assert rn._conferir_normas(a) == ([], [])


def test_situacao_da_norma_prefere_link_do_diario():
    tram = [{"situacaoProcesso": {"id": 27, "nome": "Lei Sancionada"}, "origem": {"data": "2025-01-01T12:00:00.000Z"}, "linkDOE": None},
            {"situacaoProcesso": {"id": 27, "nome": "Lei Sancionada"}, "origem": {"data": "2025-01-05T12:00:00.000Z"}, "linkDOE": "https://doe/1"}]
    assert rn.situacao_da_norma(tram)["linkDOE"] == "https://doe/1"


def test_coletar_normas_le_so_o_que_falta(tmp_path, monkeypatch):
    a = amostra("estadual_rn_normas")
    processo = {**a["processo"], "dataArquivamento": None}
    parlamentar = str(processo["iniciativa"]["parlamentar"]["id"])
    outro = {**processo, "id": 999, "propositura": {**processo["propositura"], "numero": 1}}
    monkeypatch.setattr(rn, "PASTA", tmp_path)
    monkeypatch.setattr(rn, "paginas", lambda s, caminho, **kw: [processo, outro] if kw["tipoPropositura"] == 1 else [])
    chamadas = []

    def pegar(s, caminho, **kw):
        chamadas.append(caminho)
        if caminho == f"processo/{processo['id']}/tramitacao":
            return a["tramitacao"]
        if caminho.endswith("/tramitacao"):
            return [{"situacaoProcesso": {"id": 13}}]
        raise AssertionError(caminho)

    monkeypatch.setattr(rn, "pegar", pegar)
    rn.coletar_normas(None, [{"id": parlamentar}])
    assert sorted(chamadas) == sorted([f"processo/{processo['id']}/tramitacao", "processo/999/tramitacao"])
    sit = rn.situacao_da_norma(a["tramitacao"])
    salvo = json.loads((tmp_path / f"normas_{sit['data'][:4]}.json").read_text(encoding="utf-8"))
    assert list(salvo["normas"]) == ["PL-508-2023"]
    vistas = json.loads((tmp_path / "normas_vistas.json").read_text(encoding="utf-8"))["processos"]
    assert vistas[str(processo["id"])]["norma"] is True and vistas["999"]["arquivado"] is False

    chamadas.clear()
    rn.coletar_normas(None, [{"id": parlamentar}])
    assert chamadas == []
