"""Etapas, requisição e item de órgão de scripts/estaduais_comum.py."""
import pytest
import requests

import estaduais_comum as ec
import identidades
import ids


class Resp:
    def __init__(self, conteudo=b"corpo", erro=None, dados=None):
        self.content, self.erro, self.dados = conteudo, erro, dados

    def raise_for_status(self):
        if self.erro:
            raise self.erro

    def json(self):
        return self.dados


class Sessao:
    def __init__(self, resp):
        self.resp, self.chamadas = resp, []

    def get(self, url, **kw):
        self.chamadas.append((url, kw))
        return self.resp


def test_get_repassa_timeout_e_kwargs_e_devolve_a_resposta():
    s = Sessao(Resp())
    r = ec.get(s, "https://x.example/a", 7, params={"p": 1}, headers={"h": "v"})
    assert r is s.resp
    assert s.chamadas == [("https://x.example/a", {"timeout": 7, "params": {"p": 1}, "headers": {"h": "v"}})]


def test_get_usa_timeout_padrao():
    s = Sessao(Resp())
    ec.get(s, "https://x.example/a")
    assert s.chamadas[0][1]["timeout"] == ec.TIMEOUT_PADRAO


def test_get_levanta_em_erro_http():
    s = Sessao(Resp(erro=requests.HTTPError("500")))
    with pytest.raises(requests.HTTPError):
        ec.get(s, "https://x.example/a")


def test_baixar_devolve_bytes_e_so_manda_params_quando_ha():
    s = Sessao(Resp(b"abc"))
    assert ec.baixar(s, "https://x.example/a") == b"abc"
    assert ec.baixar(s, "https://x.example/a", {"q": 1}, timeout=9) == b"abc"
    assert "params" not in s.chamadas[0][1]
    assert s.chamadas[1][1] == {"timeout": 9, "params": {"q": 1}}


def test_baixar_propaga_erro_http():
    with pytest.raises(requests.HTTPError):
        ec.baixar(Sessao(Resp(erro=requests.HTTPError("404"))), "https://x.example/a")


def test_contrato_json_le_json_da_sessao(monkeypatch):
    s = Sessao(Resp(dados={"a": 1}))
    monkeypatch.setattr(ec, "sessao", lambda: s)
    assert ec.contrato_json("https://x.example/a", timeout=5) == {"a": 1}
    assert s.chamadas == [("https://x.example/a", {"timeout": 5})]


def test_tentar_roda_a_etapa_sem_avisar(monkeypatch):
    avisos, rodou = [], []
    monkeypatch.setattr(ec, "avisar", avisos.append)
    ec.tentar("GO", "deputados", lambda: rodou.append(1))
    assert rodou == [1] and avisos == []


def test_tentar_converte_falha_em_aviso_com_uf_e_rotulo(monkeypatch):
    avisos = []
    monkeypatch.setattr(ec, "avisar", avisos.append)

    def falha():
        raise RuntimeError("quebrou")
    ec.tentar("GO", "verbas", falha)
    assert avisos == ["GO: verbas: quebrou"]


def test_tentar_trata_prazo_esgotado_como_aviso(monkeypatch):
    avisos = []
    monkeypatch.setattr(ec, "avisar", avisos.append)

    def prazo():
        raise ec.PrazoEsgotado("prazo de coleta esgotado")
    ec.tentar("PE", "materias", prazo)
    assert avisos == ["PE: materias: prazo de coleta esgotado"]


def test_tentar_nao_engole_interrupcao():
    def sair():
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        ec.tentar("GO", "x", sair)


def test_rodar_etapas_executa_na_ordem_e_isola_falhas(monkeypatch):
    avisos, ordem = [], []
    monkeypatch.setattr(ec, "avisar", avisos.append)

    def ruim():
        ordem.append("b")
        raise ValueError("x")
    ec.rodar_etapas("MG", [("a", lambda: ordem.append("a")), ("b", ruim), ("c", lambda: ordem.append("c"))])
    assert ordem == ["a", "b", "c"] and avisos == ["MG: b: x"]


