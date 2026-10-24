"""Scripts do TSE que cruzam vários arquivos: prestação de contas, votos por seção e o mapa município TSE -> IBGE."""
import json

import pytest

import coletar_contas
import coletar_secoes
import gerar_municipios_ibge
from tse_zip import zip_csv


def ler(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


def gravar(caminho, obj):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj), encoding="utf-8")


# ================================================================ contas

def test_valor_e_nulo():
    assert coletar_contas.valor("1.234,56") == 1234.56 and coletar_contas.valor("") == 0.0 and coletar_contas.valor("x") == 0.0
    assert coletar_contas.nulo("#NULO#") is None and coletar_contas.nulo("-1") is None and coletar_contas.nulo(" Ana ") == "Ana"


def monta_contas(tmp_path, monkeypatch):
    monkeypatch.setattr(coletar_contas, "TSE", tmp_path / "tse")
    monkeypatch.setattr(coletar_contas, "ZIPS", tmp_path / "zips")
    gravar(tmp_path / "tse" / "2024" / "SP.json", [
        {"uf": "SP", "sequencial": "10", "cargo": "PREFEITO"},
        {"uf": "SP", "sequencial": "11", "sequencialChapa": "10", "cargo": "VICE-PREFEITO"},   # vice usa a prestação do titular
        {"uf": "SP", "sequencial": "20", "cargo": "VEREADOR"}])

    def rec(sq, sq_rec, valor, origem, doador="", cpf="#NULO", rfb="#NULO"):
        return {"SQ_CANDIDATO": sq, "SQ_RECEITA": sq_rec, "VR_RECEITA": valor, "DS_ORIGEM_RECEITA": origem,
                "NM_DOADOR": doador, "NM_DOADOR_RFB": rfb, "NR_CPF_CNPJ_DOADOR": cpf}
    receitas = [rec("10", "r1", "1.000,00", "Recursos de partido político", "Partido A", "111"),
                rec("10", "r2", "300,00", "Recursos de pessoas físicas", "Maria", "222"),
                rec("10", "r3", "200,00", "Recursos de pessoas físicas", "Maria", "222"),
                rec("10", "r6", "40,00", "Recursos de pessoas jurídicas", "TIM S A", "02.421.421/0001-11"),
                rec("10", "r4", "50,00", "Recursos próprios", "Ele mesmo", "333"),
                rec("99", "r5", "5,00", "Recursos de pessoas físicas", "Fora da lista", "444")]
    zip_csv(tmp_path / "zips" / "prestacao_de_contas_eleitorais_candidatos_2024.zip", {
        "receitas_candidatos_2024_BRASIL.csv": receitas,
        "receitas_candidatos_doador_originario_2024_BRASIL.csv": [
            {"SQ_RECEITA": "r1", "NM_DOADOR_ORIGINARIO": "Empresa X", "NM_DOADOR_ORIGINARIO_RFB": "#NULO", "NR_CPF_CNPJ_DOADOR_ORIGINARIO": "555", "VR_RECEITA": "700,00"},
            {"SQ_RECEITA": "r2", "NM_DOADOR_ORIGINARIO": "Não é repasse", "NM_DOADOR_ORIGINARIO_RFB": "#NULO", "NR_CPF_CNPJ_DOADOR_ORIGINARIO": "666", "VR_RECEITA": "1,00"}],
        "despesas_contratadas_candidatos_2024_BRASIL.csv": [
            {"SQ_CANDIDATO": "10", "SQ_DESPESA": "d1", "VR_DESPESA_CONTRATADA": "400,00", "DS_ORIGEM_DESPESA": "Publicidade"},
            {"SQ_CANDIDATO": "10", "SQ_DESPESA": "d2", "VR_DESPESA_CONTRATADA": "100,00", "DS_ORIGEM_DESPESA": "#NULO"},
            {"SQ_CANDIDATO": "99", "SQ_DESPESA": "d3", "VR_DESPESA_CONTRATADA": "9,00", "DS_ORIGEM_DESPESA": "Outra"}],
        "despesas_pagas_candidatos_2024_BRASIL.csv": [
            {"SQ_DESPESA": "d1", "VR_PAGTO_DESPESA": "250,00"}, {"SQ_DESPESA": "d3", "VR_PAGTO_DESPESA": "9,00"}]})


