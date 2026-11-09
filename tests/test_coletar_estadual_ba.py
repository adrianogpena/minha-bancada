"""Coletor da Assembleia da Bahia (scripts/coletar_estadual_ba.py) contra amostras reais em tests/fixtures/contratos/."""
import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pytest
import requests

import coletar_estadual_ba as ba
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"


def fixture(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))


def amostra(nome):
    return fixture(nome)["amostra"]


DEPUTADOS = [
    {"id": "910629", "nome": "Adolfo Menezes", "nomeCivil": "ADOLFO EMANUEL MONTEIRO DE MENEZES"},
    {"id": "921263", "nome": "Alex da Piatã", "nomeCivil": "Alex da Piatã"},
    {"id": "921264", "nome": "Antonio Henrique Júnior", "nomeCivil": "Antonio Henrique Júnior"},
]


def test_contratos_registrados():
    assert [c["nome"] for c in ba.CONTRATOS] == [f"estadual_ba_{x}" for x in ("deputados", "verba", "proposicoes", "emendas", "presenca", "contratos", "regras")]
    for c in ba.CONTRATOS:
        falhas, _ = c["html"](amostra(c["nome"]))
        assert falhas == [], c["nome"]


def test_cartoes():
    lista = ba.cartoes(amostra("estadual_ba_deputados")["lista"])
    assert lista[0]["id"] == "910629" and lista[0]["nome"] and lista[0]["partido"]
    assert lista[0]["foto"].startswith("https://www.al.ba.gov.br/fserver/")


def test_ficha():
    dados = ba.ficha(amostra("estadual_ba_deputados")["ficha"])
    assert dados["nomeCivil"] and dados["email"].endswith("@alba.ba.gov.br")


def test_data_serial():
    assert ba.data_serial("46235.0") == date(2026, 8, 1)
    assert ba.data_serial("") is None


def test_itens_verba():
    linhas = amostra("estadual_ba_verba")["linhas"]
    itens, sem_par = ba.itens_verba(linhas, [{"id": "7", "nome": n, "nomeCivil": None} for n in {linha.get("F") for linha in linhas}], 2026)
    assert itens and sem_par == set()
    primeiro = itens[0]
    assert primeiro["valor"] > 0 and 1 <= primeiro["mes"] <= 12 and primeiro["categoria"]
    assert primeiro["fonte"].startswith("https://www.al.ba.gov.br/transparencia/verbas-idenizatorias?ano=2026&deputado=")


def test_itens_verba_sem_par_e_sem_cabecalho():
    linhas = [{"B": "N° PROCESSO", "F": "DEPUTADO (A)", "G": "CATEGORIA", "H": "VALOR (R$)", "E": "DATA"},
              {"B": "1", "E": "46235.0", "F": "  Fulano   Qualquer ", "G": "Consultorias", "H": "10500.0"},
              {"B": "2", "E": "46235.0", "F": "Adolfo Menezes", "G": "Consultorias", "H": "100.5"}]
    itens, sem_par = ba.itens_verba(linhas, DEPUTADOS, 2026)
    assert [i["idDeputado"] for i in itens] == ["910629"] and itens[0]["valor"] == 100.5 and itens[0]["mes"] == 8
    assert sem_par == {"Fulano Qualquer"}
    assert ba.itens_verba([{"A": "x"}], DEPUTADOS, 2026) == ([], set())


def test_proposicoes_da_lista():
    lista = ba.proposicoes_da_lista(amostra("estadual_ba_proposicoes")["lista"])
    p = lista[0]
    assert p["slug"] == f"PL.-{p['numero']}-{p['ano']}" and p["sigla"] == "PL" and p["ementa"] and p["linkTexto"].startswith("http")
    assert ba.ultima_pagina(amostra("estadual_ba_proposicoes")["lista"]) > 1


def test_detalhe_proposicao():
    d = ba.detalhe_proposicao(amostra("estadual_ba_proposicoes")["detalhe"])
    assert d["autor"].startswith("DEPUTADO") and d["ementa"] and len(d["dataApresentacao"]) == 10
    assert d["situacao"] and "Recebido" not in d["situacao"]


def test_autores():
    assert ba.autores("DEPUTADO VITOR AZEVEDO") == ["VITOR AZEVEDO"]
    assert ba.autores("DEPUTADO A, DEPUTADA B E DEPUTADO C") == ["A", "B", "C"]
    assert ba.autores("PODER EXECUTIVO") == ["PODER EXECUTIVO"]


def test_itens_emendas():
    csv_texto = amostra("estadual_ba_emendas")["csv"]
    nome = csv_texto.splitlines()[1].split(";")[8].strip('" ')
    por_ano, sem_par = ba.itens_emendas(csv_texto, [{"id": "9", "nome": nome, "nomeCivil": None}])
    itens = [i for v in por_ano.values() for i in v]
    assert itens and all(i["idDeputado"] == "9" and i["fonte"] == ba.EMENDAS_PAGINA for i in itens)
    assert all(i["empenhado"] is not None and i["objeto"] for i in itens)


def test_itens_pagamentos():
    csv_texto = amostra("estadual_ba_emendas")["pagamentos"]
    numero = csv_texto.splitlines()[1].split(";")[9].strip('"')
    por_ano = ba.itens_pagamentos(csv_texto, {numero})
    assert list(por_ano) == [2026]
    primeiro = por_ano[2026][0]
    assert primeiro["numero"] == numero and primeiro["data"] == "2026-01-20" and primeiro["valor"] == 500000.0
    assert primeiro["credor"] and primeiro["objeto"] and primeiro["empenho"] and primeiro["efetivado"] is False
    assert [i["efetivado"] for i in por_ano[2026]] == [False, True]
    assert sorted(ba.itens_pagamentos(csv_texto, {numero}, 2025)) == [2025, 2026]
    assert ba.itens_pagamentos(csv_texto, {"outra"}) == {}


