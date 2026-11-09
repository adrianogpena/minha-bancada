import json
from datetime import date

import pytest

import coletar_estadual_pe as pe
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

LISTA = [
    {"id": "4508", "nome": "Abimael Santos", "partido": "PL", "email": "abimael.santos@alepe.pe.gov.br", "foto": ""},
    {"id": "4496", "nome": "João Paulo", "partido": "PT", "email": "joao.paulo@alepe.pe.gov.br", "foto": "/imagens/deputados/joaopaulo.jpg"},
    {"id": "4497", "nome": "João Paulo Costa", "partido": "PC Do B", "email": None, "foto": ""},
    {"id": "4514", "nome": "Gilmar Junior", "partido": "PV", "email": "gilmar.junior@alepe.pe.gov.br", "foto": ""},
    {"id": "5", "nome": "Adelmo Duarte", "partido": "DEM", "email": None, "foto": ""},
]
PARLAMENTARES = [
    {"nomeParlamentar": "Abimael Santos", "partido": "PL"},
    {"nomeParlamentar": "João Paulo do PT", "partido": "PT"},
    {"nomeParlamentar": "Gilmar Júnior", "partido": "PV"},
    {"nomeParlamentar": "Cayo Albino", "partido": "PSB"},
]


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_montar_deputados_so_em_exercicio_e_sem_id_para_quem_nao_esta_na_lista():
    deputados = pe.montar_deputados(LISTA, PARLAMENTARES)
    assert [d["id"] for d in deputados] == ["4508", "4496", "4514", "sem-cayo-albino"]
    joao = deputados[1]
    assert joao["nome"] == "João Paulo do PT" and joao["foto"] == "https://www.alepe.pe.gov.br/imagens/deputados/joaopaulo.jpg"
    assert deputados[0]["foto"] is None and deputados[0]["email"] == "abimael.santos@alepe.pe.gov.br"
    assert deputados[3]["fonte"] == pe.PARLAMENTARES_URL


def test_ligar_tira_o_partido_do_nome_do_autor():
    deputados = pe.montar_deputados(LISTA, PARLAMENTARES)
    ligados = pe.ligar(["João Paulo do PT", "João Paulo Costa", "Fulano do PT"], deputados)
    assert ligados == {"João Paulo do PT": "4496"}


def test_deputados_do_contrato():
    assert pe._conferir_deputados(amostra("estadual_pe_deputados")) == ([], [])


def test_itens_verba_com_fornecedor_e_tipo():
    lancamento = {"docid": "7561", "numero": "77", "tipo": "P", "total": "44880"}
    notas = [{"rubrica": 3, "data": "30/01/2026", "cnpj": "47006999000140", "empresa": "Alysson Advocacia", "valor": "21880"}]
    itens = pe.itens_verba(lancamento, notas, "4508", 2026, 1, {3: "ASSESSORIA JURÍDICA"})
    assert itens == [{"idDeputado": "4508", "mes": 1, "categoria": "ASSESSORIA JURÍDICA", "fornecedor": "Alysson Advocacia", "cnpj": "47006999000140",
                      "valor": 21880.0, "data": "2026-01-30", "tipo": "Pedido", "numero": "77", "docid": "7561", "fonte": pe.VERBA_PAGINA}]


def test_itens_verba_sem_notas_usa_o_total():
    itens = pe.itens_verba({"docid": "1", "numero": "2", "tipo": "C", "total": "15000"}, [], "4508", 2026, 1, {})
    assert itens[0]["valor"] == 15000.0 and itens[0]["tipo"] == "Complemento" and itens[0]["fornecedor"] is None


def test_verba_do_contrato():
    a = amostra("estadual_pe_verba")
    assert pe._conferir_verba(a) == ([], [])
    linha, n = a["lancamentos"][0], a["notas"]
    itens = pe.itens_verba(linha, n, "4508", a["ano"], 1, {r["numero_categoria"]: r["nome_categoria"] for r in a["rubricas"]})
    assert itens[0]["categoria"] == "ASSESSORIA JURÍDICA" and itens[0]["data"] == "2025-01-31" and itens[0]["cnpj"] == "47006999000140"


def test_proposicoes_do_contrato():
    for tipo in pe.TIPOS_PROPOSICAO:
        a = amostra(f"estadual_pe_{tipo}")
        assert pe._conferir_proposicoes(tipo)(a) == ([], [])