def test_contas_resume_receitas_doadores_originarios_e_despesas(tmp_path, monkeypatch):
    monta_contas(tmp_path, monkeypatch)
    coletar_contas.coletar_ano(2024)
    sp = ler(tmp_path / "tse" / "contas" / "2024" / "SP.json")
    assert list(sp) == ["10"]   # vereador sem movimento e candidato fora da lista não aparecem
    c = sp["10"]
    assert c["receitas"] == 1590.0 and c["despesasContratadas"] == 500.0 and c["despesasPagas"] == 250.0
    assert c["origensReceita"][0] == ["Recursos de partido político", 1000.0]
    assert c["principaisDoadores"] == [["Partido A", "Recursos de partido político", 1000.0], ["Maria", "Recursos de pessoas físicas", 500.0],
                                      ["TIM S A", "Recursos de pessoas jurídicas", 40.0]]   # próprios ficam de fora; Maria soma pelo CPF
    assert c["doadoresPJ"] == [["02421421000111", "TIM S A", "Recursos de pessoas jurídicas", 40.0]]   # só quem tem CNPJ válido; CPF e documento inválido não entram
    assert c["originariosPJ"] == []
    assert c["doadoresOriginarios"] == [["Empresa X", 700.0]]   # só o que veio por repasse de partido
    assert c["gastosPorCategoria"] == [["Publicidade", 400.0], ["Não informada", 100.0]]
    assert ler(tmp_path / "tse" / "contas" / "2024" / "_coleta.json")["prestacoes"] == 1


def test_contas_sem_zip_orienta_o_download(tmp_path, monkeypatch):
    monkeypatch.setattr(coletar_contas, "TSE", tmp_path / "tse")
    monkeypatch.setattr(coletar_contas, "ZIPS", tmp_path / "zips")
    (tmp_path / "tse" / "2024").mkdir(parents=True)
    with pytest.raises(SystemExit) as e:
        coletar_contas.coletar_ano(2024)
    assert "baixar_tse.py prestacao_contas" in str(e.value)


# ================================================================ seções

def test_coordenada_descarta_zero_e_menos_um():
    c = coletar_secoes.coordenada
    assert c("-23.55052") == -23.5505 and c("0") is None and c("-1") is None and c("abc") is None


def test_secoes_votos_por_local_municipio_e_ultimo_turno(tmp_path, monkeypatch):
    monkeypatch.setattr(coletar_secoes, "TSE", tmp_path / "tse")
    monkeypatch.setattr(coletar_secoes, "BRUTO", tmp_path / "bruto")
    gravar(tmp_path / "tse" / "2022" / "SP.json", [
        {"uf": "SP", "sequencial": "1", "cargo": "GOVERNADOR"}, {"uf": "SP", "sequencial": "2", "sequencialChapa": "1", "cargo": "VICE-GOVERNADOR"},
        {"uf": "SP", "sequencial": "3", "cargo": "PRESIDENTE"}])
    zip_csv(tmp_path / "bruto" / "eleitorado_locais_votacao" / "eleitorado_local_votacao_2022.zip", {
        "eleitorado_local_votacao_2022.csv": [
            {"SG_UF": "SP", "CD_MUNICIPIO": 1, "NR_ZONA": 1, "NR_LOCAL_VOTACAO": 10, "NR_LATITUDE": "-23.5", "NR_LONGITUDE": "-46.6"},
            {"SG_UF": "SP", "CD_MUNICIPIO": 1, "NR_ZONA": 1, "NR_LOCAL_VOTACAO": 11, "NR_LATITUDE": "-1", "NR_LONGITUDE": "-1"}]})

    def v(sq, turno, mun, nm, local, nl, votos):
        return {"SQ_CANDIDATO": sq, "NR_TURNO": turno, "QT_VOTOS": votos, "SG_UF": "SP", "CD_MUNICIPIO": mun, "NM_MUNICIPIO": nm,
                "NR_ZONA": 1, "NR_LOCAL_VOTACAO": local, "NM_LOCAL_VOTACAO": nl}
    zip_csv(tmp_path / "bruto" / "votacao_secao" / "votacao_secao_2022_SP.zip", {"votacao_secao_2022_SP.csv": [
        v("1", 1, 1, "Santos", 10, "Escola A", 100), v("1", 1, 2, "Campinas", 20, "Escola C", 999),   # 1º turno: descartado, há 2º
        v("1", 2, 1, "Santos", 10, "Escola A", 60), v("1", 2, 1, "Santos", 11, "Escola B", 40), v("1", 2, 2, "Campinas", 20, "Escola C", 30),
        v("3", 1, 1, "Santos", 10, "Escola A", 7), v("77", 1, 1, "Santos", 10, "Escola A", 5)]})
    coletar_secoes.coletar_ano(2022)
    sp = ler(tmp_path / "tse" / "secoes" / "2022" / "SP.json")
    assert set(sp) == {"1", "3"}   # o vice entra pela chapa do titular; 77 não é eleito
    g = sp["1"]
    assert g["turno"] == 2 and g["totalVotos"] == 130
    assert g["locaisDeVotacao"] == [["Escola A", -23.5, -46.6, 60], ["Escola B", None, None, 40], ["Escola C", None, None, 30]]
    assert g["municipios"] == [["Santos", 100], ["Campinas", 30]]
    assert g["votosPorMunicipio"] == [[1, 100], [2, 30]]
    p = sp["3"]
    assert p["totalVotos"] == 7 and "locaisDeVotacao" not in p and p["municipios"] == [["Santos", 7]] and "votosPorMunicipio" not in p


