"""Um dados/ mínimo (1 deputado, 1 senador, 1 votação de cada) e a geração do site sobre ele.
Usado por test_gerar_integracao.py e por tests/e2e/preparar_site.py (teste de fumaça no navegador)."""
import json
from unittest import mock

import gerar
import gerar_estaduais
import gerar_politicos
import gerar_prefeituras


def gravar(caminho, obj):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def montar_bruto(bruto):
    gravar(bruto / "deputados.json", [101])
    gravar(bruto / "deputados" / "101.json", {
        "id": 101, "nome": "Ana Souza", "nomeCivil": "Ana Maria Souza", "partido": "PT", "uf": "SP",
        "foto": "https://exemplo/101.jpg", "email": "dep.ana@camara.leg.br", "situacao": "Exercício",
        "condicaoEleitoral": "Titular", "gabinete": {"sala": "10"}, "nascimento": "1980-01-02",
        "municipioNascimento": "Santos", "ufNascimento": "SP", "escolaridade": "Superior", "redesSociais": [],
        "proposicoes": [{"id": 900, "tipo": "PL", "numero": 1, "ano": 2026, "ementa": "Dispõe sobre algo."}],
        "despesas": {"ano": 2026, "itens": [
            {"mes": 1, "tipo": "Passagens", "valor": 120.5, "fornecedor": "Cia Aérea", "cnpj": "12345678000195", "data": "2026-01-10", "documento": None}]},
        "frentes": [{"id": 1, "titulo": "Frente X"}],
        "profissoes": [{"titulo": "Advogada", "desde": "2019-02-06"}], "mandatosExternos": [], "historico": [{"data": "2023-02-01", "partido": "PT"}],
        "discursos": [{"data": "2026-09-02", "tipo": "PELA ORDEM", "link": None}], "coletadoEm": "2026-10-01T00:00:00+00:00"})
    gravar(bruto / "votacoes" / "2026.json", {"1-1": {
        "id": "1-1", "data": "2026-08-12", "hora": "17:58", "orgao": "PLEN", "descricao": "Aprovado.", "proposicao": "PL 1/2026",
        "propId": 900, "ementa": "Dispõe sobre algo.", "aprovada": 1, "votos": [[101, "Sim"], [102, "Não"]]}})
    gravar(bruto / "senado.json", [{"id": "7", "nome": "Bia Lima", "partido": "PL", "uf": "RJ"}])
    gravar(bruto / "senado_ficha.json", {"7": {"comissoes": [{"sigla": "CAE", "nome": "Assuntos Econômicos", "inicio": "2023-02-02", "fim": None}],
                                               "mandatos": [{"uf": "RJ", "inicio": "2023-02-01", "fim": "2031-01-31", "partidos": []}]}})
    gravar(bruto / "senado_atividade.json", {"7": {
        "relatorias": {"total": 2, "tramitando": 1, "porAno": [[2025, 2]], "porColegiado": [["CAE", 2]], "recentes": [
            {"id": "55", "materia": "PL 5/2025", "ementa": "Dispõe sobre algo.", "colegiado": "CAE", "tipo": "Relator", "desde": "2025-03-01", "ate": None, "tramitando": True}]},
        "discursos": {"total": 4, "apartes": 1, "porAno": [[2026, 4]], "assuntos": [["saúde", 3]], "recentes": [
            {"id": "9", "data": "2026-05-01", "tipo": "Pela ordem", "resumo": "Fala sobre saúde.", "url": "https://www25.senado.leg.br/web/atividade/pronunciamentos/-/p/texto/9"}]},
        "cargos": [{"sigla": "CAE", "nome": "Assuntos Econômicos", "cargo": "PRESIDENTE", "inicio": "2025-03-01", "fim": None}],
        "licencas": [{"inicio": "2025-05-20", "fim": "2025-05-21", "tipo": "Missão política"}],
        "liderancas": [{"unidade": "Liderança de Partido", "cargo": "Líder", "casa": "SF", "partido": "PL", "desde": "2025-02-01"}]}})
    gravar(bruto / "senado_votacoes" / "2026.json", {"9": {
        "id": "9", "data": "2026-02-24", "descricao": "Votação X", "aprovada": 1, "votos": [["7", "sim", "Sim|"]]}})
    gravar(bruto / "tse" / "2024" / "SP.json", [
        {"sequencial": "500", "nome": "Vera Eadora", "urna": "Vera", "cargo": "VEREADOR", "situacao": "eleito", "partido": "PT", "federacao": "PT/PC do B/PV",
         "numero": "13123", "uf": "SP", "unidadeEleitoral": "71072", "municipio": "São Paulo", "nascimento": "1980-05-05", "genero": "FEMININO",
         "resultado": "Eleito por qp", "votos": [{"turno": 1, "data": "2024-10-06", "votos": 900, "percentual": 0.5}], "bens": [], "totalBens": 0.0},
        {"sequencial": "501", "nome": "Outro Eador", "urna": "Outro", "cargo": "VEREADOR", "situacao": "eleito", "partido": "PL", "federacao": None,
         "numero": "22456", "uf": "SP", "unidadeEleitoral": "71072", "municipio": "São Paulo", "nascimento": "1975-05-05", "genero": "MASCULINO",
         "resultado": "Eleito por média", "votos": [{"turno": 1, "data": "2024-10-06", "votos": 800, "percentual": 0.4}], "bens": [], "totalBens": 0.0}])
    gravar(bruto / "tse" / "disputa" / "2024" / "SP.json", {"VEREADOR|71072": {"turnos": {"1": {"aptos": 1000, "comparecimento": 800, "abstencoes": 200,
                                                                                                "brancos": 10, "nulos": 20, "validos": 770}}, "vagas": 55}})
    gravar(bruto / "tse" / "partidos" / "2024" / "SP.json", {"VEREADOR|71072": {"totalVotos": 770, "partidos": {
        "PT": [100, 300, "PT/PC do B/PV"], "PC do B": [10, 20, "PT/PC do B/PV"], "PL": [50, 290, ""]}}})
    gravar(bruto / "tse" / "coligacoes" / "2024" / "SP.json", {"VEREADOR|71072": {
        "coligacoes": [["F", "", "Federação BRASIL DA ESPERANÇA (13-PT / 65-PC do B / 43-PV)", "Deferido"], ["I", "", "PL", "Deferido"]],
        "coligacaoDoPartido": {"PT": 0, "PC do B": 0, "PL": 1}}})
    gravar(bruto / "municipios_ibge.json", {})
    gravar(bruto / "meta.json", {"coletadoEm": "2026-10-01"})


