"""Roda o gerar.py inteiro sobre um dados/ mínimo e confere o que o front (site/assets/js) vai ler:
quais arquivos existem e quais campos cada página usa. Um campo renomeado aqui, sem ajustar o front, falha no CI."""
import json
import re

import pytest

import dados_minimos
from conftest import RAIZ


@pytest.fixture
def site(tmp_path):
    """Gera site/dados/ a partir de um dados/ mínimo (1 deputado, 1 senador, 1 votação de cada) e devolve a pasta."""
    return dados_minimos.gerar_tudo(tmp_path)


def ler(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_arquivos_basicos_do_site_existem(site):
    for rel in ("meta.json", "deputados.json", "votacoes.json", "votacao/1-1.json", "deputado/101.json",
                "senador/7.json", "votacoes_senado.json", "votacao_senado/9.json", "fornecedores.json", "nucleo/fornecedores.json", "cobertura.json"):
        assert (site / rel).is_file(), rel


def test_lista_de_deputados_tem_os_campos_da_home(site):
    (d,) = ler(site / "deputados.json")
    for campo in ("id", "nome", "partido", "uf", "foto", "proposicoes", "gasto", "votou", "votacoes"):
        assert campo in d, campo
    assert d["gasto"] == 120.5 and d["votou"] == 1 and d["votacoes"] == 1


def test_ficha_do_deputado_tem_os_campos_da_pagina(site):
    d = ler(site / "deputado" / "101.json")
    for campo in ("id", "nome", "partido", "uf", "proposicoes", "autoria", "votos", "despesas", "totalVotacoes", "presenca", "orgaos"):
        assert campo in d, campo
    for campo in ("ano", "total", "porCategoria", "porMes", "fornecedores", "recentes", "mediaUF"):
        assert campo in d["despesas"], campo
    assert d["votos"][0]["voto"] == "sim" and d["votos"][0]["id"] == "1-1"


def test_votacao_liga_lista_e_detalhe(site):
    (resumo,) = ler(site / "votacoes.json")
    det = ler(site / "votacao" / f"{resumo['id']}.json")
    assert det["placar"] == resumo["placar"] == {"sim": 1, "nao": 1}
    assert {v["voto"] for v in det["votos"]} == {"sim", "nao"}
    assert det["porPartido"]["PT"] == {"sim": 1}
    assert next(v for v in det["votos"] if v["id"] == 102)["nome"] == "Deputado 102"   # votou mas saiu do exercício


def test_senado_liga_lista_detalhe_e_ficha(site):
    (resumo,) = ler(site / "votacoes_senado.json")
    assert (site / "votacao_senado" / f"{resumo['id']}.json").is_file()
    sen = ler(site / "senador" / "7.json")
    assert sen["votos"] == [{"id": "9", "voto": "sim"}]


def test_meta_traz_ano_e_periodo(site):
    meta = ler(site / "meta.json")
    assert meta["ano"] == 2026 and meta["periodoVotacoes"] == ["2026-08-12", "2026-08-12"]


def test_tudo_que_o_front_busca_com_caminho_fixo_e_gerado_ou_conhecido(site):
    """Todo `carregar("dados/…")` com caminho literal nos módulos JS/HTML aponta para algo que o gerar.py produz.
    Os que dependem de coletas opcionais (executivo, histórico, eleitorado…) ficam em OPCIONAIS."""
    opcionais = {"dados/executivo.json", "dados/municipios_ibge.json", "dados/historico/indice.json", "dados/indice/BR.json"}
    fontes = [*(RAIZ / "site" / "assets" / "js").glob("*.js"), *(RAIZ / "site").glob("*.html")]
    achados = set()
    for f in fontes:
        achados |= set(re.findall(r'carregar\("(dados/[^"$`]+\.json)"\)', f.read_text(encoding="utf-8")))
    assert "dados/deputados.json" in achados and "dados/votacoes.json" in achados   # a busca em si funciona
    faltando = {c for c in achados if c not in opcionais and not (site.parent / c).is_file()}
    assert not faltando, faltando


def test_proposicoes_ligam_indice_ficha_autores_e_votacao(site):
    (item,) = ler(site / "proposicoes.json")
    assert item["k"] == "c-900" and (item["t"], item["n"], item["a"]) == ("PL", 1, 2026)
    ficha = ler(site / "proposicao" / "c-2026.json")["900"]
    assert ficha["au"] == [{"id": "101"}]
    assert "v" not in ficha   # a votação 1-1 tem propId 900 mas só entra por proposicoes_votacoes.json (coleta da Câmara)


def test_nucleo_de_identidades_e_o_id_da_pessoa_nas_fichas(site):
    pessoas = ler(site / "nucleo" / "pessoas.json")
    assert (site / "nucleo" / "partidos.json").is_file() and (site / "nucleo" / "ligacoes.json").is_file()
    por_id = {p["id"]: p for p in pessoas}
    assert por_id[ler(site / "deputado" / "101.json")["pessoa"]]["fontes"]["camara"] == 101
    assert por_id[ler(site / "p" / "senado.json")["7"]["pessoa"]]["fontes"]["senado"] == "7"


def test_autorias_ligam_proposicao_e_pessoa(site):
    aut = ler(site / "nucleo" / "autorias.json")
    quem = ler(site / "deputado" / "101.json")["pessoa"]
    assert [k for k, _ in aut["porPessoa"][quem]] == ["c-900"]
    assert any(i["k"] == "c-900" for i in ler(site / "proposicoes.json"))


def test_mandatos_ligam_pessoa_e_exercicio(site):
    quem = ler(site / "deputado" / "101.json")["pessoa"]
    (m,) = [m for m in ler(site / "nucleo" / "mandatos.json") if m["pessoa"] == quem]
    assert m["cargo"] == "DEPUTADO FEDERAL" and m["status"] == "atual" and m["confirmado"] is True and m["fontes"] == {"camara": 101}


def test_nucleo_gera_candidaturas_e_disputas(site):
    cands = {c["id"]: c for c in ler(site / "nucleo" / "candidaturas" / "2024.json")}
    pessoas = {p["id"] for p in ler(site / "nucleo" / "pessoas.json")}
    assert cands["can_2024_500"]["pessoa"] in pessoas and cands["can_2024_500"]["federacao"] == "fed_pcdob_pt_pv"
    disputa = ler(site / "nucleo" / "disputas" / "2024.json")["dsp_2024_vereador_71072"]
    assert disputa["vagas"] == 55 and disputa["partidos"]["par_pt"] == [100, 300, "fed_pcdob_pt_pv"]


def test_fichas_do_tse_trazem_o_que_o_local_tem_em_comum_uma_vez_so(site):
    arq = ler(site / "p" / "t" / "2024" / "71072.json")
    comuns = arq["_disputas"]
    assert sorted(comuns) == ["coligacoes", "disputa", "partidos"] and list(comuns["disputa"]) == ["VEREADOR|71072"]
    for seq in ("500", "501"):
        assert not {"disputa", "partidoVotos", "alianca"} & set(arq[seq])           # nada repetido em cada ficha
    assert comuns["partidos"]["VEREADOR|71072"]["partidos"]["PT"] == [100, 300, "PT/PC do B/PV"]
