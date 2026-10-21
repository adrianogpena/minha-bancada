"""Pipeline completo do TSE (coletar_ano) com arquivos CSV/ZIP sintéticos no formato do TSE."""
import json
import zipfile

import pytest

import coletar_tse as t

CAND = t.COLUNAS


def csv(colunas, linhas):
    def cel(v):
        return '"' + str(v).replace('"', '""') + '"'
    return "\n".join(";".join(cel(c) for c in colunas) if i == 0 else ";".join(cel(c) for c in linhas[i - 1]) for i in range(len(linhas) + 1))


def cand(sq, cargo, sit, nr, nome, ue="71072", uf="SP", turno=1, **extra):
    base = {"SQ_CANDIDATO": sq, "NR_TURNO": turno, "DS_CARGO": cargo, "DS_SIT_TOT_TURNO": sit, "SG_UF": uf, "SG_UE": ue, "NM_UE": "SÃO PAULO",
            "NR_CANDIDATO": nr, "NM_CANDIDATO": nome, "NM_URNA_CANDIDATO": nome, "SG_PARTIDO": "ABC", "DT_NASCIMENTO": "03/02/1980",
            "DS_GENERO": "FEMININO", "DS_GRAU_INSTRUCAO": "SUPERIOR COMPLETO", "DS_OCUPACAO": "ADVOGADO",
            "DS_EMAIL": "FULANO@EXEMPLO.COM", "CD_ELEICAO": "619", "SG_FEDERACAO": "#NULO#", "NM_COLIGACAO": "UNIÃO DE TODOS", "DS_EMAIL ": ""}
    base.update(extra)
    return [base.get(c, "#NULO#") for c in CAND]


def zip_de(tmp_path, nome, texto):
    caminho = tmp_path / nome
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr(nome.replace(".zip", "_BRASIL.csv"), texto.encode("latin-1"))
    return caminho


@pytest.fixture
def tse(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "DADOS", tmp_path / "tse")
    monkeypatch.setattr(t, "FOTOS", tmp_path / "fotos")
    monkeypatch.setattr(t, "AVISOS", 0)
    arquivos = {}

    def baixar(url):
        for chave, texto in arquivos.items():
            if chave in url:
                return zip_de(tmp_path, f"{chave}_{len(list(tmp_path.glob('*.zip')))}.zip", texto)
        raise RuntimeError(f"404 {url}")

    monkeypatch.setattr(t, "baixar", baixar)
    return arquivos


def candidaturas():
    return csv(CAND, [
        cand("1", "PREFEITO", "ELEITO", "10", "JOSÉ DA SILVA"),
        cand("2", "VICE-PREFEITO", "ELEITO", "10", "MARIA DE SOUZA"),
        cand("3", "PREFEITO", "NÃO ELEITO", "20", "PEDRO PERDEU"),
        cand("4", "VEREADOR", "ELEITO POR QP", "12345", "ANA DOS SANTOS", ue="71072"),
        cand("5", "VEREADOR", "SUPLENTE", "12999", "SUPLENTE UM"),
        cand("6", "VEREADOR", "NÃO ELEITO", "12888", "SEM VOTOS"),
        # 2 turnos: o último turno vale
        cand("7", "PREFEITO", "2º TURNO", "30", "CARLOS PRIMEIRO", ue="01392", uf="AC", turno=1),
        cand("7", "PREFEITO", "ELEITO", "30", "CARLOS PRIMEIRO", ue="01392", uf="AC", turno=2),
        cand("8", "PREFEITO", "NÃO ELEITO", "40", "DANIEL SEGUNDO", ue="01392", uf="AC", turno=2),
    ])


def test_coletar_ano_2024_completo(tse, tmp_path):
    tse["consulta_cand_2024"] = candidaturas()
    tse["votacao_candidato_munzona_2024"] = csv(
        ["DS_CARGO", "NR_TURNO", "SG_UE", "SQ_CANDIDATO", "QT_VOTOS_NOMINAIS_VALIDOS", "DT_ELEICAO"],
        [["Prefeito", 1, "71072", "1", "300", "06/10/2024"], ["Prefeito", 1, "71072", "1", "100", "06/10/2024"],
         ["Prefeito", 1, "71072", "3", "600", "06/10/2024"], ["Vereador", 1, "71072", "4", "50", "06/10/2024"],
         ["Prefeito", 2, "01392", "7", "1000", "27/10/2024"], ["Prefeito", 2, "01392", "8", "3000", "27/10/2024"]])
    tse["bem_candidato_2024"] = csv(["SQ_CANDIDATO", "DS_TIPO_BEM_CANDIDATO", "DS_BEM_CANDIDATO", "VR_BEM_CANDIDATO"],
                                    [["1", "CASA", "Casa na praia", "250.000,50"], ["1", "VEÍCULO", "Carro", "50.000,00"], ["6", "X", "não eleito", "1,00"]])
    tse["rede_social_candidato_2024"] = csv(["SQ_CANDIDATO", "DS_URL"],
                                            [["1", "instagram.com/jose"], ["1", "instagram.com/jose"], ["1", "@so_usuario"], ["4", "https://x.com/ana"]])
    t.coletar_ano(2024)

    por_uf = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (t.DADOS / "2024").glob("[A-Z][A-Z].json")}
    assert set(por_uf) == {"SP", "AC"}
    sp = {e["sq"]: e for e in por_uf["SP"]}
    assert set(sp) == {"1", "2", "4"}   # suplente e não eleitos ficam de fora

    prefeito = sp["1"]
    assert prefeito["nome"] == "José da Silva" and prefeito["cargo"] == "PREFEITO" and prefeito["situacao"] == "eleito"
    assert prefeito["municipio"] == "São Paulo" and prefeito["nascimento"] == "1980-02-03" and prefeito["email"] == "fulano@exemplo.com"
    assert prefeito["instrucao"] == "Superior completo" and "reeleicao" not in prefeito and prefeito["federacao"] is None
    assert prefeito["votos"] == [{"turno": 1, "data": "2024-10-06", "votos": 400, "pct": 40.0}]   # 400 de 1000 válidos
    assert prefeito["totalBens"] == 300000.5 and prefeito["bens"][0] == ["Casa", "Casa na praia", 250000.5]  # ordenado por valor
    assert prefeito["redes"] == ["https://instagram.com/jose"]   # sem duplicata nem @usuario

    vice = sp["2"]
    assert vice["chapaSq"] == "1" and vice["titular"] == "José da Silva" and vice["situacao"] == "eleito"
    assert vice["votos"][0]["votos"] == 400   # vice herda os votos da chapa

    assert sp["4"]["situacao"] == "eleito" and sp["4"]["votos"][0]["votos"] == 50 and sp["4"]["redes"] == ["https://x.com/ana"]

    ac = {e["sq"]: e for e in por_uf["AC"]}
    assert set(ac) == {"7"}   # só o vencedor do 2º turno
    assert ac["7"]["votos"] == [{"turno": 2, "data": "2024-10-27", "votos": 1000, "pct": 25.0}]

    marca = json.loads((t.DADOS / "2024" / "_coleta.json").read_text())
    assert marca["versao"] == t.VERSAO and marca["eleitos"] == 4
    assert not t.precisa_coletar(2024, False)