def gerar_site(bruto, saida):
    """Roda o gerar.py com BRUTO/SAIDA trocados em todos os módulos que os têm."""
    with mock.patch.multiple(gerar, BRUTO=bruto, SAIDA=saida), mock.patch.multiple(gerar_politicos, BRUTO=bruto, SAIDA=saida), \
            mock.patch.multiple(gerar_estaduais, BRUTO=bruto / "estaduais", SAIDA=saida), \
            mock.patch.multiple(gerar_prefeituras, BRUTO=bruto / "municipais", SAIDA=saida):
        gerar.main()


def gerar_tudo(raiz):
    """Monta dados/ em raiz/dados e gera raiz/site/dados; devolve esta última."""
    bruto, saida = raiz / "dados", raiz / "site" / "dados"
    montar_bruto(bruto)
    gerar_site(bruto, saida)
    return saida


def eleito_tse(seq, nome, cargo, partido, receitas=None, votos=10, uf="SP", urna=None, situacao="eleito", nascimento="1980-01-02", **extra):
    return {"sequencial": seq, "nome": nome, "urna": urna or nome, "cargo": cargo, "situacao": situacao, "partido": partido, "uf": uf,
            "unidadeEleitoral": uf, "nascimento": nascimento, "genero": "FEMININO", "resultado": "Eleito", "titular": True, "eleicao": "2022",
            "votos": [{"turno": 1, "data": "2022-10-02", "votos": votos}], "totalBens": 1000.0, **extra}