# ================================================================ município TSE -> IBGE

def test_chave_ignora_acento_caixa_e_pontuacao():
    assert gerar_municipios_ibge.chave("São Luís do Paraitinga") == "sao luis do paraitinga"
    assert gerar_municipios_ibge.chave("Alvorada D'Oeste") == "alvorada d oeste"


def test_municipios_tse_le_utf8_ou_latin1_e_ignora_exterior(tmp_path, monkeypatch):
    monkeypatch.setattr(gerar_municipios_ibge, "ZIPS", tmp_path)
    monkeypatch.setattr(gerar_municipios_ibge, "ANOS", [2024, 2022])
    zip_csv(tmp_path / "detalhe_votacao_munzona_2024.zip", {
        "detalhe_votacao_munzona_2024_SP.csv": [{"SG_UF": "SP", "NM_MUNICIPIO": "SÃO PAULO", "CD_MUNICIPIO": "71072"},
                                                {"SG_UF": "SP", "NM_MUNICIPIO": "SÃO PAULO", "CD_MUNICIPIO": "71072"}],
        "detalhe_votacao_munzona_2024_BRASIL.csv": [{"SG_UF": "SP", "NM_MUNICIPIO": "X", "CD_MUNICIPIO": "1"}],
        "detalhe_votacao_munzona_2024_ZZ.csv": [{"SG_UF": "ZZ", "NM_MUNICIPIO": "Y", "CD_MUNICIPIO": "2"}]})
    zip_csv(tmp_path / "detalhe_votacao_munzona_2022.zip", {
        "detalhe_votacao_munzona_2022_DF.csv": [{"SG_UF": "DF", "NM_MUNICIPIO": "BRASÍLIA", "CD_MUNICIPIO": "97012"}]})
    assert gerar_municipios_ibge.municipios_tse() == {("SP", "SÃO PAULO"): "71072", ("DF", "BRASÍLIA"): "97012"}


def test_municipios_tse_sem_zip_orienta_o_download(tmp_path, monkeypatch):
    monkeypatch.setattr(gerar_municipios_ibge, "ZIPS", tmp_path)
    with pytest.raises(SystemExit) as e:
        gerar_municipios_ibge.municipios_tse()
    assert "baixar_tse.py detalhe_votacao_munzona" in str(e.value)


def test_main_liga_por_nome_usa_ajustes_e_so_grava_com_flag(tmp_path, monkeypatch, capsys):
    destino = tmp_path / "municipios_ibge.json"
    gravar(destino, {"71072": "3550308", "99999": "1"})
    monkeypatch.setattr(gerar_municipios_ibge, "DESTINO", destino)
    monkeypatch.setattr(gerar_municipios_ibge, "municipios_tse", lambda: {
        ("SP", "SÃO PAULO"): "71072", ("PR", "Munhoz de Mello"): "70001", ("MG", "Inexistente"): "5"})

    ibge = [{"id": 3550308, "nome": "São Paulo", "microrregiao": {"mesorregiao": {"UF": {"sigla": "SP"}}}},
            {"id": 4115309, "nome": "Munhoz de Melo", "microrregiao": None,
             "regiao-imediata": {"regiao-intermediaria": {"UF": {"sigla": "PR"}}}}]

    class Resp:
        def __enter__(s): return s
        def __exit__(s, *a): return False
        def read(s): return json.dumps(ibge).encode()
    monkeypatch.setattr(gerar_municipios_ibge.urllib.request, "urlopen", lambda *a, **k: Resp())
    monkeypatch.setattr("sys.argv", ["gerar_municipios_ibge"])
    gerar_municipios_ibge.main()
    out = capsys.readouterr().out
    assert "sem par no IBGE: MG Inexistente" in out and "só no antigo: 99999" in out and "só no novo: 70001" in out
    assert ler(destino) == {"71072": "3550308", "99999": "1"}   # sem --gravar não mexe no arquivo
    monkeypatch.setattr("sys.argv", ["gerar_municipios_ibge", "--gravar"])
    gerar_municipios_ibge.main()
    assert ler(destino) == {"70001": "4115309", "71072": "3550308"}