def test_rodar_etapas_vazio_nao_faz_nada(monkeypatch):
    monkeypatch.setattr(ec, "avisar", lambda m: pytest.fail("sem aviso"))
    ec.rodar_etapas("MG", [])


def test_principal_coleta_grava_ligacoes_e_sai_com_zero(monkeypatch):
    ordem = []
    monkeypatch.setattr(identidades, "gravar_ligacoes", lambda *a, **k: ordem.append("ligacoes"))
    with pytest.raises(SystemExit) as e:
        ec.principal(lambda: ordem.append("coletar"))
    assert e.value.code == 0 and ordem == ["coletar", "ligacoes"]


def test_principal_nao_grava_ligacoes_se_a_coleta_levanta(monkeypatch):
    monkeypatch.setattr(identidades, "gravar_ligacoes", lambda *a, **k: pytest.fail("não deve gravar"))

    def coleta():
        raise RuntimeError("falhou")
    with pytest.raises(RuntimeError):
        ec.principal(coleta)


CNPJ = "11.222.333/0001-81"


def test_item_orgao_monta_item_com_cnpj_valor_texto_e_arquivos():
    id_, item = ec.item_orgao("estadual_pr", "contrato", 55, fornecedor_nome="  ACME   Ltda ", documento=CNPJ, valor="1.234,50",
                              inicio="2026-01-01", fim="2026-12-31", objeto=" Serviço   de limpeza ", numero="12/2026",
                              arquivos=[{"url": "https://x/a.pdf"}, {"url": None}, {"nome": "sem url"}],
                              fonte="https://x/c/55", modalidade="Pregão")
    assert id_ == ids.gerar_id("ctr", "estadual_pr_contrato", 55)
    assert item["tipo"] == "contrato" and item["idFonte"] == 55 and item["numero"] == "12/2026"
    assert item["fornecedor"] == "ACME Ltda" and item["cnpj"] == "11222333000181"
    assert item["nomeChave"] and item["objeto"] == "Serviço de limpeza"
    assert item["valor"] == 1234.5 and item["inicio"] == "2026-01-01" and item["fim"] == "2026-12-31"
    assert item["arquivos"] == [{"url": "https://x/a.pdf"}]
    assert item["fonte"] == "https://x/c/55" and item["modalidade"] == "Pregão"


def test_item_orgao_valor_numerico_ou_ausente_passa_direto():
    assert ec.item_orgao("f", "ata_registro", 1, fornecedor_nome="A", valor=10)[1]["valor"] == 10
    assert ec.item_orgao("f", "ata_registro", 1, fornecedor_nome="A", valor=2.5)[1]["valor"] == 2.5
    assert ec.item_orgao("f", "ata_registro", 1, fornecedor_nome="A")[1]["valor"] is None


def test_item_orgao_cpf_ou_documento_invalido_nao_vira_cnpj():
    assert ec.item_orgao("f", "contrato", 1, fornecedor_nome="Fulano", documento="529.982.247-25")[1]["cnpj"] is None
    assert ec.item_orgao("f", "contrato", 1, fornecedor_nome="Fulano", documento="123")[1]["cnpj"] is None
    assert ec.item_orgao("f", "contrato", 1, fornecedor_nome="Fulano")[1]["cnpj"] is None


def test_item_orgao_id_depende_de_fonte_tipo_e_id_na_fonte():
    base = ec.item_orgao("f", "contrato", 1, fornecedor_nome="A")[0]
    assert ec.item_orgao("f", "contrato", 1, fornecedor_nome="Outro nome")[0] == base
    assert len({base, ec.item_orgao("f", "ata_adesao", 1, fornecedor_nome="A")[0],
                ec.item_orgao("g", "contrato", 1, fornecedor_nome="A")[0], ec.item_orgao("f", "contrato", 2, fornecedor_nome="A")[0]}) == 4


def test_item_orgao_tipo_desconhecido_levanta():
    with pytest.raises(ValueError, match="desconhecido: leilao"):
        ec.item_orgao("f", "leilao", 1, fornecedor_nome="A")


def test_item_orgao_nome_vazio_fica_none():
    assert ec.item_orgao("f", "contrato", 1, fornecedor_nome="   ")[1]["fornecedor"] is None