def test_materias_liga_autor_e_corta_ementa():
    xml = ("<projetos><projeto docid='16370' numero='33' ano='2026' tipo='PROPOSTA DE EMENDA A CONSTITUIÇÃO' subtipo='' "
           "ementa='&lt;p&gt;Altera &amp;aacute; Constituição.&lt;/p&gt;' dataPublicacao='31/03/2026'>"
           "<autores><autor nome='João Paulo do PT' tipo='DEPUTADO'/><autor nome='Comissão' tipo='COMISSAO'/></autores></projeto>"
           "<projeto docid='1' numero='1' ano='2026' tipo='X' subtipo='' ementa='a' dataPublicacao='01/01/2026'><autores><autor nome='Outro' tipo='DEPUTADO'/></autores></projeto>"
           "</projetos>")
    props = pe.parse_proposicoes(xml.encode("utf-8"), "projetos")
    assert props[0]["ementa"] == "Altera á Constituição." and props[0]["autores"] == ["João Paulo do PT"]
    achadas = pe.materias(props, {"João Paulo do PT": "4496"}, "projetos")
    assert list(achadas) == ["projetos-16370"]
    m = achadas["projetos-16370"]
    assert m["idsDeputados"] == ["4496"] and m["dataApresentacao"] == "2026-03-31" and m["numero"] == 33 and m["tipo"] == "PROJ"
    assert m["fonte"] == pe.PROPOSICOES_PAGINA
    longa = [{**props[0], "ementa": "palavra " * 100}]
    assert pe.materias(longa, {"João Paulo do PT": "4496"}, "projetos")["projetos-16370"]["ementa"].endswith("...")


def test_portal_fora_do_ar_usa_lista_anterior_e_pula_verba(monkeypatch, tmp_path):
    monkeypatch.setattr(pe.comum, "DADOS", tmp_path)
    pe.comum.salvar(tmp_path / "PE" / "deputados.json", {"deputados": [{"id": "4508", "nome": "Fulano"}]})

    def fora(*a, **k):
        raise pe.requests.ConnectionError("sem conexão")

    monkeypatch.setattr(pe, "get_json_utf8", fora)
    monkeypatch.setattr(pe, "verba_do_ano", lambda *a: pytest.fail("verba com o portal fora do ar"))
    anos = []
    monkeypatch.setattr(pe, "proposicoes_do_ano", lambda s, ano, tipo: anos.append(ano) or [])
    pe.coletar()
    assert set(anos) == set(range(pe.PRIMEIRO_ANO, pe.date.today().year + 1))


class RespostaPE:
    def __init__(self, conteudo, erro=None):
        self.content, self._erro = conteudo, erro

    def raise_for_status(self):
        if self._erro:
            raise self._erro


class SessaoPE:
    def __init__(self, conteudo, erro=None):
        self.conteudo, self.erro, self.pedidos = conteudo, erro, []

    def get(self, url, params=None, timeout=None):
        self.pedidos.append((url, params, timeout))
        return RespostaPE(self.conteudo, self.erro)


def deputados_pe():
    return pe.montar_deputados(LISTA, PARLAMENTARES)


def test_get_json_utf8_decodifica_utf8_e_passa_parametros():
    sessao = SessaoPE(json.dumps([{"nome": "João"}], ensure_ascii=False).encode("utf-8"))
    assert pe.get_json_utf8(sessao, "https://x/api", dep="1", ano=2026) == [{"nome": "João"}]
    assert sessao.pedidos == [("https://x/api", {"dep": "1", "ano": 2026}, 60)]


def test_get_json_utf8_propaga_erro_http():
    with pytest.raises(RuntimeError, match="500"):
        pe.get_json_utf8(SessaoPE(b"[]", erro=RuntimeError("500")), "https://x/api")


def test_montar_deputados_sem_parlamentares_em_exercicio():
    assert pe.montar_deputados(LISTA, []) == []


def test_rubricas_do_ano_mapeia_numero_para_nome(monkeypatch):
    chamadas = []

    def falso(sessao, url, **params):
        chamadas.append((url, params))
        return [{"numero_categoria": 3, "nome_categoria": "ASSESSORIA JURÍDICA"}, {"numero_categoria": 5, "nome_categoria": "COMBUSTÍVEL"}]

    monkeypatch.setattr(pe, "get_json_utf8", falso)
    assert pe.rubricas_do_ano(None, 2026) == {3: "ASSESSORIA JURÍDICA", 5: "COMBUSTÍVEL"}
    assert chamadas == [(pe.RUBRICAS_URL, {"ano": 2026})]


