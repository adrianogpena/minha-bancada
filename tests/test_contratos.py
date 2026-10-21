"""Testes do verificador de contrato (scripts/contrato_apis.py) e dos coletores contra respostas REAIS gravadas
em tests/fixtures/contratos/ (regrave com `python scripts/contrato_apis.py --gravar`)."""
import json

import pytest

import contrato_apis as c
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"


def fixture(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))


def amostra(nome):
    return fixture(nome)["amostra"]


# ================================================================ forma / comparação (sem rede)

def test_forma_tipos_caminhos_e_opcionais():
    f = c.forma({"dados": [{"id": 1, "nome": "a", "x": None}, {"id": 2, "nome": "b", "extra": {"y": 1.5}}], "ok": True})
    assert f["dados"]["tipos"] == ["list"] and f["dados[]"]["tipos"] == ["dict"]
    assert f["dados[].id"]["tipos"] == ["int"] and "opcional" not in f["dados[].id"]
    assert f["dados[].x"] == {"tipos": ["null"], "opcional": True}
    assert f["dados[].extra.y"]["tipos"] == ["float"] and f["dados[].extra"]["opcional"] is True   # só um item tem "extra"
    assert f["ok"]["tipos"] == ["bool"]


def test_forma_lista_na_raiz():
    f = c.forma([{"a": 1}])
    assert f["[].a"]["tipos"] == ["int"]


def test_reduzir_corta_listas_e_textos():
    r = c.reduzir({"l": list(range(10)), "t": "x" * 1000, "n": [{"a": [1, 2, 3, 4]}] * 5})
    assert r["l"] == [0, 1] and len(r["t"]) == c.TEXTO_MAX and len(r["n"]) == 2 and r["n"][0]["a"] == [1, 2]


def test_casa_exato_e_curinga_sem_diferenciar_caixa():
    f = c.forma({"A": {"CodigoParlamentar": 1}, "b": [{"codigoparlamentar": 2}]})
    assert c.casa("A.CodigoParlamentar", f) == ["A.CodigoParlamentar"]
    assert sorted(c.casa("**codigoParlamentar", f)) == ["A.CodigoParlamentar", "b[].codigoparlamentar"]
    assert c.casa("nao.existe", f) == [] and c.casa("**nada", f) == []


def test_sem_amostra_quando_lista_ancestral_vazia():
    f = c.forma({"dados": []})
    assert c.sem_amostra("dados[].id", f)
    assert not c.sem_amostra("dados[].id", c.forma({"dados": [{"id": 1}]}))
    assert not c.sem_amostra("outro", f)


def gravada():
    return c.forma({"dados": [{"id": 1, "nome": "a", "tel": None}, {"id": 2, "nome": "b", "opc": "x"}]})


def test_comparar_igual_nao_acusa_nada():
    assert c.comparar(gravada(), gravada(), ["dados[].id", "dados[].nome"]) == ([], [])


def test_comparar_campo_usado_que_sumiu_e_falha():
    viva = c.forma({"dados": [{"id": 1}]})
    falhas, _ = c.comparar(gravada(), viva, ["dados[].id", "dados[].nome"])
    assert falhas == ["dados[].nome: campo sumiu da resposta"]


def test_comparar_campo_usado_que_mudou_de_tipo_e_falha():
    viva = c.forma({"dados": [{"id": "1", "nome": "a"}]})
    falhas, _ = c.comparar(gravada(), viva, ["dados[].id"])
    assert "tipo mudou" in falhas[0]


def test_comparar_null_e_tolerado():
    viva = c.forma({"dados": [{"id": None, "nome": "a"}]})
    assert c.comparar(gravada(), viva, ["dados[].id"])[0] == []


def test_comparar_campo_opcional_ausente_so_avisa():
    viva = c.forma({"dados": [{"id": 1, "nome": "a"}]})
    falhas, avisos = c.comparar(gravada(), viva, ["dados[].opc"])
    assert falhas == [] and any("opcional" in a for a in avisos)


def test_comparar_resposta_vazia_nao_e_falha():
    falhas, avisos = c.comparar(gravada(), c.forma({"dados": []}), ["dados[].id"])
    assert falhas == [] and any("sem itens" in a for a in avisos)


def test_comparar_campo_usado_que_nunca_apareceu_so_avisa():
    falhas, avisos = c.comparar(gravada(), gravada(), ["dados[].nunca"])
    assert falhas == [] and any("não aparecia" in a for a in avisos)


def test_comparar_campos_novos_sao_avisos():
    viva = c.forma({"dados": [{"id": 1, "nome": "a", "novo": 1}]})
    falhas, avisos = c.comparar(gravada(), viva, ["dados[].id"])
    assert falhas == [] and any("campos novos: dados[].novo" in a for a in avisos)


