import json
from datetime import date

import pytest

import coletar_estadual_pa as pa
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

DEPUTADOS = [
    {"id": "1024", "nome": "Adriano Coelho", "nomeCivil": "Marco Adriano Alburquerque Coelho"},
    {"id": "1011", "nome": "Ana Cunha", "nomeCivil": "Ana Cunha da Silva"},
    {"id": "1030", "nome": "Delegado Nilton Neves", "nomeCivil": "Nilton Neves"},
    {"id": "1040", "nome": "Dr Wanderlan", "nomeCivil": "Wanderlan Quaresma"},
]


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_parse_cartoes_do_contrato():
    pagina = pa.parse_cartoes(amostra("estadual_pa_frequencia")["trecho"])
    assert pagina["totalSessoes"] == 4
    assert pagina["deputados"][0] == {
        "id": "1024", "nome": "Adriano Coelho", "partido": "MDB",
        "foto": "https://alepa.quartertec.com.br/Content/Portal/PerfilAgentePolitico/DEPUTADO_Adriano%20Coelho.png",
        "ficha": "https://alepa.pa.gov.br/Institucional/Deputado/1024", "presente": 3, "licenciado": 1, "ausente": 0}
    assert pa._conferir_frequencia(amostra("estadual_pa_frequencia")) == ([], [])


def test_parse_cartoes_deputado_sem_ficha():
    html = ("card-frequencia-deputados\"><div><img src=\"x.png\" /><h3><b>Fulano (PL)</b></h3>"
            "<p><b>Presente: </b>1</p><p><b>Licenciado: </b>0</p><p><b>Ausente: </b>2</p></div>")
    d = pa.parse_cartoes(html)["deputados"][0]
    assert d["id"] is None and d["ficha"] is None and d["ausente"] == 2
    assert pa.id_deputado(d) == "sem-fulano"


def test_parse_ficha_do_contrato():
    a = amostra("estadual_pa_ficha")
    assert pa.parse_ficha(a["trecho"] + a["email"]) == {"nomeCivil": "Marco Adriano Alburquerque Coelho", "email": "dep.adrianocoelho@alepa.pa.gov.br"}
    assert pa._conferir_ficha(a) == ([], [])


def test_itens_presenca():
    pagina = {"totalSessoes": 4, "deputados": [{"id": "1024", "nome": "Adriano Coelho", "presente": 3, "licenciado": 1, "ausente": 0}]}
    assert pa.itens_presenca(pagina, 2026, 9) == [{"idDeputado": "1024", "periodo": "2026-09", "presente": 3, "ausente": 0, "licenca": 1,
                                                   "totalSessoes": 4, "fonte": pa.FREQUENCIA_URL}]


def test_linhas_dashboard_do_contrato():
    a = amostra("estadual_pa_verba_indenizatoria")
    linhas = pa.linhas_dashboard(a["DataStorageDTO"])
    assert linhas[0]["deputado"] == "Ana Cunha" and linhas[0]["data"] == "2026-10-21" and linhas[0]["conta"] == "INDENIZACAO DE TRANSPORTE"
    assert sorted(linha["valor"] for linha in linhas) == [1607.86, 4238.89]
    assert pa._conferir_dashboard(a) == ([], [])


def test_recortar_dto_mantem_so_celulas_pedidas():
    dto = {"EncodeMaps": {"DataItem1": ["2026-01-02T00:00:00", "2026-01-03T00:00:00"], "DataItem0": ["A", "B"]},
           "Slices": [{"KeyIds": ["DataItem1", "DataItem0"], "ValueIds": {"DataItem3": 0}, "Data": {"[1,1]": {"0": 5.0}, "[0,0]": {"0": 7.0}, "[1,0]": {"0": 9.0}}}]}
    menor = pa.recortar_dto(dto, 2)
    assert pa.linhas_dashboard(menor) == [{"data": "2026-01-02", "deputado": "A", "conta": None, "descricao": None, "valor": 7.0},
                                          {"data": "2026-01-03", "deputado": "B", "conta": None, "descricao": None, "valor": 5.0}]


def test_itens_verba_e_diarias_filtram_ano_e_deputado():
    linhas = [{"data": "2026-03-05", "deputado": "Ana Cunha", "conta": "INDENIZACOES", "descricao": "X", "valor": 10.0},
              {"data": "2025-03-05", "deputado": "Ana Cunha", "conta": "INDENIZACOES", "descricao": "Y", "valor": 20.0},
              {"data": "2026-03-05", "deputado": "Desconhecido", "conta": "INDENIZACOES", "descricao": "Z", "valor": 30.0}]
    ids = pa.ligar({linha["deputado"] for linha in linhas}, DEPUTADOS)
    verba = pa.itens_verba(linhas, ids, 2026)
    assert [(i["idDeputado"], i["mes"], i["valor"], i["fonte"]) for i in verba] == [("1011", 3, 10.0, pa.VERBA_PAGINA)]
    diarias = pa.itens_diarias(linhas, ids, 2026)
    assert [(i["idDeputado"], i["data"], i["motivo"], i["fonte"]) for i in diarias] == [("1011", "2026-03-05", "X", pa.DIARIAS_PAGINA)]


def test_ligar_casa_abreviaturas_e_titulos():
    ligados = pa.ligar(["ADRIANO COELHO", "DELEG. NILTON NEVES", "DR. WANDERLAN", "SEM PAR"], DEPUTADOS)
    assert ligados == {"ADRIANO COELHO": "1024", "DELEG. NILTON NEVES": "1030", "DR. WANDERLAN": "1040"}


def test_parse_gabinetes_do_contrato():
    a = amostra("estadual_pa_verba_gabinete")
    gabinetes = pa.parse_gabinetes(a["html"])
    assert gabinetes[0] == {"gabinete": "ADRIANO COELHO", "referencia": "Setembro/2026", "assessores": 48, "total": 122069.17}
    itens = pa.itens_gabinete(gabinetes, pa.ligar({g["gabinete"] for g in gabinetes}, DEPUTADOS), 2026, 9)
    assert itens[0]["idDeputado"] == "1024" and itens[0]["valor"] == 122069.17 and itens[0]["fonte"] == pa.GABINETE_PAGINA
    assert pa._conferir_gabinete(a) == ([], [])


def test_meses_ate():
    assert list(pa.meses_ate(date(2023, 4, 10))) == [(2023, 2), (2023, 3), (2023, 4)]


class Resposta:
    def __init__(self, texto="", dados=None, ok=True):
        self.text, self._dados, self.ok = texto, dados, ok

    def raise_for_status(self):
        pass

    def json(self):
        return self._dados