def test_coletar_ano_falha_nas_partes_opcionais_nao_impede_salvar(tse):
    tse["consulta_cand_2024"] = candidaturas()   # sem votos, bens nem redes: baixar() levanta 404
    t.coletar_ano(2024)
    assert t.AVISOS >= 3
    sp = json.loads((t.DADOS / "2024" / "SP.json").read_text(encoding="utf-8"))
    assert {e["sq"] for e in sp} == {"1", "2", "4"} and all(e["votos"] == [] and e["totalBens"] == 0 for e in sp)


def test_coletar_ano_sem_eleitos_levanta(tse):
    tse["consulta_cand_2024"] = csv(CAND, [cand("1", "PREFEITO", "NÃO ELEITO", "10", "X")])
    with pytest.raises(SystemExit, match="Nenhum eleito"):
        t.coletar_ano(2024)
    assert not (t.DADOS / "2024").exists()


def test_coletar_ano_so_cargos_2018_somente_senador(tse):
    tse["consulta_cand_2018"] = csv(CAND, [cand("1", "SENADOR", "ELEITO", "123", "SENA DOR", uf="PE", ue="PE"),
                                           cand("2", "DEPUTADO FEDERAL", "ELEITO", "1234", "DEP FED", uf="PE", ue="PE")])
    tse["votacao_candidato_munzona_2018"] = csv(["DS_CARGO", "NR_TURNO", "SG_UE", "SQ_CANDIDATO", "QT_VOTOS_NOMINAIS_VALIDOS", "DT_ELEICAO"],
                                                [["Senador", 1, "PE", "1", "5000", "07/10/2018"]])
    t.coletar_ano(2018)
    pe = json.loads((t.DADOS / "2018" / "PE.json").read_text(encoding="utf-8"))
    assert [e["cargo"] for e in pe] == ["SENADOR"] and pe[0]["votos"][0]["votos"] == 5000
    assert pe[0]["bens"] == []   # 2018 não coleta bens


def test_vice_substituido_fica_com_o_registro_mais_recente(tse):
    tse["consulta_cand_2024"] = csv(CAND, [
        cand("1", "PREFEITO", "ELEITO", "10", "TITULAR"),
        cand("2", "VICE-PREFEITO", "SUBSTITUÍDO", "10", "VICE ANTIGO"),
        cand("9", "VICE-PREFEITO", "ELEITO", "10", "VICE NOVO"),
    ])
    t.coletar_ano(2024)
    sp = {e["sq"] for e in json.loads((t.DADOS / "2024" / "SP.json").read_text(encoding="utf-8"))}
    assert sp == {"1", "9"}


def test_2026_finalistas_ainda_sem_resultado_entram_como_segundo_turno(tse, monkeypatch):
    monkeypatch.setattr(t, "ANO_EM_ANDAMENTO", 2026)
    tse["consulta_cand_2026"] = csv(CAND, [
        cand("1", "GOVERNADOR", "#NULO#", "10", "FINALISTA UM", uf="SP", ue="SP", turno=2),
        cand("2", "GOVERNADOR", "#NULO#", "20", "FINALISTA DOIS", uf="SP", ue="SP", turno=2),
        cand("3", "GOVERNADOR", "NÃO ELEITO", "30", "ELIMINADO", uf="SP", ue="SP", turno=1),
    ])
    t.coletar_ano(2026)
    sp = json.loads((t.DADOS / "2026" / "SP.json").read_text(encoding="utf-8"))
    assert {e["sq"]: e["situacao"] for e in sp} == {"1": "2turno", "2": "2turno"}


def test_2026_numero_de_finalistas_estranho_avisa(tse, monkeypatch):
    monkeypatch.setattr(t, "ANO_EM_ANDAMENTO", 2026)
    tse["consulta_cand_2026"] = csv(CAND, [cand("1", "GOVERNADOR", "#NULO#", "10", "SOZINHO", uf="SP", ue="SP", turno=2)])
    t.coletar_ano(2026)
    assert t.AVISOS >= 1
