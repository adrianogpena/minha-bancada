import json
from datetime import date

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