def montar_tse_federal(bruto):
    """TSE 2018/2022 de SP e RJ com contas, seções, disputa, partidos e coligações: 6 deputados federais eleitos (custo do voto 10 a 60),
    um não eleito, um vice, deputado estadual e senadores de 2018 e 2022 (vereadores de 2024: os de montar_bruto), mais DCA do SICONFI."""
    dep = [eleito_tse(f"s{i}", nome, "DEPUTADO FEDERAL", "PT", i * 100.0, urna=urna,
                      instrucao="SUPERIOR COMPLETO", corRaca="Parda", ocupacao="advogado")
           for i, (nome, urna) in enumerate([("Ana Maria Souza", "Ana Souza"), ("Beto Dois", "Beto"), ("Caio Tres", "Caio"),
                                              ("Davi Quatro", "Davi"), ("Edu Cinco", "Edu")], 1)]
    dep.append(eleito_tse("s6", "Fabio Seis", "DEPUTADO FEDERAL", "PL", 600.0))
    dep.append(eleito_tse("s7", "Gil Sete", "DEPUTADO FEDERAL", "PT", 700.0, situacao="nao eleito"))
    dep.append(eleito_tse("s8", "Hugo Vice", "VICE-GOVERNADOR", "PT", 800.0, sequencialChapa="s9"))
    dep.append(eleito_tse("e1", "Ines Estadual", "DEPUTADO ESTADUAL", "PT", 100.0))
    gravar(bruto / "tse" / "2022" / "SP.json", dep)
    gravar(bruto / "tse" / "2022" / "RJ.json", [eleito_tse("r1", "Bia Lima", "SENADOR", "PL", None, uf="RJ")])
    gravar(bruto / "tse" / "2022" / "BR.json", [eleito_tse("b1", "Pres Ident", "PRESIDENTE", "PT", None, uf="BR")])
    gravar(bruto / "tse" / "2018" / "RJ.json", [eleito_tse("r0", "Bia Lima", "SENADOR", "PL", None, uf="RJ", eleicao="2018")])
    gravar(bruto / "tse" / "contas" / "2022" / "SP.json", {f"s{i}": {"receitas": i * 100.0, "origensReceita": []} for i in range(1, 8)}
            | {"s9": {"receitas": 800.0, "origensReceita": []}, "e1": {"receitas": 100.0, "origensReceita": []}})
    gravar(bruto / "tse" / "secoes" / "2022" / "SP.json", {"s1": {"secoes": 12}})
    gravar(bruto / "tse" / "disputa" / "2022" / "SP.json", {"DEPUTADO FEDERAL|SP": {"vagas": 70}, "GOVERNADOR|SP": {"vagas": 1}})
    gravar(bruto / "tse" / "partidos" / "2022" / "SP.json", {"DEPUTADO FEDERAL|SP": {"totalVotos": 1000, "partidos": {
        "PT": [10, 500, "Fed X"], "PC do B": [5, 50, "Fed X"], "PL": [1, 2, ""]}}})
    gravar(bruto / "tse" / "coligacoes" / "2022" / "SP.json", {"DEPUTADO FEDERAL|SP": {
        "coligacoes": [["F", "Fed X", "PT/PC do B", "Deferido"], ["I", "PL", "PL", "Deferido"]], "coligacaoDoPartido": {"PT": 0, "PL": 1}}})
    gravar(bruto / "municipios_ibge.json", {"71072": "3550308"})   # sobrescreve o {} de montar_bruto
    gravar(bruto / "siconfi" / "SP.json", {"anos": {"2022": {"legislativa": {"acaoLegislativa": {"liquidada": 999.0}}},
                                                    "2023": {"legislativa": {"acaoLegislativa": {"liquidada": 2000.0}, "fonte": "https://dca"}}}})
    gravar(bruto / "siconfi_municipios" / "SP.json", {"ano": 2023, "municipios": {"3550308": {"liquidada": 500.0, "fonte": "https://dca-mun"}}})