def test_comparar_colunas():
    falhas, avisos = c.comparar_colunas(["A", "B"], ["A", "C"], ["A", "B"], ["A", "X"])
    assert falhas == ["coluna B sumiu do CSV"]
    assert any("X" in a for a in avisos) and any("colunas novas: C" in a for a in avisos)


def test_descontinuacao_avisa():
    resp = {"Metadados": {"Descontinuacao": {"DataDesativacaoCompleta": "2026-02-01", "UrlServicoSubstituto": "https://x/novo"}}}
    assert "2026-02-01" in c.descontinuacao(resp)[0] and "https://x/novo" in c.descontinuacao(resp)[0]
    assert c.descontinuacao({"Metadados": {"Descontinuacao": {"DataDesativacaoCompleta": None}}}) == []


def test_verificar_sai_com_1_quando_campo_usado_sumiu(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(c, "FIXTURES", tmp_path)
    e = c.Endpoint("falso", "http://x", lambda ctx: {"dados": [{"id": 1}]}, ["dados[].id", "dados[].nome"])
    antes = {"fonte": "x", "forma": c.forma({"dados": [{"id": 1, "nome": "a"}]})}
    (tmp_path / "falso.json").write_text(json.dumps(antes))
    monkeypatch.setattr(c, "ENDPOINTS", [e])
    assert c.verificar([]) == 1
    assert "❌" in capsys.readouterr().out


def test_verificar_fonte_fora_do_ar_nao_e_falha(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(c, "FIXTURES", tmp_path)
    monkeypatch.setattr(c, "ENDPOINTS", [c.Endpoint("falso", "http://x", lambda ctx: (_ for _ in ()).throw(ConnectionError("fora")), ["a"])])
    assert c.verificar([]) == 0
    assert "⚠️" in capsys.readouterr().out


def test_verificar_ok_e_resumo_em_arquivo(monkeypatch, tmp_path):
    monkeypatch.setattr(c, "FIXTURES", tmp_path)
    monkeypatch.setenv("RESUMO_ARQUIVO", str(tmp_path / "r.md"))
    e = c.Endpoint("falso", "http://x", lambda ctx: {"a": 1}, ["a"])
    (tmp_path / "falso.json").write_text(json.dumps({"forma": c.forma({"a": 2})}))
    monkeypatch.setattr(c, "ENDPOINTS", [e])
    assert c.verificar([]) == 0
    assert "✅ **falso**" in (tmp_path / "r.md").read_text(encoding="utf-8")


def test_gravar_cria_fixture(monkeypatch, tmp_path):
    monkeypatch.setattr(c, "FIXTURES", tmp_path / "f")
    monkeypatch.setattr(c, "ENDPOINTS", [c.Endpoint("falso", "http://x", lambda ctx: {"l": list(range(9))}, ["l[]"])])
    assert c.gravar([]) == 0
    reg = json.loads((tmp_path / "f" / "falso.json").read_text())
    assert reg["amostra"] == {"l": [0, 1]} and "l[]" in reg["forma"]


# ================================================================ as fixtures reais

NOMES = [e.nome for e in c.ENDPOINTS if not e.html]
SO_COM_FIXTURE = [n for n in NOMES if (FIX / f"{n}.json").exists()]


def test_ha_fixtures_gravadas():
    assert len(SO_COM_FIXTURE) >= 30


# campos que o coletor lê mas que a API real não devolve na amostra gravada: lacunas conhecidas do projeto.
# Se a API voltar a devolver o campo (ou o coletor mudar), remova a linha: o teste abaixo exige que a lista seja exata.
LACUNAS = {
    "senado_materia": {"**DescricaoSituacao", "**SiglaLocal", "**DataSituacao", "**ExplicacaoEmentaMateria"},
    # só aparecem para suplentes e para exercícios já encerrados; a amostra de 2 senadores não tem
    "senado_lista": {"ListaParlamentarEmExercicio.Parlamentares.Parlamentar[].Mandato.Titular.NomeParlamentar",
                     "ListaParlamentarEmExercicio.Parlamentares.Parlamentar[].Mandato.Exercicios.Exercicio[].DataFim"},
}


@pytest.mark.parametrize("nome", SO_COM_FIXTURE)
def test_campos_que_o_coletor_usa_existem_nas_respostas_reais(nome):
    e = next(x for x in c.ENDPOINTS if x.nome == nome)
    reg = fixture(nome)
    if "colunas" in reg:
        faltam = {x for x in e.colunas_criticas if x not in reg["colunas"]}
        assert not faltam, f"colunas críticas ausentes: {faltam}"
        return
    f = reg["forma"]
    ausentes = {u for u in e.usados if not c.casa(u, f) and not c.sem_amostra(u, f)}
    assert ausentes == LACUNAS.get(nome, set()) | PRECISAM_DE_DADOS.get(nome, set()) & ausentes, f"{nome}: {ausentes}"


# respostas que podem vir vazias conforme o momento (sem despesas, sem vetos...); não é falha de contrato
PRECISAM_DE_DADOS = {
    "camara_despesas": {"dados[].mes", "dados[].tipoDespesa", "dados[].valorLiquido", "dados[].nomeFornecedor", "dados[].dataDocumento", "dados[].urlDocumento"},
}


def test_colunas_do_tse_que_o_coletor_tolera_mas_nao_vem():
    import coletar_tse
    cand = fixture("tse_consulta_cand")["colunas"]
    ausentes = [col for col in coletar_tse.COLUNAS if col not in cand]
    # ST_REELEICAO deixou de existir em 2024: o campo "reeleicao" sai sempre False (ver relatório do contrato)
    assert ausentes == ["ST_REELEICAO"]


# ---------------------------------------------------------------- Câmara com respostas reais

def test_coletar_deputado_com_resposta_real(monkeypatch, tmp_path):
    import coletar
    monkeypatch.setattr(coletar, "DADOS", tmp_path)
    monkeypatch.setattr(coletar, "coletar_proposicoes", lambda dep: [])
    det, desp = amostra("camara_deputado"), amostra("camara_despesas")
    did = det["dados"]["id"]
    monkeypatch.setattr(coletar, "get", lambda caminho, **p: det if caminho == f"/deputados/{did}" else desp)
    monkeypatch.setattr(coletar, "get_todos", lambda caminho, **p: desp["dados"])
    d = coletar.coletar_deputado({"id": did, "nome": "x"}, 2026)
    assert d["nome"] and d["partido"] and len(d["uf"]) == 2 and d["foto"].startswith("https://")
    assert d["nomeCivil"] and d["situacao"]
    assert set(d["gabinete"]) <= {"predio", "sala", "andar", "telefone", "email"}


def test_coletar_votos_com_resposta_real(monkeypatch):
    import coletar
    votos, det = amostra("camara_votos"), amostra("camara_votacao")
    monkeypatch.setattr(coletar, "get", lambda caminho, **p: votos if caminho.endswith("/votos") else det)
    v = coletar.coletar_votos({"id": "1", "data": "2026-10-14", "dataHoraRegistro": "2026-10-14T20:52:43", "siglaOrgao": "PLEN"})
    assert v["votos"] and all(isinstance(i, int) and t for i, t in v["votos"])
    assert {t for _, t in v["votos"]} <= set(__import__("gerar").VOTOS_NORMAIS) | {"Não", "Sim", "Abstenção", "Obstrução", "Artigo 17"}


def test_votos_reais_sao_classificados_pelo_gerar():
    import gerar
    for v in amostra("camara_votos")["dados"]:
        assert gerar.tipo_voto(v["tipoVoto"]) != "outro", v["tipoVoto"]


def test_detalhe_da_proposicao_real_gera_os_campos_curtos(monkeypatch, tmp_path):
    import coletar
    monkeypatch.setattr(coletar, "DADOS", tmp_path)
    prop = amostra("camara_proposicao")
    coletar.salvar(tmp_path / "proposicoes" / "1.json", {"itens": [{"id": prop["dados"]["id"], "siglaTipo": "PL"}]})
    monkeypatch.setattr(coletar, "get", lambda caminho, **p: prop)
    coletar.coletar_detalhes_proposicoes()
    info = json.loads((tmp_path / "proposicoes_detalhe.json").read_text())[str(prop["dados"]["id"])]
    # proposição recém-apresentada ainda não tem situação (descricaoSituacao nula): o coletor tem de aceitar isso
    assert info["apres"] and info["data"] and info["org"] and "sit" in info and info["fim"] is False


def test_executivo_com_respostas_reais(monkeypatch):
    import coletar_executivo as ex
    prop, tram = amostra("camara_proposicao"), amostra("camara_tramitacoes")
    monkeypatch.setattr(ex, "get", lambda caminho, **p: tram if caminho.endswith("/tramitacoes") else prop)
    d = ex.detalhar({"id": prop["dados"]["id"]})
    assert d["tipo"] and d["numero"] and d["ano"] and d["apres"] and d["data"] and "sit" in d
    assert isinstance(ex.desfecho(1), dict)


# ---------------------------------------------------------------- Senado com respostas reais

def test_votacoes_reais_do_senado_sao_normalizadas():
    import coletar
    lista = amostra("senado_votacoes")["ListaVotacoes"]["Votacoes"]["Votacao"]
    assert lista
    for bruto in lista:
        n = coletar.normalizar_votacao_senado(bruto)
        assert n, "votação nominal real descartada"
        assert n["id"] and n["data"].count("-") == 2 and n["proposicao"] and n["votos"]
        assert n["aprovada"] in (0, 1, None)
        for cod, tipo, rotulo in n["votos"]:
            assert cod.isdigit() and tipo != "outro", rotulo


def test_lista_real_de_senadores(monkeypatch, tmp_path):
    import coletar

    class R:
        ok, status_code = True, 200
        raise_for_status = lambda self: None
        json = lambda self: amostra("senado_lista")

    monkeypatch.setattr(coletar, "DADOS", tmp_path)
    monkeypatch.setattr(coletar.S, "get", lambda *a, **k: R())
    coletar.coletar_senado()
    s = json.loads((tmp_path / "senado.json").read_text())
    assert s and all(x["id"] and x["nome"] and x["partido"] and len(x["uf"]) == 2 and x["fimMandato"] for x in s)


def test_autorias_reais_do_senado(monkeypatch, tmp_path):
    import coletar
    monkeypatch.setattr(coletar, "DADOS", tmp_path)
    coletar.salvar(tmp_path / "senado.json", [{"id": "5672"}])
    monkeypatch.setattr(coletar, "get_senado", lambda caminho, **p: amostra("senado_autorias") if "autorias" in caminho else amostra("senado_materia"))
    coletar.coletar_autorias_senado()
    aut = json.loads((tmp_path / "senado_autorias.json").read_text())["5672"]
    assert aut and all(a["id"] and a["tipo"] and a["ano"] >= 2019 for a in aut)


def test_ceaps_real(monkeypatch, tmp_path):
    import coletar

    class R:
        ok = True
        raise_for_status = lambda self: None
        json = lambda self: amostra("senado_ceaps")

    monkeypatch.setattr(coletar, "DADOS", tmp_path)
    monkeypatch.setattr(coletar.S, "get", lambda *a, **k: R())
    coletar.coletar_ceaps_senado()
    itens = json.loads((tmp_path / "senado_ceaps.json").read_text())["itens"]
    assert itens and all(i["tipo"] and i["data"] for lista in itens.values() for i in lista)


# ---------------------------------------------------------------- SAPL e SPLegis com respostas reais

def test_materia_real_do_sapl_e_compactada():
    import coletar_estaduais as est
    tipos = {t["id"]: {"s": t["sigla"], "d": t["descricao"]} for t in amostra("sapl_tipomateria")["results"]}
    for m in amostra("sapl_materia")["results"]:
        r = est.compactar_materia(m, {**tipos, m["tipo"]: tipos.get(m["tipo"], {"s": "?", "d": "?"})})
        assert r["n"] == m["numero"] and r["a"] == m["ano"] and r["sit"] and isinstance(r["au"], list)


def test_resultados_e_votos_reais_do_sapl():
    import coletar_estaduais as est
    for r in amostra("sapl_tiporesultado")["results"]:
        assert est.resultado_aprovado(r["nome"], r["natureza"]) in (0, 1, None)
    for v in amostra("sapl_votoparlamentar")["results"]:
        assert isinstance(v["votacao"], int) and isinstance(v["parlamentar"], int) and v["voto"]
    r = amostra("sapl_registrovotacao")
    assert est.data_curta(r["data_hora"]) and isinstance(r["numero_votos_sim"], int)


def test_autor_do_prefeito_ou_governador_no_sapl_real():
    amostra_autor = amostra("sapl_autor")["results"]
    assert all({"id", "tipo", "object_id", "nome"} <= a.keys() for a in amostra_autor)


def test_promovente_do_prefeito_de_sp_com_resposta_real(monkeypatch):
    import coletar_prefeitura_sp as sp
    monkeypatch.setattr(sp, "ws", lambda op, **p: amostra("splegis_promoventes"))
    assert isinstance(sp.promovente_id(), int)


def test_projetos_e_resumo_reais_de_sp(monkeypatch):
    import coletar_prefeitura_sp as sp
    projetos = amostra("splegis_projetos")
    assert all(sp.chave(p) and p["data"][:10] and p["ementa"] for p in projetos)
    monkeypatch.setattr(sp, "ws", lambda op, **p: amostra("splegis_resumo"))
    autores = amostra("splegis_resumo")["Autores"]
    assert sp.e_do_prefeito("PL", 1, 2026, autores[0]["Chave"]) is True
    assert sp.e_do_prefeito("PL", 1, 2026, -1) is False