def test_url_zip_emendas():
    pacote = {"result": {"resources": [{"format": "PNG", "url": "a"}, {"format": "ZIP", "url": "b"}]}}
    assert ba.url_zip_emendas(pacote) == "b"


def test_coletar_deputados_grava_no_formato_comum(tmp_path, monkeypatch):
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    monkeypatch.setattr(ba, "baixar", lambda s, url, *a, **k: (amostra("estadual_ba_deputados")["lista"].encode() if url == ba.LISTA_URL
                                                              else amostra("estadual_ba_deputados")["ficha"].encode()))
    deputados = ba.coletar_deputados(None)
    gravado = comum.ler(tmp_path / "deputados.json")
    assert gravado["fonte"] == ba.LISTA_URL and gravado["host"] is None
    assert gravado["deputados"] == deputados and deputados[0]["fonte"].startswith(f"{ba.FICHA_URL}/")
    assert deputados[0]["nomeCivil"] and deputados[0]["email"]


def test_coletar_verba_grava_por_ano(tmp_path, monkeypatch):
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    monkeypatch.setattr(ba, "ANO_VERBA", date.today().year)
    monkeypatch.setattr(ba, "baixar", lambda *a, **k: b"")
    linhas = amostra("estadual_ba_verba")["linhas"]
    monkeypatch.setattr(ba.comum, "xlsx_linhas", lambda conteudo: linhas)
    deputados = [{"id": "7", "nome": n, "nomeCivil": None} for n in {linha.get("F") for linha in linhas}]
    ba.coletar_verba(None, deputados)
    gravado = comum.ler(tmp_path / f"verbas_{date.today().year}.json")
    assert gravado["itens"] and gravado["fonte"].endswith(f"?ano={date.today().year}")


def test_coletar_emendas_grava_por_ano(tmp_path, monkeypatch):
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    csv_texto = amostra("estadual_ba_emendas")["csv"]
    nome = csv_texto.splitlines()[1].split(";")[8].strip('" ')
    pacote = json.dumps({"result": {"resources": [{"format": "ZIP", "url": "https://x/z.zip"}]}}).encode()
    mini = io.BytesIO()
    with zipfile.ZipFile(mini, "w") as z:
        z.writestr(ba.EMENDAS_CSV, csv_texto)
        z.writestr(ba.PAGAMENTOS_CSV, amostra("estadual_ba_emendas")["pagamentos"])
    monkeypatch.setattr(ba, "baixar_ckan", lambda s, url, *a, **k: pacote if url == ba.EMENDAS_API else mini.getvalue())
    ba.coletar_emendas(None, [{"id": "9", "nome": nome, "nomeCivil": None}])
    arquivos = sorted(p.name for p in tmp_path.glob("emendas_*.json"))
    assert arquivos and comum.ler(tmp_path / arquivos[0])["itens"][0]["idDeputado"] == "9"
    assert not list(tmp_path.glob("pagamentos_*.json"))


def test_coletar_emendas_grava_pagamentos_por_ano_do_pagamento(tmp_path, monkeypatch):
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    pagamentos = amostra("estadual_ba_emendas")["pagamentos"]
    numero = pagamentos.splitlines()[1].split(";")[9].strip('"')
    pacote = json.dumps({"result": {"resources": [{"format": "ZIP", "url": "https://x/z.zip"}]}}).encode()
    mini = io.BytesIO()
    with zipfile.ZipFile(mini, "w") as z:
        z.writestr(ba.EMENDAS_CSV, amostra("estadual_ba_emendas")["csv"])
        z.writestr(ba.PAGAMENTOS_CSV, pagamentos)
    monkeypatch.setattr(ba, "baixar_ckan", lambda s, url, *a, **k: pacote if url == ba.EMENDAS_API else mini.getvalue())
    monkeypatch.setattr(ba, "itens_emendas", lambda texto, deputados: ({2025: [{"idDeputado": "9", "numero": numero}]}, set()))
    ba.coletar_emendas(None, [])
    gravado = comum.ler(tmp_path / "pagamentos_2026.json")
    assert gravado["fonte"] == ba.EMENDAS_PAGINA and len(gravado["itens"]) == 2
    assert not (tmp_path / "pagamentos_2025.json").exists()


def test_precisa_detalhe_ano_corrente_renova_escalonado_e_ano_encerrado_nao():
    from datetime import date, timedelta

    hoje = date(2026, 10, 22)
    velha = (hoje - timedelta(days=40)).isoformat()
    assert ba.precisa_detalhe("PL-1-2026", 2026, {}, hoje)                                  # nunca lida
    assert not ba.precisa_detalhe("PL-1-2026", 2026, {"PL-1-2026": hoje.isoformat()}, hoje)   # lida hoje
    assert ba.precisa_detalhe("PL-1-2026", 2026, {"PL-1-2026": velha}, hoje)                # lida há mais que o prazo máximo (20 dias)
    assert not ba.precisa_detalhe("PL-1-2025", 2025, {"PL-1-2025": velha}, hoje)            # ano encerrado: uma leitura só


