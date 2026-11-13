import json

import pytest

import coletar_estadual_mt as mt
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

ELEITOS = [{"sequencial": "1", "urna": "Beto Dois A Um", "nome": "Alberto Machado", "partido": "PL", "email": "beto@x.com"}]


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def servidor(matricula, nome, lotacao, situacao="ATIVO", cargo="DEPUTADO ESTADUAL"):
    return {"matricula": matricula, "nome": nome, "descricaoLotacao": lotacao, "situacao": situacao, "descricaoCargo": cargo}


def test_deputados_ativos_filtra_cargo_e_situacao():
    lista = [servidor(1, "A", "x"), servidor(2, "B", "x", situacao="EXONERADO"), servidor(3, "C", "x", cargo="ASSESSOR PARLAMENTAR")]
    assert [s["matricula"] for s in mt.deputados_ativos(lista)] == [1]


def test_deputados_ativos_do_contrato():
    assert mt.deputados_ativos(amostra("estadual_mt_servidores")["content"])
    assert mt._conferir_servidores(amostra("estadual_mt_servidores")) == ([], [])


def test_nome_do_gabinete():
    assert mt.nome_do_gabinete('GAB DEP FABIO TARDIN "FABINHO"') == "Fabio Tardin Fabinho"
    assert mt.nome_do_gabinete("WILSON SANTOS") == "Wilson Santos"
    assert mt.nome_do_gabinete("GAB DEP JULIO DE CAMPOS") == "Julio de Campos"


def test_montar_deputados_usa_tse_quando_o_nome_civil_casa():
    servidores = [servidor(100176, "ALBERTO MACHADO", "GAB DEP BETO DOIS A UM"), servidor(100213, "FRANCISCO GUARNIERI DE LIMA", "GAB DEP CHICO GUARNIERI")]
    a, b = mt.montar_deputados(servidores, ELEITOS)
    assert a["nome"] == "Beto Dois A Um" and a["partido"] == "PL" and a["email"] == "beto@x.com" and a["id"] == "100176"
    assert a["nomeCivil"] == "Alberto Machado" and a["fonte"].endswith("/MT/1")
    assert b["nome"] == "Chico Guarnieri" and b["nomeCivil"] == "Francisco Guarnieri de Lima" and b["partido"] is None and b["fonte"].endswith("/servidores")


def test_itens_remuneracao_do_contrato():
    r = amostra("estadual_mt_remuneracao")
    itens = mt.itens_remuneracao({"dadosFinanceiros": r["dadosFinanceiros"]}, "7", r["ano"])
    assert itens and all(i["idDeputado"] == "7" and 1 <= i["mes"] <= 12 for i in itens)
    assert itens[0]["liquido"] == round(itens[0]["bruto"] - itens[0]["componentes"]["descontos"], 2)
    assert mt._conferir_remuneracao(r) == ([], [])


def test_itens_remuneracao_ignora_outro_ano():
    detalhe = {"dadosFinanceiros": [{"anoCompetencia": 2025, "mesCompetencia": 1, "vencimentos": 10.0, "descontos": 2.0}]}
    assert mt.itens_remuneracao(detalhe, "1", 2026) == []
    assert mt.itens_remuneracao({}, "1", 2026) == []


def test_itens_diarias_so_de_deputados():
    registros = amostra("estadual_mt_diarias")["content"]
    nome = registros[0]["nome"]
    deputados = [{"id": "9", "nome": "X", "nomeCivil": nome.title()}]
    itens = mt.itens_diarias(registros, deputados)
    assert itens and all(i["idDeputado"] == "9" for i in itens)
    primeiro = itens[0]
    assert primeiro["fonte"] == f"{mt.PORTAL}diarias" and primeiro["data"] and primeiro["valor"] is not None
    assert "\n" not in (primeiro["motivo"] or "")
    assert mt.itens_diarias(registros, [{"id": "9", "nome": "Y", "nomeCivil": "Outra Pessoa"}]) == []
    assert mt._conferir_diarias(amostra("estadual_mt_diarias")) == ([], [])


