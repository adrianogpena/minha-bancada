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


class SessaoFalsa:
    def __init__(self, respostas):
        self.respostas = respostas
        self.chamadas = []

    def get(self, url, params=None, timeout=None):
        self.chamadas.append((url, params))
        return self.respostas.pop(0)


def test_pegar_monta_url_e_levanta_em_erro_http():
    s = SessaoFalsa([Resp({"dados": [1]}), Resp({"dados": []}), Resp(status=500)])
    assert rn.pegar(s, "parlamentar") == {"dados": [1]}
    assert s.chamadas[0] == (f"{rn.API}/parlamentar", None)
    rn.pegar(s, "processo", iniciativa=3)
    assert s.chamadas[1] == (f"{rn.API}/processo", {"iniciativa": 3})
    with pytest.raises(RuntimeError, match="HTTP 500"):
        rn.pegar(s, "processo")


def test_paginas_segue_ate_pagina_incompleta(monkeypatch):
    monkeypatch.setattr(rn, "TAMANHO", 2)
    s = SessaoFalsa([Resp({"dados": [1, 2]}), Resp({"dados": [3, 4]}), Resp({"dados": [5]})])
    assert list(rn.paginas(s, "processo", iniciativa=7)) == [1, 2, 3, 4, 5]
    assert [p["pagina"] for _, p in s.chamadas] == [0, 1, 2]
    assert all(p["tamanhoPagina"] == 2 and p["iniciativa"] == 7 for _, p in s.chamadas)
    assert list(rn.paginas(SessaoFalsa([Resp({})]), "reuniao")) == []


def test_sessao_nao_repete_erro_500():
    retry = rn.sessao().get_adapter("https://api").max_retries
    assert 500 not in retry.status_forcelist and 429 in retry.status_forcelist and retry.total == 3


def test_coletar_deputados_grava_sem_iniciativas(tmp_path, monkeypatch):
    brutos = amostra("estadual_rn_deputados")["parlamentar"]
    monkeypatch.setattr(rn, "PASTA", tmp_path)
    monkeypatch.setattr(rn, "pegar", lambda s, caminho, **kw: {"dados": brutos})
    deputados = rn.coletar_deputados(None)
    assert [d["id"] for d in deputados] == [str(p["id"]) for p in brutos]
    assert deputados[0]["iniciativas"] == [3]
    salvo = json.loads((tmp_path / "deputados.json").read_text(encoding="utf-8"))
    assert len(salvo["deputados"]) == len(brutos) and all("iniciativas" not in d for d in salvo["deputados"])
    assert salvo["legislatura"] == "63ª (2023-2027)"


def test_projetos_do_deputado_para_na_data_limite_e_ignora_nao_projetos(monkeypatch):
    processos = amostra("estadual_rn_projetos")["processos"]
    projeto = next(p for p in processos if rn.eh_projeto(p))
    outro = next(p for p in processos if not rn.eh_projeto(p))
    novo = {**projeto, "id": 1, "dataEntrada": "2025-05-01T10:00:00.000Z"}
    velho = {**projeto, "id": 2, "dataEntrada": "2020-05-01T10:00:00.000Z"}
    lidos = []

    def paginas(s, caminho, **kw):
        lidos.append(kw["iniciativa"])
        yield {**outro, "dataEntrada": "2025-06-01T10:00:00.000Z"}
        yield novo
        yield velho
        yield {**projeto, "id": 3, "dataEntrada": "2025-07-01T10:00:00.000Z"}

    monkeypatch.setattr(rn, "paginas", paginas)
    achados = rn.projetos_do_deputado(None, {"iniciativas": [10, 11]}, "2023-01-01")
    assert [p["id"] for p in achados] == [1, 1] and lidos == [10, 11]


def test_coletar_projetos_erro_de_um_deputado_vira_aviso(tmp_path, monkeypatch, capsys):
    projeto = next(p for p in amostra("estadual_rn_projetos")["processos"] if rn.eh_projeto(p))
    monkeypatch.setattr(rn, "PASTA", tmp_path)

    def falso(s, d, desde=rn.DESDE):
        if d["id"] == "9":
            raise RuntimeError("HTTP 500")
        return [projeto]

    monkeypatch.setattr(rn, "projetos_do_deputado", falso)
    rn.coletar_projetos(None, [{"id": "8", "nome": "A", "iniciativas": []}, {"id": "9", "nome": "B", "iniciativas": []}])
    assert "AVISO: RN: projetos de B: HTTP 500" in capsys.readouterr().err
    salvo = json.loads((tmp_path / f"materias_{projeto['propositura']['ano']}.json").read_text(encoding="utf-8"))
    assert [m["idsDeputados"] for m in salvo["materias"].values()] == [["8"]]