def test_coletar_proposicoes_nao_rele_o_que_ja_viu(tmp_path, monkeypatch):
    from datetime import date

    hoje = date.today()
    a = amostra("estadual_ba_proposicoes")

    def item(n, ano):
        return {"slug": f"PL.-{n}-{ano}", "sigla": "PL", "numero": n, "ano": ano, "ementa": "e", "linkTexto": None}

    lista = {i["slug"]: i for i in (item(1, 2025), item(2, 2025), item(3, hoje.year))}
    lidos = []
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    monkeypatch.setattr(ba, "listar_proposicoes", lambda s: lista)
    monkeypatch.setattr(ba, "baixar", lambda s, url, *a, **k: lidos.append(url) or a_detalhe)
    a_detalhe = a["detalhe"].encode()
    ba.coletar_proposicoes(None, [])
    assert len(lidos) == 3                      # primeira vez: lê tudo (ninguém é deputado da lista vazia)
    assert comum.ler(tmp_path / "materias_2025.json")["vistas"].keys() == {"PL-1-2025", "PL-2-2025"}
    lidos.clear()
    ba.coletar_proposicoes(None, [])
    assert lidos == []                          # segunda vez, no mesmo dia: nada a reler, nem o que não é de deputado


def pagina_frequencia(data, linhas):
    corpo = "".join(f'<tr class="table-itens"><td><span>{n}</span></td><td><span>{r}</span></td></tr>' for n, r in linhas)
    return f'<div class="titulo-presidente">1ª Sessão Ordinária - {data} às 14:00</div><table>{corpo}</table>'.encode()


def test_sessoes_da_lista():
    sessoes = ba.sessoes_da_lista(amostra("estadual_ba_presenca")["lista"])
    assert sessoes == [{"id": "6420", "numero": "52º", "tipo": "Ordinária", "data": "2025-06-18"}]


def test_frequencia_da_sessao():
    f = ba.frequencia_da_sessao(amostra("estadual_ba_presenca")["frequencia"])
    assert f["data"] == "2025-06-18" and f["titulo"] == "52ª Sessão Ordinária"
    assert f["presencas"]["Adolfo Menezes"] is False and f["presencas"]["Alan Sanches"] is True and len(f["presencas"]) == 4
    assert ba.frequencia_da_sessao("<html></html>") is None


def test_presenca_soma_ano_e_mes_e_ignora_nome_sem_par():
    contagem = {}
    ligacao = {"Adolfo Menezes": "910629"}
    ba.somar_presenca(contagem, {"data": "2025-06-10", "presencas": {"Adolfo Menezes": True, "Fulano": True}}, ligacao)
    ba.somar_presenca(contagem, {"data": "2025-06-11", "presencas": {"Adolfo Menezes": False}}, ligacao)
    itens = {i["periodo"]: i for i in ba.itens_presenca(contagem)}
    assert set(itens) == {"2025", "2025-06"}
    assert itens["2025"]["presente"] == 1 and itens["2025"]["ausente"] == 1 and itens["2025"]["totalSessoes"] == 2
    assert itens["2025-06"]["idDeputado"] == "910629" and itens["2025-06"]["fonte"] == ba.SESSOES


def test_coletar_presenca_nao_rele_sessao_lida(tmp_path, monkeypatch):
    sessoes = {"1": {"id": "1", "data": "2025-06-10"}, "2": {"id": "2", "data": "2025-06-11"}}
    paginas = {"1": pagina_frequencia("10/06/2025", [("Adolfo Menezes", "Sim")]), "2": pagina_frequencia("11/06/2025", [("Adolfo Menezes", "Não")])}
    lidos = []
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    monkeypatch.setattr(ba, "listar_sessoes", lambda s, desde, hoje: sessoes)
    monkeypatch.setattr(ba, "baixar", lambda s, url, *a, **k: lidos.append(url) or paginas[url.rsplit("/", 1)[1]])
    ba.coletar_presenca(None, DEPUTADOS)
    assert len(lidos) == 2
    arq = comum.ler(tmp_path / "presenca.json")
    assert arq["lidas"] == {"1": "2025-06-10", "2": "2025-06-11"}
    ano = next(i for i in arq["itens"] if i["periodo"] == "2025")
    assert (ano["idDeputado"], ano["presente"], ano["ausente"], ano["totalSessoes"]) == ("910629", 1, 1, 2)
    lidos.clear()
    sessoes["3"] = {"id": "3", "data": "2025-06-12"}
    paginas["3"] = pagina_frequencia("12/06/2025", [("Adolfo Menezes", "Sim")])
    ba.coletar_presenca(None, DEPUTADOS)
    assert lidos == [f"{ba.FREQUENCIA}/3"]
    ano = next(i for i in comum.ler(tmp_path / "presenca.json")["itens"] if i["periodo"] == "2025")
    assert (ano["presente"], ano["ausente"]) == (2, 1)


def test_coletar_presenca_ignora_sessao_com_data_diferente_ou_vazia(tmp_path, monkeypatch):
    sessoes = {"1": {"id": "1", "data": "2025-06-10"}, "2": {"id": "2", "data": "2025-06-11"}, "3": {"id": "3", "data": "2025-06-12"}}
    paginas = {"1": pagina_frequencia("09/06/2025", [("Adolfo Menezes", "Sim")]), "2": pagina_frequencia("11/06/2025", []),
               "3": pagina_frequencia("12/06/2025", [("Adolfo Menezes", "Sim")])}
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    monkeypatch.setattr(ba, "listar_sessoes", lambda s, desde, hoje: sessoes)
    monkeypatch.setattr(ba, "baixar", lambda s, url, *a, **k: paginas[url.rsplit("/", 1)[1]])
    ba.coletar_presenca(None, DEPUTADOS)
    assert comum.ler(tmp_path / "presenca.json")["lidas"] == {"2": "2025-06-11", "3": "2025-06-12"}


