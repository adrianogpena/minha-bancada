"""Pastas, ligação de ministros e de requerimentos e mandato de ministro (ministerios.py, identidades.py, mandatos.py, gerar_ministros.py)."""
from collections import Counter, defaultdict

import pytest

import gerar_ministros
import identidades
import mandatos
import ministerios


@pytest.mark.parametrize("texto,esperado", [
    ("Solicita informações ao Sr. Ministro da Saúde, a respeito de vacinas.", ["saude"]),
    ("Requer informações à Ministra dos Povos Indígenas, Sonia Guajajara, sobre o memorando", ["povos_indigenas"]),
    ("Solicita informações ao Exmo. Sr. Ministro de Estado do Ministério da Agricultura e Pecuária sobre Starlink", ["agricultura"]),
    ("Requer do Ministro de Estado do Desenvolvimento, Indústria, Comércio e Serviços informações sobre tarifas", ["mdic"]),
    ("Solicita ao Ministro do Desenvolvimento Agrário e Agricultura Familiar o envio de dados", ["mda"]),
    ("Requer ao Ministro-Chefe da Casa Civil da Presidência da República informações sobre contratos", ["casa_civil"]),
    ("Requer ao Exmo. Sr. Advogado-Geral da União informações sobre descontos", ["agu"]),
    ("Convocação do Ministro das Relações Exteriores e da Ministra do Turismo", ["relacoes_exteriores", "turismo"]),
    ("Requer informações ao Ministro de Estado da Justiça e Segurança Pública, por intermédio do Conselho Administrativo de Defesa Econômica",
     ["justica"]),
    ("Requer audiência pública sobre o piso salarial", []),
])
def test_pastas_do_texto(texto, esperado):
    assert ministerios.pastas_do_texto(texto) == esperado


def test_pasta_do_cargo_do_planalto():
    assert ministerios.pasta_do_cargo("Ministro de Estado da Saúde") == "saude"
    assert ministerios.pasta_do_cargo("Ministra de Estado dos Direitos Humanos e da Cidadania") == "direitos_humanos"
    assert ministerios.pasta_do_cargo("Ministro de Estado Chefe do Gabinete de Segurança Institucional da Presidência da República") == "gsi"
    assert ministerios.pasta_do_cargo("Advocacia-Geral da União") == "agu"
    assert ministerios.pasta_do_cargo("Ministro de Estado da Secretaria de Comunicação Social da Presidência da República") == "comunicacao_social"
    assert ministerios.pasta_do_cargo("Cargo qualquer") is None


def _registro(*pessoas):
    reg = identidades._Registro()
    for fonte, ident, nome, extra in pessoas:
        p = reg.obter(fonte, ident)
        identidades._preencher(p, nome)
        p.update(extra)
    return reg


def _ligar(planalto, reg, licenciados=None):
    chaves, ambiguos = {}, []
    resumo, sem = defaultdict(Counter), Counter()
    ms = identidades.ligar_ministros(planalto, reg, licenciados or {}, chaves, ambiguos, resumo, sem)
    return ms, chaves, ambiguos, resumo, sem


def test_ministro_licenciado_liga_por_nome_com_confianca_alta_e_inicio_da_licenca(monkeypatch):
    monkeypatch.setattr(identidades, "POSSES", {})
    reg = _registro(("camara", "1", "ALEXANDRE ROCHA SANTOS PADILHA", {"camara": 1}))
    licencas = {"camara": {"1": {"historico": [
        {"data": "2023-02-02", "situacao": "Licença", "descricao": "Saída - Afastamento sem prazo determinado - Ministro de Estado"},
        {"data": "2025-01-31", "situacao": "Exercício", "descricao": "Entrada - Reassunção"},
        {"data": "2025-02-03", "situacao": "Licença", "descricao": "Saída - Afastamento sem prazo determinado - Ministro de Estado"},
        {"data": "2025-03-10", "situacao": "Licença", "descricao": "Saída - Afastamento sem prazo determinado - Ministro de Estado"}]}}}
    planalto = {"atuais": [{"cargo": "Ministro de Estado da Saúde", "nome": "Alexandre Rocha Santos Padilha", "vistoDesde": "2026-10-29"}]}
    (m,), chaves, _, resumo, _ = _ligar(planalto, reg, licencas)
    assert m["pessoa"] == next(iter(reg.por_id)) and (m["pasta"], m["inicio"], m["inicioFonte"]) == ("saude", "2025-03-10", "licenca")
    assert reg.por_id[m["pessoa"]]["ligacao"]["planalto"] == ["nome", "alta"]
    assert chaves[("planalto", "saude", "alexandre rocha santos padilha")] == m["pessoa"] and resumo["planalto"]["nome"] == 1


