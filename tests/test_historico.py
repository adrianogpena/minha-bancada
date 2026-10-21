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
    salvar("dados/tse/2026/AC.json", [{"sq": "1", "nome": "Fulano", "urna": "Fu", "cargo": "DEPUTADO ESTADUAL", "partido": "X", "uf": "AC", "situacao": "eleito", "resultado": "Eleito"}])
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
    salvar("dados/tse/2026/AC.json", [{"sq": "1", "nome": "Fulano", "urna": "Fu", "cargo": "DEPUTADO ESTADUAL", "partido": "Y", "uf": "AC", "situacao": "eleito", "resultado": "Eleito"}])
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
    nova, = por(ev, t="REQ 2/2026")
    assert nova["l"] == "BR" and nova["k"] == "nova" and nova["p"][0]["c"] == "dep:1"
    assert any("fichadetramitacao?idProposicao=11" in f[1] for f in nova["f"])
    # situação só vira evento para projetos; a mudança da Câmara traz o antes e o depois
    sit, = por(ev, t="PL 1/2026", k="situacao")
    assert sit["m"] == ["Aguardando", "Aprovada"] and sit["x"] == "Aprovado em Plenário"
    # Assembleia: nova e com nova situação, no local do estado, com o nome do deputado e o link do SAPL
    novo_ac, = por(ev, l="UF:AC", k="nova")
    assert novo_ac["p"][0]["n"] == "ANTONIA SALES" and novo_ac["p"][0]["c"] == "est:AC:28"
    assert ["Matéria no sistema legislativo", "https://sapl.al.ac.leg.br/materia/6"] in novo_ac["f"]
    assert ["Texto", "https://x/y.pdf"] in novo_ac["f"]
    mud, = por(ev, l="UF:AC", k="situacao")
    assert mud["m"] == ["Em tramitação", "Aprovado"] and mud["uf"] == "AC"
    # Presidência
    pres, = por(ev, k="situacao", t="PL 9/2026")
    assert pres["p"][0]["c"] == "pres" and pres["m"] == ["Aguardando", "Sancionada"]
    # TSE
    tse, = por(ev, k="eleicao")
    assert tse["m"] == ["X", "Y"] and tse["s"] == "Partido"
    assert d["locais"]["UF:AC"] == "Estado: Acre" and d["contagem"]["UF:AC"] == {"nova": 1, "situacao": 1, "eleicao": 1}


def test_senado_ignora_situacao_que_so_foi_preenchida(repo):
    ev = h.dia("2026-01-02", "HEAD~1", "HEAD")["eventos"]
    titulos = {e["t"]: e for e in ev if e["t"].startswith("Matéria")}
    assert "Matéria 7 do Senado" not in titulos          # estava sem situação: a coleta só preencheu
    assert titulos["Matéria 8 do Senado"]["m"] == ["A", "B"]
    assert titulos["Matéria 9 do Senado"]["k"] == "nova"
    assert titulos["Matéria 9 do Senado"]["f"][0][1].endswith("/materia/9")


def test_primeira_coleta_nao_vira_novidade(repo, tmp_path):
    # o commit anterior não tinha dados do Acre: tudo seria "novo", então nada é registrado para o estado
    subprocess.run(["git", "rm", "-rq", "dados/estaduais"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "sem AC"], cwd=tmp_path, check=True)
    subprocess.run(["git", "checkout", "-q", "HEAD~1", "--", "dados/estaduais"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "Dados atualizados em 2026-01-03"], cwd=tmp_path, check=True)
    assert not [e for e in h.dia("2026-01-03", "HEAD~1", "HEAD")["eventos"] if e["l"] == "UF:AC" and e["k"] != "eleicao"]


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
    assert [x["d"] for x in indice] == ["2026-01-03", "2026-01-02"]
    assert indice[0]["n"] == len(d["eventos"]) and indice[0]["l"]["UF:AC"] == 3
    assert json.loads((pasta / "2026-01-02.json").read_text(encoding="utf-8"))["eventos"] == d["eventos"]


def test_carga_em_lote_do_tse_vira_um_evento(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(h, "LIMITE_ELEICAO", 1)
    lote = [{"sq": str(i), "nome": "N", "urna": "N", "cargo": "SENADOR", "partido": "X", "uf": "AC", "situacao": "eleito"} for i in range(5)]
    (tmp_path / "dados" / "tse" / "2026" / "AC.json").write_text(json.dumps(lote))
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "lote"], cwd=tmp_path, check=True)
    ev = [e for e in h.dia("2026-01-03", "HEAD~1", "HEAD")["eventos"] if e["k"] == "eleicao"]
    assert len(ev) == 1 and "registros novos ou alterados" in ev[0]["t"]