def test_listar_sessoes_pagina_ate_acabar(monkeypatch):
    def pagina(n):
        return "" if n else (f'<td width="100"><span>1º</span></td><td><span>Ordinária</span></td><td><span>10/06/2025</span></td>'
                             f'<a href="/atividade-legislativa/frequencia-sessao/7">x</a>')

    chamadas = []
    monkeypatch.setattr(ba, "baixar", lambda s, url, params=None, **k: chamadas.append(params) or pagina(params["page"]).encode())
    achadas = ba.listar_sessoes(None, 2025, date(2025, 8, 1))
    assert list(achadas) == ["7"] and [c["page"] for c in chamadas] == [0, 1]


def test_contratos_da_pagina():
    itens = ba.contratos_da_pagina(amostra("estadual_ba_contratos")["html"])
    primeiro = next(iter(itens.values()))
    assert primeiro["numero"] == "037/2026" and primeiro["inicio"] == "2026-11-01" and primeiro["valor"] == 37859.49
    assert primeiro["cnpj"] is None and primeiro["modalidade"] == "Pregão Eletrônico" and primeiro["situacao"] == "Ativo"
    assert primeiro["fonte"].endswith("/detalhar/110100012600000433")
    assert all(i.startswith("ctr_") for i in itens)


def test_coletar_contratos_grava_por_ano_sem_regravar_ano_encerrado(tmp_path, monkeypatch):
    html = amostra("estadual_ba_contratos")["html"]
    paginas = {0: html, 1: ""}
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    monkeypatch.setattr(ba, "baixar", lambda s, url, params=None, **k: paginas[params["page"]].encode())
    ba.coletar_contratos(None)
    arq = tmp_path / "orgao_2026.json"
    assert len(comum.ler(arq)["itens"]) == 2 and comum.ler(arq)["fonte"] == ba.CONTRATOS_PAGINA
    paginas[0] = ""
    try:
        ba.coletar_contratos(None)
    except RuntimeError as e:
        assert "sem linhas" in str(e)
    assert len(comum.ler(arq)["itens"]) == 2


def test_normas_da_verba_e_regras(tmp_path, monkeypatch):
    html = amostra("estadual_ba_regras")["html"]
    normas = ba.normas_da_verba(html)
    assert normas[0]["ano"] == 2023 and normas[0]["url"].startswith("https://www.al.ba.gov.br/fserver/") and normas[0]["url"].endswith(".pdf")
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    monkeypatch.setattr(ba, "baixar", lambda s, url, *a, **k: html.encode())
    ba.coletar_regras(None)
    regra = comum.ler(tmp_path / "regras_ressarcimento.json")
    assert regra["ano"] == 2023 and regra["url"] == normas[0]["url"] and regra["fonte"] == ba.REGRAS_PAGINA and len(regra["documentos"]) == len(normas)


def avisos(capsys):
    return capsys.readouterr().err


def test_decodificar():
    assert ba.decodificar("ação".encode("utf-8-sig")) == "ação"
    assert ba.decodificar("ação".encode("cp1252")) == "ação"


def test_pequenos_parsers_com_entrada_invalida():
    assert ba.iso_data("xx") is None and ba.iso_data("") is None
    assert ba.data_serial("abc") is None and ba.data_serial(None) is None
    assert ba.sem_espacos(None) == "" and ba.sem_espacos("  a   b ") == "a b"
    assert ba.cartoes("<html></html>") == []
    assert ba.ultima_pagina("<html></html>") == 1
    assert ba.proposicoes_da_lista('<tr class="table-itens"><td>sem link</td></tr>') == []
    assert ba.detalhe_proposicao("<html></html>") == {"autor": "", "dataApresentacao": None, "ementa": None, "situacao": None}


def test_cadeia_ckan_junta_raizes_e_intermediario_e_reaproveita(tmp_path, monkeypatch):
    (tmp_path / "raizes.pem").write_text("RAIZES", encoding="ascii")
    (tmp_path / "inter.pem").write_text("INTERMEDIARIO", encoding="ascii")
    criados = []

    def mkstemp(suffix=""):
        caminho = str(tmp_path / f"cadeia{len(criados)}{suffix}")
        criados.append(caminho)
        return None, caminho

    monkeypatch.setattr(ba, "_cadeia_ckan", [])
    monkeypatch.setattr(ba, "INTERMEDIARIO_CKAN", tmp_path / "inter.pem")
    monkeypatch.setattr(ba.certifi, "where", lambda: str(tmp_path / "raizes.pem"))
    monkeypatch.setattr(ba.tempfile, "mkstemp", mkstemp)
    primeiro = ba.cadeia_ckan()
    assert Path(primeiro).read_text(encoding="ascii") == "RAIZES\nINTERMEDIARIO" and primeiro.endswith(".pem")
    assert ba.cadeia_ckan() == primeiro and len(criados) == 1
    Path(primeiro).unlink()
    novo = ba.cadeia_ckan()
    assert novo != primeiro and Path(novo).exists() and len(criados) == 2


class RespostaHttp:
    def __init__(self, conteudo=b"", erro=None):
        self.content = conteudo
        self.erro = erro

    def raise_for_status(self):
        if self.erro:
            raise self.erro


def test_baixar_ckan_verifica_com_a_cadeia_propria(monkeypatch):
    pedidos = []

    def get(url, **kw):
        pedidos.append((url, kw))
        return RespostaHttp(b"conteudo")

    monkeypatch.setattr(ba.requests, "get", get)
    monkeypatch.setattr(ba, "cadeia_ckan", lambda: "/cadeia.pem")
    assert ba.baixar_ckan(None, "https://dados.ba.gov.br/x", 7) == b"conteudo"
    assert pedidos == [("https://dados.ba.gov.br/x", {"timeout": 7, "verify": "/cadeia.pem", "headers": {"User-Agent": comum.USER_AGENT}})]