class Sessao:
    def __init__(self, tabela_presenca, dto, gabinete_html):
        self.tabela_presenca, self.dto, self.gabinete_html = tabela_presenca, dto, gabinete_html

    def get(self, url, params=None, timeout=None):
        if url == pa.FREQUENCIA_URL:
            return Resposta(self.tabela_presenca)
        if url == pa.DASHBOARD_URL:
            return Resposta(dados={"ItemData": {"DataStorageDTO": self.dto}})
        if url == pa.NORMAS_API:
            return Resposta(dados={"status": True, "total": 0, "resultados": []})
        return Resposta("<span>Nome completo: <b>Marco Adriano</b></span>mailto:a@b.c")

    def post(self, url, data=None, timeout=None):
        if url == pa.FREQUENCIA_URL:
            return Resposta(self.tabela_presenca)
        return Resposta(self.gabinete_html)


def test_coletar_grava_arquivos(tmp_path, monkeypatch):
    trecho = amostra("estadual_pa_frequencia")["trecho"]
    dto = amostra("estadual_pa_verba_indenizatoria")["DataStorageDTO"]
    gabinete = amostra("estadual_pa_verba_gabinete")["html"]
    sessao = Sessao(trecho, dto, f"<table>{gabinete}</table>")
    monkeypatch.setattr(comum, "DADOS", tmp_path)
    monkeypatch.setattr(comum, "sessao", lambda: sessao)
    monkeypatch.setattr(pa, "PRIMEIRO_MES", (date.today().year, date.today().month))
    monkeypatch.setattr(pa, "PRIMEIRO_ANO", date.today().year)
    monkeypatch.setattr(pa.time, "sleep", lambda _s: None)
    pa.coletar()
    pasta = tmp_path / "PA"
    deputados = json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))["deputados"]
    assert [d["id"] for d in deputados] == ["1024", "1011"] and deputados[0]["nomeCivil"] == "Marco Adriano"
    presenca = json.loads((pasta / "presenca.json").read_text(encoding="utf-8"))["itens"]
    assert {i["idDeputado"] for i in presenca} == {"1024", "1011"} and presenca[0]["totalSessoes"] == 4
    ano = date.today().year
    verbas = json.loads((pasta / f"verbas_{ano}.json").read_text(encoding="utf-8"))["itens"]
    assert any(i["idDeputado"] == "1011" and i["valor"] == 4238.89 for i in verbas)
    assert (pasta / f"diarias_{ano}.json").exists()


def lista_html(*pares):
    return "".join(f"<a class='pauta-item-title' href='/Legislativo/DetalhesVotacaoNominal?IdProposicao={p}&IdVotacao={v}'>27/10/2026 - PROJETO DE LEI N º 5/2026 - 1º TURNO</a>"
                   f"<a class='download-button' href='/Legislativo/DetalhesVotacaoNominal?IdProposicao={p}&IdVotacao={v}&type=DOC'>x</a>" for p, v in pares)


def test_parse_votacao_do_contrato():
    a = amostra("estadual_pa_votacao_nominal")
    assert pa.parse_lista_votacoes(a["lista"]) == [{"idProposicao": "16339", "idVotacao": "8869", "data": "2026-10-27",
                                                    "titulo": "PROJETO DE LEI COMPLEMENTAR N º 10/2026 - 1º TURNO"}]
    lido = pa.parse_votacao(a["detalhe"])
    assert lido["resultado"] == "APROVADA" and lido["turno"] == "1º TURNO" and lido["data"] == "2026-10-27" and lido["sessaoNumero"] == "29"
    assert lido["votos"]["SIM"][0] == ["ANDRÉIA XARÃO", "MDB"] and lido["votos"]["NAO VOTARAM"][0] == ["ADRIANO COELHO", "MDB"]
    assert lido["quantidades"] == {"SIM": 25, "NAO": 0, "ABSTENCAO": 0, "NAO VOTARAM": 16}
    assert pa._conferir_votacao(a) == ([], [])


def test_votacao_gravada_id_estavel_e_voto_sem_par_fora():
    a = amostra("estadual_pa_votacao_nominal")
    item = pa.parse_lista_votacoes(a["lista"])[0]
    lido = pa.parse_votacao(a["detalhe"])
    ligacao = pa.ligar({n for lista in lido["votos"].values() for n, _ in lista}, DEPUTADOS)
    vid, votacao, materia = pa.votacao_gravada(lido, item, ligacao)
    assert vid == pa.votacao_gravada(lido, item, ligacao)[0] and vid.startswith("vot_") and votacao["idMateria"] == vid
    assert votacao["votos"] == [["1011", "não votou"], ["1024", "não votou"]]
    assert (votacao["sim"], votacao["nao"], votacao["aprovada"], votacao["idProposicao"], votacao["idVotacao"]) == (25, 0, True, "16339", "8869")
    assert votacao["fonte"] == pa.VOTACAO_URL.format("16339", "8869")
    assert materia == {"tipo": "PLC", "tipoDescricao": "Projeto de lei complementar (1º turno)", "numero": 10, "ano": 2026, "ementa": None}


def test_votacoes_dos_meses_incremental(monkeypatch):
    detalhe = amostra("estadual_pa_votacao_nominal")["detalhe"]
    listas = {(2026, 9): lista_html(("1", "10")), (2026, 10): lista_html(("1", "10"), ("2", "20")), (2026, 11): ""}
    pedidos = {"listas": [], "detalhes": []}

    def lista(_s, ano, mes):
        pedidos["listas"].append((ano, mes))
        return listas.get((ano, mes), "")

    def detalhe_de(_s, item):
        pedidos["detalhes"].append(item["idVotacao"])
        return detalhe

    class S:
        def get(self, *a, **k):
            return Resposta()

    monkeypatch.setattr(pa, "consulta_lista_votacoes", lista)
    monkeypatch.setattr(pa, "consulta_votacao", detalhe_de)
    monkeypatch.setattr(pa, "PRIMEIRO_MES", (2026, 8))
    monkeypatch.setattr(pa.time, "sleep", lambda _s: None)
    salvos = []
    votos, materias, estado = pa.votacoes_dos_meses(S(), DEPUTADOS, {}, date(2026, 10, 31), lambda *a: salvos.append(a))
    assert pedidos == {"listas": [(2026, 8), (2026, 9), (2026, 10)], "detalhes": ["10", "10", "20"]}
    assert len(votos) == 2 and set(materias) == set(votos) and len(salvos) == 3
    assert estado["2026-10"]["lidas"] == ["1|10", "2|20"]

    pedidos["listas"].clear(), pedidos["detalhes"].clear()
    listas[(2026, 10)] = lista_html(("1", "10"), ("2", "20"), ("3", "30"))
    votos2, _, estado2 = pa.votacoes_dos_meses(S(), DEPUTADOS, {"votacoes": votos, "materias": materias, "meses": estado}, date(2026, 11, 1))
    assert pedidos == {"listas": [(2026, 10), (2026, 11)], "detalhes": ["30"]}
    assert len(votos2) == 3 and set(estado2) == {"2026-08", "2026-09", "2026-10", "2026-11"}