def montar_tribunais_e_ministros(bruto):
    """TCU e STJ com relatorias, e requerimentos de ministros da Câmara e do Senado."""
    gravar(bruto / "tribunais" / "tribunais.json", {"coletadoEm": "2026-10-30", "tribunais": {
        "TCU": {"nome": "Tribunal de Contas da União", "fonte": "https://tcu", "wikipedia": "https://w/tcu",
                "atuais": [{"nome": "Aroldo Cedraz de Oliveira", "wiki": "Aroldo_Cedraz", "posse": "2007-01-01", "vistoDesde": "2026-10-30"},
                           {"nome": "Bruno Dantas", "wiki": "Bruno_Dantas", "vistoDesde": "2026-10-30"}],
                "anteriores": [{"nome": "Ex Ministro", "vistoDesde": "2026-01-01", "vistoAte": "2026-06-01"}]},
        "STJ": {"nome": "Superior Tribunal de Justiça", "fonte": "https://stj", "wikipedia": "https://w/stj",
                "atuais": [{"nome": "Herman Benjamin", "wiki": "Herman_Benjamin", "vistoDesde": "2026-10-30"}], "anteriores": []},
        "STF": {"nome": "Supremo Tribunal Federal", "fonte": "https://stf", "wikipedia": "https://w/stf",
                "atuais": [{"nome": "Gilmar Mendes", "wiki": "Gilmar_Mendes", "vistoDesde": "2026-10-30"}]}}})
    gravar(bruto / "tribunais" / "relatorias_tcu.json", {
        "dias": {"2026-03-10": {"AROLDO CEDRAZ": {"Acordao": 3, "Outro": 1}, "ANDRE SUBSTITUTO": {"Acordao": 1}},
                 "2025-05-02": {"AROLDO CEDRAZ": {"Acordao": 2}}, "2024-01-05": {"ANDRE SUBSTITUTO": {"Acordao": 5}}},
        "recentes": {"AROLDO CEDRAZ": [{"numero": 1, "ano": 2026}]}})
    gravar(bruto / "tribunais" / "relatorias_stj.json", {"recursos": {
        "r1": {"contagem": {"HERMAN BENJAMIN": {"2025": 4, "2026": 1}, "FANTASMA": {"2020": 0}}},
        "r2": {"contagem": {"HERMAN BENJAMIN": {"2025": 2}}}}})
    gravar(bruto / "ministros" / "camara_2026.json", {"itens": {
        "10": {"tipo": "RIC", "numero": 1, "ano": 2026, "ementa": "Requer informações ao Ministro de Estado da Saúde sobre vacinas.",
               "situacao": "Aguardando", "dataApresentacao": "2026-03-01", "resposta": "Respondido", "remessa": "",
               "autores": [[101, "Ana Souza"], [999, "Antigo Deputado"]]}}})
    gravar(bruto / "ministros" / "senado_2026.json", {"itens": {
        "20": {"identificacao": "RQS 5/2026", "ementa": "Requer a convocação do Ministro de Estado da Saúde.", "autoria": "Senador Bia Lima (PL/RJ)",
               "tipoConteudo": "Convocação", "dataApresentacao": "2026-03-02", "tramitando": True},
        "21": {"identificacao": None, "ementa": "Requer providências sobre a obra X.", "autoria": None}}})


def montar_bruto_completo(bruto):
    montar_bruto(bruto)
    montar_tse_federal(bruto)
    montar_tribunais_e_ministros(bruto)


def gerar_tudo_completo(raiz):
    bruto, saida = raiz / "dados", raiz / "site" / "dados"
    montar_bruto_completo(bruto)
    gerar_politicos._RESUMOS.clear()
    gerar_politicos._CUSTOS.clear()
    gerar_site(bruto, saida)
    return saida