def test_sessoes_plenarias_filtra_tipo_e_para_antes_de_2023(monkeypatch):
    chamadas = []

    def paginas(s, caminho, **kw):
        chamadas.append((caminho, kw))
        yield {"id": 1, "dataInicio": "2026-05-01T10:00:00.000Z", "tipoReuniao": {"id": 1}}
        yield {"id": 2, "dataInicio": "2026-04-01T10:00:00.000Z", "tipoReuniao": {"id": 5}}
        yield {"id": 3, "dataInicio": "2025-04-01T10:00:00.000Z", "tipoReuniao": {"id": 12}}
        yield {"id": 4, "dataInicio": "2022-12-31T10:00:00.000Z", "tipoReuniao": {"id": 1}}
        yield {"id": 5, "dataInicio": "2024-12-31T10:00:00.000Z", "tipoReuniao": {"id": 1}}

    monkeypatch.setattr(rn, "paginas", paginas)
    assert [r["id"] for r in rn.sessoes_plenarias(None)] == [1, 3]
    assert chamadas == [("reuniao", {"situacao": "R", "tipoOrdenacao": "DESC"})]


def processo_votado(pid, reuniao, tipo="A", abertura="2026-10-20T10:41:30.000Z"):
    base = amostra("estadual_rn_votacao")["processo"]
    return {**base, "id": pid, "tipoVotacao": tipo,
            "resultadoVotacao": {**base["resultadoVotacao"], "dataSituacaoAbertura": abertura, "reuniao": {"id": reuniao}}}


def test_coletar_votacoes_filtra_candidatas_guarda_existentes_e_avisa(tmp_path, monkeypatch, capsys):
    a = amostra("estadual_rn_votacao")
    ids = {str(v["parlamentar"]["id"]) for v in a["detalhe"]["votacao"]["dados"]}
    monkeypatch.setattr(rn, "PASTA", tmp_path)
    ultimas = [processo_votado(1, 3029), processo_votado(2, 3029, tipo="S"), processo_votado(3, 9999),
               processo_votado(4, 3029, abertura="2022-01-01T10:00:00.000Z"), processo_votado(5, 3029), processo_votado(6, 3029)]
    monkeypatch.setattr(rn, "paginas", lambda s, caminho, **kw: iter(ultimas))
    rn.comum.salvar(tmp_path / "votacoes.json", {"votacoes": {"6-3029": {"data": "2026-01-01"}}})
    pedidos = []

    def pegar(s, caminho, **kw):
        pedidos.append(caminho)
        if caminho.startswith("processo/5/"):
            raise RuntimeError("HTTP 500")
        return a["detalhe"]

    monkeypatch.setattr(rn, "pegar", pegar)
    rn.coletar_votacoes(None, [{"id": i} for i in ids], [{"id": 3029}])
    assert pedidos == ["processo/1/detalhamento-votacao/3029", "processo/5/detalhamento-votacao/3029"]
    salvo = json.loads((tmp_path / "votacoes.json").read_text(encoding="utf-8"))["votacoes"]
    assert set(salvo) == {"1-3029", "6-3029"} and salvo["6-3029"] == {"data": "2026-01-01"}
    assert salvo["1-3029"]["idMateria"] == "PL-394-2026"
    materias = json.loads((tmp_path / "materias_votadas.json").read_text(encoding="utf-8"))
    assert list(materias) == ["PL-394-2026"]
    assert "AVISO: RN: a API respondeu erro no detalhe de 1 votações de plenário" in capsys.readouterr().err


