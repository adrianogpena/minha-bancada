import json
from pathlib import Path

import fornecedores as forn
import identidades

TIM = "02421421000111"       # CNPJs reais de grandes empresas, com dígito verificador válido
VIVO = "02558157000162"
VIVO_FILIAL = "02558157001053"


def gravar(caminho, obj):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def test_documento_valida_digito_e_recupera_zero_perdido():
    assert forn.documento("02.421.421/0001-11") == ("cnpj", TIM)
    assert forn.documento("2421421000111") == ("cnpj", TIM)               # planilha perdeu o zero
    assert forn.documento("111.444.777-35") == ("cpf", "11144477735")
    assert forn.documento("11144477735") == ("cpf", "11144477735")
    for ruim in (None, "", "0", "00000000000000", "11111111111", "02421421000112", "***.444.777-**", "123", "1" * 15, "abc"):
        assert forn.documento(ruim) is None, ruim


def test_nome_chave_ignora_caixa_acento_pontuacao_e_forma_juridica():
    chaves = {forn.nome_chave(n) for n in ("TIM S/A", "Tim S.A.", "tim s a", "TIM SA", "Tim  S. A .")}
    assert chaves == {"TIM"}
    assert forn.nome_chave("Telefônica Brasil S/A") == forn.nome_chave("TELEFONICA BRASIL SA") == "TELEFONICA BRASIL"
    assert forn.nome_chave("Casa & Cia Ltda") == "CASA E"
    assert forn.nome_chave(None) == ""


def test_nome_exibido_prefere_a_grafia_de_maior_valor_e_arruma_minusculas():
    from collections import Counter
    assert forn.nome_exibido(Counter({"TIM S/A": 10, "tim s.a": 3})) == "TIM S/A"
    assert forn.nome_exibido(Counter({"tim s.a": 9, "TIM SA": 1})) == "TIM SA"
    assert forn.nome_exibido(Counter({"tim s.a": 9})) == "Tim S.A"


def test_mascarar_e_formatar():
    assert forn.mascarar_cpf("11144477735") == "***.444.777-**"
    assert forn.formatar_cnpj(TIM) == "02.421.421/0001-11"


def montar(bruto):
    gravar(bruto / "tse" / "2022" / "SP.json", [{"sequencial": "10", "nome": "Carlos Lima", "urna": "Carlão", "cargo": "DEPUTADO ESTADUAL", "uf": "SP",
                                                 "nascimento": "1970-05-05", "partido": "PL", "federacao": None}])
    gravar(bruto / "estaduais" / "SP" / "deputados.json", {"deputados": [{"id": "a", "nome": "Carlão", "nomeCivil": "Carlos Lima", "partido": "PL"}]})
    gravar(bruto / "estaduais" / "SP" / "verbas_2026.json", {"itens": [
        {"idDeputado": "a", "fornecedor": "tim s.a", "cnpj": TIM, "valor": 100.0},
        {"idDeputado": "a", "fornecedor": "TIM S/A", "cnpj": "", "valor": 50.0},            # sem CNPJ: pelo nome vira TIM
        {"idDeputado": "a", "fornecedor": "Vivo", "cnpj": "2558157000162", "valor": 30.0},
        {"idDeputado": "a", "fornecedor": "Vivo filial", "cnpj": VIVO_FILIAL, "valor": 20.0},  # filial soma com a matriz
        {"idDeputado": "a", "fornecedor": "Mercadinho", "cnpj": "", "valor": 5.0},
        {"idDeputado": "a", "fornecedor": "", "cnpj": "", "valor": 7.0}]})
    gravar(bruto / "estaduais" / "SP" / "verbas_2025.json", {"itens": [{"idDeputado": "a", "fornecedor": "Antiga", "cnpj": TIM, "valor": 999.0}]})


def test_ranking_nacional_junta_casas_filiais_e_grafias(tmp_path):
    montar(tmp_path)
    camara = {1: {"id": 1, "nome": "Ana", "partido": "PT", "uf": "RJ", "nomeCivil": "Ana Souza", "nascimento": "1980-01-02",
                  "despesas": {"ano": 2026, "itens": [{"fornecedor": "TIM S.A.", "cnpj": "02421421000111", "valor": 400.0},
                                                      {"fornecedor": "Cpf Pessoa", "cnpj": "11144477735", "valor": 10.0},
                                                      {"fornecedor": "Lixo", "cnpj": "00000000000001", "valor": 3.0}]}}}
    (tmp_path / "senado.json").write_text(json.dumps([{"id": "7", "nome": "Bia", "partido": "PL", "uf": "RJ"}]), encoding="utf-8")
    gravar(tmp_path / "senado_ceaps.json", {"ano": 2026, "itens": {"7": [{"fornecedor": "Tim", "cnpj": "", "valor": 1.0, "mes": 1}]}})
    nucleo = identidades.construir(camara, tmp_path)
    r = forn.construir(camara, tmp_path, nucleo)
    ranking = r["ranking"]
    assert ranking["ano"] == 2026
    nomes = [f["nome"] for f in ranking["fornecedores"]]
    assert nomes[0].upper().startswith("TIM") and ranking["fornecedores"][0]["id"] == "for_02421421"
    tim = ranking["fornecedores"][0]
    assert tim["total"] == 551.0 and tim["notas"] == 4 and tim["documento"] == "02.421.421/0001-11"
    assert tim["porCasa"] == {"camara": 400.0, "estadual": 150.0, "senado": 1.0} and tim["politicos"] == 3   # 2025 não entra
    assert [m["nome"] for m in tim["maioresPoliticos"]] == ["Ana", "Carlão", "Bia"]
    assert tim["maioresPoliticos"][0]["pagina"] == "deputado.html?id=1" and tim["maioresPoliticos"][2]["pagina"] == "politico.html?f=senado&i=7"
    assert tim["maioresPoliticos"][1]["pagina"] == "politico.html?f=t/2022/SP&i=10"
    vivo = next(f for f in ranking["fornecedores"] if f["id"] == "for_02558157")
    assert vivo["total"] == 50.0 and vivo["documento"] == "02.558.157/0001-62"        # matriz em destaque, filial somada
    pf = next(f for f in ranking["fornecedores"] if f["tipo"] == "PF")
    assert pf["documento"] == "***.444.777-**" and pf["id"].startswith("for_pf_") and "11144477735" not in json.dumps(r)
    sem = next(f for f in ranking["fornecedores"] if f["nome"] == "Mercadinho")
    assert sem["semDocumento"] is True and sem["id"].startswith("for_n_")
    lixo = next(f for f in ranking["fornecedores"] if f["nome"] == "Lixo")
    assert lixo["semDocumento"] is True                                              # documento inválido não vira CNPJ
    resumo = ranking["resumo"]
    assert resumo["linhas"]["documentoPeloNome"] == 2 and resumo["linhas"]["documentoInvalido"] == 1 and resumo["totalSemIdentificacao"] == 7.0
    assert len({e["id"] for e in r["entidades"]}) == len(r["entidades"])
    assert next(e for e in r["entidades"] if e["id"] == "for_02558157")["estabelecimentos"] == 2


def test_salvar_fornecedores(tmp_path):
    montar(tmp_path)
    nucleo = identidades.construir({}, tmp_path)
    forn.salvar_fornecedores(forn.construir({}, tmp_path, nucleo), tmp_path / "saida")
    assert json.loads((tmp_path / "saida" / "fornecedores.json").read_text(encoding="utf-8"))["ano"] == 2026
    assert (tmp_path / "saida" / "nucleo" / "fornecedores.json").is_file()