def test_coletar_grava_deputados_remuneracao_e_diarias(tmp_path, monkeypatch):
    ano = mt.date.today().year
    sv = servidor(100176, "ALBERTO MACHADO", "GAB DEP BETO DOIS A UM")
    detalhe = {"dadosFinanceiros": [{"anoCompetencia": ano, "mesCompetencia": 1, "vencimentos": 100.0, "descontos": 20.0, "salarioBase": 80.0,
                                      "outrosProventos": 20.0, "descricaoTipoFolha": "Folha Normal"}]}
    diaria = {"nome": "ALBERTO MACHADO", "dataSaida": f"{ano}-02-01", "dataRetorno": f"{ano}-02-02", "destino": "BRASILIA / DF", "valorDiarias": 500.0,
              "valorPassagem": 0.0, "quantidadeDiarias": 2.0, "motivo": "REUNIAO", "displayEmpenho": "1/2026", "valorAnulado": 0.0}

    class Resp:
        def __init__(self, dados, status=200):
            self.dados, self.status_code = dados, status

        def raise_for_status(self):
            pass

        def json(self):
            return self.dados

    class Sessao:
        def get(self, url, params=None, headers=None, timeout=None):
            if url.endswith("/servidores"):
                return Resp({"content": [sv], "last": True})
            if url.endswith("/diarias"):
                return Resp({"content": [diaria], "last": True})
            if url.endswith("/servidores/100176"):
                return Resp({}, 404) if headers["exercicio"] == "2023" else Resp(detalhe)
            raise AssertionError(url)

    arquivo = tmp_path / "MT.json"
    arquivo.write_text(json.dumps([{"cargo": "DEPUTADO ESTADUAL", "situacao": "eleito", **ELEITOS[0]}]), encoding="utf-8")
    monkeypatch.setattr(mt, "TSE_ARQUIVO", arquivo)
    monkeypatch.setattr(comum, "DADOS", tmp_path / "estaduais")
    monkeypatch.setattr(comum, "sessao", Sessao)
    mt.coletar()
    pasta = tmp_path / "estaduais" / "MT"
    deps = json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))
    assert deps["host"] is None and [d["nome"] for d in deps["deputados"]] == ["Beto Dois A Um"]
    rem = json.loads((pasta / f"remuneracao_{ano}.json").read_text(encoding="utf-8"))
    assert rem["itens"][0]["liquido"] == 80.0
    assert json.loads((pasta / "remuneracao_2023.json").read_text(encoding="utf-8"))["itens"] == []
    dia = json.loads((pasta / f"diarias_{ano}.json").read_text(encoding="utf-8"))
    assert dia["itens"][0]["idDeputado"] == "100176" and dia["itens"][0]["valor"] == 500.0


DEPUTADOS = [{"id": "1", "nome": "Dilmar Dal Bosco", "nomeCivil": "Dilmar Dal Bosco"}, {"id": "2", "nome": "Julio Campos", "nomeCivil": "Julio Campos"}]


def test_servidores_do_gabinete_so_ativos_de_deputado_ligado():
    registros = amostra("estadual_mt_gabinete")["content"]
    itens = mt.servidores_do_gabinete(registros, DEPUTADOS)
    assert [i["matricula"] for i in itens] == [50063, 50071]
    assert all(i["idDeputado"] == "1" and i["id"].startswith("srv_") for i in itens)
    assert itens[0]["nome"] == "Abiqueila Pires França" and itens[0]["simbolo"] == "AP-2"
    assert mt.servidores_do_gabinete(registros, DEPUTADOS) == itens
    assert mt._conferir_gabinete(amostra("estadual_mt_gabinete")) == ([], [])


def test_lotacao_liga_por_palavras_sem_de():
    registros = [{"matricula": 1, "nome": "ANA", "descricaoLotacao": "GAB DEP JULIO DE CAMPOS", "situacao": "ATIVO", "descricaoCargo": "X", "faixa": "AP-1"}]
    assert [i["idDeputado"] for i in mt.servidores_do_gabinete(registros, DEPUTADOS)] == ["2"]
    assert mt.servidores_do_gabinete(registros, [{"id": "3", "nome": "Outro", "nomeCivil": "Outro"}]) == []