def test_verba_do_mes_junta_notas_de_cada_lancamento(monkeypatch):
    def falso(sessao, url, **params):
        if url == pe.LANCAMENTOS_URL:
            assert params == {"dep": "4508", "ano": 2026, "mes": 1}
            return [{"docid": "10", "numero": "1", "tipo": "P", "total": "100"}, {"docid": "11", "numero": "2", "tipo": "C", "total": "50"}]
        assert url == pe.NOTAS_URL
        if params["docid"] == "10":
            return [{"rubrica": 3, "data": "15/01/2026", "cnpj": "47006999000140", "empresa": "Alysson", "valor": "100"}]
        return []

    monkeypatch.setattr(pe, "get_json_utf8", falso)
    itens = pe.verba_do_mes(None, "4508", 2026, 1, {3: "ASSESSORIA"})
    assert [(i["docid"], i["tipo"], i["categoria"], i["valor"]) for i in itens] == [("10", "Pedido", "ASSESSORIA", 100.0), ("11", "Complemento", "Sem detalhamento", 50.0)]


def test_verba_do_ano_rele_so_meses_recentes_e_ignora_deputado_sem_id(monkeypatch):
    lidos = []

    def falso(sessao, url, **params):
        if url == pe.RUBRICAS_URL:
            return [{"numero_categoria": 3, "nome_categoria": "ASSESSORIA"}]
        if url == pe.MESES_URL:
            assert params["dep"] != "sem-cayo-albino"
            return [{"mes": "1"}, {"mes": "2"}, {"mes": "3"}] if params["dep"] == "4508" else []
        if url == pe.LANCAMENTOS_URL:
            lidos.append((params["dep"], params["mes"]))
            return [{"docid": f"n{params['mes']}", "numero": "1", "tipo": "P", "total": "10"}]
        return []

    monkeypatch.setattr(pe, "get_json_utf8", falso)
    existentes = [{"idDeputado": "4508", "mes": 1, "docid": "antigo1", "data": None}, {"idDeputado": "4508", "mes": 2, "docid": "antigo2", "data": None}]
    itens = pe.verba_do_ano(None, deputados_pe(), 2026, existentes, date(2026, 3, 10))
    assert sorted(lidos) == [("4508", 2), ("4508", 3)]
    assert [(i["mes"], i["docid"]) for i in itens] == [(1, "antigo1"), (2, "n2"), (3, "n3")]


def etapas_de_coletar(monkeypatch, tmp_path, lista=None, parlamentares=None):
    monkeypatch.setattr(pe.comum, "DADOS", tmp_path)

    def falso(sessao, url, **params):
        if url == pe.DEPUTADOS_URL:
            return LISTA if lista is None else lista
        if url == pe.PARLAMENTARES_URL:
            return PARLAMENTARES if parlamentares is None else parlamentares
        return []

    monkeypatch.setattr(pe, "get_json_utf8", falso)
    monkeypatch.setattr(pe.comum, "sessao", lambda: None)


def test_coletar_lista_vazia_sem_anterior_avisa_e_nao_coleta_nada(monkeypatch, tmp_path, capsys):
    etapas_de_coletar(monkeypatch, tmp_path, lista=[], parlamentares=[])
    monkeypatch.setattr(pe, "verba_do_ano", lambda *a: pytest.fail("verba sem deputados"))
    monkeypatch.setattr(pe, "proposicoes_do_ano", lambda *a: pytest.fail("proposições sem deputados"))
    pe.coletar()
    assert "PE: lista de deputados vazia" in capsys.readouterr().err
    assert not (tmp_path / "PE").exists()


