"""
Pastas do Executivo federal: de que ministério fala um texto (ementa de requerimento, cargo da lista do Planalto).

Sem internet e sem ligar nomes a pessoas (isso fica em `identidades.py`). Cada pasta tem uma chave estável (`PASTAS`),
a mesma para o cargo do Planalto e para as formas que aparecem nas ementas ("Ministro da Saúde", "Ministra dos Povos
Indígenas", "Ministro-Chefe da Casa Civil"). Pasta extinta ou renomeada entra como chave nova; a chave é o que os
requerimentos e os ministros guardam, o nome exibido vem de `PASTAS`.
"""

import re

from estaduais_comum import sem_acento

# chave: (nome exibido, expressão sobre o texto sem acento e em minúsculas)
PASTAS = {
    "casa_civil": ("Casa Civil", r"casa civil"),
    "secretaria_geral": ("Secretaria-Geral da Presidência", r"secretaria[- ]geral da presid"),
    "relacoes_institucionais": ("Relações Institucionais", r"relacoes institucionais"),
    "comunicacao_social": ("Secretaria de Comunicação Social", r"comunicacao social|\bsecom\b|secretaria de comunicacao"),
    "gsi": ("Gabinete de Segurança Institucional", r"gabinete de seguranca institucional|\bgsi\b"),
    "agu": ("Advocacia-Geral da União", r"advocacia[- ]geral|advogado[- ]geral"),
    "cgu": ("Controladoria-Geral da União", r"controladoria[- ]geral|\bcgu\b"),
    "mda": ("Desenvolvimento Agrário e Agricultura Familiar", r"desenvolvimento agrario|\bmda\b"),
    "agricultura": ("Agricultura e Pecuária", r"agricultura(?! familiar)|\bmapa\b"),
    "cidades": ("Cidades", r"\bcidades\b"),
    "ciencia": ("Ciência, Tecnologia e Inovação", r"\bciencia\b"),
    "comunicacoes": ("Comunicações", r"\bcomunicacoes\b"),
    "cultura": ("Cultura", r"\bcultura\b"),
    "defesa": ("Defesa", r"\bdefesa\b"),
    "desenvolvimento_social": ("Desenvolvimento e Assistência Social, Família e Combate à Fome", r"assistencia social|desenvolvimento social"),
    "mdic": ("Desenvolvimento, Indústria, Comércio e Serviços", r"desenvolvimento,? industria|desenvolvimento,? (?:e )?comercio|\bmdic\b"),
    "direitos_humanos": ("Direitos Humanos e da Cidadania", r"direitos humanos"),
    "educacao": ("Educação", r"\beducacao\b"),
    "empreendedorismo": ("Empreendedorismo, Microempresa e Empresa de Pequeno Porte", r"empreendedorismo|microempresa"),
    "esporte": ("Esporte", r"\besportes?\b"),
    "fazenda": ("Fazenda", r"\bfazenda\b"),
    "gestao": ("Gestão e Inovação em Serviços Públicos", r"gestao e (?:da )?inovacao|\bgestao\b"),
    "igualdade_racial": ("Igualdade Racial", r"igualdade racial"),
    "integracao": ("Integração e Desenvolvimento Regional", r"integracao"),
    "justica": ("Justiça e Segurança Pública", r"\bjustica\b"),
    "meio_ambiente": ("Meio Ambiente e Mudança do Clima", r"meio ambiente"),
    "minas_energia": ("Minas e Energia", r"minas e energia|\benergia\b"),
    "mulheres": ("Mulheres", r"\bmulher(?:es)?\b"),
    "pesca": ("Pesca e Aquicultura", r"\bpesca\b"),
    "planejamento": ("Planejamento e Orçamento", r"planejamento"),
    "portos": ("Portos e Aeroportos", r"portos"),
    "povos_indigenas": ("Povos Indígenas", r"povos indigenas"),
    "previdencia": ("Previdência Social", r"previdencia"),
    "relacoes_exteriores": ("Relações Exteriores", r"relacoes exteriores|itamaraty"),
    "saude": ("Saúde", r"\bsaude\b"),
    "trabalho": ("Trabalho e Emprego", r"\btrabalho\b"),
    "transportes": ("Transportes", r"\btransportes?\b"),
    "turismo": ("Turismo", r"\bturismo\b"),
}
_PADROES = {k: re.compile(v[1]) for k, v in PASTAS.items()}
_CITACAO = re.compile(r"minist(?:ro|ra)s?\b|ministerio\b")
_AUTONOMAS = ("agu", "cgu", "casa_civil")   # o chefe não leva "Ministro" no nome: vale a menção em qualquer ponto do texto
_FIM_JANELA = re.compile(r"[;.(]| a respeito| sobre | quanto | acerca| referente| relativ| solicit| informac| detalhad| o qual| que | para |"
                         r" ouvid| tendo | com base| por intermedio")


def pastas_do_texto(texto: str | None) -> list[str]:
    """Chaves das pastas citadas depois de "Ministro(a)", na ordem em que aparecem; [] se nenhuma. A janela vai até o
    fim da expressão do cargo (um ponto, "a respeito", "sobre"...), não até a vírgula: "Desenvolvimento, Indústria"."""
    t = sem_acento(texto or "").lower()
    achadas: dict[str, int] = {}
    for m in _CITACAO.finditer(t):
        janela = _FIM_JANELA.split(t[m.end():m.end() + 110], 1)[0]
        for chave, padrao in _PADROES.items():
            p = padrao.search(janela)
            if p and chave not in achadas:
                achadas[chave] = m.end() + p.start()
    for chave in _AUTONOMAS:
        p = _PADROES[chave].search(t)
        if p and chave not in achadas:
            achadas[chave] = p.start()
    return sorted(achadas, key=achadas.get)


def pasta_do_cargo(cargo: str | None) -> str | None:
    """Pasta de um cargo da lista do Planalto ("Ministro de Estado da Saúde", "Advocacia-Geral da União")."""
    t = sem_acento(cargo or "").lower()
    achadas = {c: p.search(t).start() for c, p in _PADROES.items() if p.search(t)}
    if not achadas:
        return None
    return min(achadas, key=achadas.get)