def test_parse_pautas_e_atas_do_contrato():
    registro = amostra("estadual_pa_pautas_atas")
    pauta = pa.parse_pautas("ordem-do-dia", registro["ordem-do-dia"])[0]
    assert pauta["tipo"] == "ordem-do-dia" and pauta["data"] and pauta["id"].isdigit()
    assert pauta["arquivos"][0]["url"] == f"https://alepa.pa.gov.br/Legislativo/DetalhesPauta?Id={pauta['id']}"
    ata = pa.parse_pautas("atas", registro["atas"])[0]
    assert ata["arquivos"][0]["url"] == f"https://downloads.alepa.pa.gov.br/Ata/{ata['id']}.PDF"
    assert pa._conferir_pautas(registro) == ([], [])


def html_pauta(*itens):
    return "".join(f"<a class='pauta-item-title' target='_blank' href='https://downloads.alepa.pa.gov.br/Ata/{i}.PDF'>{d} - ATA DA {i} SESSÃO</a>"
                   f"<a class='download-button' href='https://downloads.alepa.pa.gov.br/Ata/{i}.PDF'>x</a>" for i, d in itens)


def test_pautas_do_ano_incremental(monkeypatch):
    meses = {(2026, 8): html_pauta((1, "04/08/2026")), (2026, 9): html_pauta((2, "01/09/2026")), (2026, 10): html_pauta((3, "06/10/2026"))}
    pedidos = []

    def consulta(_s, tipo, ano, mes):
        pedidos.append((tipo, ano, mes))
        return meses.get((ano, mes), "") if tipo == "atas" else ""

    class S:
        def get(self, *a, **k):
            return Resposta()

    monkeypatch.setattr(pa, "consulta_pautas", consulta)
    monkeypatch.setattr(pa.time, "sleep", lambda _s: None)
    itens, estado = pa.pautas_do_ano(S(), 2026, date(2026, 10, 31), {})
    assert len(pedidos) == 20 and set(itens) == {"atas|1", "atas|2", "atas|3"} and "atas|2026-10" in estado
    pedidos.clear()
    meses[(2026, 10)] = html_pauta((3, "06/10/2026"), (4, "27/10/2026"))
    itens2, _ = pa.pautas_do_ano(S(), 2026, date(2026, 11, 1), {"itens": itens, "meses": estado})
    assert sorted({(t, m) for t, _, m in pedidos}) == [("atas", 10), ("atas", 11), ("ordem-do-dia", 10), ("ordem-do-dia", 11)]
    assert set(itens2) == {"atas|1", "atas|2", "atas|3", "atas|4"}


def test_normas_do_tipo_parte_resposta_cheia(monkeypatch):
    todas = [str(n) for n in range(100, 175)]
    pedidos = []

    def consulta(_s, ano, tipo, numero=""):
        pedidos.append(numero)
        achados = [n for n in todas if numero in n]
        return [{"id": int(n), "numero": n, "ano": "2026", "tipo": "Lei Ordinária", "ementa": f"Lei {n}", "link_pdf": f"https://x/{n}.pdf"} for n in achados[:pa.NORMAS_LIMITE]]

    monkeypatch.setattr(pa, "consulta_normas", consulta)
    achadas = pa.normas_do_tipo(None, 2026, 3)
    assert sorted(achadas) == sorted(todas) and pedidos[0] == "" and len(pedidos) > 1
    assert achadas["100"] == {"tipo": "Lei Ordinária", "numero": "100", "ano": 2026, "ementa": "Lei 100", "link": "https://x/100.pdf", "fonte": pa.NORMAS_PAGINA}


def test_normas_do_contrato():
    registro = amostra("estadual_pa_normas")
    assert pa._conferir_normas(registro) == ([], [])
    assert pa.parse_norma({"id": 1, "numero": " "}) is None


def test_orgao_do_contrato():
    registro = amostra("estadual_pa_orgao")
    assert pa._conferir_orgao(registro) == ([], [])
    contratos = pa.itens_contratos(pa.celulas_grade(registro["contratos"]))
    atas = pa.itens_atas_registro(pa.celulas_grade(registro["licitacoes"]))
    assert contratos and atas
    assert all(i["tipo"] == "contrato" and i["cnpj"] is None and i["valor"] is None and i["fonte"] == pa.CONTRATOS_PAGINA for i in contratos.values())
    assert all(i["tipo"] == "ata_registro" and i["cnpj"] is None and i["fonte"] == pa.LICITACOES_PAGINA for i in atas.values())
    assert set(contratos) == set(pa.itens_contratos(pa.celulas_grade(registro["contratos"])))
    assert all(iid.startswith("ctr_") for iid in contratos | atas)


def test_itens_do_orgao_filtra_e_agrupa_por_ano():
    linhas = [
        {"DataItem5": 7, "DataItem1": "2026-07-30T00:00:00.0000000", "DataItem2": "Em andamento", "DataItem8": "011/2026", "DataItem4": "EMPRESA A LTDA",
         "DataItem3": "008/2026 Pregão", "DataItem0": " Licença  de software"},
        {"DataItem5": 8, "DataItem1": "2022-01-10T00:00:00.0000000", "DataItem4": "EMPRESA B", "DataItem3": "001/2022 Dispensa", "DataItem0": "x"},
        {"DataItem5": 9, "DataItem1": None, "DataItem4": "EMPRESA C"},
    ]
    contratos = pa.itens_contratos(linhas)
    assert len(contratos) == 2
    item = next(i for i in contratos.values() if i["idFonte"] == 7)
    assert (item["modalidade"], item["numeroModalidade"], item["objeto"], item["numero"]) == ("Pregão", "008/2026", "Licença de software", "011/2026")
    licitacoes = [
        {"DataItem6": "2026", "DataItem0": "Pregão", "DataItem2": "003", "DataItem1": "DISPÕE SOBRE REGISTRO DE PREÇOS PARA MEDALHAS", "DataItem9": "2026-02-27T00:00:00.0000000",
         "DataItem10": "Suspenso", "DataItem11": 128310.23, "DataItem7": "FAX LTDA"},
        {"DataItem6": "2026", "DataItem0": "Pregão", "DataItem2": "004", "DataItem1": "CONTRATAÇÃO DE SERVIÇO", "DataItem9": "2026-03-01T00:00:00.0000000", "DataItem7": "OUTRA"},
        {"DataItem6": "0", "DataItem0": "Pregão", "DataItem2": "005", "DataItem1": "REGISTRO DE PRECOS DE TINTA", "DataItem9": "2025-05-02T00:00:00.0000000", "DataItem7": "TINTAS SA"},
    ]
    atas = pa.itens_atas_registro(licitacoes)
    assert sorted(i["idFonte"] for i in atas.values()) == ["2025|Pregão|005", "2026|Pregão|003"]
    ata = next(i for i in atas.values() if i["idFonte"] == "2026|Pregão|003")
    assert (ata["valor"], ata["numeroModalidade"], ata["situacao"], ata["inicio"]) == (128310.23, "003/2026", "Suspenso", "2026-02-27")
    assert sorted(pa.orgao_por_ano(contratos | atas)) == [2025, 2026]