def test_coletar_grava_deputados_avisa_sem_id_e_coleta_verba_ano_a_ano(monkeypatch, tmp_path, capsys):
    etapas_de_coletar(monkeypatch, tmp_path)
    ano_atual = pe.date.today().year
    pasta = tmp_path / "PE"
    pe.comum.salvar(pasta / f"verbas_{ano_atual}.json", {"itens": [{"mes": 1, "idDeputado": "4508"}]})
    verba, props = [], []

    def falsa_verba(sessao, deputados, ano, existentes, hoje):
        verba.append((ano, existentes))
        if ano == ano_atual - 1:
            raise RuntimeError("verba quebrada")
        return [{"mes": 1, "idDeputado": "4508", "docid": str(ano)}]

    def falsas_props(sessao, ano, tipo):
        props.append((ano, tipo))
        if ano == ano_atual:
            raise RuntimeError("xml quebrado")
        return []

    monkeypatch.setattr(pe, "verba_do_ano", falsa_verba)
    monkeypatch.setattr(pe, "proposicoes_do_ano", falsas_props)
    pe.coletar()
    erros = capsys.readouterr().err
    assert "PE: sem id na lista da legislatura (sem verba): Cayo Albino" in erros
    assert f"PE: verba {ano_atual - 1}: RuntimeError: verba quebrada" in erros
    assert f"PE: proposições {ano_atual}: RuntimeError: xml quebrado" in erros
    assert [a for a, _ in verba] == list(range(pe.PRIMEIRO_ANO, ano_atual + 1))
    assert dict(verba)[ano_atual] == [{"mes": 1, "idDeputado": "4508"}]
    assert not (pasta / f"verbas_{ano_atual - 1}.json").exists()
    assert pe.comum.ler(pasta / "deputados.json")["deputados"][-1]["id"] == "sem-cayo-albino"
    assert pe.comum.ler(pasta / f"verbas_{pe.PRIMEIRO_ANO}.json")["itens"][0]["docid"] == str(pe.PRIMEIRO_ANO)
    assert (pasta / f"materias_{pe.PRIMEIRO_ANO}.json").exists() and not (pasta / f"materias_{ano_atual}.json").exists()
    assert {t for _, t in props} == set(pe.TIPOS_PROPOSICAO)


def test_coletar_pula_ano_encerrado_com_arquivo(monkeypatch, tmp_path):
    etapas_de_coletar(monkeypatch, tmp_path)
    pasta = tmp_path / "PE"
    pe.comum.salvar(pasta / f"verbas_{pe.PRIMEIRO_ANO}.json", {"itens": []})
    pe.comum.salvar(pasta / f"materias_{pe.PRIMEIRO_ANO}.json", {"materias": {}})
    anos_verba, anos_props = [], []
    monkeypatch.setattr(pe, "verba_do_ano", lambda s, d, ano, e, h: anos_verba.append(ano) or [])
    monkeypatch.setattr(pe, "proposicoes_do_ano", lambda s, ano, tipo: anos_props.append(ano) or [])
    pe.coletar()
    assert pe.PRIMEIRO_ANO not in anos_verba and pe.PRIMEIRO_ANO not in anos_props
    assert pe.PRIMEIRO_ANO + 1 in anos_verba and pe.PRIMEIRO_ANO + 1 in anos_props