def test_itens_contratos_separa_contrato_e_ata_com_links():
    r = amostra("estadual_mt_contratos")
    arquivos = {mt.id_fonte_contrato(r["content"][1], 2026): mt.arquivos_do_contrato(r["arquivos"], 2026)}
    itens = mt.itens_contratos(r["content"], 2026, arquivos)
    por_tipo = {i["tipo"]: i for i in itens.values()}
    ata = por_tipo["ata_registro"]
    assert set(por_tipo) == {"contrato", "ata_registro"} and all(k.startswith("ctr_") for k in itens)
    assert ata["cnpj"] == "50390402000118" or ata["cnpj"] is None
    assert ata["valor"] == 316125.0 and ata["inicio"] == "2026-07-15" and ata["fonte"] == mt.CONTRATOS_PAGINA and ata["numero"] == "202645/2026"
    assert ata["arquivos"][0]["url"].endswith("/files/arquivo/93826?entidade=1&exercicio=2026") and ata["arquivos"][0]["data"] == "2026-07-20"
    assert por_tipo["contrato"]["arquivos"] == []
    assert mt._conferir_contratos(r) == ([], [])


class Resp:
    def __init__(self, dados):
        self.dados = dados
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self.dados


def sessao_contratos(registros, atualizacao, chamadas):
    class Sessao:
        def get(self, url, params=None, headers=None, timeout=None):
            chamadas.append(url.replace(mt.API, ""))
            if url.endswith("/contratos"):
                return Resp({"content": registros, "last": True})
            if url.endswith("/contratos/arquivos"):
                return Resp([{"idArquivo": 7, "nomeArquivo": "a.pdf", "dataPublicacao": "2026-01-02"}])
            if url.endswith("/ultimas-atualizacoes"):
                return Resp([{"modulo": "10", "ultimoAcesso": atualizacao}])
            raise AssertionError(url)
    return Sessao()


def test_contratos_incremental_e_completa_velha(tmp_path):
    hoje = mt.date(2026, 11, 2)
    registros = amostra("estadual_mt_contratos")["content"]
    chamadas = []
    s = sessao_contratos(registros, "t1", chamadas)
    mt.contratos_do_ano(s, tmp_path, 2026, hoje, "t1")
    arq = tmp_path / "orgao_2026.json"
    env = json.loads(arq.read_text(encoding="utf-8"))
    assert len(env["itens"]) == 2 and env["atualizacao"] == "t1" and env["completaEm"] == "2026-11-02"
    assert chamadas.count("/contratos/arquivos") == 2

    chamadas.clear()
    mt.contratos_do_ano(s, tmp_path, 2026, mt.date(2026, 11, 3), "t1")
    assert chamadas == []

    mt.contratos_do_ano(s, tmp_path, 2026, mt.date(2026, 11, 4), "t2")
    assert chamadas == ["/contratos"]
    assert json.loads(arq.read_text(encoding="utf-8"))["atualizacao"] == "t2"

    chamadas.clear()
    mt.contratos_do_ano(s, tmp_path, 2026, mt.date(2026, 11, 20), "t2")
    assert chamadas == ["/contratos"]
    assert json.loads(arq.read_text(encoding="utf-8"))["completaEm"] == "2026-11-20"


def test_contratos_ano_encerrado_nao_e_lido(tmp_path):
    (tmp_path / "orgao_2023.json").write_text("{}", encoding="utf-8")
    chamadas = []
    mt.contratos_do_ano(sessao_contratos([], "t", chamadas), tmp_path, 2023, mt.date(2026, 11, 2), None)
    assert chamadas == []