CSV_PESSOAL = (
    "Matricula;Nome;Admissao;Exoneracao;Cargo/Funcao;Classificacao;Lotacao;Situacao\n"
    '24201;"ABIAS DA SILVA";01/02/2019;;"FUNCAO PUB. APOIO LEGISLATIVO FPAL-04";"FUNCAO PUB. APOIO LEGISLATIVO";"10430 - GAB. DEP. GUSTAVO SEFER";Ativo\n'
    '15319;"RENATA LIMA";13/02/2017;;;Acolhidos;"10256 - GAB. DEP. ANA CUNHA";Ativo\n'
    '29661;"ANA ASSIS";01/06/2024;31/03/2025;;Estagiarios;"10430 - GAB. DEP. GUSTAVO SEFER";Inativo\n'
    '1606;"JOSE FERREIRA";02/04/1999;;"ASSESSOR LEGISLATIVO DAS-202.3";Comissionados;"88131 - GAB. DEP. TORRINHO TORRES";Ativo\n'
    '777;"MARIA EX";02/04/1999;;"ASSESSOR LEGISLATIVO DAS-202.3";Comissionados;"10358 - GAB. DEP. ELIEL FAUSTINO";Ativo\n'
    '888;"LIDER PT";02/04/1999;;"ASSESSOR DAS-202.3";Comissionados;"10001 - LIDERANCA DO PT";Ativo\n'
)

DEPUTADOS_SIGEP = [
    {"id": "1021", "nome": "Gustavo Sefer", "nomeCivil": "Gustavo Bemerguy Sefer"},
    {"id": "1011", "nome": "Ana Cunha", "nomeCivil": "Ana Maria do Socorro Magno Cunha"},
    {"id": "1037", "nome": "Torrinho", "nomeCivil": "Francisco Torres de Paula Filho"},
]


def test_pessoal_do_contrato():
    registro = amostra("estadual_pa_pessoal_gabinete")
    linhas = pa.parse_pessoal_csv(registro["csv"])
    assert linhas[0]["matricula"] == "24201" and linhas[0]["lotacao"] == "10430 - GAB. DEP. GUSTAVO SEFER" and linhas[0]["situacao"] == "Ativo"
    assert pa._conferir_pessoal_gabinete(registro) == ([], [])


def test_parse_pessoal_csv_exige_colunas():
    try:
        pa.parse_pessoal_csv("Matricula;Nome\n1;X\n")
    except RuntimeError as e:
        assert "cargo/funcao" in str(e)
    else:
        raise AssertionError("aceitou CSV sem colunas")


def test_servidores_do_gabinete_so_ativos_ligados():
    itens = pa.servidores_do_gabinete(pa.parse_pessoal_csv(CSV_PESSOAL), DEPUTADOS_SIGEP)
    assert [(i["idDeputado"], i["matricula"], i["simbolo"]) for i in itens] == [
        ("1011", "15319", "Acolhidos"), ("1021", "24201", "FPAL-04"), ("1037", "1606", "DAS-202.3")]
    assert all(i["id"].startswith("srv_") for i in itens)
    assert itens[1]["id"] == pa.ids.gerar_id("srv", "alepa_pa_sigep", "24201")
    assert pa.simbolo_do_cargo("ASSESSOR LEGISLATIVO DAS-202.3") == "DAS-202.3" and pa.simbolo_do_cargo(None) is None


class RespostaSigep:
    def __init__(self, texto):
        self.content = texto.encode("utf-8")

    def raise_for_status(self):
        pass


def tabela_servidores(*linhas):
    corpo = "".join(f'<tr><td>{m}</td><td><a href="detalhecc.php?mes=T{m}&amp;ano=A{m}&amp;mat=M{m}&amp;tipo=P{m}">{n}</a></td><td>{c}</td><td>{l}</td></tr>'
                    for m, n, c, l in linhas)
    return f"<table><tr><th>MATRÍCULA</th></tr>{corpo}</table>"


class SessaoSigep:
    def __init__(self, folhas):
        self.folhas, self.buscas, self.acessos = folhas, [], 0
        modelo = amostra("estadual_pa_remuneracao")
        self.filtros, self.detalhe = modelo["filtros"], modelo["detalhe"]

    def get(self, url, params=None, timeout=None):
        self.acessos += 1
        if url == pa.SERVIDORES_URL:
            return RespostaSigep(self.filtros)
        if url == pa.GABINETE_CSV_URL:
            return RespostaSigep(CSV_PESSOAL)
        mat = url.split("mat=M")[1].split("&")[0]
        ano, mes = self.folhas[mat]
        nome_mes = {8: "Agosto", 9: "Setembro", 10: "Outubro"}[mes]
        return RespostaSigep(self.detalhe.replace("Outubro/2026", f"{nome_mes}/{ano}"))

    def post(self, url, data=None, timeout=None):
        self.buscas.append((data["anoref"], data["mes"], data["b_nome"]))
        mes = int(data["mes"])
        homonimo = ("999", "GUSTAVO SILVA", "ANALISTA", "SECAO")
        sefer = ("081309", "GUSTAVO BEMERGUY SEFER", "DEPUTADO ESTADUAL", "PLENARIO")
        self.folhas["081309"] = (2026, mes)
        return RespostaSigep(tabela_servidores(homonimo, sefer) if "GUSTAVO" in data["b_nome"] else tabela_servidores())


def test_remuneracao_do_contrato():
    registro = amostra("estadual_pa_remuneracao")
    assert pa.ultimo_mes_publicado(registro["filtros"]) == (2026, 10)
    linhas, paginas = pa.parse_servidores(registro["lista"])
    assert linhas[0]["cargo"] == "DEPUTADO ESTADUAL" and linhas[0]["detalhe"].startswith("detalhecc.php?mes=") and "&amp;" not in linhas[0]["detalhe"]
    folha = pa.parse_detalhe(registro["detalhe"])
    assert (folha["ano"], folha["mes"]) == (2026, 10)
    assert folha["valores"]["total bruto"] == 34774.64 and folha["valores"]["total liquido"] == 25049.11 and folha["valores"]["descontos"] == 9725.53
    assert pa.componentes_remuneracao(folha["valores"]) == {"Remuneração": 34774.64, "Descontos": 9725.53}
    assert pa._conferir_remuneracao(registro) == ([], [])