def test_coletar_orgao_erro_de_um_ano_nao_para_os_outros(monkeypatch, capsys, tmp_path):
    anos = []

    def orgao_do_ano(s, pasta, ano, hoje):
        anos.append(ano)
        if ano == 2024:
            raise RuntimeError("PNCP fora do ar")

    monkeypatch.setattr(rn, "orgao_do_ano", orgao_do_ano)
    monkeypatch.setattr(rn.time, "sleep", lambda x: None)
    rn.coletar_orgao("s", tmp_path, rn.date(2025, 3, 1))
    assert anos == [2023, 2024, 2025]
    assert "AVISO: RN: contratos e atas de registro 2024: PNCP fora do ar" in capsys.readouterr().err


def test_pncp_pagina_204_vazio_e_erro_http_levanta():
    assert rn.pncp_pagina(SessaoFalsa([Resp(status=204)]), "atas", pagina=1) == {"data": [], "totalPaginas": 0}
    with pytest.raises(RuntimeError, match="HTTP 400"):
        rn.pncp_pagina(SessaoFalsa([Resp(status=400)]), "contratos", pagina=1)


def test_sessao_pncp_nao_repete_429():
    retry = rn.sessao_pncp().get_adapter("https://pncp.gov.br").max_retries
    assert 429 not in retry.status_forcelist and retry.total == 2