def test_regras_das_diarias_resolucao_primeiro():
    r = amostra("estadual_mt_publicacoes")
    regra = mt.regras_das_diarias(r["grupos"], 2026)
    assert regra["titulo"].startswith("Resolução Administrativa") and regra["url"].endswith("/files/arquivo/92472?entidade=1&exercicio=2026")
    assert [d["titulo"] for d in regra["documentos"]][1] == "Tabela Diárias Atualizada.xlsx" and regra["fonte"] == mt.PUBLICACOES_PAGINA
    assert mt.regras_das_diarias({"outro": [{"valor": "PORTARIAS", "arquivos": [{"idArquivo": 1}]}]}, 2026) is None
    assert mt._conferir_publicacoes(r) == ([], [])


class RespHttp:
    def __init__(self, dados, status=200):
        self.dados, self.status_code = dados, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return self.dados


class SessaoFn:
    def __init__(self, fn):
        self.fn, self.chamadas = fn, []

    def get(self, url, params=None, headers=None, timeout=None):
        caminho = url.replace(mt.API, "")
        self.chamadas.append((caminho, dict(params or {}), headers))
        return self.fn(caminho, params or {})


REGISTRO_CONTRATO = {"contrato": 5, "nome": "EMPRESA ALFA", "cnpjCpf": "11222333000181", "valorContratado": 10.0, "tipoAto": 1, "inicioVigencia": "2026-01-01",
                     "terminoVigencia": "2026-12-31", "objeto": "o", "displayContrato": "5/2026"}


def test_json_404_so_e_ignorado_quando_pedido():
    s = SessaoFn(lambda caminho, params: RespHttp({"x": 1}, 404))
    assert mt._json(s, "/x", 2026, ignorar_404=True) == {}
    with pytest.raises(RuntimeError, match="404"):
        mt._json(s, "/x", 2026)
    com_erro = SessaoFn(lambda caminho, params: RespHttp(None, 500))
    with pytest.raises(RuntimeError, match="500"):
        mt._json(com_erro, "/x", 2026, ignorar_404=True)


BUSCAS = [("buscar_servidores", "/servidores"), ("buscar_diarias", "/diarias"), ("buscar_gabinete", "/servidores"), ("buscar_contratos", "/contratos")]


@pytest.mark.parametrize("funcao,caminho", BUSCAS)
def test_busca_paginada_junta_as_paginas(funcao, caminho):
    def resposta(c, params):
        assert c == caminho
        return RespHttp({"content": [{"pagina": params["page"]}], "last": params["page"] == 1})

    s = SessaoFn(resposta)
    assert getattr(mt, funcao)(s, 2026) == [{"pagina": 0}, {"pagina": 1}]
    assert s.chamadas[0][2] == mt.cabecalhos(2026)


@pytest.mark.parametrize("funcao,caminho", BUSCAS)
def test_busca_paginada_propaga_erro_e_para_em_pagina_vazia(funcao, caminho):
    with pytest.raises(RuntimeError, match="500"):
        getattr(mt, funcao)(SessaoFn(lambda c, p: RespHttp(None, 500)), 2026)
    vazia = SessaoFn(lambda c, p: RespHttp({"content": [], "last": False}))
    assert getattr(mt, funcao)(vazia, 2026) == [] and len(vazia.chamadas) == 1


def test_coletar_gabinete_grava_e_levanta_sem_servidor_ligado(tmp_path, monkeypatch):
    registros = amostra("estadual_mt_gabinete")["content"]
    monkeypatch.setattr(mt, "buscar_gabinete", lambda s, ano: registros)
    mt.coletar_gabinete(None, tmp_path, DEPUTADOS, mt.date(2026, 11, 3))
    env = json.loads((tmp_path / "gabinete.json").read_text(encoding="utf-8"))
    assert [i["matricula"] for i in env["itens"]] == [50063, 50071] and env["coletadoEm"] == "2026-11-03"
    monkeypatch.setattr(mt, "buscar_gabinete", lambda s, ano: [])
    with pytest.raises(RuntimeError, match="nenhum servidor"):
        mt.coletar_gabinete(None, tmp_path / "outra", DEPUTADOS, mt.date(2026, 11, 3))
    assert not (tmp_path / "outra").exists()


def test_arquivos_do_contrato_lista_vazia_e_item_sem_id():
    assert mt.arquivos_do_contrato([], 2026) == [] and mt.arquivos_do_contrato(None, 2026) == []
    assert mt.arquivos_do_contrato([{"nomeArquivo": "x"}], 2026) == []