def test_coletar_lista_falha_sem_conexao_usa_anterior_e_falha_inesperada_mantem_verba(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(pe.comum, "DADOS", tmp_path)
    monkeypatch.setattr(pe.comum, "sessao", lambda: None)
    pe.comum.salvar(tmp_path / "PE" / "deputados.json", {"deputados": [{"id": "4508", "nome": "Fulano"}]})

    def falha(*a, **k):
        raise ValueError("html inesperado")

    monkeypatch.setattr(pe, "get_json_utf8", falha)
    chamadas = []
    monkeypatch.setattr(pe, "verba_do_ano", lambda s, d, ano, e, h: chamadas.append(ano) or [])
    monkeypatch.setattr(pe, "proposicoes_do_ano", lambda *a: [])
    pe.coletar()
    erros = capsys.readouterr().err
    assert "PE: lista de deputados: ValueError: html inesperado" in erros and "PE: usando a lista de deputados da coleta anterior" in erros
    assert pe.PRIMEIRO_ANO in chamadas


def test_proposicoes_do_ano_pede_xml_do_tipo_e_ano():
    xml = ("<indicacoes><indicacao docid='7' numero='3' ano='2026' tipo='I' subtipo='' ementa='e' dataPublicacao='02/02/2026'>"
           "<autores><autor nome='Abimael Santos' tipo='DEPUTADO'/></autores></indicacao></indicacoes>").encode("utf-8")
    sessao = SessaoPE(xml)
    itens = pe.proposicoes_do_ano(sessao, 2026, "indicacoes")
    assert sessao.pedidos == [(f"{pe.API}/proposicoes/indicacoes/", {"formato": "json", "ano": 2026}, 120)]
    assert itens[0]["docid"] == "7" and itens[0]["autores"] == ["Abimael Santos"] and itens[0]["data"] == "2026-02-02"


def test_proposicoes_do_ano_propaga_erro_http():
    with pytest.raises(RuntimeError, match="404"):
        pe.proposicoes_do_ano(SessaoPE(b"", erro=RuntimeError("404")), 2026, "projetos")


def test_parse_proposicoes_xml_sem_itens():
    assert pe.parse_proposicoes(b"<projetos></projetos>", "projetos") == []


def test_coletar_proposicoes_liga_autores_e_grava_o_ano(monkeypatch, tmp_path):
    projeto = {"docid": "1", "numero": "5", "ano": "2026", "tipo": "PL", "subtipo": "", "ementa": "ementa", "data": "2026-01-02", "autores": ["Abimael Santos"]}
    monkeypatch.setattr(pe, "proposicoes_do_ano", lambda s, ano, tipo: [projeto] if tipo == "projetos" else [])
    pe.coletar_proposicoes(None, deputados_pe(), 2026, tmp_path, "2026-11-03")
    arq = pe.comum.ler(tmp_path / "materias_2026.json")
    assert arq["coletadoEm"] == "2026-11-03" and arq["fonte"] == pe.PROPOSICOES_PAGINA
    assert list(arq["materias"]) == ["projetos-1"] and arq["materias"]["projetos-1"]["idsDeputados"] == ["4508"]


LINHAS_SERVIDORES = [
    {"NOME_LOTACAO": "GAB.DEP. Abimael Santos", "NOME": "  Maria   Silva ", "CARGO_NIVEL": "DAS-1", "VINCULO": "Comissionado"},
    {"NOME_LOTACAO": "GAB. DEP Abimael Santos", "NOME": "Ana", "CARGO_NIVEL": None, "CARGO_EFETIVO": "Analista", "VINCULO": "Efetivo"},
    {"NOME_LOTACAO": "LIDERANCA DO PSB", "NOME": "Zé"},
    {"NOME_LOTACAO": None, "NOME": "Sem lotação"},
    {"NOME_LOTACAO": "GAB.DEP. Abimael Santos", "NOME": None},
    {"NOME_LOTACAO": "GAB.DEP. Desconhecido Fulano", "NOME": "Beto"},
]


def test_servidores_do_gabinete_so_lotacao_ligada_a_deputado():
    itens = pe.servidores_do_gabinete(LINHAS_SERVIDORES, deputados_pe())
    assert itens == [{"idDeputado": "4508", "nome": "Ana", "simbolo": "Analista", "vinculo": "Efetivo"},
                     {"idDeputado": "4508", "nome": "Maria Silva", "simbolo": "DAS-1", "vinculo": "Comissionado"}]


def test_inteiro_converte_texto_decimal():
    assert pe.inteiro("18.00") == "18" and pe.inteiro(7) == "7"
    assert pe.inteiro(None) is None and pe.inteiro("abc") is None and pe.inteiro("") is None


def linha_contrato(**extra):
    base = {"ano": "2024.00", "cpfCnpj": "47006999000140", "numeroLicitacao": "12.00", "anoLicitacao": "2023.00",
            "vigenciaInicio": {"date": "2024-02-01 00:00:00.000000"}, "vigenciaFim": {"date": "2025-02-01 00:00:00.000000"},
            "contratada": "Empresa  X", "valor": "1000,50", "objeto": "Obj", "modalidade": "Pregão"}
    return {**base, **extra}


def test_contratos_por_ano_agrupa_filtra_anos_antigos_e_monta_licitacao():
    linhas = [linha_contrato(), linha_contrato(numeroLicitacao=None, anoLicitacao=None), linha_contrato(ano="2020.00"), linha_contrato(ano=None)]
    por_ano = pe.contratos_por_ano(linhas)
    assert list(por_ano) == [2024] and len(por_ano[2024]) == 2
    itens = list(por_ano[2024].values())
    com, sem = (itens[0], itens[1]) if itens[0]["licitacao"] else (itens[1], itens[0])
    assert com["licitacao"] == "12/2023" and sem["licitacao"] is None
    assert com["tipo"] == "contrato" and com["cnpj"] == "47006999000140" and com["fornecedor"] == "Empresa X"
    assert com["inicio"] == "2024-02-01" and com["fim"] == "2025-02-01" and com["valor"] == 1000.5 and com["fonte"] == pe.CONTRATOS_PAGINA


def test_contratos_por_ano_mesma_chave_nao_duplica():
    assert len(pe.contratos_por_ano([linha_contrato(), linha_contrato()])[2024]) == 1


def test_coletar_gabinete_grava_servidores_ligados(monkeypatch, tmp_path):
    monkeypatch.setattr(pe, "get_json_utf8", lambda s, url, **p: LINHAS_SERVIDORES)
    pe.coletar_gabinete(None, deputados_pe(), tmp_path, "2026-11-03")
    arq = pe.comum.ler(tmp_path / "gabinete.json")
    assert arq["coletadoEm"] == "2026-11-03" and arq["fonte"] == pe.SERVIDORES_PAGINA and len(arq["itens"]) == 2


def test_coletar_gabinete_sem_servidor_ligado_levanta_e_mantem_arquivo(monkeypatch, tmp_path):
    monkeypatch.setattr(pe, "get_json_utf8", lambda s, url, **p: [{"NOME_LOTACAO": "LIDERANCA", "NOME": "Zé"}])
    with pytest.raises(RuntimeError, match="nenhum servidor"):
        pe.coletar_gabinete(None, deputados_pe(), tmp_path, "2026-11-03")
    assert not (tmp_path / "gabinete.json").exists()


def test_coletar_orgao_grava_um_arquivo_por_ano(monkeypatch, tmp_path):
    monkeypatch.setattr(pe, "get_json_utf8", lambda s, url, **p: [linha_contrato(), linha_contrato(ano="2025.00")])
    pe.coletar_orgao(None, tmp_path, "2026-11-03")
    assert len(pe.comum.ler(tmp_path / "orgao_2024.json")["itens"]) == 1 and (tmp_path / "orgao_2025.json").exists()
    assert pe.comum.ler(tmp_path / "orgao_2024.json")["fonte"] == pe.CONTRATOS_PAGINA


def test_coletar_orgao_lista_vazia_levanta_e_mantem_arquivos(monkeypatch, tmp_path):
    monkeypatch.setattr(pe, "get_json_utf8", lambda s, url, **p: [linha_contrato(ano="2020.00")])
    with pytest.raises(RuntimeError, match="lista vazia"):
        pe.coletar_orgao(None, tmp_path, "2026-11-03")
    assert list(tmp_path.iterdir()) == []


def test_conferir_deputados_com_campos_faltando_ou_lista_vazia():
    falhas, _ = pe._conferir_deputados({"lista": [{"id": "1"}], "parlamentares": [{"nomeParlamentar": "A", "partido": ""}]})
    assert "deputados.php sem nome" in falhas and "deputados.php sem email" in falhas and "parlamentares sem partido" in falhas
    assert pe._conferir_deputados({"lista": [], "parlamentares": []}) == (["lista vazia"], [])


def test_conferir_verba_com_falhas():
    registro = {"meses": [], "lancamentos": [{"docid": "1", "numero": "", "tipo": "X", "total": None}],
                "notas": [{"rubrica": None, "data": "", "cnpj": "1", "empresa": "e", "valor": "1"}],
                "rubricas": [{"numero_categoria": None, "nome_categoria": "N"}]}
    falhas, _ = pe._conferir_verba(registro)
    assert "dep-meses sem mes" in falhas and "lançamento sem numero" in falhas and "lançamento sem total" in falhas
    assert "tipo de lançamento novo: X" in falhas and "nota sem rubrica" in falhas and "nota sem data" in falhas and "rubrica sem numero_categoria" in falhas
    assert "nenhum lançamento" in pe._conferir_verba({"meses": [{"mes": "1"}], "lancamentos": [], "notas": [], "rubricas": []})[0]


def test_conferir_proposicoes_sem_itens_e_sem_autor_deputado():
    assert pe._conferir_proposicoes("projetos")({"xml": "<projetos></projetos>"}) == (["nenhuma proposição"], [])
    xml = ("<projetos><projeto docid='1' numero='1' ano='2026' tipo='X' subtipo='' ementa='' dataPublicacao='01/01/2026'>"
           "<autores><autor nome='Comissão' tipo='COMISSAO'/></autores></projeto></projetos>")
    falhas, _ = pe._conferir_proposicoes("projetos")({"xml": xml})
    assert "proposição sem ementa" in falhas and "proposição sem autor deputado" in falhas