def test_link_historico_filtra_por_codigos():
    assert r.link_historico("2026-01-02") == r.SITE + "historico.html?dia=2026-01-02"
    assert r.link_historico("2026-01-02", {"UF:SP", "BR"}).endswith("dia=2026-01-02&locais=BR,UF:SP")


def test_montar_inclui_link_para_o_historico():
    d = {"camara": [{"siglaTipo": "PL", "numero": 1, "ano": 2026, "ementa": "x", "idsDeputados": []}], "senado": (0, 0), "detalhe": (0, 0), "executivo": [],
         "executivo_situacao": [], "estaduais": ({}, {}), "governo": ({}, {}), "municipais": ({}, {}), "votacoes": [], "tse": []}
    link = r.link_historico("2026-01-02")
    html_, txt = r.montar(d, "Título", detalhes=link)
    assert link in html_ and link in txt and "fonte oficial" in txt


def test_item_do_feed_aponta_para_o_historico_do_dia_e_do_local():
    it = feeds.item("T", "2026-01-02", "UF:SP", "corpo")
    assert f"<link>{r.SITE}historico.html?dia=2026-01-02&amp;locais=UF:SP</link>" in it


def test_relevancia_separa_projeto_de_verdade_do_resto(repo):
    ev = h.dia("2026-01-02", "HEAD~1", "HEAD")["eventos"]
    assert por(ev, t="REQ 2/2026")[0]["r"] == 1                                       # requerimento
    assert por(ev, t="PL 1/2026", k="situacao")[0]["r"] == 3                          # projeto aprovado
    assert por(ev, l="UF:AC", k="nova")[0]["r"] == 2                                  # projeto novo, por extenso ("Projeto de Lei")
    assert por(ev, k="eleicao")[0]["r"] == 3
    assert h.relevancia({"k": "nova", "t": "PL 3/2026", "d": "2025-01-01"}, "2026-01-02") == 1   # backlog
    assert h.relevancia({"k": "nova", "t": "PL 3/2026"}, "2026-01-02") == 2                       # sem data do ato: não penaliza
    assert h.relevancia({"k": "situacao", "t": "PL 3/2026", "s": "Nova tramitação"}, "2026-01-02") == 1
    assert h.relevancia({"k": "situacao", "t": "PL 3/2026", "m": ["A", "Em análise"]}, "2026-01-02") == 2
    assert h.relevancia({"k": "votacao", "t": "x"}, "2026-01-02") == 3


def test_lote_de_baixa_relevancia_vira_um_evento_e_poupa_projetos(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(h, "LIMITE_LOTE", 3)
    itens = [{"id": 100 + i, "siglaTipo": "REQ", "numero": i, "ano": 2026, "ementa": "x"} for i in range(5)] + [{"id": 200, "siglaTipo": "PL", "numero": 7, "ano": 2026, "ementa": "Projeto"}]
    (tmp_path / "dados" / "proposicoes" / "2.json").write_text(json.dumps({"itens": itens}))
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "lote"], cwd=tmp_path, check=True)
    d = h.dia("2026-01-03", "HEAD~1", "HEAD")
    lote, = [e for e in d["eventos"] if e["k"] == "lote"]
    assert lote["l"] == "BR" and lote["n"] == 5 and "5 REQ" in lote["s"] and lote["r"] == 1
    assert lote["i"] == ["REQ 0/2026", "REQ 1/2026", "REQ 2/2026", "REQ 3/2026", "REQ 4/2026"]
    assert not [e for e in d["eventos"] if e["t"].startswith("REQ")]
    assert [e for e in d["eventos"] if e["t"] == "PL 7/2026"]                      # projeto de verdade segue individual
    assert d["contagem"]["BR"]["lote"] == 5                                         # a contagem reflete o que foi resumido
    assert h.resumo_indice(d)["r"]["1"] >= 5


def test_cobertura_mostra_local_sem_novidade_e_desde_quando(repo, tmp_path):
    d = h.dia("2026-01-02", "HEAD~1", "HEAD")
    cob = d["cobertura"]
    assert cob["UF:AC"]["m"] is True and cob["UF:AC"]["e"] == 3 and cob["BR"]["m"] is True
    # novo commit que não mexe em nada monitorado: BR e Acre ficam sem alteração, com a data da última mudança
    (tmp_path / "dados" / "outro.json").write_text("{}")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "so tse"], cwd=tmp_path, check=True)
    cob = h.dia("2026-01-03", "HEAD~1", "HEAD")["cobertura"]
    assert cob["UF:AC"] == {"n": "Estado: Acre", "m": False, "e": 0, "u": "2026-01-02"}
    assert cob["BR"]["m"] is False and cob["BR"]["u"] == "2026-01-02"