def test_termos_de_busca_sem_acento_e_sem_titulo():
    termos = pa.termos_de_busca({"nome": "Dr. Wanderlán", "nomeCivil": "Wanderlan Augusto Brandão Quaresma"})
    assert termos[:2] == ["WANDERLAN AUGUSTO BRANDAO QUARESMA", "DR. WANDERLAN"] and "DR" not in termos


def test_remuneracao_do_mes_filtra_cargo_e_guarda_busca():
    sessao = SessaoSigep({})
    buscas = {}
    itens = pa.remuneracao_do_mes(sessao, 2026, 10, DEPUTADOS_SIGEP[:1], buscas)
    assert itens == [{"idDeputado": "1021", "mes": 10, "bruto": 34774.64, "liquido": 25049.11,
                      "componentes": {"Remuneração": 34774.64, "Descontos": 9725.53}, "fonte": pa.SERVIDORES_PAGINA}]
    assert buscas == {"1021": "GUSTAVO BEMERGUY SEFER"}
    assert sessao.buscas == [("26", "10", "GUSTAVO BEMERGUY SEFER")]


def test_coletar_remuneracao_incremental(tmp_path, monkeypatch):
    sessao = SessaoSigep({})
    monkeypatch.setattr(pa.time, "sleep", lambda _s: None)
    monkeypatch.setattr(comum, "arquivo_tse", lambda uf: tmp_path / "sem_tse.json")
    monkeypatch.setattr(pa, "PRIMEIRO_MES_REMUNERACAO", (2026, 8))
    pasta = tmp_path / "PA"
    pa.coletar_remuneracao(sessao, pasta, DEPUTADOS_SIGEP[:1], date(2026, 11, 1), "2026-11-01")
    arq = json.loads((pasta / "remuneracao_2026.json").read_text(encoding="utf-8"))
    assert [i["mes"] for i in arq["itens"]] == [8, 9, 10] and set(arq["meses"]) == {"2026-08", "2026-09", "2026-10"}
    assert arq["buscas"] == {"1021": "GUSTAVO BEMERGUY SEFER"}
    sessao.buscas.clear()
    pa.coletar_remuneracao(sessao, pasta, DEPUTADOS_SIGEP[:1], date(2026, 11, 2), "2026-11-02")
    assert sorted(m for _, m, _ in sessao.buscas) == ["09", "10"]
    arq = json.loads((pasta / "remuneracao_2026.json").read_text(encoding="utf-8"))
    assert [i["mes"] for i in arq["itens"]] == [8, 9, 10] and arq["meses"]["2026-08"] == "2026-11-01" and arq["meses"]["2026-10"] == "2026-11-02"


def test_coletar_gabinete_grava_foto(tmp_path):
    pasta = tmp_path / "PA"
    pa.coletar_gabinete(SessaoSigep({}), pasta, DEPUTADOS_SIGEP, "2026-11-01")
    env = json.loads((pasta / "gabinete.json").read_text(encoding="utf-8"))
    assert env["fonte"] == pa.PESSOAL_PAGINA and len(env["itens"]) == 3


def test_ligar_nome_de_urna_com_sobrenome_a_mais():
    deputados = [{"id": "1037", "nome": "Torrinho", "nomeCivil": "Francisco Torres de Paula Filho"},
                 {"id": "1038", "nome": "Torres", "nomeCivil": "Pedro Torres"}]
    assert pa.ligar(["TORRINHO TORRES", "TORRINHO"], deputados) == {"TORRINHO TORRES": "1037", "TORRINHO": "1037"}


class RespostaHttp:
    def __init__(self, texto="", dados=None, status=200):
        self.text, self._dados, self.status_code = texto, dados, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._dados


class SessaoHttp:
    def __init__(self, resposta):
        self.resposta = resposta
        self.chamadas = []

    def get(self, url, **kw):
        self.chamadas.append(("GET", url, kw))
        return self.resposta

    def post(self, url, **kw):
        self.chamadas.append(("POST", url, kw))
        return self.resposta


def test_mes_anterior_vira_o_ano():
    assert pa.mes_anterior(2026, 1) == (2025, 12) and pa.mes_anterior(2026, 5) == (2026, 4)


def test_consulta_lista_votacoes_e_votacao_montam_a_requisicao():
    s = SessaoHttp(RespostaHttp("<html/>"))
    assert pa.consulta_lista_votacoes(s, 2026, 10) == "<html/>"
    metodo, url, kw = s.chamadas[0]
    assert (metodo, url) == ("POST", pa.VOTACOES_LISTA_URL) and kw["data"] == {"__DXCallbackName": "cbpPautas", "__DXCallbackArgument": "c0:", "ano": "2026", "mes": "10"}
    assert pa.consulta_votacao(s, {"idProposicao": "16339", "idVotacao": "8869"}) == "<html/>"
    assert s.chamadas[1][:2] == ("GET", pa.VOTACAO_URL.format("16339", "8869"))
    with pytest.raises(RuntimeError, match="HTTP 500"):
        pa.consulta_lista_votacoes(SessaoHttp(RespostaHttp(status=500)), 2026, 10)
    with pytest.raises(RuntimeError, match="HTTP 404"):
        pa.consulta_votacao(SessaoHttp(RespostaHttp(status=404)), {"idProposicao": "1", "idVotacao": "2"})


def test_consulta_frequencia_e_gabinete_enviam_ano_e_mes():
    s = SessaoHttp(RespostaHttp("<tabela/>"))
    assert pa.consulta_frequencia(s, 2026, 9) == "<tabela/>"
    assert s.chamadas[0][1] == pa.FREQUENCIA_URL and s.chamadas[0][2]["data"] == {"__DXCallbackName": "cbpFrequencia", "__DXCallbackArgument": "c0:", "ano": "2026", "mes": "9", "tipoSessao": "0"}
    assert pa.consulta_gabinete(s, 2026, 9) == "<tabela/>"
    assert s.chamadas[1][1] == pa.GABINETE_URL and s.chamadas[1][2]["data"] == {"anoref": "26", "mes": "09"}
    with pytest.raises(RuntimeError, match="HTTP 502"):
        pa.consulta_frequencia(SessaoHttp(RespostaHttp(status=502)), 2026, 9)