def test_presenca_erro_vira_aviso_e_prazo_esgotado_guarda_o_lido(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(rn, "PASTA", tmp_path)
    sessoes = [{"id": 1, "dataInicio": "2024-05-01"}, {"id": 2, "dataInicio": "2024-06-01"}]

    def pegar(s, caminho, **kw):
        if caminho.endswith("/2"):
            raise RuntimeError("HTTP 500")
        return {"dados": [{"id": 8, "evento": {"chave": "presenca"}}]}

    monkeypatch.setattr(rn, "pegar", pegar)
    rn.coletar_presenca(None, [{"id": "8"}], sessoes)
    assert "AVISO: RN: a API respondeu erro em 1 sessões plenárias (ids 2 a 2)" in capsys.readouterr().err

    def prazo(s, caminho, **kw):
        if caminho.endswith("/3"):
            raise rn.comum.PrazoEsgotado("prazo de coleta esgotado")
        return {"dados": [{"id": 8, "evento": {"chave": "presenca"}}]}

    monkeypatch.setattr(rn, "pegar", prazo)
    novas = [{"id": 1, "dataInicio": "2024-05-01"}, {"id": 3, "dataInicio": "2024-07-01"}]
    with pytest.raises(rn.comum.PrazoEsgotado):
        rn.coletar_presenca(None, [{"id": "8"}], novas)
    guardado = json.loads((tmp_path / "presenca_sessoes.json").read_text(encoding="utf-8"))
    assert "1" in guardado["sessoes"] and "3" not in guardado["sessoes"]


def test_pautas_e_atas_prazo_esgotado_salva_o_estado_e_erro_vira_aviso(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(rn, "PASTA", tmp_path)
    tipo = {"nome": "Sessão"}
    sessoes = [{"id": 1, "numero": 1, "dataInicio": f"{rn.ANO_INICIAL}-05-02T13:00:00.000Z", "tipoReuniao": tipo}]

    def prazo(s, caminho, **kw):
        raise rn.comum.PrazoEsgotado("prazo de coleta esgotado")

    monkeypatch.setattr(rn, "pegar", prazo)
    with pytest.raises(rn.comum.PrazoEsgotado):
        rn.coletar_pautas_atas(None, [{"id": "16"}], sessoes)
    assert (tmp_path / f"pautas_{rn.ANO_INICIAL}.json").exists()

    def erro(s, caminho, **kw):
        raise RuntimeError("HTTP 500")

    monkeypatch.setattr(rn, "pegar", erro)
    rn.coletar_pautas_atas(None, [{"id": "16"}], sessoes)
    assert "AVISO: RN: pauta ou ata de 1 sessões plenárias respondeu erro" in capsys.readouterr().err
    salvo = json.loads((tmp_path / f"pautas_{rn.ANO_INICIAL}.json").read_text(encoding="utf-8"))
    assert list(salvo["falhas"]) == ["1"] and salvo["lidas"] == {}


def test_pautas_e_atas_ignora_sessao_de_ano_fora_da_janela(tmp_path, monkeypatch):
    monkeypatch.setattr(rn, "PASTA", tmp_path)
    chamadas = []
    monkeypatch.setattr(rn, "pegar", lambda s, caminho, **kw: chamadas.append(caminho))
    rn.coletar_pautas_atas(None, [], [{"id": 1, "dataInicio": "2019-05-02T13:00:00.000Z"}])
    assert chamadas == []


def test_normas_erro_na_tramitacao_vira_aviso_e_prazo_esgotado_salva_estado(tmp_path, monkeypatch, capsys):
    a = amostra("estadual_rn_normas")
    processo = {**a["processo"], "dataArquivamento": None}
    parlamentar = str(processo["iniciativa"]["parlamentar"]["id"])
    monkeypatch.setattr(rn, "PASTA", tmp_path)
    monkeypatch.setattr(rn, "paginas", lambda s, caminho, **kw: [processo] if kw["tipoPropositura"] == 1 else [])

    def erro(s, caminho, **kw):
        raise RuntimeError("HTTP 500")

    monkeypatch.setattr(rn, "pegar", erro)
    rn.coletar_normas(None, [{"id": parlamentar}])
    assert "AVISO: RN: a API respondeu erro na tramitação de 1 projetos" in capsys.readouterr().err
    assert json.loads((tmp_path / "normas_vistas.json").read_text(encoding="utf-8"))["processos"] == {}

    def prazo(s, caminho, **kw):
        raise rn.comum.PrazoEsgotado("prazo de coleta esgotado")

    monkeypatch.setattr(rn, "pegar", prazo)
    with pytest.raises(rn.comum.PrazoEsgotado):
        rn.coletar_normas(None, [{"id": parlamentar}])
    assert (tmp_path / "normas_vistas.json").exists()


def test_coletar_normas_incremental_le_lista_desde_a_ultima_coleta(tmp_path, monkeypatch):
    hoje = rn.date.today()
    monkeypatch.setattr(rn, "PASTA", tmp_path)
    rn.comum.salvar(tmp_path / "normas_vistas.json", {"coletadoEm": hoje.isoformat(), "completaEm": hoje.isoformat(), "processos": {}})
    janelas = []

    def paginas(s, caminho, **kw):
        janelas.append((kw["dataInicio"], kw["dataFinal"]))
        return []

    monkeypatch.setattr(rn, "paginas", paginas)
    rn.coletar_normas(None, [{"id": "1"}])
    assert janelas[0] == ((hoje - rn.timedelta(days=1)).isoformat(), f"{hoje.year}-12-31")
    assert json.loads((tmp_path / "normas_vistas.json").read_text(encoding="utf-8"))["completaEm"] == hoje.isoformat()


def test_coletar_roda_etapas_em_ordem_e_falha_de_uma_nao_para_as_outras(monkeypatch, capsys):
    chamadas = []
    deputados = [{"id": "8"}]
    monkeypatch.setattr(rn, "sessao", lambda: "s")
    monkeypatch.setattr(rn, "sessao_pncp", lambda: "pncp")
    monkeypatch.setattr(rn, "coletar_deputados", lambda s: deputados)

    def lista_reunioes(s):
        raise RuntimeError("HTTP 500")

    monkeypatch.setattr(rn, "sessoes_plenarias", lista_reunioes)
    monkeypatch.setattr(rn, "coletar_projetos", lambda s, d: chamadas.append(("projetos", s, d)))

    def presenca(s, d, sessoes):
        chamadas.append(("presenca", sessoes))
        raise RuntimeError("quebrou")

    monkeypatch.setattr(rn, "coletar_presenca", presenca)
    monkeypatch.setattr(rn, "coletar_votacoes", lambda s, d, sessoes: chamadas.append(("votacoes", sessoes)))
    monkeypatch.setattr(rn, "coletar_orgao", lambda s, pasta, hoje: chamadas.append(("orgao", s, pasta)))
    monkeypatch.setattr(rn, "coletar_pautas_atas", lambda s, d, sessoes: chamadas.append(("pautas", sessoes)))
    monkeypatch.setattr(rn, "coletar_normas", lambda s, d: chamadas.append(("normas", d)))
    rn.coletar()
    assert chamadas == [("projetos", "s", deputados), ("presenca", []), ("votacoes", []), ("orgao", "pncp", rn.PASTA),
                        ("pautas", []), ("normas", deputados)]
    erro = capsys.readouterr().err
    assert "AVISO: RN: lista de reuniões: HTTP 500" in erro and "AVISO: RN: presença: quebrou" in erro