def test_baixar_ckan_erro_http_timeout_e_prazo_propagam(monkeypatch):
    monkeypatch.setattr(ba, "cadeia_ckan", lambda: "/cadeia.pem")
    monkeypatch.setattr(ba.requests, "get", lambda url, **kw: RespostaHttp(erro=requests.HTTPError("503")))
    with pytest.raises(requests.HTTPError):
        ba.baixar_ckan(None, "https://x")

    def get_lento(url, **kw):
        raise requests.Timeout("lento")

    monkeypatch.setattr(ba.requests, "get", get_lento)
    with pytest.raises(requests.Timeout):
        ba.baixar_ckan(None, "https://x")
    chamadas = []
    monkeypatch.setattr(ba.requests, "get", lambda url, **kw: chamadas.append(url))

    def prazo():
        raise comum.PrazoEsgotado("prazo de coleta esgotado")

    monkeypatch.setattr(ba.comum, "checar_prazo", prazo)
    with pytest.raises(comum.PrazoEsgotado):
        ba.baixar_ckan(None, "https://x")
    assert chamadas == []


def test_coletar_deputados_sem_cartoes_levanta_e_ficha_com_falha_avisa(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    monkeypatch.setattr(ba, "baixar", lambda s, url, *a, **k: b"<html></html>")
    with pytest.raises(RuntimeError, match="sem cartões"):
        ba.coletar_deputados(None)
    assert not (tmp_path / "deputados.json").exists()
    lista = amostra("estadual_ba_deputados")["lista"].encode()

    def baixar(s, url, *a, **k):
        if url == ba.LISTA_URL:
            return lista
        raise RuntimeError("ficha fora")

    monkeypatch.setattr(ba, "baixar", baixar)
    deputados = ba.coletar_deputados(None)
    assert all(d["nomeCivil"] is None and d["email"] is None for d in deputados) and deputados[0]["id"] == "910629"
    assert "BA: ficha de 910629: ficha fora" in avisos(capsys)


def test_coletar_verba_pula_ano_encerrado_grava_atual_vazio_e_avisa_sem_par(tmp_path, monkeypatch, capsys):
    ano = date.today().year
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    monkeypatch.setattr(ba, "ANO_VERBA", ano - 1)
    (tmp_path / f"verbas_{ano - 1}.json").write_text('{"itens":[]}', encoding="utf-8")
    pedidos = []
    monkeypatch.setattr(ba, "baixar", lambda s, url, params=None, **k: pedidos.append(params) or b"")
    monkeypatch.setattr(ba.comum, "xlsx_linhas", lambda conteudo: [{"F": "DEPUTADO (A)", "G": "CATEGORIA", "H": "VALOR (R$)", "E": "DATA"},
                                                                    {"F": "Fulano Qualquer", "G": "x", "H": "1", "E": "46235"}])
    ba.coletar_verba(None, [])
    assert pedidos == [{"ano": ano}]
    assert comum.ler(tmp_path / f"verbas_{ano}.json")["itens"] == []
    assert comum.ler(tmp_path / f"verbas_{ano - 1}.json") == {"itens": []}
    assert f"verba {ano} sem deputado atual (1): ['Fulano Qualquer']" in avisos(capsys)


def linha_lista(slug, ementa="Ementa"):
    return (f'<tr class="table-itens"><td><a href="/atividade-legislativa-nova/proposicao/{slug}">x</a></td>'
            f'<td><span class="fe-html-ativ">{ementa}</span></td><td><a href="https://x/{slug}.pdf">texto</a></td></tr>')


def test_listar_proposicoes_pagina_deduplica_e_isola_falhas(monkeypatch, capsys):
    ultima = '<a href="?page=2&amp;size=20" title="Última Página">u</a>'
    paginas = {("PL.", 0): ultima + linha_lista("PL.-1-2025") + linha_lista("PL.-2-2025"), ("PL.", 2): linha_lista("PL.-2-2025", "Ementa nova") + linha_lista("PL.-3-2025"),
               ("PEC", 0): linha_lista("PEC-9-2024")}
    pedidos = []

    def baixar(s, url, params=None, **k):
        pedidos.append((params["tipo"], params["page"]))
        if params["tipo"] == "PLC" or (params["tipo"], params["page"]) == ("PL.", 1):
            raise RuntimeError("fora do ar")
        return paginas.get((params["tipo"], params["page"]), "").encode("utf-8")

    monkeypatch.setattr(ba, "baixar", baixar)
    achados = ba.listar_proposicoes(None)
    assert set(achados) == {"PL.-1-2025", "PL.-2-2025", "PL.-3-2025", "PEC-9-2024"}
    assert achados["PL.-2-2025"]["ementa"] == "Ementa nova" and achados["PEC-9-2024"]["sigla"] == "PEC"
    assert sorted(set(pedidos)) == sorted({("PL.", 0), ("PL.", 1), ("PL.", 2), ("PLC", 0), ("PEC", 0), ("PDL", 0), ("PRS", 0)})
    err = avisos(capsys)
    assert "BA: proposições PLC: fora do ar" in err and "BA: proposições PL. página 1: fora do ar" in err


def test_listar_proposicoes_parametros_da_consulta(monkeypatch):
    pedidos = []
    monkeypatch.setattr(ba, "baixar", lambda s, url, params=None, **k: pedidos.append((url, params)) or b"")
    assert ba.listar_proposicoes(None) == {}
    assert len(pedidos) == len(ba.TIPOS) and pedidos[0][0] == ba.PROPOSICOES
    assert pedidos[0][1] == {"dataInicio": "01/01/2023", "dataFim": date.today().strftime("%d/%m/%Y"), "size": 20, "tipo": "PL.", "page": 0}


def detalhe_html(autor, entrada="10/02/2025", ementa="Dispõe sobre algo"):
    return (f'Autor: <span>{autor}</span><strong>Data de Entrada:</strong> <span>{entrada}</span><strong>Ementa:</strong> <span>{ementa}</span>'
            '<div class="inter-title">TRAMITAÇÃO</div><span>10/02/2025 - Recebido</span><span>11/02/2025 - Aprovado em plenário</span></div></div></div>').encode("utf-8")


def item_lista(n, ano, sigla="PL"):
    return {"slug": f"{sigla}.-{n}-{ano}", "sigla": sigla, "numero": n, "ano": ano, "ementa": "da lista", "linkTexto": "https://x/t.pdf"}


def test_coletar_proposicoes_liga_autor_deputado_marca_vistas_e_avisa(tmp_path, monkeypatch, capsys):
    ano = date.today().year
    lista = {i["slug"]: i for i in (item_lista(1, ano), item_lista(2, ano), item_lista(3, ano), item_lista(4, ano, "PEC"))}
    detalhes = {f"PL.-1-{ano}": detalhe_html("DEPUTADO ADOLFO MENEZES, DEPUTADO ALEX DA PIATÃ"), f"PL.-2-{ano}": detalhe_html("PODER EXECUTIVO"),
                f"PEC.-4-{ano}": detalhe_html("DEPUTADO ADOLFO MENEZES", ementa="")}

    def baixar(s, url, *a, **k):
        slug = url.rsplit("/", 1)[1]
        if slug not in detalhes:
            raise RuntimeError("detalhe fora")
        return detalhes[slug]

    monkeypatch.setattr(ba, "PASTA", tmp_path)
    monkeypatch.setattr(ba, "listar_proposicoes", lambda s: lista)
    monkeypatch.setattr(ba, "baixar", baixar)
    ba.coletar_proposicoes(None, DEPUTADOS)
    gravado = comum.ler(tmp_path / f"materias_{ano}.json")
    assert set(gravado["materias"]) == {f"PL-1-{ano}", f"PEC-4-{ano}"}
    m = gravado["materias"][f"PL-1-{ano}"]
    assert m["idsDeputados"] == ["910629", "921263"] and m["idsAutores"] == m["idsDeputados"] and m["tipoDescricao"] == "Projeto de Lei"
    assert m["dataApresentacao"] == "2025-02-10" and m["ementa"] == "Dispõe sobre algo" and m["situacao"] == "11/02/2025 - Aprovado em plenário"
    assert m["fonte"] == f"{ba.PROPOSICAO}/PL.-1-{ano}" and m["linkTexto"] == "https://x/t.pdf"
    assert gravado["materias"][f"PEC-4-{ano}"]["ementa"] == "da lista" and gravado["materias"][f"PEC-4-{ano}"]["tipoDescricao"] == "Proposta de Emenda à Constituição"
    assert set(gravado["vistas"]) == {f"PL-1-{ano}", f"PL-2-{ano}", f"PEC-4-{ano}"} and gravado["fonte"] == ba.PROPOSICOES
    err = avisos(capsys)
    assert "BA: proposição PL.-3-" in err and "autores sem deputado da lista (1): ['PODER EXECUTIVO']" in err


def test_coletar_proposicoes_preserva_guardado_quando_nao_rele_ou_a_releitura_falha(tmp_path, monkeypatch, capsys):
    ano = date.today().year
    hoje = date.today().isoformat()
    antigo_a, antigo_b = {"numero": 1, "marca": "a"}, {"numero": 2, "marca": "b"}
    (tmp_path / f"materias_{ano}.json").write_text(json.dumps({"coletadoEm": hoje, "materias": {f"PL-1-{ano}": antigo_a, f"PL-2-{ano}": antigo_b},
                                                              "vistas": {f"PL-1-{ano}": hoje, f"PL-2-{ano}": "2020-01-01"}}), encoding="utf-8")
    lista = {i["slug"]: i for i in (item_lista(1, ano), item_lista(2, ano), item_lista(5, ano))}
    lidos = []

    def baixar(s, url, *a, **k):
        lidos.append(url.rsplit("/", 1)[1])
        if url.endswith(f"PL.-2-{ano}"):
            raise RuntimeError("fora do ar")
        return detalhe_html("DEPUTADO ADOLFO MENEZES")

    monkeypatch.setattr(ba, "PASTA", tmp_path)
    monkeypatch.setattr(ba, "listar_proposicoes", lambda s: lista)
    monkeypatch.setattr(ba, "baixar", baixar)
    ba.coletar_proposicoes(None, DEPUTADOS)
    assert sorted(lidos) == [f"PL.-2-{ano}", f"PL.-5-{ano}"]
    gravado = comum.ler(tmp_path / f"materias_{ano}.json")
    assert gravado["materias"][f"PL-1-{ano}"] == antigo_a and gravado["materias"][f"PL-2-{ano}"] == antigo_b
    assert gravado["materias"][f"PL-5-{ano}"]["idsDeputados"] == ["910629"]
    assert gravado["vistas"] == {f"PL-1-{ano}": hoje, f"PL-2-{ano}": "2020-01-01", f"PL-5-{ano}": hoje}
    assert f"BA: proposição PL.-2-{ano}: fora do ar" in avisos(capsys)


def test_itens_emendas_sem_par_sem_ano_e_valores():
    texto = ("Nome do Deputado;Ano Exercício;Ação do Programa;Órgão;Unidade Orçamentária;NUM_CODIGO;Valor Orçado Atual;Valor Empenhado;Valor Liquidado;Valor Pago\n"
             "Adolfo  Menezes;2025;Obra  X;SEC;UO 1;123;1.000,00;500,50;400,00;300,00\n"
             "Fulano Qualquer;2025;Obra Y;SEC;UO 1;124;1,00;1,00;1,00;1,00\n"
             "Adolfo Menezes;;Obra Z;SEC;UO 1;125;1,00;1,00;1,00;1,00\n"
             "Alex da Piatã;2024;;;;;;;;\n")
    por_ano, sem_par = ba.itens_emendas(texto, DEPUTADOS)
    assert sem_par == {"Fulano Qualquer"} and sorted(por_ano) == [2024, 2025]
    item = por_ano[2025][0]
    assert item == {"idDeputado": "910629", "ano": 2025, "objeto": "Obra X", "orgao": "SEC", "unidade": "UO 1", "numero": "123", "orcado": 1000.0,
                    "empenhado": 500.5, "liquidado": 400.0, "pago": 300.0, "fonte": ba.EMENDAS_PAGINA}
    assert por_ano[2024][0]["objeto"] is None and por_ano[2024][0]["numero"] is None and por_ano[2024][0]["pago"] is None
    assert ba.itens_emendas("", DEPUTADOS) == ({}, set())


def zip_emendas(**arquivos):
    mini = io.BytesIO()
    with zipfile.ZipFile(mini, "w") as z:
        for nome, conteudo in arquivos.items():
            z.writestr(nome, conteudo)
    return mini.getvalue()


def pacote_ckan(*recursos):
    return json.dumps({"result": {"resources": list(recursos)}}).encode()


def test_coletar_emendas_zip_sem_csv_levanta_sem_gravar(tmp_path, monkeypatch):
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    zip_bytes = zip_emendas(**{"outro.csv": "x"})
    monkeypatch.setattr(ba, "baixar_ckan", lambda s, url, *a, **k: pacote_ckan({"format": "ZIP", "url": "u"}) if url == ba.EMENDAS_API else zip_bytes)
    with pytest.raises(KeyError):
        ba.coletar_emendas(None, DEPUTADOS)
    assert list(tmp_path.iterdir()) == []


def test_coletar_emendas_pacote_sem_zip_levanta_e_nao_baixa_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    pedidos = []
    monkeypatch.setattr(ba, "baixar_ckan", lambda s, url, *a, **k: pedidos.append(url) or pacote_ckan({"format": "CSV", "url": "u"}))
    with pytest.raises(RuntimeError, match="sem recurso ZIP"):
        ba.coletar_emendas(None, DEPUTADOS)
    assert pedidos == [ba.EMENDAS_API]


def test_coletar_emendas_avisa_sem_par(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    zip_bytes = zip_emendas(**{ba.EMENDAS_CSV: amostra("estadual_ba_emendas")["csv"], ba.PAGAMENTOS_CSV: amostra("estadual_ba_emendas")["pagamentos"]})
    monkeypatch.setattr(ba, "baixar_ckan", lambda s, url, *a, **k: pacote_ckan({"format": "zip", "url": "u"}) if url == ba.EMENDAS_API else zip_bytes)
    ba.coletar_emendas(None, [])
    assert list(tmp_path.iterdir()) == []
    assert "BA: emendas sem deputado atual" in avisos(capsys)


def test_listar_sessoes_varre_cada_ano(monkeypatch):
    def pagina(ano):
        return (f'<td width="100"><span>1º</span></td><td><span>Ordinária</span></td><td><span>10/06/{ano}</span></td>'
                f'<a href="/atividade-legislativa/frequencia-sessao/{ano}">x</a>')

    chamadas = []

    def baixar(s, url, params=None, **k):
        ano = int(params["dataInicio"][:4])
        chamadas.append((ano, params["page"]))
        return pagina(ano).encode()

    monkeypatch.setattr(ba, "baixar", baixar)
    achadas = ba.listar_sessoes(None, 2024, date(2025, 8, 1))
    assert list(achadas) == ["2024", "2025"] and achadas["2025"]["data"] == "2025-06-10"
    assert chamadas == [(2024, 0), (2024, 1), (2025, 0), (2025, 1)]
    assert ba.listar_sessoes(None, 2026, date(2025, 8, 1)) == {}


def configurar_presenca(monkeypatch, tmp_path, sessoes, paginas):
    lidos = []

    def baixar(s, url, *a, **k):
        lidos.append(url.rsplit("/", 1)[1])
        valor = paginas[lidos[-1]]
        if isinstance(valor, Exception):
            raise valor
        return valor

    monkeypatch.setattr(ba, "PASTA", tmp_path)
    monkeypatch.setattr(ba, "listar_sessoes", lambda s, desde, hoje: sessoes)
    monkeypatch.setattr(ba, "baixar", baixar)
    return lidos


def test_coletar_presenca_sessao_com_falha_nao_entra_em_lidas(tmp_path, monkeypatch, capsys):
    sessoes = {"1": {"id": "1", "data": "2025-06-10"}, "2": {"id": "2", "data": "2025-06-11"}}
    configurar_presenca(monkeypatch, tmp_path, sessoes, {"1": pagina_frequencia("10/06/2025", [("Adolfo Menezes", "Sim")]), "2": RuntimeError("fora do ar")})
    ba.coletar_presenca(None, DEPUTADOS)
    assert comum.ler(tmp_path / "presenca.json")["lidas"] == {"1": "2025-06-10"}
    assert "BA: frequência da sessão 2: fora do ar" in avisos(capsys)


def test_coletar_presenca_sem_sessoes_novas_nao_baixa_e_mantem_contagem(tmp_path, monkeypatch):
    sessoes = {"1": {"id": "1", "data": "2025-06-10"}}
    lidos = configurar_presenca(monkeypatch, tmp_path, sessoes, {})
    (tmp_path / "presenca.json").write_text(json.dumps({"lidas": {"1": "2025-06-10"}, "itens": [
        {"idDeputado": "910629", "periodo": "2025", "presente": 3, "ausente": 1}]}), encoding="utf-8")
    ba.coletar_presenca(None, DEPUTADOS)
    arq = comum.ler(tmp_path / "presenca.json")
    assert lidos == [] and arq["lidas"] == {"1": "2025-06-10"}
    assert (arq["itens"][0]["presente"], arq["itens"][0]["ausente"]) == (3, 1)


def test_coletar_presenca_nenhuma_sessao_lida_levanta(tmp_path, monkeypatch):
    configurar_presenca(monkeypatch, tmp_path, {}, {})
    with pytest.raises(RuntimeError, match="nenhuma sessão lida"):
        ba.coletar_presenca(None, DEPUTADOS)


def test_coletar_presenca_prazo_esgotado_guarda_o_lido_e_avisa(tmp_path, monkeypatch, capsys):
    sessoes = {"1": {"id": "1", "data": "2025-06-10"}, "2": {"id": "2", "data": "2025-06-11"}}
    configurar_presenca(monkeypatch, tmp_path, sessoes, {"1": comum.PrazoEsgotado("prazo de coleta esgotado"), "2": comum.PrazoEsgotado("prazo de coleta esgotado")})
    (tmp_path / "presenca.json").write_text(json.dumps({"lidas": {"0": "2025-06-01"}, "itens": []}), encoding="utf-8")
    ba.coletar_presenca(None, DEPUTADOS)
    assert comum.ler(tmp_path / "presenca.json")["lidas"] == {"0": "2025-06-01"}
    assert "prazo esgotado na presença" in avisos(capsys)


def test_coletar_contratos_rele_ano_corrente_e_nao_regrava_ano_encerrado(tmp_path, monkeypatch):
    ano = date.today().year
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    paginas = {0: {"a": {"inicio": "2023-05-01"}, "b": {"inicio": f"{ano}-01-02"}}, 1: {}}
    monkeypatch.setattr(ba, "baixar", lambda s, url, params=None, **k: str(params["page"]).encode())
    monkeypatch.setattr(ba, "contratos_da_pagina", lambda html: paginas[int(html)])
    (tmp_path / "orgao_2023.json").write_text('{"itens":{"velho":1}}', encoding="utf-8")
    (tmp_path / f"orgao_{ano}.json").write_text('{"coletadoEm":"2020-01-01","itens":{"velho":1}}', encoding="utf-8")
    ba.coletar_contratos(None)
    assert comum.ler(tmp_path / "orgao_2023.json") == {"itens": {"velho": 1}}
    atual = comum.ler(tmp_path / f"orgao_{ano}.json")
    assert atual["itens"] == {"b": {"inicio": f"{ano}-01-02"}} and atual["coletadoEm"] == date.today().isoformat()


def test_normas_da_verba_pagina_sem_normas_e_regras_levantam(tmp_path, monkeypatch):
    assert ba.normas_da_verba("<html></html>") == []
    monkeypatch.setattr(ba, "PASTA", tmp_path)
    monkeypatch.setattr(ba, "baixar", lambda s, url, *a, **k: b"<html></html>")
    with pytest.raises(RuntimeError, match="nenhuma norma"):
        ba.coletar_regras(None)
    assert list(tmp_path.iterdir()) == []


ETAPAS_BA = ["coletar_verba", "coletar_proposicoes", "coletar_emendas", "coletar_presenca", "coletar_contratos", "coletar_regras"]


def test_coletar_roda_etapas_na_ordem_e_isola_erro(monkeypatch, capsys):
    chamadas = []
    monkeypatch.setattr(ba.comum, "sessao", lambda: "sessao")
    monkeypatch.setattr(ba, "coletar_deputados", lambda s: chamadas.append(("deputados", (s,))) or ["dep"])
    for nome in ETAPAS_BA:
        def etapa(*args, nome=nome):
            chamadas.append((nome, args))
            if nome == "coletar_emendas":
                raise RuntimeError("ckan fora")

        monkeypatch.setattr(ba, nome, etapa)
    ba.coletar()
    assert [c[0] for c in chamadas] == ["deputados"] + ETAPAS_BA
    assert chamadas[1][1] == ("sessao", ["dep"]) and chamadas[5][1] == ("sessao",) and chamadas[6][1] == ("sessao",)
    assert "BA: emendas: ckan fora" in avisos(capsys)


def test_coletar_sem_deputados_nao_roda_etapas(monkeypatch):
    chamadas = []
    monkeypatch.setattr(ba.comum, "sessao", lambda: "sessao")

    def sem_deputados(s):
        raise RuntimeError("página de deputados sem cartões")

    monkeypatch.setattr(ba, "coletar_deputados", sem_deputados)
    monkeypatch.setattr(ba, "coletar_verba", lambda *a: chamadas.append("verba"))
    with pytest.raises(RuntimeError, match="sem cartões"):
        ba.coletar()
    assert chamadas == []
