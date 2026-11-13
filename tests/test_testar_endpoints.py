"""Teste de endpoints (scripts/testar_endpoints.py), sem rede."""
import datetime as dt
import json

import pytest
import requests

import testar_endpoints as te

TABELA = (
    "# Endpoints\n\n"
    "| Nome | Grupo | URL de teste | Usado em | Status | Verificado em | Detalhe |\n"
    "|---|---|---|---|---|---|---|\n"
    "| alfa | Câmara | https://a.example/x | coletar | ❔ | - | - |\n"
    "| beta | Senado | https://b.example/y | coletar | ❔ | - | - |\n"
)


class Resposta:
    def __init__(self, status=200, tipo="application/json; charset=utf-8", tamanho=None, json_ok=True):
        self.status_code, self.ok = status, status < 400
        self.headers = {"Content-Type": tipo}
        if tamanho is not None:
            self.headers["Content-Length"] = str(tamanho)
        self.json_ok = json_ok

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def json(self):
        if not self.json_ok:
            raise ValueError("ruim")
        return {}


def falsa_get(monkeypatch, *respostas):
    chamadas = []
    fila = list(respostas)

    def get(url, **kw):
        chamadas.append((url, kw))
        item = fila.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(te.requests, "get", get)
    return chamadas


def test_testar_sucesso_com_tipo_e_tamanho_em_kb(monkeypatch):
    falsa_get(monkeypatch, Resposta(tamanho=3072))
    assert te.testar("https://a.example/x") == (True, "HTTP 200, application/json, 3 KB")


def test_testar_tamanho_em_mb_e_sem_content_length(monkeypatch):
    falsa_get(monkeypatch, Resposta(tipo="application/zip", tamanho=5_000_000), Resposta(tipo="text/html"))
    assert te.testar("https://a.example/x") == (True, "HTTP 200, application/zip, 5.0 MB")
    assert te.testar("https://a.example/x") == (True, "HTTP 200, text/html")


def test_testar_erro_http(monkeypatch):
    falsa_get(monkeypatch, Resposta(status=503))
    assert te.testar("https://a.example/x") == (False, "HTTP 503")


def test_testar_json_invalido_pequeno_e_grande(monkeypatch):
    falsa_get(monkeypatch, Resposta(json_ok=False, tamanho=10), Resposta(json_ok=False, tamanho=te.LIMITE_JSON + 1))
    assert te.testar("https://a.example/x") == (False, "HTTP 200, JSON inválido")
    ok, detalhe = te.testar("https://a.example/x")
    assert ok is True and detalhe.endswith("MB")


def test_testar_cabecalhos_xhr_so_para_host_listado(monkeypatch):
    chamadas = falsa_get(monkeypatch, Resposta(), Resposta())
    te.testar("https://transparencia.assembleia.pr.leg.br/api/x")
    te.testar("https://a.example/x")
    assert chamadas[0][1]["headers"]["X-Requested-With"] == "XMLHttpRequest"
    assert chamadas[0][1]["headers"]["Accept"] == "application/json"
    assert "X-Requested-With" not in chamadas[1][1]["headers"]
    assert chamadas[1][1]["verify"] is True and chamadas[1][1]["stream"] is True


def test_testar_ssl_repete_com_cadeia_extra(monkeypatch):
    chamadas = falsa_get(monkeypatch, requests.exceptions.SSLError("x"), Resposta(tamanho=2048))
    monkeypatch.setattr(te, "bundle_extra", lambda: "cadeia.pem")
    ok, detalhe = te.testar("https://a.example/x")
    assert ok is True and detalhe.endswith("; só com a cadeia extra de scripts/certs")
    assert [c[1]["verify"] for c in chamadas] == [True, "cadeia.pem"]


def test_testar_ssl_que_continua_falhando_troca_pipe_e_corta(monkeypatch):
    falsa_get(monkeypatch, requests.exceptions.SSLError("a"), requests.exceptions.SSLError("a|b" + "z" * 200))
    monkeypatch.setattr(te, "bundle_extra", lambda: "cadeia.pem")
    ok, detalhe = te.testar("https://a.example/x")
    assert ok is False and detalhe.startswith("SSLError: a/b") and len(detalhe) == len("SSLError: ") + 100