def test_itens_contratos_cnpj_invalido_e_registros_sem_chave():
    registros = [{**REGISTRO_CONTRATO, "cnpjCpf": "12345"}, {"contrato": None, "nome": "X"}, {"contrato": 6, "nome": " "}]
    (item,) = mt.itens_contratos(registros, 2026).values()
    assert item["cnpj"] is None and item["tipo"] == "contrato" and item["idFonte"] == "2026|5" and item["valor"] == 10.0


def test_buscar_arquivos_usa_o_tipo_do_ato_e_tolera_resposta_que_nao_e_lista():
    s = SessaoFn(lambda c, p: RespHttp([{"idArquivo": 1, "nomeArquivo": "a.pdf"}]))
    assert mt.buscar_arquivos(s, 2026, {"contrato": 7, "tipoAto": 2})[0]["url"].endswith("/files/arquivo/1?entidade=1&exercicio=2026")
    mt.buscar_arquivos(s, 2026, {"contrato": 8, "tipoAto": 1})
    assert [(c[1]["contrato"], c[1]["tipoAto"]) for c in s.chamadas] == [(7, 2), (8, 1)]
    assert mt.buscar_arquivos(SessaoFn(lambda c, p: RespHttp({})), 2026, {"contrato": 7}) == []
    with pytest.raises(RuntimeError, match="500"):
        mt.buscar_arquivos(SessaoFn(lambda c, p: RespHttp(None, 500)), 2026, {"contrato": 7})


def test_ultima_atualizacao_do_modulo_de_contratos():
    s = SessaoFn(lambda c, p: RespHttp([{"modulo": 3, "ultimoAcesso": "x"}, {"modulo": "10", "ultimoAcesso": "t1"}]))
    assert mt.ultima_atualizacao(s, 2026) == "t1" and s.chamadas[0][0] == "/contratos/ultimas-atualizacoes"
    assert mt.ultima_atualizacao(SessaoFn(lambda c, p: RespHttp([{"modulo": 3, "ultimoAcesso": "x"}])), 2026) is None
    assert mt.ultima_atualizacao(SessaoFn(lambda c, p: RespHttp({})), 2026) is None


def test_contratos_erro_nos_arquivos_vira_aviso_e_o_item_fica_sem_link(tmp_path, capsys):
    def resposta(c, params):
        return RespHttp({"content": [REGISTRO_CONTRATO], "last": True}) if c == "/contratos" else RespHttp(None, 404)

    mt.contratos_do_ano(SessaoFn(resposta), tmp_path, 2026, mt.date(2026, 11, 2), None)
    (item,) = json.loads((tmp_path / "orgao_2026.json").read_text(encoding="utf-8"))["itens"].values()
    assert item["arquivos"] == []
    assert "arquivos do contrato 2026|5" in capsys.readouterr().err


def test_contratos_prazo_esgotado_nos_arquivos_propaga_sem_gravar(tmp_path):
    def resposta(c, params):
        if c == "/contratos":
            return RespHttp({"content": [REGISTRO_CONTRATO], "last": True})
        raise comum.PrazoEsgotado("fim")

    with pytest.raises(comum.PrazoEsgotado):
        mt.contratos_do_ano(SessaoFn(resposta), tmp_path, 2026, mt.date(2026, 11, 2), None)
    assert not (tmp_path / "orgao_2026.json").exists()


