"""Montagem do que o site lê de deputados estaduais, governadores e prefeitos de capitais, a partir do cache bruto."""
import json

import gerar_estaduais
import gerar_prefeituras
from coletar_prefeituras import TODAS


def gravar(caminho, obj):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def ler(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_tipo_voto_normaliza_grafias():
    t = gerar_estaduais.tipo_voto
    assert (t("Sim"), t(" NÃO "), t("nao"), t("Abstenção"), t("Obstrução"), t("Não votou")) == ("sim", "nao", "nao", "abstencao", "obstrucao", "ausente")
    assert t(None) == "outro" and t("Presente") == "outro"


def materia(tipo, numero, data, ementa="Dispõe\n  sobre   algo.", ids=(1,), desc=None, situacao="Em tramitação"):
    return {"tipo": tipo, "tipoDescricao": desc or tipo, "numero": numero, "ano": 2026, "dataApresentacao": data, "ementa": ementa,
            "situacao": situacao, "emTramitacao": True, "linkTexto": None, "idsDeputados": list(ids)}


def monta_assembleia(bruto):
    pasta = bruto / "XX"
    gravar(pasta / "deputados.json", {"host": "al.xx.leg.br", "deputados": [
        {"id": 1, "nome": "Ana Souza", "nomeCivil": "Ana Maria Souza (Aninha)", "foto": "f1", "email": "a@xx", "titular": True},
        {"id": 2, "nome": "Beto Lima"}]})
    gravar(pasta / "votacoes.json", {"votacoes": {
        "v1": {"idMateria": 50, "data": "2026-03-01", "sim": 1, "nao": 1, "abstencoes": 0, "aprovada": True, "resultado": "Aprovado",
               "votos": [[1, "Sim"], [2, "Não"]]},
        "v2": {"idMateria": 51, "data": "2026-06-01", "sim": None, "nao": None, "abstencoes": None, "aprovada": False,
               "votos": [[1, "Abstenção"]]}}})
    gravar(pasta / "materias_votadas.json", {"50": {"tipo": "PL", "numero": 7, "ano": 2026, "tipoDescricao": "Projeto de Lei", "ementa": "Ementa 7"}})
    gravar(pasta / "materias_2026.json", {"materias": {
        "m1": materia("PL", 1, "2026-01-10", ids=(1, 2)), "m2": materia("REQ", 2, "2026-05-10", ids=(1,))}})
    gravar(pasta / "governo_2026.json", {"materias": {
        "g1": materia("PL", 3, "2026-02-01", desc="Projeto de Lei"), "g2": materia("PL", 4, "2026-04-01", desc="Veto Total"),
        "g3": materia("MSG", 5, "2026-04-01", desc="Mensagem")}})
    return pasta


def test_assembleia_gera_votacoes_fichas_e_projetos(tmp_path, monkeypatch):
    bruto, saida = tmp_path / "estaduais", tmp_path / "site"
    monkeypatch.setattr(gerar_estaduais, "BRUTO", bruto)
    monkeypatch.setattr(gerar_estaduais, "SAIDA", saida)
    pasta = monta_assembleia(bruto)
    deputados = gerar_estaduais.gerar_assembleia("XX", pasta)
    assert [d["id"] for d in deputados] == [1, 2]

    lista = ler(saida / "votacoes_estadual_XX.json")
    assert [v["id"] for v in lista] == ["v2", "v1"]   # da mais nova para a mais antiga
    assert "_votos" not in lista[0]
    v1 = lista[1]
    assert v1["proposicao"] == "PL 7/2026" and v1["descricao"] == "Projeto de Lei" and v1["placar"] == {"sim": 1, "nao": 1, "abstencao": 0}
    assert lista[0]["proposicao"] is None and lista[0]["descricao"] == "Votação" and lista[0]["placar"] == {"sim": 0, "nao": 0, "abstencao": 0}

    ana = ler(saida / "estadual" / "XX" / "1.json")
    assert [(v["id"], v["voto"]) for v in ana["votos"]] == [("v2", "abstencao"), ("v1", "sim")]
    assert [p["id"] for p in ana["proposicoes"]] == ["m2", "m1"]            # mais nova primeiro
    assert ana["proposicoes"][1]["coautores"] == ["Beto Lima"] and "coautores" not in ana["proposicoes"][0]
    beto = ler(saida / "estadual" / "XX" / "2.json")
    assert [(v["id"], v["voto"]) for v in beto["votos"]] == [("v2", "ausente"), ("v1", "nao")]   # não votou na v2


def test_deputado_sem_voto_nao_recebe_lista_de_votos(tmp_path, monkeypatch):
    bruto, saida = tmp_path / "estaduais", tmp_path / "site"
    monkeypatch.setattr(gerar_estaduais, "BRUTO", bruto)
    monkeypatch.setattr(gerar_estaduais, "SAIDA", saida)
    pasta = bruto / "XX"
    gravar(pasta / "deputados.json", {"host": "h", "deputados": [{"id": 9, "nome": "Novo"}]})
    gravar(pasta / "votacoes.json", {"votacoes": {"v": {"idMateria": 1, "data": "2026-01-01", "sim": 0, "nao": 0, "abstencoes": 0, "aprovada": True, "votos": []}}})
    gerar_estaduais.gerar_assembleia("XX", pasta)
    assert ler(saida / "estadual" / "XX" / "9.json")["votos"] == []


def test_assembleia_sem_arquivo_de_deputados_e_ignorada(tmp_path):
    assert gerar_estaduais.gerar_assembleia("XX", tmp_path) == []


def test_governo_marca_veto_normaliza_ementa_e_ordena(tmp_path, monkeypatch):
    bruto, saida = tmp_path / "estaduais", tmp_path / "site"
    monkeypatch.setattr(gerar_estaduais, "SAIDA", saida)
    gerar_estaduais.gerar_governo("XX", monta_assembleia(bruto), "al.xx.leg.br")
    j = ler(saida / "governo" / "XX.json")
    assert j["host"] == "al.xx.leg.br"
    assert [m["id"] for m in j["materias"]] == ["g3", "g2", "g1"]   # empate de data desempata pelo id, decrescente
    assert {m["id"]: m["tipo"] for m in j["materias"]} == {"g1": "PL", "g2": "VET", "g3": "MSG"}
    assert j["materias"][0]["ementa"] == "Dispõe sobre algo."


def test_governo_sem_materias_nao_cria_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(gerar_estaduais, "SAIDA", tmp_path / "site")
    gerar_estaduais.gerar_governo("XX", tmp_path, "h")
    assert not (tmp_path / "site").exists()


def test_gerar_liga_deputado_por_nome_civil_apelido_e_uf(tmp_path, monkeypatch):
    from gerar_politicos import chave_nome
    bruto, saida = tmp_path / "estaduais", tmp_path / "site"
    monkeypatch.setattr(gerar_estaduais, "BRUTO", bruto)
    monkeypatch.setattr(gerar_estaduais, "SAIDA", saida)
    monta_assembleia(bruto)
    ligacao = gerar_estaduais.gerar()
    for nome in ("Ana Souza", "Ana Maria Souza (Aninha)", "Ana Maria Souza"):
        assert ligacao[chave_nome(nome, "XX")] == ("XX", 1)
    assert ligacao[chave_nome("Beto Lima", "XX")] == ("XX", 2)


def test_gerar_sem_pasta_bruta_devolve_vazio(tmp_path, monkeypatch):
    monkeypatch.setattr(gerar_estaduais, "BRUTO", tmp_path / "nao_existe")
    assert gerar_estaduais.gerar() == {}


def test_prefeituras_gera_arquivo_pelo_codigo_tse_da_capital(tmp_path, monkeypatch):
    bruto, saida = tmp_path / "municipais", tmp_path / "site"
    monkeypatch.setattr(gerar_prefeituras, "BRUTO", bruto)
    monkeypatch.setattr(gerar_prefeituras, "SAIDA", saida)
    (uf, (ue, host)), (outra, _) = list(TODAS.items())[:2]
    gravar(bruto / uf / "prefeitura_2026.json", {"materias": {
        "1": materia("PLO", 1, "2026-01-10", desc="Projeto de Lei Ordinária"), "2": materia("PL", 2, "2026-03-10", desc="Veto Parcial")}})
    gerar_prefeituras.gerar()
    j = ler(saida / "prefeitura" / f"{ue}.json")
    assert j["host"] == host and [m["id"] for m in j["materias"]] == ["2", "1"]
    assert j["materias"][0]["tipo"] == "VET" and j["materias"][1]["tipo"] == "PLO"
    assert [p.name for p in (saida / "prefeitura").iterdir()] == [f"{ue}.json"]   # capital sem matéria não gera arquivo