def test_testar_conexao_repete_uma_vez(monkeypatch):
    chamadas = falsa_get(monkeypatch, requests.ConnectionError("reset"), Resposta())
    assert te.testar("https://a.example/x")[0] is True
    assert len(chamadas) == 2


def test_testar_conexao_que_falha_duas_vezes_limpa_a_mensagem(monkeypatch):
    chamadas = falsa_get(monkeypatch, requests.ConnectionError("a|b"), requests.ConnectionError("linha1\nlinha2|x"))
    assert te.testar("https://a.example/x") == (False, "ConnectionError: linha1 linha2/x")
    assert len(chamadas) == 2


def test_testar_timeout_nao_repete(monkeypatch):
    chamadas = falsa_get(monkeypatch, requests.Timeout("lento"))
    assert te.testar("https://a.example/x") == (False, "Timeout: lento")
    assert len(chamadas) == 1


def test_bundle_extra_junta_cadeia_do_sistema_e_dos_scripts(monkeypatch, tmp_path):
    certs = tmp_path / "scripts" / "certs"
    certs.mkdir(parents=True)
    (certs / "b.pem").write_text("CERT-B", encoding="ascii")
    (certs / "a.pem").write_text("CERT-A", encoding="ascii")
    sistema = tmp_path / "sistema.pem"
    sistema.write_text("SISTEMA", encoding="ascii")
    import certifi
    import tempfile
    monkeypatch.setattr(te, "RAIZ", tmp_path)
    monkeypatch.setattr(certifi, "where", lambda: str(sistema))
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    caminho = te.bundle_extra()
    assert (tmp_path / "minha_bancada_ca_endpoints.pem").read_text(encoding="ascii") == "SISTEMA\nCERT-A\nCERT-B"
    assert caminho == str(tmp_path / "minha_bancada_ca_endpoints.pem")


def test_ler_tabela_ignora_cabecalho_separador_e_texto():
    achados = te.ler_tabela(TABELA.split("\n"))
    assert [(i, c[0]) for i, c in achados] == [(4, "alfa"), (5, "beta")]
    assert achados[0][1][2] == "https://a.example/x" and len(achados[0][1]) == 7


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    arq = tmp_path / "ENDPOINTS.md"
    arq.write_text(TABELA, encoding="utf-8")
    status = tmp_path / "dados" / "status_apis.json"
    monkeypatch.setattr(te, "ARQUIVO", arq)
    monkeypatch.setattr(te, "STATUS", status)
    return arq, status


def alvo_de(arq, *nomes):
    return [(i, c) for i, c in te.ler_tabela(arq.read_text(encoding="utf-8").split("\n")) if not nomes or c[0] in nomes]


def test_atualizar_status_cria_arquivo_com_primeira_verificacao_e_ultimo_ok(ambiente):
    arq, status = ambiente
    te.atualizar_status(alvo_de(arq), [(True, "HTTP 200"), (False, "HTTP 500")], "2026-11-03T10:00:00Z")
    gravado = json.loads(status.read_text(encoding="utf-8"))
    assert gravado["alfa"] == {"grupo": "Câmara", "url": "https://a.example/x", "ok": True, "detalhe": "HTTP 200",
                               "verificadoEm": "2026-11-03T10:00:00Z", "primeiraVerificacao": "2026-11-03T10:00:00Z",
                               "ultimoOk": "2026-11-03T10:00:00Z"}
    assert gravado["beta"]["ok"] is False and gravado["beta"]["ultimoOk"] is None