def test_contratos_lista_vazia_com_arquivo_anterior_levanta(tmp_path):
    (tmp_path / "orgao_2026.json").write_text(json.dumps({"completaEm": "2026-11-01", "itens": {"x": {"idFonte": "2026|1", "arquivos": []}}}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="lista vazia"):
        mt.contratos_do_ano(SessaoFn(lambda c, p: RespHttp({"content": [], "last": True})), tmp_path, 2026, mt.date(2026, 11, 2), None)


def test_contratos_nao_busca_de_novo_os_arquivos_ja_guardados(tmp_path):
    guardado = {"completaEm": "2026-11-01", "atualizacao": "t1", "itens": {"x": {"idFonte": "2026|5", "arquivos": [{"url": "u", "nome": "n", "data": None}]}}}
    (tmp_path / "orgao_2026.json").write_text(json.dumps(guardado), encoding="utf-8")
    s = SessaoFn(lambda c, p: RespHttp({"content": [REGISTRO_CONTRATO], "last": True}))
    mt.contratos_do_ano(s, tmp_path, 2026, mt.date(2026, 11, 2), "t2")
    assert [c[0] for c in s.chamadas] == ["/contratos"]
    (item,) = json.loads((tmp_path / "orgao_2026.json").read_text(encoding="utf-8"))["itens"].values()
    assert item["arquivos"] == [{"url": "u", "nome": "n", "data": None}]


def test_coletar_contratos_passa_atualizacao_so_ao_ano_corrente_e_isola_falha(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(mt, "PRIMEIRO_ANO", 2025)
    monkeypatch.setattr(mt, "ultima_atualizacao", lambda s, ano: "t9")
    chamadas = []

    def contratos_do_ano(s, pasta, ano, hoje, atualizacao):
        chamadas.append((ano, atualizacao))
        if ano == 2025:
            raise RuntimeError("fora do ar")

    monkeypatch.setattr(mt, "contratos_do_ano", contratos_do_ano)
    mt.coletar_contratos(None, tmp_path, mt.date(2026, 11, 3))
    assert chamadas == [(2025, None), (2026, "t9")]
    assert "MT: contratos 2025: fora do ar" in capsys.readouterr().err


def test_grupos_por_nome_aninhado_e_arquivos_do_grupo():
    arvore = {"a": [{"b": {"valor": "Legislações de Diárias", "x": []}}], "valor": 5}
    assert [g["valor"] for g in mt.grupos_por_nome(arvore, mt.GRUPO_DIARIAS)] == ["Legislações de Diárias"]
    assert mt.grupos_por_nome(arvore, "inexistente") == []
    assert mt.arquivos_do_grupo({"valor": "x"}) == [] and mt.arquivos_do_grupo("texto") == [] and mt.arquivos_do_grupo([]) == []
    assert [a["idArquivo"] for a in mt.arquivos_do_grupo({"n": [{"idArquivo": 0}, {"k": {"idArquivo": 1}}]})] == [0, 1]


def test_regras_das_diarias_sem_resolucao_vale_o_mais_novo():
    arvore = [{"valor": "Legislações de Diárias", "arquivos": [{"idArquivo": 1, "nomeArquivo": "Tabela A.xlsx", "dataArquivo": "2024-01-05"},
                                                              {"idArquivo": 2, "nomeArquivo": "Tabela B.xlsx", "dataArquivo": "2025-02-01"},
                                                              {"idArquivo": 3, "nomeArquivo": "Sem data.xlsx"}]}]
    regra = mt.regras_das_diarias(arvore, 2026)
    assert regra["titulo"] == "Tabela B.xlsx" and regra["ano"] == 2025
    assert [d["ano"] for d in regra["documentos"]] == [2025, 2024, None]


def test_coletar_regras_grava_e_levanta_sem_grupo(tmp_path, monkeypatch):
    arvore = {"grupos": [{"valor": "Legislações de Diárias", "arquivos": [{"idArquivo": 1, "nomeArquivo": "Resolução 1", "dataArquivo": "2023-03-01"}]}]}
    monkeypatch.setattr(mt, "_json", lambda s, caminho, ano, **kw: arvore)
    mt.coletar_regras(None, tmp_path, mt.date(2026, 11, 3))
    env = json.loads((tmp_path / "regras_ressarcimento.json").read_text(encoding="utf-8"))
    assert env["titulo"] == "Resolução 1" and env["ano"] == 2023
    monkeypatch.setattr(mt, "_json", lambda s, caminho, ano, **kw: {})
    with pytest.raises(RuntimeError, match="não achado"):
        mt.coletar_regras(None, tmp_path / "outra", mt.date(2026, 11, 3))
    assert not (tmp_path / "outra").exists()


def test_coletar_sem_deputados_avisa_e_nao_grava(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(comum, "DADOS", tmp_path)
    monkeypatch.setattr(comum, "sessao", lambda: None)
    monkeypatch.setattr(mt, "buscar_servidores", lambda s, ano: [])
    mt.coletar()
    assert "nenhum deputado ativo" in capsys.readouterr().err
    assert not (tmp_path / "MT").exists()


def test_coletar_pula_ano_encerrado_e_avisa_etapas_que_falham(tmp_path, monkeypatch, capsys):
    pasta = tmp_path / "estaduais" / "MT"
    pasta.mkdir(parents=True)
    for nome in ("remuneracao_2023.json", "diarias_2023.json"):
        (pasta / nome).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mt, "PRIMEIRO_ANO", 2023)
    monkeypatch.setattr(comum, "DADOS", tmp_path / "estaduais")
    monkeypatch.setattr(comum, "sessao", lambda: None)
    monkeypatch.setattr(mt, "buscar_servidores", lambda s, ano: [servidor(100176, "ALBERTO MACHADO", "GAB DEP BETO")])
    monkeypatch.setattr(mt, "deputados_do_tse", lambda: [])
    monkeypatch.setattr(mt, "_json", lambda s, caminho, ano, **kw: {})
    anos = []
    monkeypatch.setattr(mt, "buscar_diarias", lambda s, ano: anos.append(ano) or [])
    chamadas = []

    def falha(*a, **k):
        raise RuntimeError("fora do ar")

    monkeypatch.setattr(mt, "coletar_gabinete", falha)
    monkeypatch.setattr(mt, "coletar_contratos", lambda *a, **k: chamadas.append("contratos"))
    monkeypatch.setattr(mt, "coletar_regras", falha)
    mt.coletar()
    assert anos == list(range(2024, mt.date.today().year + 1))
    assert (pasta / "remuneracao_2023.json").read_text(encoding="utf-8") == "{}"
    assert json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))["deputados"][0]["id"] == "100176"
    err = capsys.readouterr().err
    assert chamadas == ["contratos"] and "MT: gabinete: fora do ar" in err and "MT: regras das diárias: fora do ar" in err