def test_consulta_pautas_usa_a_url_e_o_callback_de_cada_tipo():
    s = SessaoHttp(RespostaHttp("<a/>"))
    assert pa.consulta_pautas(s, "atas", 2026, 3) == "<a/>"
    assert pa.consulta_pautas(s, "ordem-do-dia", 2026, 12) == "<a/>"
    assert s.chamadas[0][1] == pa.PAUTAS["atas"][1] and s.chamadas[0][2]["data"] == {"__DXCallbackName": "cbpAtas", "__DXCallbackArgument": "c0:", "ano": "2026", "mes": "3"}
    assert s.chamadas[1][1] == pa.PAUTAS["ordem-do-dia"][1] and s.chamadas[1][2]["data"]["__DXCallbackName"] == "cbpPautas"
    with pytest.raises(RuntimeError, match="HTTP 500"):
        pa.consulta_pautas(SessaoHttp(RespostaHttp(status=500)), "atas", 2026, 3)


def test_consulta_normas_devolve_resultados_e_levanta_com_status_falso(monkeypatch):
    monkeypatch.setattr(pa.time, "sleep", lambda s: None)
    s = SessaoHttp(RespostaHttp(dados={"status": True, "resultados": [{"id": 1}]}))
    assert pa.consulta_normas(s, 2026, 3, "12") == [{"id": 1}]
    assert s.chamadas[0][1] == pa.NORMAS_API and s.chamadas[0][2]["params"] == {"ano": 2026, "tipo": 3, "numero": "12", "q": ""}
    assert pa.consulta_normas(SessaoHttp(RespostaHttp(dados={"status": True, "resultados": None})), 2026, 3) == []
    with pytest.raises(RuntimeError, match="leis.php ano=2026 tipo=3 numero=12: status falso"):
        pa.consulta_normas(SessaoHttp(RespostaHttp(dados={"status": False})), 2026, 3, "12")
    with pytest.raises(RuntimeError, match="HTTP 500"):
        pa.consulta_normas(SessaoHttp(RespostaHttp(status=500)), 2026, 3)


def test_consulta_grade_e_dashboard_leem_o_datastorage():
    dto = {"Slices": [], "EncodeMaps": {}}
    s = SessaoHttp(RespostaHttp(dados={"ItemData": {"DataStorageDTO": dto}}))
    assert pa.consulta_grade(s, pa.DASHBOARD_CONTRATOS) == dto
    assert s.chamadas[0][1] == pa.DASHBOARD_URL
    assert s.chamadas[0][2]["params"] == {"dashboardId": "dashboard52", "parameters": "[]", "itemId": "gridDashboardItem1", "query": "{}"}
    assert pa.consulta_dashboard(s, pa.DASHBOARD_VERBA, 2026) == dto
    params = s.chamadas[1][2]["params"]
    assert params["dashboardId"] == "dashboard57" and json.loads(params["query"])["Filter"][0]["values"] == [[2026]]
    with pytest.raises(RuntimeError, match="HTTP 500"):
        pa.consulta_grade(SessaoHttp(RespostaHttp(status=500)), pa.DASHBOARD_LICITACOES)
    with pytest.raises(RuntimeError, match="HTTP 403"):
        pa.consulta_dashboard(SessaoHttp(RespostaHttp(status=403)), pa.DASHBOARD_VERBA, 2026)


def test_normas_do_ano_junta_tipos_e_ordena(monkeypatch):
    tipos = []

    def consulta(_s, ano, tipo, numero=""):
        tipos.append(tipo)
        n = {1: "20", 2: "3"}.get(tipo)
        if not n:
            return []
        return [{"id": tipo, "numero": n, "ano": "2026", "tipo": "Lei Ordinária", "ementa": "x", "link_pdf": f"https://x/{n}.pdf"}]

    monkeypatch.setattr(pa, "consulta_normas", consulta)
    achadas = pa.normas_do_ano(None, 2026)
    assert tipos == list(pa.NORMAS_TIPOS) and list(achadas) == ["2", "1"]


def test_ultimo_mes_publicado_sem_filtros_levanta():
    with pytest.raises(RuntimeError, match="sem os filtros"):
        pa.ultimo_mes_publicado("<html>sem select</html>")


def test_coletar_gabinete_sem_servidor_ligado_nao_grava(tmp_path):
    with pytest.raises(RuntimeError, match="nenhum servidor ligado"):
        pa.coletar_gabinete(SessaoSigep({}), tmp_path / "PA", [], "2026-11-01")
    assert not (tmp_path / "PA" / "gabinete.json").exists()


class SessaoDuasLinhas(SessaoSigep):
    def post(self, url, data=None, timeout=None):
        self.buscas.append((data["anoref"], data["mes"], data["b_nome"]))
        mes = int(data["mes"])
        self.folhas["081309"] = (2026, mes)
        self.folhas["055"] = (2026, mes)
        if "GUSTAVO" in data["b_nome"]:
            return RespostaSigep(tabela_servidores(("081309", "GUSTAVO BEMERGUY SEFER", "DEPUTADO ESTADUAL", "PLENARIO"),
                                                  ("055", "ANA MARIA DO SOCORRO MAGNO CUNHA", "DEPUTADO ESTADUAL", "PLENARIO")))
        return RespostaSigep(tabela_servidores())


def test_remuneracao_do_mes_nao_busca_quem_ja_veio_ligado(monkeypatch):
    sessao = SessaoDuasLinhas({})
    monkeypatch.setattr(pa.time, "sleep", lambda _s: None)
    buscas = {}
    itens = pa.remuneracao_do_mes(sessao, 2026, 10, DEPUTADOS_SIGEP[:2], buscas)
    assert [i["idDeputado"] for i in itens] == ["1011", "1021"]
    assert len(sessao.buscas) == 1 and buscas == {"1021": "GUSTAVO BEMERGUY SEFER"}


def test_remuneracao_do_mes_busca_primeiro_o_termo_que_deu_certo(monkeypatch):
    sessao = SessaoSigep({})
    monkeypatch.setattr(pa.time, "sleep", lambda _s: None)
    buscas = {"1021": "GUSTAVO SEFER"}
    itens = pa.remuneracao_do_mes(sessao, 2026, 10, DEPUTADOS_SIGEP[:1], buscas)
    assert len(itens) == 1 and sessao.buscas == [("26", "10", "GUSTAVO SEFER")] and buscas == {"1021": "GUSTAVO SEFER"}


