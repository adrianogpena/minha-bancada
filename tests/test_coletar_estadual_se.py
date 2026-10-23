import json

import coletar_estadual_se as se
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_deputados_da_pagina_do_contrato():
    deputados = se.deputados_da_pagina(amostra("estadual_se_deputados")["trecho"])
    assert len(deputados) == 3
    d = deputados[0]
    assert d["id"].isdigit() and d["nome"] and d["partido"] and d["foto"].startswith("https://")
    assert d["fonte"] == se.FICHA.format(d["id"]) and d["titular"] is True and d["email"] is None


def test_conferir_contrato_deputados():
    assert se._conferir_deputados(amostra("estadual_se_deputados")) == ([], [])
    falhas, _ = se._conferir_deputados({"trecho": "<html></html>"})
    assert falhas


def test_cartao_repetido_conta_uma_vez():
    cartao = ('<article class="qodef-portfolio-item mix"><a href="https://aleselegis.al.se.leg.br/spl/parlamentar.aspx?id=7"><img src="https://x/f.jpg"></a>'
              '<h4 class="qodef-item-title"><a href="x"> Fulano </a></h4><div class="qodef-ptf-category-holder"><span>PT</span></div></article>')
    deputados = se.deputados_da_pagina(cartao + cartao)
    assert [d["id"] for d in deputados] == ["7"] and deputados[0]["nome"] == "Fulano" and deputados[0]["partido"] == "PT"


def test_completar_com_tse_preenche_nome_civil_quando_um_so_casa():
    deputados = [{"nome": "Carminha Paiva", "nomeCivil": "Carminha Paiva"}, {"nome": "Luizão Donatrampi", "nomeCivil": "Luizão Donatrampi"},
                 {"nome": "Paulo Júnior", "nomeCivil": "Paulo Júnior"}, {"nome": "Kitty Lima", "nomeCivil": "Kitty Lima"},
                 {"nome": "Luciano Silva", "nomeCivil": "Luciano Silva"}]
    eleitos = [{"urna": "Carminha", "nome": "Maria do Carmo Paiva da Silva"}, {"urna": "Luizao Dona Trampi", "nome": "Jose Luiz da Mota Cruz"},
               {"urna": "Paulo Jr", "nome": "Paulo Roberto de Santana Junior"}, {"urna": "Luciano Bispo", "nome": "Luciano Bispo de Lima"},
               {"urna": "Luciano Pimentel", "nome": "Luciano Azevedo Pimentel"}]
    se.completar_com_tse(deputados, eleitos)
    assert [d["nomeCivil"] for d in deputados] == ["Maria do Carmo Paiva da Silva", "Jose Luiz da Mota Cruz", "Paulo Roberto de Santana Junior",
                                                    "Kitty Lima", "Luciano Silva"]


def test_coletar_grava_deputados(tmp_path, monkeypatch):
    html = amostra("estadual_se_deputados")["trecho"]

    class Resp:
        text = html

        def raise_for_status(self):
            pass

    class Sessao:
        def get(self, url, timeout=None):
            return Resp()

    eleitos = [{"cargo": "DEPUTADO ESTADUAL", "situacao": "eleito", "urna": "Adailton Martins", "nome": "Adailton Martins de Oliveira Filho"}]
    (tmp_path / "SE.json").write_text(json.dumps(eleitos), encoding="utf-8")
    monkeypatch.setattr(se, "TSE_ARQUIVO", tmp_path / "SE.json")
    monkeypatch.setattr(comum, "DADOS", tmp_path)
    monkeypatch.setattr(comum, "sessao", Sessao)
    se.coletar()
    info = json.loads((tmp_path / "SE" / "deputados.json").read_text(encoding="utf-8"))
    assert info["host"] is None and info["fonte"] == se.HOME and len(info["deputados"]) == 3
    assert any(d["nomeCivil"] == "Adailton Martins de Oliveira Filho" for d in info["deputados"])