def test_conferir_com_falhas():
    assert mt._conferir_gabinete({"content": []}) == (["/servidores?lotacao=GAB sem lotação de deputado"], [])
    assert "servidor de gabinete sem nome" in mt._conferir_gabinete({"content": [{"matricula": 1}]})[0]
    assert mt._conferir_contratos({"content": [], "ano": 2026, "arquivos": [], "atualizacoes": []}) == (
        ["/contratos sem contrato nem ata no ano", "/contratos sem ata de registro de preço (descricaoTipoAto)", "/contratos/arquivos sem idArquivo",
         "/contratos/ultimas-atualizacoes sem o módulo 10"], [])
    assert mt._conferir_publicacoes({"grupos": [], "ano": 2026}) == (['/publicacoes sem o grupo "Legislações de Diárias" com arquivos'], [])
    assert mt._conferir_servidores({"content": []}) == (["nenhum deputado ativo em /servidores?cargo=DEPUTADO"], [])
    assert "servidor sem nome" in mt._conferir_servidores({"content": [{"matricula": 1}]})[0]
    assert mt._conferir_remuneracao({"matricula": 1, "ano": 2026, "dadosFinanceiros": []}) == (["/servidores/{matrícula} sem dadosFinanceiros do ano"], [])
    sem_valores = {"matricula": 1, "ano": 2026, "dadosFinanceiros": [{"anoCompetencia": 2026, "mesCompetencia": 1, "vencimentos": None, "descontos": None}]}
    assert mt._conferir_remuneracao(sem_valores) == (["folha sem vencimentos ou descontos"], [])
    assert mt._conferir_diarias({"content": []}) == (["/diarias sem registros no ano"], [])
    assert "diária sem dataSaida" in mt._conferir_diarias({"content": [{"nome": "x"}]})[0]