def test_remuneracao_do_mes_avisa_deputado_sem_linha_e_descarta_folha_de_outro_mes(monkeypatch, capsys):
    monkeypatch.setattr(pa.time, "sleep", lambda _s: None)
    sem_par = {"id": "9999", "nome": "Fulano Inexistente", "nomeCivil": "Fulano Inexistente Da Silva"}
    itens = pa.remuneracao_do_mes(SessaoSigep({}), 2026, 10, [DEPUTADOS_SIGEP[0], sem_par], {})
    assert [i["idDeputado"] for i in itens] == ["1021"]
    assert "AVISO: PA: remuneração 2026-10 sem linha de deputado para: Fulano Inexistente" in capsys.readouterr().err

    class Divergente(SessaoSigep):
        def post(self, url, data=None, timeout=None):
            r = super().post(url, data, timeout)
            self.folhas["081309"] = (2026, 10)
            return r

    assert pa.remuneracao_do_mes(Divergente({}), 2026, 9, [DEPUTADOS_SIGEP[0], sem_par], {}) == []
    assert capsys.readouterr().err == ""

    monkeypatch.setattr(pa, "parse_detalhe", lambda html: {"ano": 2026, "mes": 10, "valores": {"total bruto": None}})
    assert pa.remuneracao_do_mes(SessaoSigep({}), 2026, 10, DEPUTADOS_SIGEP[:1], {}) == []


def test_coletar_remuneracao_pula_ano_encerrado_e_meses_lidos(tmp_path, monkeypatch):
    sessao = SessaoSigep({})
    monkeypatch.setattr(pa.time, "sleep", lambda _s: None)
    monkeypatch.setattr(comum, "arquivo_tse", lambda uf: tmp_path / "sem_tse.json")
    monkeypatch.setattr(pa, "PRIMEIRO_MES_REMUNERACAO", (2025, 12))
    pasta = tmp_path / "PA"
    comum.salvar(pasta / "remuneracao_2025.json", {"marca": "antiga", "meses": {}, "itens": []})
    comum.salvar(pasta / "remuneracao_2026.json", {"meses": {f"2026-{m:02d}": "2026-12-01" for m in range(1, 9)}, "buscas": {"1021": "GUSTAVO SEFER"},
                                                   "itens": [{"idDeputado": "1021", "mes": 8, "bruto": 1.0, "liquido": 1.0, "componentes": {}}]})
    pa.coletar_remuneracao(sessao, pasta, DEPUTADOS_SIGEP[:1], date(2027, 1, 15), "2027-01-15")
    assert json.loads((pasta / "remuneracao_2025.json").read_text(encoding="utf-8"))["marca"] == "antiga"
    assert sorted(m for _, m, _ in sessao.buscas) == ["09", "10"] and {t for _, _, t in sessao.buscas} == {"GUSTAVO SEFER"}
    arq = json.loads((pasta / "remuneracao_2026.json").read_text(encoding="utf-8"))
    assert [i["mes"] for i in arq["itens"]] == [8, 9, 10] and arq["itens"][0]["bruto"] == 1.0


def test_coletar_remuneracao_mes_sem_deputado_levanta_e_nao_grava(tmp_path, monkeypatch):
    class SemLinhas(SessaoSigep):
        def post(self, url, data=None, timeout=None):
            return RespostaSigep(tabela_servidores())

    monkeypatch.setattr(pa.time, "sleep", lambda _s: None)
    monkeypatch.setattr(comum, "arquivo_tse", lambda uf: tmp_path / "sem_tse.json")
    monkeypatch.setattr(pa, "PRIMEIRO_MES_REMUNERACAO", (2026, 8))
    with pytest.raises(RuntimeError, match="folha de 2026-08 sem nenhum deputado; mantém o arquivo anterior"):
        pa.coletar_remuneracao(SemLinhas({}), tmp_path / "PA", DEPUTADOS_SIGEP[:1], date(2026, 11, 1), "2026-11-01")
    assert not (tmp_path / "PA" / "remuneracao_2026.json").exists()


def orgao_de_amostra(s, dashboard):
    registro = amostra("estadual_pa_orgao")
    return registro["contratos"] if dashboard == pa.DASHBOARD_CONTRATOS else registro["licitacoes"]


def test_coletar_catalogos_grava_pautas_normas_e_orgao_por_ano(tmp_path, monkeypatch, capsys):
    pasta = tmp_path / "PA"
    monkeypatch.setattr(pa, "pautas_do_ano", lambda s, ano, hoje, anterior: ({f"atas|{ano}": {"id": str(ano)}}, {f"atas|{ano}-01": "2026-11-02"}))
    monkeypatch.setattr(pa, "normas_do_ano", lambda s, ano: {"1": {"numero": "1", "ano": ano}})
    monkeypatch.setattr(pa, "consulta_grade", orgao_de_amostra)
    pa.coletar_catalogos(None, pasta, date(2026, 11, 2))
    for ano in (2025, 2026):
        assert list(json.loads((pasta / f"pautas_{ano}.json").read_text(encoding="utf-8"))["itens"]) == [f"atas|{ano}"]
        assert json.loads((pasta / f"leis_{ano}.json").read_text(encoding="utf-8"))["normas"] == {"1": {"numero": "1", "ano": ano}}
    orgaos = sorted(pasta.glob("orgao_[0-9]*.json"))
    assert orgaos and all(json.loads(p.read_text(encoding="utf-8"))["itens"] for p in orgaos)
    assert capsys.readouterr().err == ""


def test_coletar_catalogos_erros_viram_aviso_e_normas_recentes_nao_sao_relidas(tmp_path, monkeypatch, capsys):
    pasta = tmp_path / "PA"
    comum.salvar(pasta / "leis_2025.json", {"coletadoEm": "2026-01-01", "normas": {"1": {}}})
    comum.salvar(pasta / "leis_2026.json", {"coletadoEm": "2026-11-01", "normas": {"2": {}}})
    comum.salvar(pasta / "orgao_2020.json", {"itens": {"ctr_x": {}}})
    normas_lidas = []

    def normas_vazias(s, ano):
        normas_lidas.append(ano)
        return {}

    def pautas(s, ano, hoje, anterior):
        raise RuntimeError(f"HTTP 500 {ano}")

    monkeypatch.setattr(pa, "pautas_do_ano", pautas)
    monkeypatch.setattr(pa, "normas_do_ano", normas_vazias)
    monkeypatch.setattr(pa, "consulta_grade", lambda s, dashboard: {})
    monkeypatch.setattr(pa, "celulas_grade", lambda dto: [])
    pa.coletar_catalogos(None, pasta, date(2026, 11, 2))
    erro = capsys.readouterr().err
    assert normas_lidas == [2025]
    assert "AVISO: PA: pautas e atas 2025: HTTP 500 2025" in erro and "AVISO: PA: pautas e atas 2026: HTTP 500 2026" in erro
    assert "AVISO: PA: normas 2025: banco de leis devolveu lista vazia para 2025; mantém o arquivo anterior" in erro
    assert "AVISO: PA: contratos e atas de registro do órgão: dashboards devolveram lista vazia; mantém os arquivos anteriores" in erro
    assert json.loads((pasta / "leis_2025.json").read_text(encoding="utf-8"))["normas"] == {"1": {}}
    assert json.loads((pasta / "orgao_2020.json").read_text(encoding="utf-8"))["itens"] == {"ctr_x": {}}


