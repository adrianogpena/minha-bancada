"""main() e auxiliares de git/SMTP da operação diária: historico, resumo_email, feeds e contrato_apis, sem git, rede nem SMTP reais."""
import json
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime

import pytest

import contrato_apis as c
import feeds
import historico as h
import resumo_email as r

TS = int(datetime(2026, 11, 3, 12, 0, tzinfo=UTC).timestamp())


def vazio_d(**extra):
    d = {"camara": [], "senado": (0, 0), "detalhe": (0, 0), "executivo": [], "executivo_situacao": [],
         "estaduais": (defaultdict(list), defaultdict(list)), "governo": (defaultdict(list), defaultdict(list)),
         "municipais": (defaultdict(list), defaultdict(list)), "votacoes": [], "tse": []}
    d.update(extra)
    return d


def prop(n=1, deps=()):
    return {"siglaTipo": "PL", "numero": n, "ano": 2026, "ementa": "Dispõe sobre algo", "idsDeputados": list(deps)}


# ---------------------------------------------------------------- resumo_email: git e SMTP

def test_resumo_dia_do_commit_e_da_coleta(monkeypatch):
    monkeypatch.setattr(r, "git", lambda *a: f"{TS}\n")
    assert r.dia_do_commit("HEAD") == "2026-11-02"
    assert r.dia_da_coleta("HEAD") == "2026-11-03"


def test_resumo_dia_do_commit_sem_commit(monkeypatch):
    monkeypatch.setattr(r, "git", lambda *a: "\n")
    assert r.dia_do_commit("HEAD") is None
    assert r.dia_da_coleta("HEAD") is None


def test_resumo_dia_do_commit_passa_caminhos_ao_git(monkeypatch):
    chamadas = []
    monkeypatch.setattr(r, "git", lambda *a: chamadas.append(a) or f"{TS}")
    r.dia_do_commit("abc", "dados/x.json")
    assert chamadas == [("log", "-1", "--format=%ct", "abc", "--", "dados/x.json")]


def test_resumo_carregar_devolve_json_do_git(monkeypatch):
    chamadas = []
    monkeypatch.setattr(r, "git", lambda *a: chamadas.append(a) or '{"a": 1}')
    assert r.carregar("abc", "dados/x.json") == {"a": 1}
    assert chamadas == [("show", "abc:dados/x.json")]


def test_resumo_carregar_ausente_ou_invalido_vira_none(monkeypatch):
    def ausente(*a):
        raise subprocess.CalledProcessError(128, "git")
    monkeypatch.setattr(r, "git", ausente)
    assert r.carregar("abc", "dados/x.json") is None
    monkeypatch.setattr(r, "git", lambda *a: "não é json")
    assert r.carregar("abc", "dados/x.json") is None


def test_resumo_arquivos_lista_do_diff(monkeypatch):
    chamadas = []
    monkeypatch.setattr(r, "git", lambda *a: chamadas.append(a) or "dados/a.json\ndados/b.json\n")
    assert r.arquivos("A", "B", "dados/") == ["dados/a.json", "dados/b.json"]
    assert chamadas == [("diff", "--name-only", "A", "B", "--", "dados/")]


def test_resumo_longo_junta_titulos_trocando_travessao():
    d = vazio_d(camara=[prop()], senado=(1, 3))
    assert r.resumo_longo(d) == "Câmara dos Deputados: 1 proposição nova · Senado: 2 matérias novas"
    assert r.resumo_longo(vazio_d()) == ""