def test_posse_da_wikipedia_vale_sobre_licenca_e_traz_quem_nomeou(monkeypatch):
    reg = _registro(("camara", "1", "ALEXANDRE ROCHA SANTOS PADILHA", {"camara": 1}))
    licencas = {"camara": {"1": {"historico": [
        {"data": "2025-03-05", "situacao": "Licença", "descricao": "Saída - Afastamento sem prazo determinado - Ministro de Estado"}]}}}
    posse = {"pasta": "saude", "nome": "Alexandre Rocha Santos Padilha", "posse": "2025-03-10", "nomeadoPor": "Luiz Inácio Lula da Silva",
             "fonte": "https://pt.wikipedia.org/wiki/Lista_de_ministros_da_Sa%C3%BAde_do_Brasil"}
    monkeypatch.setattr(identidades, "POSSES", {("saude", posse["nome"]): posse})
    planalto = {"atuais": [{"cargo": "Ministro de Estado da Saúde", "nome": posse["nome"], "vistoDesde": "2026-10-29"}],
                "anteriores": [{"cargo": "Ministro de Estado da Saúde", "nome": posse["nome"], "vistoDesde": "2024-01-01", "vistoAte": "2024-06-01"}]}
    (atual, anterior), *_ = _ligar(planalto, reg, licencas)
    assert (atual["inicio"], atual["inicioFonte"], atual["nomeadoPor"], atual["inicioUrl"]) == ("2025-03-10", "wikipedia", "Luiz Inácio Lula da Silva", posse["fonte"])
    assert anterior["inicioFonte"] == "licenca" and "nomeadoPor" not in anterior   # quem já saiu não leva a posse do mandato atual


def test_ministro_sem_par_ganha_pessoa_propria_e_nome_repetido_nao_liga():
    reg = _registro(("camara", "1", "João Silva", {}), ("senado", "2", "Joao Silva", {}))
    planalto = {"atuais": [{"cargo": "Ministro de Estado do Turismo", "nome": "João Silva", "vistoDesde": "2026-10-29"},
                           {"cargo": "Ministro de Estado da Cultura", "nome": "Maria Souza", "vistoDesde": "2026-10-29"}],
                "anteriores": [{"cargo": "Ministro de Estado do Esporte", "nome": "Pedro Lima", "vistoDesde": "2026-01-01", "vistoAte": "2026-06-01"}]}
    ms, _, ambiguos, _, sem = _ligar(planalto, reg)
    assert sem["planalto"] == 3 and len(ambiguos) == 1 and ambiguos[0]["fonte"] == "planalto"
    assert [m["inicioFonte"] for m in ms] == ["planalto"] * 3 and ms[2]["fim"] == "2026-06-01"
    assert reg.por_id[ms[1]["pessoa"]]["planalto"] == ["cultura"]


MINISTROS = [
    {"pasta": "saude", "nome": "Alexandre Rocha Santos Padilha", "pessoa": "pes_a", "inicio": "2025-03-10", "inicioFonte": "licenca"},
    {"pasta": "defesa", "nome": "José Mucio Monteiro Filho", "pessoa": "pes_b", "inicio": "2026-10-29", "inicioFonte": "planalto"},
]


def test_requerimento_com_nome_do_ministro_liga_com_confianca_alta():
    itens = {"x": {"ementa": "Solicita ao Ministro da Defesa, José Múcio, informações", "dataApresentacao": "2023-05-01", "pastas": ["defesa"]}}
    assert identidades.ligar_requerimentos(itens, MINISTROS) == {"x": ["pes_b", "nome+pasta", "alta"]}


def test_requerimento_sem_nome_liga_pela_pasta_depois_do_inicio_do_ministro():
    itens = {"antes": {"ementa": "x", "dataApresentacao": "2025-03-09", "pastas": ["saude"]},
             "depois": {"ementa": "x", "dataApresentacao": "2025-04-01", "pastas": ["saude"]},
             "inicio_planalto": {"ementa": "x", "dataApresentacao": "2026-11-02", "pastas": ["defesa"]},
             "sem_pasta": {"ementa": "x", "dataApresentacao": "2026-11-02", "pastas": []}}
    assert identidades.ligar_requerimentos(itens, MINISTROS) == {
        "depois": ["pes_a", "pasta+data", "média"], "inicio_planalto": ["pes_b", "pasta+data", "baixa"]}