class DataFixa(date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 2)


class SessaoRastreada(Sessao):
    def __init__(self, *a):
        super().__init__(*a)
        self.dashboards, self.meses_frequencia, self.fichas = [], [], []

    def get(self, url, params=None, timeout=None):
        if url == pa.DASHBOARD_URL:
            self.dashboards.append(params["dashboardId"])
        elif url not in (pa.FREQUENCIA_URL, pa.NORMAS_API):
            self.fichas.append(url)
        return super().get(url, params, timeout)

    def post(self, url, data=None, timeout=None):
        if url == pa.FREQUENCIA_URL:
            self.meses_frequencia.append(data["mes"])
        return super().post(url, data, timeout)


def preparar_coletar_pa(monkeypatch, tmp_path, html_frequencia):
    dto = amostra("estadual_pa_verba_indenizatoria")["DataStorageDTO"]
    gabinete = amostra("estadual_pa_verba_gabinete")["html"]
    sessao = SessaoRastreada(html_frequencia, dto, f"<table>{gabinete}</table>")
    monkeypatch.setattr(comum, "DADOS", tmp_path)
    monkeypatch.setattr(comum, "sessao", lambda: sessao)
    monkeypatch.setattr(pa, "date", DataFixa)
    monkeypatch.setattr(pa.time, "sleep", lambda _s: None)
    return sessao, tmp_path / "PA"


def test_coletar_sem_deputados_avisa_e_ainda_coleta_os_catalogos(monkeypatch, tmp_path, capsys):
    sessao, pasta = preparar_coletar_pa(monkeypatch, tmp_path, "<html></html>")
    catalogos = []
    monkeypatch.setattr(pa, "coletar_catalogos", lambda s, p, hoje: catalogos.append((p, hoje)))
    pa.coletar()
    assert "AVISO: PA: nenhum deputado na página de frequência" in capsys.readouterr().err
    assert catalogos == [(pasta, DataFixa(2026, 11, 2))] and not (pasta / "deputados.json").exists() and sessao.dashboards == []


def test_coletar_reaproveita_nome_civil_le_presenca_incremental_e_pula_ano_encerrado(monkeypatch, tmp_path):
    trecho = amostra("estadual_pa_frequencia")["trecho"]
    sessao, pasta = preparar_coletar_pa(monkeypatch, tmp_path, trecho)
    monkeypatch.setattr(pa, "PRIMEIRO_MES", (2026, 8))
    monkeypatch.setattr(pa, "PRIMEIRO_ANO", 2024)
    comum.salvar(pasta / "deputados.json", {"deputados": [{"id": "1024", "nomeCivil": "Nome Antigo", "email": "antigo@x.gov.br"}]})
    comum.salvar(pasta / "presenca.json", {"itens": [{"idDeputado": "1024", "periodo": "2026-08", "totalSessoes": 1}, {"idDeputado": "1024", "periodo": "2026-10", "totalSessoes": 1}]})
    comum.salvar(pasta / "verbas_2024.json", {"marca": "antiga", "itens": []})
    comum.salvar(pasta / "diarias_2024.json", {"marca": "antiga", "itens": []})
    chamadas = []
    monkeypatch.setattr(pa, "coletar_gabinete", lambda s, p, deputados, agora: chamadas.append(("gabinete", [d["id"] for d in deputados], agora)))
    monkeypatch.setattr(pa, "coletar_remuneracao", lambda s, p, deputados, hoje, agora: chamadas.append(("remuneracao", agora)))
    monkeypatch.setattr(pa, "votacoes_dos_meses", lambda s, deputados, anterior, hoje, gravar: chamadas.append(("votacoes", sorted(anterior))) or ({}, {}, {}))
    monkeypatch.setattr(pa, "coletar_catalogos", lambda s, p, hoje: chamadas.append(("catalogos", hoje)))
    pa.coletar()
    deputados = json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))["deputados"]
    assert deputados[0]["nomeCivil"] == "Nome Antigo" and deputados[0]["email"] == "antigo@x.gov.br" and deputados[1]["id"] == "1011"
    assert [u for u in sessao.fichas if "/Institucional/Deputado/" in u] == [pa.FICHA_URL.format("1011")]
    assert sessao.meses_frequencia == ["9", "10", "11"]
    presenca = json.loads((pasta / "presenca.json").read_text(encoding="utf-8"))["itens"]
    assert [i["periodo"] for i in presenca if i["idDeputado"] == "1024"][0] == "2026-08" and {i["periodo"] for i in presenca} == {"2026-08", "2026-09", "2026-10", "2026-11"}
    assert sorted(sessao.dashboards) == ["dashboard57", "dashboard57", "dashboard58", "dashboard58"]
    assert json.loads((pasta / "verbas_2024.json").read_text(encoding="utf-8"))["marca"] == "antiga"
    assert (pasta / "verbas_2025.json").exists() and (pasta / "diarias_2026.json").exists()
    assert chamadas == [("gabinete", ["1024", "1011"], "2026-11-02"), ("remuneracao", "2026-11-02"), ("votacoes", ["materias"]), ("catalogos", DataFixa(2026, 11, 2))]


def test_coletar_etapa_que_falha_vira_aviso_e_nao_para_as_outras(monkeypatch, tmp_path, capsys):
    trecho = amostra("estadual_pa_frequencia")["trecho"]
    sessao, pasta = preparar_coletar_pa(monkeypatch, tmp_path, trecho)
    monkeypatch.setattr(pa, "PRIMEIRO_MES", (2026, 10))
    monkeypatch.setattr(pa, "PRIMEIRO_ANO", 2026)
    chamadas = []

    def quebra(*a, **k):
        raise RuntimeError("quebrou")

    monkeypatch.setattr(pa, "coletar_gabinete", quebra)
    monkeypatch.setattr(pa, "coletar_remuneracao", quebra)
    monkeypatch.setattr(pa, "votacoes_dos_meses", quebra)
    monkeypatch.setattr(pa, "coletar_catalogos", lambda s, p, hoje: chamadas.append("catalogos"))
    pa.coletar()
    erro = capsys.readouterr().err
    assert "AVISO: PA: gabinete: quebrou" in erro and "AVISO: PA: remuneração: quebrou" in erro and "AVISO: PA: votações: quebrou" in erro
    assert chamadas == ["catalogos"] and (pasta / "presenca.json").exists()
