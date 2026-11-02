"""Coletor da Assembleia da Bahia (scripts/coletar_estadual_ba.py) contra amostras reais em tests/fixtures/contratos/."""
import io
import json
import zipfile
from datetime import date

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