def test_atualizar_status_preserva_historico_e_descarta_o_que_saiu_da_tabela(ambiente):
    arq, status = ambiente
    status.parent.mkdir(parents=True)
    status.write_text(json.dumps({
        "alfa": {"primeiraVerificacao": "2026-01-01T00:00:00Z", "ultimoOk": "2026-10-01T00:00:00Z"},
        "beta": {"primeiraVerificacao": "2026-02-01T00:00:00Z", "ultimoOk": "2026-10-02T00:00:00Z"},
        "velho": {"ok": True},
    }), encoding="utf-8")
    te.atualizar_status(alvo_de(arq, "alfa"), [(False, "HTTP 500")], "2026-11-03T10:00:00Z")
    gravado = json.loads(status.read_text(encoding="utf-8"))
    assert set(gravado) == {"alfa", "beta"}
    assert gravado["alfa"]["primeiraVerificacao"] == "2026-01-01T00:00:00Z"
    assert gravado["alfa"]["ultimoOk"] == "2026-10-01T00:00:00Z" and gravado["alfa"]["ok"] is False
    assert gravado["beta"]["ultimoOk"] == "2026-10-02T00:00:00Z"


def rodar_main(monkeypatch, *args):
    monkeypatch.setattr(te.sys, "argv", ["testar_endpoints.py", *args])
    return te.main()


def test_main_listar_nao_consulta_nem_grava(ambiente, monkeypatch, capsys):
    arq, status = ambiente
    monkeypatch.setattr(te, "testar", lambda url: pytest.fail("não deve consultar"))
    assert rodar_main(monkeypatch, "--listar") == 0
    saida = capsys.readouterr().out
    assert "alfa" in saida and "https://b.example/y" in saida and "coletar" not in saida
    assert not status.exists() and arq.read_text(encoding="utf-8") == TABELA


def test_main_nome_desconhecido_sai_com_mensagem(ambiente, monkeypatch):
    monkeypatch.setattr(te, "testar", lambda url: pytest.fail("não deve consultar"))
    with pytest.raises(SystemExit) as e:
        rodar_main(monkeypatch, "alfa", "zeta", "omega")
    assert str(e.value.code) == "não está no ENDPOINTS.md: omega, zeta"


def test_main_reescreve_tabela_e_devolve_1_com_erro(ambiente, monkeypatch, capsys):
    arq, status = ambiente
    monkeypatch.setattr(te, "testar", lambda url: (True, "HTTP 200") if "a.example" in url else (False, "HTTP 500"))
    assert rodar_main(monkeypatch) == 1
    hoje = dt.date.today().isoformat()
    linhas = arq.read_text(encoding="utf-8").split("\n")
    assert linhas[4] == f"| alfa | Câmara | https://a.example/x | coletar | ✅ OK | {hoje} | HTTP 200 |"
    assert linhas[5] == f"| beta | Senado | https://b.example/y | coletar | ❌ ERRO | {hoje} | HTTP 500 |"
    saida = capsys.readouterr().out
    assert "1/2 funcionando; com erro: beta" in saida and "OK   alfa" in saida and "ERRO beta" in saida
    assert json.loads(status.read_text(encoding="utf-8"))["beta"]["ok"] is False


def test_main_todos_ok_devolve_0(ambiente, monkeypatch, capsys):
    monkeypatch.setattr(te, "testar", lambda url: (True, "HTTP 200"))
    assert rodar_main(monkeypatch) == 0
    assert "2/2 funcionando" in capsys.readouterr().out


def test_main_so_os_nomes_pedidos(ambiente, monkeypatch):
    arq, status = ambiente
    consultadas = []
    monkeypatch.setattr(te, "testar", lambda url: consultadas.append(url) or (True, "HTTP 200"))
    assert rodar_main(monkeypatch, "beta") == 0
    assert consultadas == ["https://b.example/y"]
    assert "❔" in arq.read_text(encoding="utf-8").split("\n")[4]
    assert "✅ OK" in arq.read_text(encoding="utf-8").split("\n")[5]


def test_main_sem_tabela_nao_reescreve_o_markdown_mas_grava_status(ambiente, monkeypatch):
    arq, status = ambiente
    monkeypatch.setattr(te, "testar", lambda url: (True, "HTTP 200"))
    assert rodar_main(monkeypatch, "--sem-tabela") == 0
    assert arq.read_text(encoding="utf-8") == TABELA
    assert set(json.loads(status.read_text(encoding="utf-8"))) == {"alfa", "beta"}
