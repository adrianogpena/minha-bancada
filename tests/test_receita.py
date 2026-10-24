import csv
import io
import json
import zipfile

import pytest

import coletar_receita as R
import empresas

TIM = "02421421"
VIVO = "02558157"


def zip_csv(caminho, linhas):
    """ZIP com um CSV no layout da Receita: `;`, aspas, latin-1, sem cabeçalho, arquivo de nome estranho."""
    buf = io.StringIO()
    csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n").writerows(linhas)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("K3241.K03200Y0.D60913.ESTABELE", buf.getvalue().encode("latin-1"))


def estab(raiz, ordem, matriz, situacao, abertura, cnae, sec="", uf="SP", mun="7107"):
    c = [""] * 30
    c[:4] = [raiz, ordem, "00", matriz]
    c[5], c[6], c[10], c[11], c[12], c[19], c[20] = situacao, "20200101", abertura, cnae, sec, uf, mun
    return c


@pytest.fixture
def pasta(tmp_path):
    p = tmp_path / "bruto" / "2026-09"
    for i in R.PARTES:
        zip_csv(p / f"Empresas{i}.zip", [[TIM, "TIM S A", "2046", "10", "1.000.000,50", "05", ""], ["99999999", "Outra", "2062", "49", "0,00", "01", ""]]
                if i == 0 else [])
        zip_csv(p / f"Estabelecimentos{i}.zip", [estab(TIM, "0001", "1", "02", "19981101", "6190601", "6110801,6190699"), estab(TIM, "0002", "2", "02", "20100101", "6190601"),
                                                 estab(VIVO, "0001", "1", "08", "00000000", "6110801"), estab("99999999", "0001", "1", "02", "20200101", "4711302")]
                if i == 0 else [])
        zip_csv(p / f"Socios{i}.zip", [[TIM, "1", "TELECOM ITALIA", "***000000**", "22", "19981101", "", "", "", "", "0"],
                                       [TIM, "2", "Ana  Souza", "***123456**", "49", "20200101", "", "", "", "", "5"], ["99999999", "2", "Fora", "", "49", "", "", "", "", "", "0"]]
                if i == 0 else [])
    zip_csv(p / "Cnaes.zip", [["6190601", "Provedores de acesso"], ["6110801", "Telefonia"], ["6190699", "Outras"], ["4711302", "Supermercados"]])
    zip_csv(p / "Naturezas.zip", [["2046", "Sociedade Anônima Aberta"], ["2062", "Sociedade Limitada"]])
    zip_csv(p / "Qualificacoes.zip", [["22", "Sócio"], ["49", "Sócio-Administrador"]])
    zip_csv(p / "Municipios.zip", [["7107", "SAO PAULO"], ["1", "Outro"]])
    return p


def test_data_receita_so_aceita_data_que_existe():
    assert R.data_receita("20190315") == "2019-03-15"
    assert all(R.data_receita(t) is None for t in ("0", "00000000", "20190230", "", None, "2019-03-15"))


def test_montar_guarda_so_fornecedores_matriz_socios_e_tabelas(pasta):
    saida, tabelas = R.montar(pasta, {TIM, VIVO})
    assert set(saida) == {TIM, VIVO}
    t = saida[TIM]
    assert t["razaoSocial"] == "TIM S A" and t["capitalSocial"] == 1000000.5 and t["porte"] == "05" and t["natureza"] == "2046"
    assert t["abertura"] == "1998-11-01" and t["situacao"] == "02" and t["cnaePrincipal"] == "6190601" and t["cnaesSecundarios"] == ["6110801", "6190699"]
    assert t["estabelecimentos"] == 2 and t["uf"] == "SP" and t["municipio"] == "7107"
    assert t["socios"] == [["TELECOM ITALIA", "22", "1998-11-01", "1"], ["Ana Souza", "49", "2020-01-01", "2"]]
    assert "***" not in json.dumps(saida) and "123456" not in json.dumps(saida)            # nenhum CPF, nem mascarado
    assert "abertura" not in saida[VIVO] and saida[VIVO]["situacao"] == "08"               # data zerada vira ausente
    assert "4711302" not in tabelas["cnae"]                                                # só os códigos usados
    assert tabelas["cnae"]["6110801"] == "Telefonia" and tabelas["natureza"] == {"2046": "Sociedade Anônima Aberta"}
    assert tabelas["municipio"] == {"7107": "SAO PAULO"} and tabelas["qualificacao"] == {"22": "Sócio", "49": "Sócio-Administrador"}


def test_fornecedores_so_pj_e_competencia(tmp_path, monkeypatch, pasta):
    arq = tmp_path / "forn.json"
    arq.write_text(json.dumps([{"id": f"for_{TIM}", "tipo": "PJ"}, {"id": "for_pf_abc", "tipo": "PF"}, {"id": "for_n_x"}]), encoding="utf-8")
    assert R.raizes_dos_fornecedores(arq) == {TIM}
    monkeypatch.setattr(R, "BRUTO", tmp_path / "bruto")
    assert R.competencia_local(None) == "2026-09" and R.competencia_local("2025-01") == "2025-01"
    assert R.arquivos()[0] == "Empresas0.zip" and len(R.arquivos()) == 34


def montar_empresas(tmp_path, pasta):
    saida, tabelas = R.montar(pasta, {TIM, VIVO})
    R.salvar(saida, tabelas, "2026-09", tmp_path / "bruto" / "receita")
    return tmp_path / "bruto"


def test_empresas_junta_receita_com_a_primeira_nota(tmp_path, pasta):
    bruto = montar_empresas(tmp_path, pasta)
    r = empresas.construir(bruto, {f"for_{TIM}", f"for_{VIVO}", "for_pf_x", "for_00000000"}, {f"for_{TIM}": ("1999-02-01", "1999-12-31")})
    assert set(r["empresas"]) == {f"for_{TIM}", f"for_{VIVO}"}
    e = r["empresas"][f"for_{TIM}"]
    assert e["primeiraNota"] == "1999-02-01" and e["diasAteNota"] == 92 and r["fonte"]["competencia"] == "2026-09"
    assert "primeiraNota" not in r["empresas"][f"for_{VIVO}"] and "diasAteNota" not in r["empresas"][f"for_{VIVO}"]
    assert r["tabelas"]["situacao"]["02"] == "Ativa" and r["tabelas"]["cnae"]["6190601"] == "Provedores de acesso"
    assert r["fonte"]["url"].startswith("https://")
    empresas.salvar_empresas(r, tmp_path / "site")
    assert (tmp_path / "site" / "nucleo" / "empresas.json").is_file()


def test_empresas_sem_coleta_da_receita_gera_arquivo_vazio(tmp_path):
    r = empresas.construir(tmp_path, {f"for_{TIM}"}, {})
    assert r["fonte"] is None and r["empresas"] == {}
    empresas.salvar_empresas(r, tmp_path / "site")
    assert json.loads((tmp_path / "site" / "nucleo" / "empresas.json").read_text(encoding="utf-8"))["empresas"] == {}
