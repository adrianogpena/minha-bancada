import pytest

import categorias


@pytest.mark.parametrize("rotulo, esperado", [
    # Câmara
    ("PASSAGEM AÉREA - SIGEPA", "locomocao"), ("SERVIÇO DE TÁXI, PEDÁGIO E ESTACIONAMENTO", "locomocao"),
    ("HOSPEDAGEM ,EXCETO DO PARLAMENTAR NO DISTRITO FEDERAL.", "locomocao"), ("COMBUSTÍVEIS E LUBRIFICANTES.", "combustivel"),
    ("LOCAÇÃO OU FRETAMENTO DE VEÍCULOS AUTOMOTORES", "veiculos"), ("LOCAÇÃO OU FRETAMENTO DE AERONAVES", "veiculos"),
    ("MANUTENÇÃO DE ESCRITÓRIO DE APOIO À ATIVIDADE PARLAMENTAR", "imovel"), ("TELEFONIA", "telecom"),
    ("SERVIÇOS POSTAIS", "publicacoes"), ("ASSINATURA DE PUBLICAÇÕES", "publicacoes"),
    ("CONSULTORIAS, PESQUISAS E TRABALHOS TÉCNICOS.", "consultoria"), ("DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR.", "comunicacao"),
    ("PARTICIPAÇÃO EM CURSO, PALESTRA OU EVENTO SIMILAR", "eventos"), ("SERVIÇO DE SEGURANÇA PRESTADO POR EMPRESA ESPECIALIZADA.", "seguranca"),
    # Senado (CEAPS)
    ("Locomoção, hospedagem, alimentação, combustíveis e lubrificantes", "locomocao"),
    ("Aquisição de material de consumo para uso no escritório político, inclusive aquisição ou locação de software, despesas postais, "
     "aquisição de publicações, locação de móveis e de equipamentos.", "material"),
    ("Aluguel de imóveis para escritório político, compreendendo despesas concernentes a eles", "imovel"),
    ("Passagens aéreas, aquáticas e terrestres nacionais", "locomocao"), ("Serviços de Segurança Privada", "seguranca"),
    # Assembleias
    ("REFERE-SE A DISPONIBILIZACAO DO BENEFICIO ALIMENTACAO DE OUTUBRO/2026", "locomocao"),
    ("CONTRATACAO DE PACOTE DE DADOS MOVEIS", "telecom"), ("LOCACAO DE VEICULOS PARA O GABINETE", "veiculos"),
    ("A - COMBUSTÍVEIS E LUBRIFICANTES", "combustivel"), ("H - SERV.UTIL.PÚBLICA (TELEF.MÓVEL/FIXA, ENERGIA, ÁGUA, GÁS ETC)", "imovel"),
    ("K - LOCAÇÃO DE BENS MÓVEIS", "material"), ("L - LOCAÇÃO DE BENS IMÓVEIS", "imovel"),
    ("C - MATERIAIS E SERVIÇOS DE MANUT E CONSERV DE VEÍCULOS ; PEDÁGIOS", "veiculos"),
    ("D - MATERIAIS E SERVIÇOS GRÁFICOS, DE CÓPIAS E REPRODUÇÃO DE DOCS", "graficos"),
    ("Imóvel de Apoio à Atividade Parlamentar (aluguel, condomínio, IPTU, água, telefone fixo e/ou móvel, energia elétrica)", "imovel"),
    ("Aquisição ou Locação de Software, serviços postais, assinatura de publicações, TV a cabo ou similar", "material"),
    ("REFERE-SE AO REEMBOLSO D DESPESAS INDENIZATORIAS CONFORME ATO NORMATIVO 343/2024 SEGURO DE VIDA EM SUBSTITUICAO A NE 006593", "outros"),
    ("REFERE-SE AO REEMBOLSO DE DESPESAS INDEDENIZATORIAS CONFORME ATO NORMATIVO 343/24 PROGRAMACAO E MANUTENCAO DE SITE", "material"),
    ("Consultoria e assessoria de imprensa", "comunicacao"), ("Assessoria de comunicação", "comunicacao"), ("ASSESSORIA JURÍDICA", "consultoria"),
    ("REEMBOLSOS / Escritório de Apoio - Energia Elétrica", "imovel"), ("REEMBOLSOS / Escritório de Apoio - Internet", "telecom"),
    ("REEMBOLSOS / Escritório de Apoio - Locação de móveis e equipamentos", "material"),
    ("PASSAGENS / Passagens Aéreas - Deputado", "locomocao"), ("DIÁRIAS / Diárias - Funcionários", "diarias"),
    ("ALMOXARIFADO / Jornais e Revistas", "publicacoes"), ("INSCRIÇÃO / Cursos", "eventos"),
    ("Verba de gabinete (pessoal)", "pessoal"), ("Cota parlamentar (reembolso)", "sem_detalhe"), ("Verba indenizatória", "sem_detalhe"),
    ("INDENIZACAO DE TRANSPORTE", "locomocao"), ("Outros", "outros"), ("Anulação de empenho", "outros"),
    (None, "sem_detalhe"), ("  ", "sem_detalhe"),
])
def test_categoria_id(rotulo, esperado):
    categorias.DESCONHECIDAS.clear()
    assert categorias.categoria_id(rotulo) == esperado
    assert not categorias.DESCONHECIDAS


def test_rotulo_sem_regra_vira_outros_e_fica_registrado():
    categorias.DESCONHECIDAS.clear()
    assert categorias.categoria_id("Despesa  nunca vista") == "outros"
    assert categorias.DESCONHECIDAS == {"Despesa nunca vista"}
    categorias.DESCONHECIDAS.clear()


def test_todo_id_das_regras_esta_na_lista_fixa():
    assert {cid for cid, _ in categorias.REGRAS} <= set(categorias.CATEGORIAS)


def test_agrupar_soma_por_id_e_guarda_os_rotulos_originais():
    r = categorias.agrupar({"Combustível": 10.0, "COMBUSTÍVEIS E LUBRIFICANTES.": 5.5, "Aluguel de imóveis": 20.0, None: 1.0})
    assert [(c["id"], c["total"]) for c in r] == [("imovel", 20.0), ("combustivel", 15.5), ("sem_detalhe", 1.0)]
    assert r[1]["categoria"] == categorias.CATEGORIAS["combustivel"]
    assert r[1]["originais"] == [["Combustível", 10.0], ["COMBUSTÍVEIS E LUBRIFICANTES.", 5.5]]
    assert r[2]["originais"] == [["Sem categoria", 1.0]]
