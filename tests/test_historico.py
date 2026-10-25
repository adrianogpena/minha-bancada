import json
import os
import subprocess

import pytest

import historico as h
import resumo_email as r
import feeds


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Repositório git de mentira com dois commits de dados, para o histórico comparar."""
    def git(*a, data=None):
        env = {**os.environ, "GIT_COMMITTER_DATE": f"{data}T12:00:00", "GIT_AUTHOR_DATE": f"{data}T12:00:00"} if data else None
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True, env=env)

    def salvar(caminho, obj):
        arq = tmp_path / caminho
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(obj), encoding="utf-8")

    git("init", "-q", "-b", "master")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    salvar("dados/proposicoes/1.json", {"itens": [{"id": 10, "siglaTipo": "PL", "numero": 1, "ano": 2026, "ementa": "Antiga"}]})
    salvar("dados/proposicoes_detalhe.json", {"10": {"situacao": "Aguardando", "tramitacao": "Apresentação", "dataSituacao": "2026-01-01"}})
    salvar("dados/estaduais/AC/deputados.json", {"host": "sapl.al.ac.leg.br", "deputados": [{"id": 28, "nome": "ANTONIA SALES"}]})
    salvar("dados/estaduais/AC/materias_2026.json", {"materias": {"5": {"ano": 2026, "numero": 1, "tipo": "PL", "tipoDescricao": "Projeto de Lei", "ementa": "Antigo", "situacao": "Em tramitação", "idsDeputados": [28], "dataApresentacao": "2026-01-02"}}})
    salvar("dados/senado_materias.json", {"7": {"situacao": "", "dataSituacao": "2026-01-01"}, "8": {"situacao": "A", "dataSituacao": "2026-01-01"}})
    salvar("dados/executivo.json", [{"id": 3, "tipo": "PL", "numero": 9, "ano": 2026, "ementa": "Do Executivo", "situacao": "Aguardando", "dataSituacao": "2026-01-01"}])
    salvar("dados/tse/2026/AC.json", [{"sequencial": "1", "nome": "Fulano", "urna": "Fu", "cargo": "DEPUTADO ESTADUAL", "partido": "X", "uf": "AC", "situacao": "eleito", "resultado": "Eleito"}])
    git("add", "-A")
    git("commit", "-qm", "Dados atualizados em 2026-01-01", data="2026-01-01")
    salvar("dados/proposicoes/1.json", {"itens": [{"id": 10, "siglaTipo": "PL", "numero": 1, "ano": 2026, "ementa": "Antiga"},
                                                   {"id": 11, "siglaTipo": "REQ", "numero": 2, "ano": 2026, "ementa": "Requerimento novo"}]})
    salvar("dados/proposicoes_detalhe.json", {"10": {"situacao": "Aprovada", "tramitacao": "Aprovação", "dataSituacao": "2026-01-02", "despacho": "Aprovado em Plenário"}})
    salvar("dados/estaduais/AC/materias_2026.json", {"materias": {
        "5": {"ano": 2026, "numero": 1, "tipo": "PL", "tipoDescricao": "Projeto de Lei", "ementa": "Antigo", "situacao": "Aprovado", "idsDeputados": [28], "dataApresentacao": "2026-01-02"},
        "6": {"ano": 2026, "numero": 2, "tipo": "PL", "tipoDescricao": "Projeto de Lei", "ementa": "Novo", "situacao": "Em tramitação", "idsDeputados": [28], "dataApresentacao": "2026-01-02", "linkTexto": "https://x/y.pdf"}}})
    salvar("dados/senado_materias.json", {"7": {"situacao": "Aprovada", "dataSituacao": "2026-01-02"}, "8": {"situacao": "B", "dataSituacao": "2026-01-02"}, "9": {"situacao": "N", "dataApresentacao": "2026-01-02", "processo": 99}})
    salvar("dados/executivo.json", [{"id": 3, "tipo": "PL", "numero": 9, "ano": 2026, "ementa": "Do Executivo", "situacao": "Sancionada", "dataSituacao": "2026-01-02"}])
    salvar("dados/tse/2026/AC.json", [{"sequencial": "1", "nome": "Fulano", "urna": "Fu", "cargo": "DEPUTADO ESTADUAL", "partido": "Y", "uf": "AC", "situacao": "eleito", "resultado": "Eleito"}])
    git("add", "-A")
    git("commit", "-qm", "Dados atualizados em 2026-01-02", data="2026-01-02")
    monkeypatch.setattr(r, "RAIZ", tmp_path)
    monkeypatch.setattr(h, "SITE_DADOS", tmp_path / "site" / "dados")
    return tmp_path


def por(eventos, **filtro):
    return [e for e in eventos if all(e.get(k) == v for k, v in filtro.items())]


def test_dia_separa_por_local_politico_e_traz_fontes(repo):
    d = h.dia("2026-01-02", "HEAD~1", "HEAD")
    ev = d["eventos"]
    nova, = por(ev, titulo="REQ 2/2026")
    assert nova["local"] == "BR" and nova["categoria"] == "nova" and nova["politicos"][0]["codigo"] == "dep:1"
    assert any("fichadetramitacao?idProposicao=11" in f[1] for f in nova["fontes"])
    # situação só vira evento para projetos; a mudança da Câmara traz o antes e o depois
    sit, = por(ev, titulo="PL 1/2026", categoria="situacao")
    assert sit["mudanca"] == ["Aguardando", "Aprovada"] and sit["texto"] == "Aprovado em Plenário"
    # Assembleia: nova e com nova situação, no local do estado, com o nome do deputado e o link do SAPL
    novo_ac, = por(ev, local="UF:AC", categoria="nova")
    assert novo_ac["politicos"][0]["nome"] == "ANTONIA SALES" and novo_ac["politicos"][0]["codigo"] == "est:AC:28"
    assert ["Matéria no sistema legislativo", "https://sapl.al.ac.leg.br/materia/6"] in novo_ac["fontes"]
    assert ["Texto", "https://x/y.pdf"] in novo_ac["fontes"]
    mud, = por(ev, local="UF:AC", categoria="situacao")
    assert mud["mudanca"] == ["Em tramitação", "Aprovado"] and mud["uf"] == "AC"
    # Presidência
    pres, = por(ev, categoria="situacao", titulo="PL 9/2026")
    assert pres["politicos"][0]["codigo"] == "pres" and pres["mudanca"] == ["Aguardando", "Sancionada"]
    # TSE
    tse, = por(ev, categoria="eleicao")
    assert tse["mudanca"] == ["X", "Y"] and tse["resumo"] == "Partido"
    assert d["locais"]["UF:AC"] == "Estado: Acre" and d["contagem"]["UF:AC"] == {"nova": 1, "situacao": 1, "eleicao": 1}


def test_senado_ignora_situacao_que_so_foi_preenchida(repo):
    ev = h.dia("2026-01-02", "HEAD~1", "HEAD")["eventos"]
    titulos = {e["titulo"]: e for e in ev if e["titulo"].startswith("Matéria")}
    assert "Matéria 7 do Senado" not in titulos          # estava sem situação: a coleta só preencheu
    assert titulos["Matéria 8 do Senado"]["mudanca"] == ["A", "B"]
    assert titulos["Matéria 9 do Senado"]["categoria"] == "nova"
    assert titulos["Matéria 9 do Senado"]["fontes"][0][1].endswith("/materia/9")


def test_primeira_coleta_nao_vira_novidade(repo, tmp_path):
    # o commit anterior não tinha dados do Acre: tudo seria "novo", então nada é registrado para o estado
    subprocess.run(["git", "rm", "-rq", "dados/estaduais"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "sem AC"], cwd=tmp_path, check=True)
    subprocess.run(["git", "checkout", "-q", "HEAD~1", "--", "dados/estaduais"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "Dados atualizados em 2026-01-03"], cwd=tmp_path, check=True)
    assert not [e for e in h.dia("2026-01-03", "HEAD~1", "HEAD")["eventos"] if e["local"] == "UF:AC" and e["categoria"] != "eleicao"]


def test_dias_git_agrupa_commits_do_mesmo_dia(repo, tmp_path):
    (tmp_path / "dados" / "x.json").write_text("{}")
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-01-02T20:00:00", "GIT_AUTHOR_DATE": "2026-01-02T20:00:00"}
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "Dados atualizados em 2026-01-02"], cwd=tmp_path, check=True, env=env)
    # o dia 01-01 não tem commit anterior para comparar; o 01-02 vai do pai do primeiro commit do dia ao último
    (dia,) = h.dias_git(None)
    primeiro, ultimo = r.git("rev-parse", "HEAD~2").strip(), r.git("rev-parse", "HEAD").strip()
    assert dia[0] == "2026-01-02" and r.git("rev-parse", dia[1]).strip() == primeiro and dia[2] == ultimo
    assert h.dias_git(None) == h.dias_git(1)


def test_gravar_cria_arquivo_do_dia_e_indice(repo, tmp_path):
    d = h.dia("2026-01-02", "HEAD~1", "HEAD")
    pasta = tmp_path / "saida"
    h.gravar(d, pasta)
    h.gravar({**d, "data": "2026-01-03"}, pasta)
    indice = json.loads((pasta / "indice.json").read_text(encoding="utf-8"))
    assert [x["data"] for x in indice] == ["2026-01-03", "2026-01-02"]
    assert indice[0]["total"] == len(d["eventos"]) and indice[0]["locais"]["UF:AC"] == 3
    assert json.loads((pasta / "2026-01-02.json").read_text(encoding="utf-8"))["eventos"] == d["eventos"]


def test_carga_em_lote_do_tse_vira_um_evento(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(h, "LIMITE_ELEICAO", 1)
    lote = [{"sequencial": str(i), "nome": "N", "urna": "N", "cargo": "SENADOR", "partido": "X", "uf": "AC", "situacao": "eleito"} for i in range(5)]
    (tmp_path / "dados" / "tse" / "2026" / "AC.json").write_text(json.dumps(lote))
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "lote"], cwd=tmp_path, check=True)
    ev = [e for e in h.dia("2026-01-03", "HEAD~1", "HEAD")["eventos"] if e["categoria"] == "eleicao"]
    assert len(ev) == 1 and "registros novos ou alterados" in ev[0]["titulo"]


def test_link_historico_filtra_por_codigos():
    assert r.link_historico("2026-01-02") == r.SITE + "historico.html?dia=2026-01-02"
    assert r.link_historico("2026-01-02", {"UF:SP", "FEDERAL"}).endswith("dia=2026-01-02&locais=BR,UF:SP")
    assert r.link_historico("2026-01-05", {"BR"}, "semana").endswith("dia=2026-01-05&periodo=semana&locais=BR")
    assert r.link_historico("2026-01-01", None, "mes").endswith("dia=2026-01-01&periodo=mes")


def test_montar_inclui_link_para_o_historico():
    d = {"camara": [{"siglaTipo": "PL", "numero": 1, "ano": 2026, "ementa": "x", "idsDeputados": []}], "senado": (0, 0), "detalhe": (0, 0), "executivo": [],
         "executivo_situacao": [], "estaduais": ({}, {}), "governo": ({}, {}), "municipais": ({}, {}), "votacoes": [], "tse": []}
    link = r.link_historico("2026-01-02")
    html_, txt = r.montar(d, "Título", detalhes=link)
    assert link in html_ and link in txt and "fonte oficial" in txt


def test_item_do_feed_aponta_para_o_historico_do_dia_e_do_local():
    it = feeds.item("T", "2026-01-02", "UF:SP", "corpo")
    assert f"<link>{r.SITE}historico.html?dia=2026-01-02&amp;locais=UF:SP</link>" in it


def test_formato_novo_dos_arquivos_de_proposicoes_nao_vira_tudo_novo(repo, tmp_path):
    """Migração (ids + cadastro) e um dia seguinte: só a proposição realmente nova vira evento."""
    def gravar(caminho, obj):
        arq = tmp_path / caminho
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(obj), encoding="utf-8")

    def commitar(msg):
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-qm", msg], cwd=tmp_path, check=True)

    gravar("dados/proposicoes/1.json", {"ate": "2026-01-02", "ids": [11, 10]})
    gravar("dados/proposicoes_cadastro/2026.json", {"11": ["REQ", 2, "Requerimento novo"], "10": ["PL", 1, "Antiga"]})
    commitar("migração")
    migracao = h.dia("2026-01-03", "HEAD~1", "HEAD")["eventos"]
    assert not por(migracao, categoria="nova")
    gravar("dados/proposicoes/1.json", {"ate": "2026-01-03", "ids": [12, 11, 10]})
    gravar("dados/proposicoes/2.json", {"ate": "2026-01-03", "ids": [12]})
    gravar("dados/proposicoes_cadastro/2026.json", {"12": ["PL", 3, "Projeto depois da migração"], "11": ["REQ", 2, "Requerimento novo"], "10": ["PL", 1, "Antiga"]})
    commitar("dia seguinte")
    nova, = por(h.dia("2026-01-04", "HEAD~1", "HEAD")["eventos"], categoria="nova")
    assert nova["titulo"] == "PL 3/2026" and nova["texto"] == "Projeto depois da migração"
    assert sorted(p["codigo"] for p in nova["politicos"]) == ["dep:1", "dep:2"]
    d = r.coletar("HEAD~1", "HEAD")
    assert [(i["siglaTipo"], i["numero"], sorted(i["idsDeputados"])) for i in d["camara"]] == [("PL", 3, [1, 2])]


def test_relevancia_separa_projeto_de_verdade_do_resto(repo):
    ev = h.dia("2026-01-02", "HEAD~1", "HEAD")["eventos"]
    assert por(ev, titulo="REQ 2/2026")[0]["relevancia"] == 1                                       # requerimento
    assert por(ev, titulo="PL 1/2026", categoria="situacao")[0]["relevancia"] == 3                          # projeto aprovado
    assert por(ev, local="UF:AC", categoria="nova")[0]["relevancia"] == 2                                  # projeto novo, por extenso ("Projeto de Lei")
    assert por(ev, categoria="eleicao")[0]["relevancia"] == 3
    assert h.relevancia({"categoria": "nova", "titulo": "PL 3/2026", "dataDoAto": "2025-01-01"}, "2026-01-02") == 1   # backlog
    assert h.relevancia({"categoria": "nova", "titulo": "PL 3/2026"}, "2026-01-02") == 2                       # sem data do ato: não penaliza
    assert h.relevancia({"categoria": "situacao", "titulo": "PL 3/2026", "resumo": "Nova tramitação"}, "2026-01-02") == 1
    assert h.relevancia({"categoria": "situacao", "titulo": "PL 3/2026", "mudanca": ["A", "Em análise"]}, "2026-01-02") == 2
    assert h.relevancia({"categoria": "votacao", "titulo": "x"}, "2026-01-02") == 3


def test_lote_de_baixa_relevancia_vira_um_evento_e_poupa_projetos(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(h, "LIMITE_LOTE", 3)
    itens = [{"id": 100 + i, "siglaTipo": "REQ", "numero": i, "ano": 2026, "ementa": "x"} for i in range(5)] + [{"id": 200, "siglaTipo": "PL", "numero": 7, "ano": 2026, "ementa": "Projeto"}]
    (tmp_path / "dados" / "proposicoes" / "2.json").write_text(json.dumps({"itens": itens}))
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "lote"], cwd=tmp_path, check=True)
    d = h.dia("2026-01-03", "HEAD~1", "HEAD")
    lote, = [e for e in d["eventos"] if e["categoria"] == "lote"]
    assert lote["local"] == "BR" and lote["quantidade"] == 5 and "5 REQ" in lote["resumo"] and lote["relevancia"] == 1
    assert lote["titulos"] == ["REQ 0/2026", "REQ 1/2026", "REQ 2/2026", "REQ 3/2026", "REQ 4/2026"]
    assert not [e for e in d["eventos"] if e["titulo"].startswith("REQ")]
    assert [e for e in d["eventos"] if e["titulo"] == "PL 7/2026"]                      # projeto de verdade segue individual
    assert d["contagem"]["BR"]["lote"] == 5                                         # a contagem reflete o que foi resumido
    assert h.resumo_indice(d)["relevancias"]["1"] >= 5


def test_cobertura_mostra_local_sem_novidade_e_desde_quando(repo, tmp_path):
    d = h.dia("2026-01-02", "HEAD~1", "HEAD")
    cob = d["cobertura"]
    assert cob["UF:AC"]["mudou"] is True and cob["UF:AC"]["itens"] == 3 and cob["BR"]["mudou"] is True
    # novo commit que não mexe em nada monitorado: BR e Acre ficam sem alteração, com a data da última mudança
    (tmp_path / "dados" / "outro.json").write_text("{}")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "so tse"], cwd=tmp_path, check=True)
    cob = h.dia("2026-01-03", "HEAD~1", "HEAD")["cobertura"]
    assert cob["UF:AC"] == {"nome": "Estado: Acre", "mudou": False, "itens": 0, "status": "parado", "ultimaMudanca": "2026-01-02"}
    assert cob["BR"]["status"] == "parado" and cob["BR"]["ultimaMudanca"] == "2026-01-02"
    assert cob["UF:SP"] == {"nome": "Estado: São Paulo", "mudou": False, "itens": 0, "status": "sem_cobertura"}


def test_cobertura_separa_mudanca_irrelevante_de_so_data_de_coleta(repo, tmp_path):
    def commit(msg):
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-qm", msg], cwd=tmp_path, check=True)

    arq = tmp_path / "dados" / "estaduais" / "AC" / "materias_2026.json"
    base = json.loads(arq.read_text(encoding="utf-8"))
    arq.write_text(json.dumps({**base, "coletadoEm": "2026-01-01"}), encoding="utf-8")
    (tmp_path / "dados" / "outro.json").write_text("{}")
    commit("nada de AC")
    cob = h.dia("2026-01-03", "HEAD~1", "HEAD")["cobertura"]["UF:AC"]
    assert cob["status"] == "falha" and cob["ultimaColeta"] == "2026-01-01"
    arq.write_text(json.dumps({**base, "coletadoEm": "2026-01-03"}), encoding="utf-8")
    commit("so a data")
    cob = h.dia("2026-01-03", "HEAD~1", "HEAD")["cobertura"]["UF:AC"]
    assert cob["status"] == "parado" and cob["mudou"] is False
    arq.write_text(json.dumps({**base, "coletadoEm": "2026-01-04", "fonte": "outra"}), encoding="utf-8")
    commit("campo novo")
    cob = h.dia("2026-01-04", "HEAD~1", "HEAD")["cobertura"]["UF:AC"]
    assert cob["status"] == "irrelevante" and cob["mudancas"] == ["matérias"] and cob["mudou"] is True
