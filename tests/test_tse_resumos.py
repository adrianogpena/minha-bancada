"""Scripts que resumem os ZIPs do TSE (rodados à mão, fora do Actions): coligações, partidos, disputa, eleitorado e o downloader.
Os ZIPs são montados aqui, com o formato real (CSV em latin-1, separado por ";")."""
import json

import baixar_tse
import coletar_coligacoes
import coletar_disputa
import coletar_eleitorado
import coletar_partidos
from tse_zip import zip_csv


def ler(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


# ================================================================ coligações

def test_coligacoes_so_dos_partidos_eleitos_e_sem_suplentes(tmp_path, monkeypatch):
    raiz = tmp_path
    monkeypatch.setattr(coletar_coligacoes, "RAIZ", raiz)
    monkeypatch.setattr(coletar_coligacoes, "BRUTO", raiz / "bruto")
    monkeypatch.setattr(coletar_coligacoes, "SAIDA", raiz / "saida")
    (raiz / "dados" / "tse" / "2024").mkdir(parents=True)
    (raiz / "dados" / "tse" / "2024" / "SP.json").write_text(json.dumps([
        {"cargo": "PREFEITO", "unidadeEleitoral": "71072", "partido": "AAA"}]), encoding="utf-8")

    def linha(partido, tipo, nome, cargo="Prefeito", situacao="DEFERIDO", ue="71072"):
        return {"DS_CARGO": cargo, "SG_UE": ue, "SG_PARTIDO": partido, "TP_AGREMIACAO": tipo, "NM_COLIGACAO": nome,
                "DS_COMPOSICAO_COLIGACAO": "AAA / BBB", "DS_SITUACAO": situacao}
    zip_csv(raiz / "bruto" / "consulta_coligacao_2024.zip", {
        "consulta_coligacao_2024_SP.csv": [linha("AAA", "COLIGAÇÃO", "UNIÃO POR SP"), linha("BBB", "COLIGAÇÃO", "UNIÃO POR SP"),
                                           linha("AAA", "COLIGAÇÃO", "X", cargo="1º Suplente de Senador"),
                                           linha("CCC", "PARTIDO ISOLADO", "#NULO", ue="1")],
        "consulta_coligacao_2024_BRASIL.csv": [linha("AAA", "COLIGAÇÃO", "IGNORADO")]})
    coletar_coligacoes.coletar_ano(2024)
    sp = ler(raiz / "saida" / "2024" / "SP.json")
    assert list(sp) == ["PREFEITO|71072"]   # BBB não elegeu ninguém, suplente e BRASIL ficam de fora
    assert sp["PREFEITO|71072"] == {"coligacoes": [["C", "UNIÃO POR SP", "AAA / BBB", "Deferido"]], "coligacaoDoPartido": {"AAA": 0}}
    assert not (raiz / "saida" / "2024" / "BRASIL.json").exists()
    assert ler(raiz / "saida" / "2024" / "_coleta.json")["versao"] == coletar_coligacoes.VERSAO


def test_coligacoes_trata_nulo_e_tipo_desconhecido():
    assert coletar_coligacoes.limpo("#NULO") == "" and coletar_coligacoes.limpo("x") == "x"
    assert coletar_coligacoes.TIPOS["FEDERAÇÃO"] == "F"


# ================================================================ partidos

def test_partidos_soma_legenda_e_nominais_so_em_cargos_proporcionais(tmp_path, monkeypatch):
    monkeypatch.setattr(coletar_partidos, "BRUTO", tmp_path / "bruto")
    monkeypatch.setattr(coletar_partidos, "SAIDA", tmp_path / "saida")

    def linha(cargo, partido, leg, nom, fed="#NULO", ue="71072"):
        return {"DS_CARGO": cargo, "SG_UE": ue, "SG_PARTIDO": partido, "SG_FEDERACAO": fed,
                "QT_TOTAL_VOTOS_LEG_VALIDOS": leg, "QT_VOTOS_NOMINAIS_VALIDOS": nom}
    zip_csv(tmp_path / "bruto" / "votacao_partido_munzona_2024.zip", {
        "votacao_partido_munzona_2024_SP.csv": [
            linha("Vereador", "AAA", 10, 90, fed="FED"), linha("Vereador", "AAA", 5, 5, fed="FED"),   # duas zonas do mesmo partido
            linha("Vereador", "BBB", "#NULO", 40), linha("Prefeito", "AAA", 0, 999)],
        "votacao_partido_munzona_2024_BRASIL.csv": [linha("Vereador", "AAA", 1, 1)]})
    coletar_partidos.coletar_ano(2024)
    sp = ler(tmp_path / "saida" / "2024" / "SP.json")
    assert sp == {"VEREADOR|71072": {"totalVotos": 150, "partidos": {"AAA": [15, 95, "FED"], "BBB": [0, 40, ""]}}}


def test_partidos_inteiro_aceita_lixo():
    assert coletar_partidos.inteiro("12") == 12 and coletar_partidos.inteiro("#NULO") == 0 and coletar_partidos.inteiro(None) == 0


# ================================================================ disputa

def test_disputa_soma_turnos_e_junta_vagas(tmp_path, monkeypatch):
    monkeypatch.setattr(coletar_disputa, "BRUTO", tmp_path / "bruto")
    monkeypatch.setattr(coletar_disputa, "SAIDA", tmp_path / "saida")

    def detalhe(turno, aptos, comp, abst, br, nu, val, ue="71072"):
        return {"SG_UF": "SP", "DS_CARGO": "Prefeito", "SG_UE": ue, "NR_TURNO": turno, "QT_APTOS": aptos, "QT_COMPARECIMENTO": comp,
                "QT_ABSTENCOES": abst, "QT_VOTOS_BRANCOS": br, "QT_TOTAL_VOTOS_NULOS": nu, "QT_TOTAL_VOTOS_VALIDOS": val}
    zip_csv(tmp_path / "bruto" / "detalhe_votacao_munzona" / "detalhe_votacao_munzona_2024.zip", {
        "detalhe_votacao_munzona_2024_SP.csv": [detalhe(1, 100, 80, 20, 5, 5, 70), detalhe(1, 50, 40, 10, 1, 2, 37), detalhe(2, 100, 90, 10, 0, 0, 90)],
        "detalhe_votacao_munzona_2024_BRASIL.csv": [detalhe(1, 999, 999, 0, 0, 0, 999)]})
    zip_csv(tmp_path / "bruto" / "consulta_vagas" / "consulta_vagas_2024.zip", {
        "consulta_vagas_2024_SP.csv": [{"SG_UF": "SP", "DS_CARGO": "Prefeito", "SG_UE": "71072", "QT_VAGA": 1}]})
    coletar_disputa.coletar_ano(2024)
    d = ler(tmp_path / "saida" / "2024" / "SP.json")["PREFEITO|71072"]
    assert d["vagas"] == 1
    assert d["turnos"]["1"] == {"aptos": 150, "comparecimento": 120, "abstencoes": 30, "brancos": 6, "nulos": 7, "validos": 107}
    assert d["turnos"]["2"]["validos"] == 90


# ================================================================ eleitorado

def test_faixa_etaria_pelos_codigos_do_tse():
    f = coletar_eleitorado.faixa
    assert f(1500) is None                      # antes dos 16 anos
    assert (f(1617), f(1824), f(2529), f(7579), f(9999)) == (0, 1, 2, 7, 7)
    assert [f(c) for c in (1600, 1800, 2500, 3500, 4500, 5500, 6500, 7500)] == list(range(8))


def test_eleitorado_soma_por_municipio_e_total_da_uf(tmp_path, monkeypatch):
    monkeypatch.setattr(coletar_eleitorado, "BRUTO", tmp_path / "bruto")
    monkeypatch.setattr(coletar_eleitorado, "SAIDA", tmp_path / "saida")

    def linha(mun, genero, faixa, escolaridade, n):
        return {"CD_MUNICIPIO": mun, "CD_GENERO": genero, "CD_FAIXA_ETARIA": faixa, "CD_GRAU_ESCOLARIDADE": escolaridade, "QT_ELEITORES": n}
    zip_csv(tmp_path / "bruto" / "perfil_eleitorado_2024.zip", {
        "perfil_eleitorado_2024_SP.csv": [linha(1, 4, 2529, 1, 10), linha(1, 2, 7579, 8, 5), linha(2, 3, 1617, 0, 7)],
        "perfil_eleitorado_2024_BRASIL.csv": [linha(9, 4, 2529, 1, 1000)]})
    coletar_eleitorado.coletar_ano(2024)
    sp = ler(tmp_path / "saida" / "2024" / "SP.json")
    assert sp["1"]["total"] == 15 and sp["1"]["porGenero"] == [5, 10]    # [masculino, feminino]
    assert sp["1"]["porFaixaEtaria"][2] == 10 and sp["1"]["porFaixaEtaria"][7] == 5
    assert sp["1"]["porEscolaridade"][0] == 10 and sp["1"]["porEscolaridade"][7] == 5
    assert sp["2"]["porGenero"] == [0, 0] and sp["2"]["porEscolaridade"] == [0] * 8   # gênero 3 e escolaridade 0 não entram nas fatias
    assert sp["_uf"]["total"] == 22


# ================================================================ baixar_tse

class FakeSessao:
    def __init__(self, tamanhos, corpo=b"x" * 10):
        self.tamanhos, self.corpo, self.headers, self.pedidos = tamanhos, corpo, {}, []

    def head(self, url, **kw):
        self.pedidos.append(("HEAD", url))
        tam = self.tamanhos.get(url)
        return type("R", (), {"status_code": 200 if tam is not None else 404, "headers": {"Content-Length": str(tam or 0)}})()

    def get(self, url, **kw):
        self.pedidos.append(("GET", url))
        corpo = self.corpo

        class R:
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def raise_for_status(s): pass
            def iter_content(s, n): yield corpo
        return R()


def test_tamanho_remoto_404_vira_none():
    s = FakeSessao({"u": 5})
    assert baixar_tse.tamanho_remoto(s, "u") == 5 and baixar_tse.tamanho_remoto(s, "outra") is None


def test_baixar_grava_confere_tamanho_e_registra_no_changelog(tmp_path, monkeypatch):
    monkeypatch.setattr(baixar_tse, "RAIZ", tmp_path)
    monkeypatch.setattr(baixar_tse, "CHANGELOG", tmp_path / "CHANGELOG.md")
    destino = tmp_path / "dados" / "tse_bruto" / "x" / "a.zip"
    baixar_tse.baixar(FakeSessao({}), "http://cdn/a.zip", destino, 10)
    assert destino.read_bytes() == b"x" * 10 and not destino.with_suffix(".tmp").exists()
    log = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert baixar_tse.CABECALHO_TSE in log and "dados/tse_bruto/x/a.zip" in log and "http://cdn/a.zip" in log
    baixar_tse.baixar(FakeSessao({}), "http://cdn/a.zip", destino, 10)   # o cabeçalho não se repete
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8").count(baixar_tse.CABECALHO_TSE) == 1


def test_baixar_descarta_arquivo_de_tamanho_errado(tmp_path, monkeypatch):
    monkeypatch.setattr(baixar_tse, "RAIZ", tmp_path)
    monkeypatch.setattr(baixar_tse, "CHANGELOG", tmp_path / "CHANGELOG.md")
    destino = tmp_path / "a.zip"
    try:
        baixar_tse.baixar(FakeSessao({}), "http://cdn/a.zip", destino, 99)
    except IOError:
        pass
    else:
        raise AssertionError("devia falhar")
    assert not destino.exists() and not destino.with_suffix(".tmp").exists() and not (tmp_path / "CHANGELOG.md").exists()


def test_main_listar_nao_baixa_e_pula_o_que_nao_existe(tmp_path, monkeypatch, capsys):
    cdn = "http://cdn"
    monkeypatch.setattr(baixar_tse, "CDN", cdn)
    monkeypatch.setattr(baixar_tse, "DESTINO", tmp_path / "bruto")
    sessao = FakeSessao({f"{cdn}/perfil_eleitorado/perfil_eleitorado_2024.zip": 3_000_000})
    monkeypatch.setattr(baixar_tse.requests, "Session", lambda: sessao)
    monkeypatch.setattr("sys.argv", ["baixar_tse", "perfil_eleitorado", "--anos", "2022", "2024", "--listar"])
    assert baixar_tse.main() == 0
    saida = capsys.readouterr()
    assert "perfil_eleitorado_2024.zip" in saida.out and "Total: 3 MB" in saida.out
    assert "perfil_eleitorado_2022.zip: não existe" in saida.err
    assert all(metodo == "HEAD" for metodo, _ in sessao.pedidos)


def test_main_pula_o_que_ja_foi_baixado_e_usa_uma_url_por_uf(tmp_path, monkeypatch, capsys):
    cdn = "http://cdn"
    monkeypatch.setattr(baixar_tse, "CDN", cdn)
    monkeypatch.setattr(baixar_tse, "DESTINO", tmp_path / "bruto")
    monkeypatch.setattr(baixar_tse, "RAIZ", tmp_path)
    monkeypatch.setattr(baixar_tse, "CHANGELOG", tmp_path / "CHANGELOG.md")
    ja = tmp_path / "bruto" / "votacao_secao" / "votacao_secao_2024_DF.zip"
    ja.parent.mkdir(parents=True)
    ja.write_bytes(b"x" * 10)
    sessao = FakeSessao({f"{cdn}/votacao_secao/votacao_secao_2024_DF.zip": 10, f"{cdn}/votacao_secao/votacao_secao_2024_AC.zip": 10})
    monkeypatch.setattr(baixar_tse.requests, "Session", lambda: sessao)
    monkeypatch.setattr("sys.argv", ["baixar_tse", "votacao_secao", "--anos", "2024", "--ufs", "DF", "AC"])
    baixar_tse.main()
    out = capsys.readouterr().out
    assert "já baixado: votacao_secao_2024_DF.zip" in out and "Baixando" in out
    assert [u for m, u in sessao.pedidos if m == "GET"] == [f"{cdn}/votacao_secao/votacao_secao_2024_AC.zip"]


def test_main_rejeita_conjunto_desconhecido(monkeypatch):
    monkeypatch.setattr("sys.argv", ["baixar_tse", "nao_existe"])
    try:
        baixar_tse.main()
    except SystemExit as e:
        assert "conjunto desconhecido" in str(e.code)
    else:
        raise AssertionError("devia sair")