@pytest.fixture
def smtp_falso(monkeypatch):
    registro = {"enviadas": [], "login": None, "host": None}

    class SMTP:
        def __init__(self, host, porta):
            registro["host"] = (host, porta)

        def login(self, u, s):
            registro["login"] = (u, s)

        def send_message(self, m):
            registro["enviadas"].append(m)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(r.smtplib, "SMTP_SSL", SMTP)
    for k, v in {"SMTP_HOST": "smtp.example", "SMTP_USUARIO": "eu@example", "SMTP_SENHA": "segredo", "EMAIL_PARA": "ele@example"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("SMTP_PORT", raising=False)
    return registro


def test_smtp_usa_porta_padrao_465_e_faz_login(smtp_falso):
    r.smtp()
    assert smtp_falso["host"] == ("smtp.example", 465) and smtp_falso["login"] == ("eu@example", "segredo")


def test_smtp_respeita_porta_do_ambiente(smtp_falso, monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "2465")
    r.smtp()
    assert smtp_falso["host"] == ("smtp.example", 2465)


def test_enviar_manda_html_e_texto_para_o_destino(smtp_falso):
    r.enviar("Assunto", "<p>oi</p>", "oi")
    (msg,) = smtp_falso["enviadas"]
    assert (msg["Subject"], msg["From"], msg["To"]) == ("Assunto", "eu@example", "ele@example")
    assert msg.get_body(("plain",)).get_content().strip() == "oi"
    assert "<p>oi</p>" in msg.get_body(("html",)).get_content()


def test_mensagem_aceita_cabecalhos_extras(smtp_falso):
    msg = r.mensagem("A", "x@example", "<p>a</p>", "a", {"List-Unsubscribe": "<https://x>"})
    assert msg["List-Unsubscribe"] == "<https://x>" and msg["To"] == "x@example"


def preparar_main_resumo(monkeypatch, d):
    chamadas = {"coletar": [], "enviar": []}
    monkeypatch.setattr(r, "dia_do_commit", lambda rev, *a: "2026-11-02")
    monkeypatch.setattr(r, "dia_da_coleta", lambda rev: "2026-11-03")
    monkeypatch.setattr(r, "coletar", lambda antes, depois, dia: chamadas["coletar"].append((antes, depois, dia)) or d)
    monkeypatch.setattr(r, "enviar", lambda *a: chamadas["enviar"].append(a))
    return chamadas


def test_resumo_main_sem_novidades_grava_arquivos_e_nao_envia(monkeypatch, tmp_path, capsys):
    chamadas = preparar_main_resumo(monkeypatch, vazio_d())
    monkeypatch.setattr(sys, "argv", ["resumo_email.py", "--saida", str(tmp_path / "out")])
    r.main()
    assert chamadas["coletar"] == [("HEAD~1", "HEAD", "2026-11-03")]
    assert chamadas["enviar"] == []
    assert (tmp_path / "out" / "resumo.txt").read_text(encoding="utf-8") == "Nenhum dado novo nesta execução."
    html = (tmp_path / "out" / "resumo.html").read_text(encoding="utf-8")
    assert html.startswith("<!doctype html><meta charset=utf-8><title>Minha Bancada — o que mudou em 02/11/2026</title>")
    assert "Nenhum dado novo nesta execução." in capsys.readouterr().out


def test_resumo_main_com_novidades_e_enviar(monkeypatch, tmp_path):
    chamadas = preparar_main_resumo(monkeypatch, vazio_d(camara=[prop()]))
    monkeypatch.setattr(sys, "argv", ["resumo_email.py", "A", "B", "--saida", str(tmp_path), "--enviar"])
    r.main()
    assert chamadas["coletar"] == [("A", "B", "2026-11-03")]
    texto = (tmp_path / "resumo.txt").read_text(encoding="utf-8")
    assert "Câmara dos Deputados — 1 proposição nova" in texto and "historico.html?dia=2026-11-03" in texto
    (assunto, corpo_html, corpo_txt), = chamadas["enviar"]
    assert assunto == "Minha Bancada — o que mudou em 02/11/2026" and corpo_txt == texto and "<h1" in corpo_html


# ---------------------------------------------------------------- feeds

def test_feeds_deputados_por_uf_le_indice(monkeypatch, tmp_path):
    (tmp_path / "SP.json").write_text(json.dumps([{"id": "7", "pagina": "deputado.html?id=7"}, {"id": 9, "pagina": "senador.html"}, {"id": 3}]), encoding="utf-8")
    (tmp_path / "BR.json").write_text("[]", encoding="utf-8")
    (tmp_path / "MIN.json").write_text("[]", encoding="utf-8")
    (tmp_path / "RJ.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(feeds, "INDICE", tmp_path)
    assert feeds.deputados_por_uf() == {"SP": {7}, "RJ": set()}


def test_feeds_deputados_por_uf_sem_indice(monkeypatch, tmp_path):
    monkeypatch.setattr(feeds, "INDICE", tmp_path / "nao-existe")
    assert feeds.deputados_por_uf() == {}


def test_feeds_deputados_por_uf_json_malformado_levanta(monkeypatch, tmp_path):
    (tmp_path / "SP.json").write_text("{ruim", encoding="utf-8")
    monkeypatch.setattr(feeds, "INDICE", tmp_path)
    with pytest.raises(ValueError):
        feeds.deputados_por_uf()


def test_feeds_dias_junta_commits_do_mesmo_dia_e_ignora_raso(monkeypatch):
    ts2 = TS + 3600
    ts_velho = TS - 86400 * 3

    def git(*a):
        if a[0] == "log":
            return "\n".join([f"c2 {ts2}", f"c1 {TS}", f"c3 {ts_velho}", f"raso {TS - 86400 * 5}"])
        if a[0] == "rev-parse":
            if a[-1].startswith("raso"):
                raise subprocess.CalledProcessError(1, "git")
            return ""
    monkeypatch.setattr(r, "git", git)
    assert feeds.dias(14) == [("c1~1", "c2", "2026-11-02"), ("c3~1", "c3", "2026-10-30")]
    assert feeds.dias(1) == [("c1~1", "c2", "2026-11-02")]


def test_feeds_main_escreve_um_arquivo_por_codigo_e_limpa_os_antigos(monkeypatch, tmp_path, capsys):
    saida = tmp_path / "feeds"
    saida.mkdir()
    (saida / "antigo.xml").write_text("x", encoding="utf-8")
    d = vazio_d(camara=[prop(1, [7])])
    chamadas = []
    monkeypatch.setattr(feeds, "SAIDA", saida)
    monkeypatch.setattr(feeds, "rotulos", lambda: {"BR": "Tudo", "UF:SP": "Estado: São Paulo", "UF:RJ": "Estado: Rio", "min:saude": "Ministro"})
    monkeypatch.setattr(feeds, "deputados_por_uf", lambda: {"SP": {7}, "RJ": {8}})
    monkeypatch.setattr(feeds, "dias", lambda n: chamadas.append(n) or [("a~1", "a", "2026-11-02")])
    monkeypatch.setattr(r, "dia_da_coleta", lambda rev: "2026-11-03")
    monkeypatch.setattr(r, "coletar", lambda antes, depois, dia: d)
    monkeypatch.setattr(sys, "argv", ["feeds.py", "--dias", "5"])
    feeds.main()
    assert chamadas == [5]
    assert not (saida / "antigo.xml").exists()
    assert sorted(p.name for p in saida.glob("*.xml")) == ["BR.xml", "UF-RJ.xml", "UF-SP.xml", "min-saude.xml"]
    assert (saida / "BR.xml").read_text(encoding="utf-8").count("<item>") == 1
    assert (saida / "UF-SP.xml").read_text(encoding="utf-8").count("<item>") == 1
    assert "<item>" not in (saida / "UF-RJ.xml").read_text(encoding="utf-8")
    assert "<item>" not in (saida / "min-saude.xml").read_text(encoding="utf-8")
    assert "<title>Minha Bancada — Tudo</title>" in (saida / "BR.xml").read_text(encoding="utf-8")
    assert "Feeds: 4 arquivos, 2 com itens, 1 dias lidos" in capsys.readouterr().out


def test_feeds_main_sem_dias_grava_feeds_vazios(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(feeds, "SAIDA", tmp_path / "novo")
    monkeypatch.setattr(feeds, "rotulos", lambda: {"BR": "Tudo"})
    monkeypatch.setattr(feeds, "deputados_por_uf", lambda: {})
    monkeypatch.setattr(feeds, "dias", lambda n: [])
    monkeypatch.setattr(sys, "argv", ["feeds.py"])
    feeds.main()
    assert "<item>" not in (tmp_path / "novo" / "BR.xml").read_text(encoding="utf-8")
    assert "Feeds: 1 arquivos, 0 com itens, 0 dias lidos" in capsys.readouterr().out


# ---------------------------------------------------------------- historico: git e main

def test_historico_dia_do_commit_e_momento(monkeypatch):
    monkeypatch.setattr(r, "git", lambda *a: f"{TS}\n")
    assert h.dia_do_commit("HEAD") == "2026-11-03"
    assert h.momento_do_commit("HEAD") == "2026-11-03T09:00:00-03:00"
    monkeypatch.setattr(r, "git", lambda *a: "\n")
    assert h.dia_do_commit("HEAD") is None and h.momento_do_commit("HEAD") is None


def test_historico_listar_devolve_caminhos_ou_vazio_em_erro(monkeypatch):
    monkeypatch.setattr(r, "git", lambda *a: "dados/a.json\ndados/b.json\n")
    assert h.listar("HEAD", "dados/") == ["dados/a.json", "dados/b.json"]

    def erro(*a):
        raise subprocess.CalledProcessError(128, "git")
    monkeypatch.setattr(r, "git", erro)
    assert h.listar("HEAD", "dados/") == []


def test_historico_ler_lote_le_existentes_e_pula_ausentes(monkeypatch):
    corpo_a = b'{"a": 1}'
    saida = b"sha1 blob " + str(len(corpo_a)).encode() + b"\n" + corpo_a + b"\n" + b"HEAD:dados/b.json missing\n"
    chamadas = []

    def run(cmd, **kw):
        chamadas.append((cmd, kw["input"]))
        return subprocess.CompletedProcess(cmd, 0, stdout=saida)
    monkeypatch.setattr(h.subprocess, "run", run)
    assert h.ler_lote("HEAD", ["dados/a.json", "dados/b.json"]) == {"dados/a.json": {"a": 1}}
    assert chamadas[0][1] == b"HEAD:dados/a.json\nHEAD:dados/b.json\n"
    assert h.ler_lote("HEAD", []) == {}
    assert len(chamadas) == 1


def test_historico_ler_lote_ignora_json_invalido(monkeypatch):
    corpo = b"nao json"
    saida = b"sha blob " + str(len(corpo)).encode() + b"\n" + corpo + b"\n"
    monkeypatch.setattr(h.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=saida))
    assert h.ler_lote("HEAD", ["dados/a.json"]) == {}


def test_historico_coleta_anterior_usa_dia_gravado_antes(tmp_path, monkeypatch):
    (tmp_path / "2026-10-30.json").write_text(json.dumps({"coletaEm": "2026-10-30T09:00:00-03:00"}), encoding="utf-8")
    (tmp_path / "2026-11-02.json").write_text(json.dumps({"coletaEm": "2026-11-02T09:00:00-03:00"}), encoding="utf-8")
    (tmp_path / "2026-11-05.json").write_text(json.dumps({"coletaEm": "futuro"}), encoding="utf-8")
    monkeypatch.setattr(h, "momento_do_commit", lambda rev: pytest.fail("não deve cair no git"))
    assert h.coleta_anterior("2026-11-03", "A", tmp_path) == "2026-11-02T09:00:00-03:00"


def test_historico_coleta_anterior_cai_no_commit_sem_arquivo_ou_sem_campo(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "momento_do_commit", lambda rev: f"commit-{rev}")
    assert h.coleta_anterior("2026-11-03", "A", tmp_path) == "commit-A"
    (tmp_path / "2026-11-02.json").write_text(json.dumps({"eventos": []}), encoding="utf-8")
    assert h.coleta_anterior("2026-11-03", "A", tmp_path) == "commit-A"
    (tmp_path / "2026-11-02.json").write_text("{ruim", encoding="utf-8")
    assert h.coleta_anterior("2026-11-03", "A", tmp_path) == "commit-A"


def test_historico_espelhar_copia_substitui_e_ignora_origem_ausente(tmp_path):
    origem, destino = tmp_path / "o", tmp_path / "d"
    origem.mkdir()
    (origem / "a.json").write_text("1", encoding="utf-8")
    destino.mkdir()
    (destino / "velho.json").write_text("x", encoding="utf-8")
    h.espelhar(origem, destino)
    assert sorted(p.name for p in destino.iterdir()) == ["a.json"]
    h.espelhar(tmp_path / "nada", destino)
    assert (destino / "a.json").exists()


def evento_dia(data):
    return {"data": data, "eventos": [{"relevancia": 3}], "locais": {"BR": "Brasil"}, "contagem": {"BR": {"nova": 1}}}


@pytest.fixture
def main_historico(monkeypatch, tmp_path):
    estado = {"dia": [], "espelho": []}
    monkeypatch.setattr(h, "dia", lambda data, antes, depois, em, ant: estado["dia"].append((data, antes, depois, em, ant)) or evento_dia(data))
    monkeypatch.setattr(h, "coleta_anterior", lambda data, antes, pasta: f"ant-{data}")
    monkeypatch.setattr(h, "espelhar", lambda o, d: estado["espelho"].append((o, d)))
    monkeypatch.setattr(h, "SITE_PASTA", tmp_path / "site")
    monkeypatch.delenv("COLETA_INICIO", raising=False)

    def rodar(*args):
        monkeypatch.setattr(sys, "argv", ["historico.py", *args])
        h.main()
    return estado, rodar


def test_historico_main_com_revisoes_explicitas(main_historico, monkeypatch, tmp_path, capsys):
    estado, rodar = main_historico
    monkeypatch.setattr(h, "dia_do_commit", lambda rev, *a: "2026-11-03")
    monkeypatch.setenv("COLETA_INICIO", "2026-11-03T09:00:00-03:00")
    saida = tmp_path / "hist"
    rodar("A", "B", "--saida", str(saida))
    assert estado["dia"] == [("2026-11-03", "A", "B", "2026-11-03T09:00:00-03:00", "ant-2026-11-03")]
    assert json.loads((saida / "2026-11-03.json").read_text(encoding="utf-8"))["data"] == "2026-11-03"
    assert json.loads((saida / "indice.json").read_text(encoding="utf-8"))[0]["total"] == 1
    assert estado["espelho"] == [(saida, tmp_path / "site")]
    assert "Histórico de 2026-11-03: 1 eventos em 1 locais" in capsys.readouterr().out


def test_historico_main_depois_padrao_e_head(main_historico, monkeypatch, tmp_path):
    estado, rodar = main_historico
    consultadas = []
    monkeypatch.setattr(h, "dia_do_commit", lambda rev, *a: consultadas.append(rev) or "2026-11-03")
    rodar("A", "--saida", str(tmp_path / "hist"))
    assert consultadas == ["HEAD"] and estado["dia"][0][2] == "HEAD"


def test_historico_main_dias_so_o_primeiro_recebe_coleta_inicio(main_historico, monkeypatch, tmp_path):
    estado, rodar = main_historico
    monkeypatch.setattr(h, "dias_git", lambda n: [("2026-11-03", "a1", "b1"), ("2026-11-02", "a0", "b0")] if n == 2 else [])
    monkeypatch.setenv("COLETA_INICIO", "inicio")
    rodar("--dias", "2", "--saida", str(tmp_path / "hist"))
    assert [x[3] for x in estado["dia"]] == ["inicio", None]
    indice = json.loads((tmp_path / "hist" / "indice.json").read_text(encoding="utf-8"))
    assert [x["data"] for x in indice] == ["2026-11-03", "2026-11-02"]


def test_historico_main_sem_dias_avisa_e_ainda_espelha(main_historico, monkeypatch, tmp_path, capsys):
    estado, rodar = main_historico
    monkeypatch.setattr(h, "dias_git", lambda n: [])
    rodar("--saida", str(tmp_path / "hist"))
    assert estado["dia"] == [] and len(estado["espelho"]) == 1
    assert "Nenhum dia com commit de dados" in capsys.readouterr().out


def test_historico_main_so_espelhar_nao_toca_no_git(main_historico, monkeypatch, tmp_path):
    estado, rodar = main_historico
    monkeypatch.setattr(h, "dias_git", lambda n: pytest.fail("não deve ler o git"))
    rodar("--so-espelhar", "--saida", str(tmp_path / "hist"))
    assert estado["dia"] == [] and estado["espelho"] == [(tmp_path / "hist", tmp_path / "site")]


# ---------------------------------------------------------------- contrato_apis: main

def fake_endpoints(monkeypatch):
    monkeypatch.setattr(c, "ENDPOINTS", [c.Endpoint("um", "https://um.example", lambda ctx: {}), c.Endpoint("dois", "https://dois.example", lambda ctx: {})])


def test_contrato_main_listar_imprime_nome_e_fonte(monkeypatch, capsys):
    fake_endpoints(monkeypatch)
    monkeypatch.setattr(c.sys, "argv", ["contrato_apis.py", "--listar"])
    assert c.main() == 0
    saida = capsys.readouterr().out.splitlines()
    assert saida[0].split() == ["um", "https://um.example"] and saida[1].split() == ["dois", "https://dois.example"]


def test_contrato_main_nome_desconhecido_sai(monkeypatch):
    fake_endpoints(monkeypatch)
    monkeypatch.setattr(c.sys, "argv", ["contrato_apis.py", "--verificar", "tres"])
    with pytest.raises(SystemExit) as e:
        c.main()
    assert str(e.value.code) == "Desconhecidos: ['tres']"


def test_contrato_main_despacha_gravar_e_verificar(monkeypatch):
    fake_endpoints(monkeypatch)
    chamadas = []
    monkeypatch.setattr(c, "gravar", lambda nomes: chamadas.append(("gravar", nomes)) or 7)
    monkeypatch.setattr(c, "verificar", lambda nomes: chamadas.append(("verificar", nomes)) or 3)
    monkeypatch.setattr(c.sys, "argv", ["contrato_apis.py", "--gravar", "um"])
    assert c.main() == 7
    monkeypatch.setattr(c.sys, "argv", ["contrato_apis.py", "--verificar"])
    assert c.main() == 3
    assert chamadas == [("gravar", ["um"]), ("verificar", [])]


def test_contrato_main_exige_um_modo(monkeypatch):
    fake_endpoints(monkeypatch)
    monkeypatch.setattr(c.sys, "argv", ["contrato_apis.py"])
    with pytest.raises(SystemExit) as e:
        c.main()
    assert e.value.code == 2


def test_contrato_main_modos_sao_exclusivos(monkeypatch):
    fake_endpoints(monkeypatch)
    monkeypatch.setattr(c.sys, "argv", ["contrato_apis.py", "--gravar", "--verificar"])
    with pytest.raises(SystemExit) as e:
        c.main()
    assert e.value.code == 2