def test_autoria_do_senado_liga_cada_senador_pelo_nome_e_uf():
    senadores = [{"id": 1, "nome": "Eduardo Girão", "nomeCivil": "Eduardo Girão", "uf": "CE"},
                 {"id": 2, "nome": "Tereza Cristina", "nomeCivil": "Tereza Cristina Corrêa", "uf": "MS"},
                 {"id": 3, "nome": "Damares Alves", "uf": "DF"}, {"id": 4, "nome": "Damares Alves", "uf": "DF"}]
    r = identidades.ligar_autoria_senado([
        "Senador Eduardo Girão (NOVO/CE), Senadora Tereza Cristina (PP/MS)", "Líder do PP Tereza Cristina (PP/MS)",
        "Senadora Damares Alves (REPUBLICANOS/DF)", "Senador Fora da Lista (PT/BA)", None], senadores)
    assert r["Senador Eduardo Girão (NOVO/CE), Senadora Tereza Cristina (PP/MS)"] == [["1", "nome+uf", "média"], ["2", "nome+uf", "média"]]
    assert r["Líder do PP Tereza Cristina (PP/MS)"] == [["2", "nome+uf", "média"]]
    assert r["Senadora Damares Alves (REPUBLICANOS/DF)"] == [] and r["Senador Fora da Lista (PT/BA)"] == []


def test_natureza_do_requerimento():
    assert gerar_ministros.natureza("RIC", "x") == "informacao"
    assert gerar_ministros.natureza("RQS", "x", "Informações") == "informacao"
    assert gerar_ministros.natureza("REQ", "Requer a convocação do Ministro") == "convocacao"
    assert gerar_ministros.natureza("REQ", "Requer o convite ao Ministro") == "convite"


def test_mandato_de_ministro_sem_prazo_e_encerrado_quando_sai_da_lista(tmp_path):
    nucleo = {"chaves": {}, "ministros": [
        {"pasta": "saude", "cargo": "Ministro de Estado da Saúde", "nome": "A B", "pessoa": "pes_a", "inicio": "2025-03-10", "inicioFonte": "licenca"},
        {"pasta": "esporte", "cargo": "Ministro de Estado do Esporte", "nome": "C D", "pessoa": "pes_c", "inicio": "2026-01-01",
         "inicioFonte": "planalto", "fim": "2026-06-01"}]}
    res = mandatos.construir({}, tmp_path, nucleo, hoje="2026-10-29")
    atual, encerrado = sorted((m for m in res["mandatos"] if m["cargo"] == "MINISTRO DE ESTADO"), key=lambda m: m["pasta"], reverse=True)
    assert (atual["pasta"], atual["status"], atual["semPrazo"], atual["inicioAproximado"], "fim" in atual) == ("saude", "atual", True, True, False)
    assert (encerrado["status"], encerrado["fim"], "semPrazo" in encerrado) == ("encerrado", "2026-06-01", False)
    assert atual["id"].startswith("man_")


def test_descricao_cobre_todas_as_pastas():
    """`scripts/ministerios_descricao.json`: uma descrição por chave de PASTAS, com fonte legal e links https."""
    import json
    import pathlib
    descricao = json.loads((pathlib.Path(gerar_ministros.__file__).parent / "ministerios_descricao.json").read_text(encoding="utf-8"))
    assert set(descricao) == set(ministerios.PASTAS)
    for chave, d in descricao.items():
        assert d["resumo"].strip() and d["areas"] and d["base"] and d["revisadoEm"], chave
        assert all(a.strip() for a in d["areas"]), chave
        assert d["site"].startswith("https://www.gov.br/"), chave
        assert all(b["rotulo"] and b["url"].startswith("https://") for b in d["base"]), chave


def test_descricoes_avisa_pasta_sem_descricao(tmp_path, capsys):
    arq = tmp_path / "d.json"
    arq.write_text('{"saude": {"resumo": "x"}, "inexistente": {"resumo": "y"}}', encoding="utf-8")
    d = gerar_ministros.descricoes(arq)
    assert list(d) == ["saude"]
    assert "sem descrição" in capsys.readouterr().err
    assert set(gerar_ministros.descricoes()) == set(ministerios.PASTAS)
