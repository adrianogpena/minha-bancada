import json
import zipfile
from io import BytesIO

import coletar_estadual_rs as rs
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

DEPUTADOS = [
    {"id": "10", "nome": "Adriano", "nomeCivil": "Adriano Marques Dornelles"},
    {"id": "11", "nome": "Outro", "nomeCivil": "Outro Deputado da Silva"},
]


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_arquivos_por_ano_do_contrato():
    achados = rs.arquivos_por_ano(amostra("estadual_rs_ckan"))
    assert achados and all(u.endswith(".zip") for u in achados.values())
    assert all(2004 <= a <= 2100 for a in achados)


def test_arquivos_por_ano_ignora_layout_pdf():
    pacote = {"result": {"resources": [{"name": "Layout Diarias", "url": "https://x/layout.pdf"},
                                       {"name": "Diárias 2025", "url": "https://x/diarias.zip"}, {"name": "Diarias 2024", "url": "https://x/d.pdf"}]}}
    assert rs.arquivos_por_ano(pacote) == {2025: "https://x/diarias.zip"}


def test_linhas_da_assembleia_filtra_orgao():
    texto = "Orgao;Favorecido\nASSEMBLEIA LEGISLATIVA;A\nSECRETARIA DA SAUDE;B\n"
    assert [linha["Favorecido"] for linha in rs.linhas_da_assembleia(texto)] == ["A"]


def test_itens_diarias_so_de_deputados_do_contrato():
    a = amostra("estadual_rs_diarias")
    linhas = rs.linhas_da_assembleia(a["csv"])
    itens = rs.itens_diarias(linhas, DEPUTADOS)
    assert itens and {i["idDeputado"] for i in itens} == {"10"}
    primeiro = itens[0]
    assert primeiro["data"] == "2025-12-12" and primeiro["valor"] == 222.38
    assert primeiro["fonte"] == rs.PAGINA_DIARIAS
    assert rs.itens_diarias(linhas, [DEPUTADOS[1]]) == []


def test_conferir_contrato_diarias():
    assert rs._conferir_diarias(amostra("estadual_rs_diarias")) == ([], [])
    falhas, _ = rs._conferir_diarias({"csv": "Exercicio;Orgao\n2026;ASSEMBLEIA"})
    assert any("Favorecido" in f for f in falhas)


def test_ler_zip_csv_decodifica_cp1252():
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Diarias.csv", "Orgao;Favorecido\nASSEMBLEIA;JOS\xc9\n".encode("cp1252"))
    assert "JOS\xc9" in rs.ler_zip_csv(buf.getvalue())


def test_coletar_grava_deputados_e_diarias(tmp_path, monkeypatch):
    a = amostra("estadual_rs_diarias")
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Diarias-RS-2026.csv", a["csv"].encode("cp1252", errors="replace"))
    pacote = {"result": {"resources": [{"name": "Diárias 2026", "url": "https://dados.rs.gov.br/d.zip"}, {"name": "Diarias 2020", "url": "https://x/20.zip"}]}}

    class Resp:
        def __init__(self, conteudo=None, dados=None):
            self.content, self._dados = conteudo, dados

        def raise_for_status(self):
            pass

        def json(self):
            return self._dados

    class Sessao:
        def get(self, url, timeout=None):
            return Resp(dados=pacote) if "package_show" in url else Resp(conteudo=buf.getvalue())

    tse = [{"cargo": "DEPUTADO ESTADUAL", "situacao": "eleito", "sequencial": "10", "urna": "Adriano", "nome": "ADRIANO MARQUES DORNELLES", "partido": "PP", "email": None},
           {"cargo": "VEREADOR", "situacao": "eleito", "sequencial": "9", "urna": "X", "nome": "X"}]
    arquivo = tmp_path / "RS.json"
    arquivo.write_text(json.dumps(tse), encoding="utf-8")
    monkeypatch.setattr(rs, "TSE_ARQUIVO", arquivo)
    monkeypatch.setattr(comum, "DADOS", tmp_path / "estaduais")
    monkeypatch.setattr(comum, "sessao", Sessao)
    rs.coletar()
    pasta = tmp_path / "estaduais" / "RS"
    deps = json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))
    assert [d["id"] for d in deps["deputados"]] == ["10"] and deps["host"] is None
    diarias = json.loads((pasta / "diarias_2026.json").read_text(encoding="utf-8"))
    assert diarias["itens"] and all(i["idDeputado"] == "10" for i in diarias["itens"])
    assert not (pasta / "diarias_2020.json").exists()
