"""
Núcleo de identidades: um id próprio para cada pessoa e para cada partido, ligando as fontes.

  site/dados/nucleo/pessoas.json    [{id, nome, nascimento, genero, nomes, partido, fontes, ligacao}]
  site/dados/nucleo/partidos.json   {partidos: [...], federacoes: [...]}
  site/dados/nucleo/ligacoes.json   como cada fonte foi ligada a cada pessoa, o que ficou ambíguo e o que não casou

Fontes: dados/tse/<ano>/<UF>.json (eleitos), Câmara (deputados federais em exercício), dados/senado.json e
dados/estaduais/<UF>/deputados.json. Não acessa a internet; chamado pelo scripts/gerar.py.

Id da pessoa ("pes_" + 12 hex): hash de "nome|nascimento" quando os dois existem (TSE e Câmara), então a mesma pessoa
tem o mesmo id em qualquer eleição e sem depender da ordem dos arquivos. Quem só tem id de uma fonte (senador e deputado
estadual sem ligação com o TSE) usa o id daquela fonte; se a ligação aparecer depois, o id muda.

Ligação com o TSE, da mais para a menos segura (`ligacao[fonte] = [método, confiança]`):
  nome+nascimento (alta)         nome civil e data de nascimento iguais
  sequencial (alta)              o id da Assembleia é o sequencial do TSE (RJ)
  nome+cargo+uf, nome+uf (média) nome civil igual, no cargo da Casa ou em qualquer cargo, na mesma UF
  urna+cargo+uf (baixa)          nome parlamentar igual ao nome de urna, no cargo da Casa e na mesma UF
Se mais de uma pessoa casa, ou as datas de nascimento divergem, não liga: a fonte fica com id próprio e entra em
`ambiguos`. Partidos: `partido_id` unifica grafias (PC do B, PCdoB; União Brasil, UB) e `PARTIDOS` guarda
renomeações (alias) e fusões (sucessor).

Nome em registro (autor de projeto, favorecido de diária, gabinete, voto...) -> deputado da Assembleia: `ligar_nomes(nomes,
deputados, uf)` é o único lugar que compara nomes de registros das Assembleias; os coletores só chamam. `ESTRATEGIAS[uf]` guarda
a regra de cada UF. O resultado de cada coleta vai para dados/estaduais/<UF>/ligacoes.json (`gravar_ligacoes`) e `construir` junta
tudo em `ligacoes.json` do núcleo, com a pessoa. Correção manual: scripts/ligacoes_manuais.json.

Doador de campanha -> fornecedor das cotas: `ligar_doadores(doadores, fornecedores)`, só para fornecedor com CNPJ (pessoa jurídica):
  cnpj (alta)   os 8 primeiros dígitos do CNPJ do doador (prestação de contas do TSE) são o id `for_<8 dígitos>` do fornecedor
  nome (média)  doador sem CNPJ na fonte (coleta antiga): nome padronizado igual ao de um único fornecedor com CNPJ
Nome que casa com mais de um fornecedor não liga (`ambiguos`). `scripts/doadores.py` só chama; o resultado vai para `ligacoes.json` (`doadores`).

Ministros de Estado (lista do Planalto, dados/ministros/): `ligar_ministros` liga cada ministro à pessoa do núcleo (`ligacao["planalto"]`):
  nome (alta)   nome civil igual ao de uma única pessoa que é parlamentar licenciado para ser ministro (dados/ministros/licencas.json)
  nome (média)  nome civil igual ao de uma única pessoa do núcleo (TSE, Câmara, Senado, Assembleia); com mais de uma, não liga
Sem par, o ministro ganha pessoa própria (fonte "planalto"). `ligar_requerimentos` liga requerimento -> ministro da pasta
(`ligacoes["ministros"]["requerimentos"]`, `[pessoa, método, confiança]`); a pasta vem de `ministerios.pastas_do_texto`:
  nome+pasta (alta)   o nome do ministro aparece na ementa e a pasta é a dele
  pasta+data (média)  a pasta é a dele e o pedido é de depois do dia em que o parlamentar se licenciou para o cargo
  pasta+data (baixa)  idem, com o início vindo só do dia em que o nome entrou na lista do Planalto
`ligar_autoria_senado` liga o texto de autoria dos requerimentos do Senado ao senador (nome+uf, média).
"""

import difflib
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import estaduais_comum as comum
import ministerios
from fornecedores import nome_chave
from gerar_politicos import ler, salvar
from ids import gerar_id

# chave -> (sigla, nome, número, outras grafias, sucessor). Renomeação é grafia; fusão ou extinção tem sucessor.
PARTIDOS = {
    "MDB": ("MDB", "Movimento Democrático Brasileiro", 15, ("PMDB",), None),
    "PT": ("PT", "Partido dos Trabalhadores", 13, (), None),
    "PSDB": ("PSDB", "Partido da Social Democracia Brasileira", 45, (), None),
    "PP": ("PP", "Progressistas", 11, ("Progressistas", "Partido Progressista"), None),
    "PDT": ("PDT", "Partido Democrático Trabalhista", 12, (), None),
    "PSB": ("PSB", "Partido Socialista Brasileiro", 40, (), None),
    "PL": ("PL", "Partido Liberal", 22, ("PR", "Partido Liberal"), None),
    "PSD": ("PSD", "Partido Social Democrático", 55, (), None),
    "UNIAO": ("UNIÃO", "União Brasil", 44, ("UB", "União", "União Brasil"), None),
    "REPUBLICANOS": ("REPUBLICANOS", "Republicanos", 10, ("PRB", "REP"), None),
    "PODE": ("PODE", "Podemos", 20, ("PODEMOS", "PTN"), None),
    "PSOL": ("PSOL", "Partido Socialismo e Liberdade", 50, (), None),
    "PV": ("PV", "Partido Verde", 43, (), None),
    "CIDADANIA": ("CIDADANIA", "Cidadania", 23, ("PPS",), None),
    "NOVO": ("NOVO", "Partido Novo", 30, (), None),
    "REDE": ("REDE", "Rede Sustentabilidade", 18, (), None),
    "SOLIDARIEDADE": ("SOLIDARIEDADE", "Solidariedade", 77, ("SD", "SDD"), None),
    "AVANTE": ("AVANTE", "Avante", 70, ("PT do B",), None),
    "AGIR": ("AGIR", "Agir", 36, ("PTC",), None),
    "DC": ("DC", "Democracia Cristã", 27, ("PSDC",), None),
    "PCDOB": ("PCdoB", "Partido Comunista do Brasil", 65, ("PC do B",), None),
    "MOBILIZA": ("MOBILIZA", "Mobiliza", 33, ("PMN",), None),
    "PRD": ("PRD", "Partido Renovação Democrática", 25, (), None),
    "PMB": ("PMB", "Partido da Mulher Brasileira", 35, (), None),
    "PRTB": ("PRTB", "Partido Renovador Trabalhista Brasileiro", 28, (), None),
    "MISSAO": ("MISSÃO", "Partido Missão", 14, (), None),
    # extintos por fusão ou incorporação
    "PSL": ("PSL", "Partido Social Liberal", 17, (), "UNIAO"),
    "DEM": ("DEM", "Democratas", 25, (), "UNIAO"),
    "PTB": ("PTB", "Partido Trabalhista Brasileiro", 14, (), "PRD"),
    "PATRIOTA": ("PATRIOTA", "Patriota", 51, ("PEN",), "PRD"),
    "PRP": ("PRP", "Partido Republicano Progressista", 44, (), "PATRIOTA"),
    "PROS": ("PROS", "Partido Republicano da Ordem Social", 90, (), "SOLIDARIEDADE"),
    "PSC": ("PSC", "Partido Social Cristão", 20, (), "PODE"),
    "PHS": ("PHS", "Partido Humanista da Solidariedade", 31, (), "PODE"),
    "PPL": ("PPL", "Partido Pátria Livre", 54, (), "PCDOB"),
}


def sem_acento(texto: str | None) -> str:
    t = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def norm_nome(nome: str | None) -> str:
    """Nome sem acento, minúsculo, sem o apelido entre parênteses e com espaços simples."""
    return " ".join(sem_acento(re.sub(r"\s*\(.*?\)", "", nome or "")).lower().split())


def _chave_partido(sigla: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", sem_acento(sigla).upper())


ALIAS_PARTIDO = {}
for _k, (_sigla, _nome, _num, _outras, _suc) in PARTIDOS.items():
    for _g in (_k, _sigla, *_outras):
        ALIAS_PARTIDO[_chave_partido(_g)] = _k


def partido_id(sigla: str | None, desconhecidas: set | None = None) -> str | None:
    """"par_<chave>" para a sigla em qualquer grafia conhecida. None se vazia ou se for federação ("FE UNIÃO PP").
    Sigla fora de PARTIDOS ganha id pela própria grafia e entra em `desconhecidas`."""
    if not sigla or not sigla.strip():
        return None
    if re.match(r"\s*FE\b", sigla):
        return None
    dentro = re.search(r"\(([^)]+)\)", sigla)
    chave = _chave_partido(dentro.group(1) if dentro else sigla)
    if not chave:
        return None
    if chave in ALIAS_PARTIDO:
        return "par_" + ALIAS_PARTIDO[chave].lower()
    if desconhecidas is not None:
        desconhecidas.add(sigla.strip())
    return "par_" + chave.lower()


def _atual(chave: str) -> str:
    while chave in PARTIDOS and PARTIDOS[chave][4]:
        chave = PARTIDOS[chave][4]
    return chave


def federacao_de(texto: str | None, desconhecidas: set | None = None) -> tuple | None:
    """Membros ("par_…") da federação do TSE ('13-PT/65-PC do B/43-PV' ou 'PT/PC do B/PV'), em ordem alfabética."""
    if not texto:
        return None
    ids = {partido_id(re.sub(r"^\d+-", "", p.strip()), desconhecidas) for p in texto.split("/")}
    ids.discard(None)
    return tuple(sorted(ids)) if len(ids) > 1 else None


def federacao_id(membros: tuple) -> str:
    """"fed_<partidos em ordem alfabética>" de uma federação (membros no formato de `federacao_de`)."""
    return "fed_" + "_".join(m[4:] for m in membros)


FEDERAIS = {"DEPUTADO FEDERAL"}
SENADORES = {"SENADOR"}
ESTADUAIS = {"DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL"}


class _Registro:
    def __init__(self):
        self.por_id = {}
        self.ancoras = {}

    def obter(self, fonte: str, id_original) -> dict:
        """A pessoa de `gerar_id("pes", fonte, id_original)`: fonte "nn" (id "nome|nascimento"), "tse" ("ano|sequencial"), "camara",
        "senado" ou "estadual" ("UF|id"). Ver ids.py."""
        ancora = (fonte, str(id_original))
        pid = gerar_id("pes", fonte, id_original)
        if pid in self.por_id:
            if self.ancoras[pid] != ancora:
                raise RuntimeError(f"colisão de id de pessoa: {ancora!r} e {self.ancoras[pid]!r}")
            return self.por_id[pid]
        self.ancoras[pid] = ancora
        p = self.por_id[pid] = {"id": pid, "nome": None, "nascimento": None, "genero": None, "nomes": {},
                                "tse": [], "camara": None, "senado": None, "estadual": [], "planalto": [], "ligacao": {}, "partidoFonte": None}
        return p


def _guardar_nome(p: dict, nome: str | None) -> None:
    if nome and nome.strip():
        p["nomes"].setdefault(norm_nome(nome), nome.strip())


def _preencher(p: dict, nome=None, nascimento=None, genero=None) -> None:
    p["nome"] = p["nome"] or (nome.strip() if nome else None)
    p["nascimento"] = p["nascimento"] or nascimento or None
    p["genero"] = p["genero"] or (genero.upper() if genero else None)


class _IndiceTse:
    """Pessoas do TSE por nome, para ligar quem vem de outra fonte."""

    def __init__(self, por_id: dict):
        self.por_id = por_id
        self.civil_cargo = defaultdict(set)    # (nome, uf, cargo)
        self.civil = defaultdict(set)          # (nome, uf)
        self.urna_cargo = defaultdict(set)     # (urna, uf, cargo)
        self.por_nome_nasc = {}                # (nome, nascimento)
        self.sequencial_estadual = {}          # (uf, sequencial) das Assembleias

    def adicionar(self, pid: str, e: dict) -> None:
        uf, cargo = e.get("uf"), e["cargo"]
        self.civil_cargo[(norm_nome(e.get("nome")), uf, cargo)].add(pid)
        self.civil[(norm_nome(e.get("nome")), uf)].add(pid)
        self.urna_cargo[(norm_nome(e.get("urna")), uf, cargo)].add(pid)
        if cargo in ESTADUAIS:
            self.sequencial_estadual[(uf, str(e["sequencial"]))] = pid

    def _sem_conflito(self, ids: set, nascimento: str | None) -> set:
        if not nascimento:
            return ids
        return {i for i in ids if not self.por_id[i]["nascimento"] or self.por_id[i]["nascimento"] == nascimento}

    def achar(self, civis: list, urnas: list, uf: str, cargos: set, nascimento: str | None = None):
        """(id, método, confiança) se uma só pessoa casa; ("ambiguo", ids) se várias; None se nenhuma."""
        ambiguos: set = set()
        civis, urnas = [norm_nome(n) for n in civis if n], [norm_nome(n) for n in urnas if n]
        etapas = [("nome+cargo+uf", "média", [self.civil_cargo.get((n, uf, c), set()) for n in civis for c in cargos]),
                  ("nome+uf", "média", [self.civil.get((n, uf), set()) for n in civis]),
                  ("urna+cargo+uf", "baixa", [self.urna_cargo.get((n, uf, c), set()) for n in urnas for c in cargos])]
        for metodo, confianca, grupos in etapas:
            ids = self._sem_conflito(set().union(*grupos), nascimento)
            if len(ids) == 1:
                return next(iter(ids)), metodo, confianca
            ambiguos |= ids
        return ("ambiguo", ambiguos) if ambiguos else None


# ---------------------------------------------------------------- nome em registro -> deputado da Assembleia

MANUAIS = ler(Path(__file__).with_name("ligacoes_manuais.json"), {}) or {}   # {uf: {nome da fonte, como em `chave_manual`: nome do deputado}}
CAMPOS_NOME = ("nome", "nomeCivil")
_LOG: dict = defaultdict(lambda: {"nomes": {}, "ambiguos": {}, "semPar": set()})   # uf -> o que `ligar_nomes` decidiu neste processo

TITULOS_UF = {
    "PA": {"dr", "dra", "prof", "profa", "deleg", "delegado", "delegada", "dep", "deputado", "deputada"},
    "PR": {"dr", "dra", "doutor", "doutora", "secretaria"},
    "RJ": {"dr", "dra", "prof", "profa", "delegado", "delegada", "dep"},
    "RR": {"dr", "dra", "prof", "profa", "coronel", "dep", "de", "da", "do", "dos", "das"},
    "SC": {"dr", "dra", "prof", "profa", "delegado", "delegada", "dep", "deputado", "deputada", "da", "de", "do", "dos", "das", "e"},
    "SE": {"dr", "dra", "prof", "profa", "dep"},
    "SP": {"agente", "federal", "major", "coronel", "delegado", "delegada", "dr", "dra", "doutor", "doutora", "professor", "professora",
           "pastor", "pastora", "capitao", "sargento", "tenente", "cabo", "soldado", "padre", "bispo", "enfermeira", "enfermeiro",
           "do", "da", "de", "dos", "das", "e"},
}
EXPANSAO_PR = {"del": "delegado", "delegada": "delegado", "prof": "professor"}
SINONIMOS_SE = {"junior": "jr", "jr": "jr"}


def _indice_nomes(deputados: list[dict], prep=None) -> dict:
    por_nome: dict[str, set] = {}
    for campo in CAMPOS_NOME:
        for d in deputados:
            if d.get(campo):
                por_nome.setdefault(comum.sem_acento(prep(d[campo]) if prep else d[campo]), set()).add(d["id"])
    return por_nome


def _casar_exato(nomes, deputados: list[dict], prep=None):
    """Nome da fonte (sem prefixo "DEP", sem acento e caixa) igual ao nome ou ao nome civil de um só deputado."""
    por_nome = _indice_nomes(deputados, prep)
    ligados, ambiguos = {}, {}
    for n in nomes:
        ids = por_nome.get(comum.sem_acento(comum.nome_limpo(prep(n) if prep else n)), set())
        if len(ids) == 1:
            ligados[n] = (next(iter(ids)), "nome", "média")
        elif ids:
            ambiguos[n] = sorted(map(str, ids))
    return ligados, ambiguos


def _decidir(n: str, ids: set, metodo: str, confianca: str, ligados: dict, ambiguos: dict) -> bool:
    if len(ids) == 1:
        ligados[n] = (next(iter(ids)), metodo, confianca)
        ambiguos.pop(n, None)
        return True
    if ids:
        ambiguos[n] = sorted(map(str, ids))
    return False


def _por_palavras(nomes, deputados: list[dict], ligados: dict, ambiguos: dict, ignorar, extra=None) -> None:
    """Quem não casou inteiro casa quando todas as suas palavras estão em um só nome do deputado. `extra`: [(método, confiança,
    função(nome, deputados) -> ids)] tentadas quando as palavras não acharam um só."""
    for n in nomes:
        alvo = set(comum.palavras(n, ignorar))
        if n in ligados or not alvo:
            continue
        ids = {d["id"] for d in deputados if any(d.get(c) and alvo <= set(comum.palavras(d[c], ignorar)) for c in CAMPOS_NOME)}
        if _decidir(n, ids, "palavras", "baixa", ligados, ambiguos):
            continue
        for metodo, confianca, fn in extra or ():
            if _decidir(n, fn(n, deputados), metodo, confianca, ligados, ambiguos):
                break


def _sem_ponto(nome) -> str:
    return " ".join((nome or "").replace(".", " ").split())


def _chave_manual(uf: str, n: str) -> str:
    """"Dep.Fulano" sem espaço, sem pontos e sem acento: a chave de `MANUAIS[uf]`."""
    n = comum.sem_acento(comum.nome_limpo(re.sub(r"^\s*dep\.(?=\S)", "dep. ", n or "", flags=re.I)))
    return n.replace(".", "")


def _estrategia_ms(nomes, deputados, uf):
    manuais = MANUAIS.get(uf, {})
    ligados, ambiguos = _casar_exato(nomes, deputados, prep=lambda n: manuais.get(_chave_manual(uf, n), _chave_manual(uf, n)))
    ligados = {n: (i, "manual", "alta") if _chave_manual(uf, n) in manuais else (i, m, c) for n, (i, m, c) in ligados.items()}
    return ligados, ambiguos


def _estrategia_pe(nomes, deputados, uf):
    """"João Paulo do PT" também tenta "João Paulo" entre os deputados do PT, quando "PT" é partido de um deputado."""
    ligados, ambiguos = _casar_exato(nomes, deputados)
    partidos = {comum.sem_acento(d["partido"]) for d in deputados if d.get("partido")}
    for n in nomes:
        m = re.match(r"^(.*\S)\s+d[oa]\s+(\S+)\s*$", n, re.I)
        if n in ligados or not m or comum.sem_acento(m.group(2)) not in partidos:
            continue
        do_partido = [d for d in deputados if comum.sem_acento(d.get("partido")) == comum.sem_acento(m.group(2))]
        achado, _ = _casar_exato([m.group(1)], do_partido)
        if m.group(1) in achado:
            ligados[n] = (achado[m.group(1)][0], "nome+partido", "média")
    return ligados, ambiguos


def _extremos(nome: str, ignorar) -> tuple:
    p = comum.palavras(nome, ignorar)
    return (p[0], p[-1]) if len(p) >= 2 else ()


def _estrategia_rr(nomes, deputados, uf):
    ignorar = TITULOS_UF[uf]

    def por_extremos(nome, deps):
        return {d["id"] for d in deps if _extremos(nome, ignorar) and any(d.get(c) and _extremos(nome, ignorar) == _extremos(d[c], ignorar) for c in CAMPOS_NOME)}

    ligados, ambiguos = _casar_exato(nomes, deputados)
    _por_palavras(nomes, deputados, ligados, ambiguos, ignorar, extra=[("extremos", "baixa", por_extremos)])
    return ligados, ambiguos


def _estrategia_palavras(nomes, deputados, uf):
    ligados, ambiguos = _casar_exato(nomes, deputados)
    _por_palavras(nomes, deputados, ligados, ambiguos, TITULOS_UF[uf])
    return ligados, ambiguos


def _cabe(a: list, b: list) -> bool:
    """Toda palavra de `a` está em `b`, igual ou como começo de palavra de 4 letras ou mais ("alex" em "alexander")."""
    return bool(a) and all(any(x == y or (len(x) >= 4 and y.startswith(x)) for y in b) for x in a)


def _unico(alvo: list, candidatos: list[tuple]):
    """(chave, conflito) do único candidato que casa com `alvo` (um contém o outro); (None, ids) se houver zero ou mais de um."""
    achados = {k for k, toks in candidatos if _cabe(alvo, toks) or (len(toks) >= 2 and _cabe(toks, alvo))}
    if len(achados) > 1:
        achados = {k for k, toks in candidatos if sorted(toks) == sorted(alvo)} or achados
    return (next(iter(achados)), achados) if len(achados) == 1 else (None, achados)


def _estrategia_sc(nomes, deputados, uf):
    """O que não casa inteiro casa pelas palavras (sem "da", "de"...) com um só nome; "Ana (Paulinha)" também tenta o apelido."""
    ligados, ambiguos = _casar_exato(nomes, deputados)
    tokens = lambda t: comum.palavras(t, TITULOS_UF[uf])  # noqa: E731
    candidatos = [(d["id"], t) for d in deputados for c in (*CAMPOS_NOME, "nomeFonte") if d.get(c) and (t := tokens(d[c]))]
    for n in nomes:
        if n in ligados:
            continue
        for v in [re.sub(r"\([^)]*\)", " ", n)] + re.findall(r"\(([^)]*)\)", n):
            achado, conflito = _unico(tokens(v), candidatos)
            if achado is not None:
                ligados[n] = (achado, "palavras", "baixa")
                ambiguos.pop(n, None)
                break
            if conflito:
                ambiguos[n] = sorted(map(str, conflito))
    return ligados, ambiguos


def _tokens_pr(nome: str) -> list[str]:
    t = re.sub(r"\(.*?\)", " ", nome or "")
    t = comum.sem_acento(comum.nome_limpo(t)).replace(".", " ")
    return [EXPANSAO_PR.get(p, p) for p in t.split() if p not in TITULOS_UF["PR"]]


def _estrategia_pr(nomes, deputados, uf):
    """Nome inteiro (nome, nome civil, ficha); "ANA JÚLIA DO PT" sem o partido; o nome contido em um só deputado ("BAZANA" em
    "PEDRO PAULO BAZANA"); por fim, nomes quase iguais."""
    partidos = {comum.sem_acento(d["partido"]) for d in deputados if d.get("partido")}
    por_alias = [(a, d["id"]) for d in deputados for a in
                 [x for x in (_tokens_pr(d["nome"]), _tokens_pr(d.get("nomeCivil") or ""), d["id"].split("-")) if x]]
    ligados, ambiguos = {}, {}
    for n in nomes:
        t = _tokens_pr(n)
        if len(t) > 2 and t[-2] in ("do", "da") and t[-1] in partidos:
            t = t[:-2]
        if not t:
            continue
        etapas = [("nome", "média", lambda a: a == t), ("palavras", "baixa", lambda a: set(t) <= set(a) or set(a) <= set(t)),
                  ("similaridade", "baixa", lambda a: difflib.SequenceMatcher(None, " ".join(a), " ".join(t)).ratio() >= 0.9)]
        for metodo, confianca, casa in etapas:
            ids = {i for a, i in por_alias if casa(a)}
            if ids:
                _decidir(n, ids, metodo, confianca, ligados, ambiguos)
                break
    return ligados, ambiguos


def _estrategia_ce(nomes, deputados, uf):
    """Sem diferenciar pontos: "AP. LUIZ HENRIQUE" e "Ap Luiz Henrique"."""
    return _casar_exato(nomes, deputados, prep=_sem_ponto)


ESTRATEGIAS = {"CE": _estrategia_ce, "MS": _estrategia_ms, "PA": _estrategia_palavras, "PE": _estrategia_pe, "PR": _estrategia_pr,
               "RJ": _estrategia_palavras, "RR": _estrategia_rr, "SC": _estrategia_sc}


def ligar_nomes(nomes, deputados: list[dict], uf: str | None = None) -> dict:
    """{nome como veio da fonte: id do deputado}. Nome ambíguo ou sem par fica de fora (e entra em `ambiguos` ou `semPar` do log).
    `uf` escolhe a regra em `ESTRATEGIAS` (padrão: nome ou nome civil igual, sem acento nem prefixo "DEP") e identifica o log."""
    nomes = [n for n in dict.fromkeys(nomes) if isinstance(n, str)]
    ligados, ambiguos = ESTRATEGIAS.get(uf, lambda n, d, u: _casar_exato(n, d))(nomes, deputados, uf)
    if uf:
        log = _LOG[uf]
        for n in nomes:
            if not n.strip():
                continue
            if n in ligados:
                log["nomes"][n] = list(ligados[n])
                log["ambiguos"].pop(n, None)
                log["semPar"].discard(n)
            elif n in ambiguos:
                log["ambiguos"][n] = ambiguos[n]
            else:
                log["semPar"].add(n)
    return {n: i for n, (i, _, _) in ligados.items()}


def ligar_doadores(doadores, fornecedores: list[dict]) -> tuple[dict, dict]:
    """`doadores`: [(chave, nome, cnpj ou None)] como a prestação de contas publica; `fornecedores`: nucleo/fornecedores.json.
    Devolve ({chave: [id do fornecedor, método, confiança]}, {chave: [ids]}) com o que ligou e o que ficou ambíguo."""
    empresas = {f["id"]: f for f in fornecedores if f.get("tipo") == "PJ"}
    por_nome = defaultdict(set)
    for f in empresas.values():
        for n in (f["nome"], *f.get("nomes", ())):
            if nome_chave(n):
                por_nome[nome_chave(n)].add(f["id"])
    ligados, ambiguos = {}, {}
    for chave, nome, cnpj in doadores:
        if cnpj:
            if (id_ := f"for_{cnpj[:8]}") in empresas:
                ligados[chave] = [id_, "cnpj", "alta"]
        elif (ids := por_nome.get(nome_chave(nome), set())):
            if len(ids) == 1:
                ligados[chave] = [next(iter(ids)), "nome", "média"]
            else:
                ambiguos[chave] = sorted(ids)
    return ligados, ambiguos


def _tokens_sp(nome: str) -> list[str]:
    return comum.sem_acento(re.sub(r"[^\w\s]", " ", nome or "")).split()


def ligar_civis(civis, deputados: list[dict], uf: str = "SP") -> dict:
    """{nome civil: id}: as palavras do nome parlamentar (sem títulos como "Agente Federal") estão todas no nome civil, e só um
    deputado serve ao nome civil e só um nome civil serve ao deputado."""
    chaves = {}
    for d in deputados:
        t = [p for p in _tokens_sp(d["nome"]) if p not in TITULOS_UF[uf]] or _tokens_sp(d["nome"])
        chaves[d["id"]] = set(t)
    por_civil = {}
    for civil in civis:
        achados = {i for i, t in chaves.items() if t and t <= set(_tokens_sp(civil))}
        if len(achados) == 1:
            por_civil[civil] = next(iter(achados))
    contagem: dict = defaultdict(int)
    for i in por_civil.values():
        contagem[i] += 1
    ligados = {c: i for c, i in por_civil.items() if contagem[i] == 1}
    _LOG[uf]["nomes"].update({c: [i, "palavras", "baixa"] for c, i in ligados.items()})
    return ligados


def ligar_civis_pelo_tse(civis, deputados: list[dict], candidatos: list[dict], uf: str = "SP") -> dict:
    """Para quem sobrou: o nome de urna do TSE casa com o nome parlamentar e o nome civil do TSE com o do subsídio
    (igual ou com os nomes de um dentro do outro)."""
    por_urna: dict = defaultdict(list)
    for c in candidatos:
        por_urna[comum.sem_acento(c.get("urna"))].append(c)
    ligados: dict = {}
    for d in deputados:
        achados = por_urna.get(comum.sem_acento(d["nome"])) or []
        if len(achados) != 1:
            continue
        civil_tse = set(_tokens_sp(achados[0].get("nome")))
        serve = [c for c in civis if civil_tse <= set(_tokens_sp(c)) or set(_tokens_sp(c)) <= civil_tse]
        if len(serve) == 1:
            ligados[serve[0]] = d["id"]
    _LOG[uf]["nomes"].update({c: [i, "urna+tse", "média"] for c, i in ligados.items()})
    return ligados


def _tokens_se(nome: str) -> list[str]:
    return [SINONIMOS_SE.get(p, p) for p in re.sub(r"[^a-z ]", " ", comum.sem_acento(nome)).split() if p not in TITULOS_UF["SE"]]


def _casam_se(a: str, b: str) -> bool:
    a, b = _tokens_se(a), _tokens_se(b)
    if not a or not b:
        return False
    return "".join(a) == "".join(b) or set(b) <= set(a) or set(a) <= set(b)


def eleito_do_tse(uf: str, nome: str, eleitos: list[dict]) -> dict | None:
    """O único eleito do TSE (de `comum.eleitos_tse`) cujo nome de urna ou nome civil casa com `nome`, da Assembleia, ou None.
    SC compara por palavras (começo de palavra vale); SE, pelas palavras sem "Dr.", "Prof." e com "Júnior" = "Jr"."""
    if uf == "SC":
        tokens = lambda t: comum.palavras(t, TITULOS_UF["SC"])  # noqa: E731
        candidatos = [(e["sequencial"], t) for e in eleitos for campo in ("nome", "urna") if e.get(campo) and (t := tokens(e[campo]))]
        achado, _ = _unico(tokens(nome), candidatos)
        return next((e for e in eleitos if e["sequencial"] == achado), None) if achado is not None else None
    achados = [e for e in eleitos if _casam_se(nome, e.get("urna") or "") or _casam_se(nome, e["nome"])]
    return achados[0] if len(achados) == 1 else None


# ---------------------------------------------------------------- ministros de Estado

PARTICULAS = {"de", "da", "do", "das", "dos", "e"}
SUFIXOS = {"filho", "junior", "jr", "neto", "sobrinho"}


def _inicio_licenca(p: dict, licenciados: dict) -> str | None:
    """Dia em que o parlamentar saiu da Casa para ser ministro: o último afastamento por "Ministro de Estado" da Câmara sem reassunção
    depois dele; no Senado, o primeiro afastamento cujo cargo é de ministro (as renovações repetem o cargo)."""
    cam = licenciados.get("camara", {}).get(str(p["camara"])) if p["camara"] else None
    if cam:
        inicio = None
        for h in sorted(cam.get("historico", []), key=lambda h: h["data"]):
            if h.get("situacao") == "Licença" and "inistro" in (h.get("descricao") or ""):
                inicio = h["data"]
            elif h.get("situacao") == "Exercício" and inicio:
                inicio = None
        return inicio
    sen = licenciados.get("senado", {}).get(str(p["senado"])) if p["senado"] else None
    datas = [a["inicio"] for a in (sen or {}).get("afastamentos", []) if "inistro" in (a.get("cargo") or "") and a.get("inicio")]
    return min(datas) if datas else None


def ligar_ministros(planalto: dict, reg: "_Registro", licenciados: dict, chaves: dict, ambiguos: list, resumo, sem_ligacao) -> list[dict]:
    """Cada par cargo+nome da lista do Planalto vira {pasta, cargo, nome, pessoa, inicio, inicioFonte, fim?} e a pessoa ganha
    `ligacao["planalto"]`. O início é o da licença do parlamentar, quando houve; senão o dia em que a coleta viu o nome pela primeira
    vez (aproximado: o Planalto não publica datas)."""
    por_nome = defaultdict(set)
    for pid, p in reg.por_id.items():
        if p["nome"]:
            por_nome[norm_nome(p["nome"])].add(pid)
    saida = []
    for situacao in ("atuais", "anteriores"):
        for x in planalto.get(situacao, []):
            pasta = ministerios.pasta_do_cargo(x["cargo"])
            nome = x["nome"].strip()
            chave = norm_nome(nome)
            if not pasta or not chave:
                continue
            ids = por_nome.get(chave, set())
            if len(ids) == 1:
                p = reg.por_id[next(iter(ids))]
                licenciado = _inicio_licenca(p, licenciados)
                p["ligacao"]["planalto"] = ["nome", "alta" if licenciado else "média"]
                resumo["planalto"]["nome"] += 1
            else:
                if ids:
                    ambiguos.append({"fonte": "planalto", "id": f"{pasta}|{chave}", "nome": nome, "uf": None, "candidatos": sorted(ids)})
                sem_ligacao["planalto"] += 1
                p = reg.obter("planalto", chave)
                licenciado = None
            _preencher(p, nome)
            _guardar_nome(p, nome)
            if pasta not in p["planalto"]:
                p["planalto"].append(pasta)
            chaves[("planalto", pasta, chave)] = p["id"]
            saida.append({"pasta": pasta, "cargo": x["cargo"], "nome": nome, "pessoa": p["id"],
                          "inicio": licenciado or x["vistoDesde"], "inicioFonte": "licenca" if licenciado else "planalto",
                          **({"fim": x["vistoAte"]} if x.get("vistoAte") else {})})
    return saida


def ligar_aposentados(aposentados: dict, reg: "_Registro", ambiguos: list, resumo, sem_ligacao) -> list[dict]:
    """Cada ex-senador aposentado da lista do Senado (só tem o nome) é ligado à pessoa do núcleo de mesmo nome que já foi candidata a
    senador ou senadora; nome repetido não liga. Devolve [{pessoa, nome, tipo, inicio, valor}] só dos ligados."""
    por_nome = defaultdict(set)
    for pid, p in reg.por_id.items():
        if p["nome"] and (p["senado"] or any(t[2] in SENADORES for t in p["tse"])):
            por_nome[norm_nome(p["nome"])].add(pid)
    saida = []
    for x in aposentados.get("itens", []):
        chave = norm_nome(x["nome"])
        ids = por_nome.get(chave, set())
        if len(ids) == 1:
            p = reg.por_id[next(iter(ids))]
            p["ligacao"]["aposentadoria"] = ["nome+cargo", "média"]
            resumo["aposentadoria"]["nome+cargo"] += 1
            saida.append({"pessoa": p["id"], "nome": x["nome"], "tipo": x["tipo"], "inicio": x.get("inicio"), "valor": x.get("valor")})
        else:
            if ids:
                ambiguos.append({"fonte": "aposentadoria", "id": chave, "nome": x["nome"], "uf": None, "candidatos": sorted(ids)})
            sem_ligacao["aposentadoria"] += 1
    return saida


def _nome_na_ementa(nome: str, ementa: str) -> bool:
    """Os dois primeiros nomes ("José Múcio"), ou um deles e o último ("Mauro Vieira" para Mauro Luiz Iecker Vieira), aparecem juntos na ementa."""
    partes = [t for t in norm_nome(nome).split() if t not in PARTICULAS]
    while len(partes) > 2 and partes[-1] in SUFIXOS:
        partes.pop()
    if len(partes) < 2:
        return False
    return f"{partes[0]} {partes[1]}" in ementa or any(f"{a} {partes[-1]}" in ementa for a in partes[:2] if a != partes[-1])


def ligar_requerimentos(itens: dict, ministros: list[dict]) -> dict:
    """`itens`: {id: {ementa, dataApresentacao, pastas}} (pastas de `ministerios.pastas_do_texto`). Devolve {id: [pessoa, método, confiança]}
    só para os que tiveram ministro; sem ele o requerimento fica com a pasta e sem pessoa."""
    por_pasta = defaultdict(list)
    for m in ministros:
        por_pasta[m["pasta"]].append(m)
    ligados = {}
    for rid, it in itens.items():
        ementa = norm_nome(it.get("ementa"))
        dia = it.get("dataApresentacao") or ""
        for pasta in it.get("pastas", [])[:1]:
            candidatos = por_pasta.get(pasta, [])
            citado = [m for m in candidatos if _nome_na_ementa(m["nome"], ementa)]
            if len({m["pessoa"] for m in citado}) == 1:
                ligados[rid] = [citado[0]["pessoa"], "nome+pasta", "alta"]
                continue
            no_cargo = [m for m in candidatos if m["inicio"] <= dia and (not m.get("fim") or dia <= m["fim"])]
            if len({m["pessoa"] for m in no_cargo}) == 1:
                ligados[rid] = [no_cargo[0]["pessoa"], "pasta+data", "média" if no_cargo[0]["inicioFonte"] == "licenca" else "baixa"]
    return ligados


def ligar_autoria_senado(autorias, senadores: list[dict]) -> dict:
    """{texto da autoria: [[id do senador, método, confiança], ...]} para "Senador Fulano (PSD/MS), Senadora Fulana (PT/BA)" e
    "Líder do PP Fulana (PP/MS)". Quem não casa com um só senador em exercício não entra na lista do texto."""
    por_nome = defaultdict(set)
    for s in senadores:
        for n in (s.get("nome"), s.get("nomeCivil")):
            if n:
                por_nome[(norm_nome(n), s["uf"])].add(str(s["id"]))
    saida = {}
    for texto in dict.fromkeys(a for a in autorias if isinstance(a, str)):
        achados = []
        for nome, uf in re.findall(r"(?:Senador(?:a)?|Líder d[oa] \S+)\s+(.+?)\s*\([^/()]+/([A-Z]{2})\)", texto):
            ids = por_nome.get((norm_nome(nome), uf), set())
            if len(ids) == 1:
                achados.append([next(iter(ids)), "nome+uf", "média"])
        saida[texto] = achados
    return saida


def gravar_ligacoes(uf: str | None = None, raiz: Path | None = None) -> None:
    """Junta o que `ligar_nomes` decidiu neste processo ao dados/estaduais/<UF>/ligacoes.json, de cada UF, para o cache do CI não perdê-lo:
    {nomes: {nome: [id, método, confiança]}, ambiguos: {nome: [ids]}, semPar: [nomes]}.
    `uf` grava só a dela."""
    raiz = raiz or comum.DADOS
    for uf, log in sorted((u, _LOG.pop(u)) for u in ([uf] if uf else list(_LOG)) if u in _LOG):
        if not (log["nomes"] or log["ambiguos"] or log["semPar"]):
            continue
        arq = raiz / uf / "ligacoes.json"
        antes = ler(arq, {}) or {}
        nomes = {**antes.get("nomes", {}), **log["nomes"]}
        ambiguos = {n: v for n, v in {**antes.get("ambiguos", {}), **log["ambiguos"]}.items() if n not in nomes}
        sem_par = {n for n in [*antes.get("semPar", []), *log["semPar"]] if n not in nomes and n not in ambiguos}
        salvar(arq, {"nomes": nomes, "ambiguos": ambiguos, "semPar": sorted(sem_par)})


def construir(deputados: dict, bruto: Path) -> dict:
    """Devolve {pessoas, partidos, ligacoes, chaves}. `chaves` liga a fonte à pessoa, em memória:
    ("tse", ano, sequencial), ("camara", id), ("senado", id), ("estadual", uf, id) e ("planalto", pasta, nome) -> id da pessoa.
    `ministros` é a lista do Planalto já ligada (ligar_ministros)."""
    reg = _Registro()
    indice = _IndiceTse(reg.por_id)
    chaves = {}
    desconhecidas: set = set()
    federacoes: dict = {}
    seen_partido = Counter()
    resumo = defaultdict(Counter)
    sem_ligacao = Counter()
    ambiguos = []

    def partido(sigla):
        pid = partido_id(sigla, desconhecidas)
        if pid:
            seen_partido[pid] += 1
        return pid

    # --- TSE: uma pessoa por nome civil + nascimento, em todas as eleições
    for pasta in sorted(p for p in (bruto / "tse").glob("*") if p.is_dir() and p.name.isdigit()):
        ano = int(pasta.name)
        for arq in sorted(pasta.glob("[A-Z][A-Z].json")):
            for e in ler(arq, []):
                nome, nasc = e.get("nome"), e.get("nascimento")
                p = reg.obter(*(("nn", f"{norm_nome(nome)}|{nasc}") if nome and nasc else ("tse", f"{ano}|{e['sequencial']}")))
                _preencher(p, nome, nasc, e.get("genero"))
                _guardar_nome(p, e.get("urna"))
                par = partido(e.get("partido"))
                p["tse"].append([ano, e["sequencial"], e["cargo"], par])
                chaves[("tse", ano, e["sequencial"])] = p["id"]
                indice.adicionar(p["id"], e)
                if nome and nasc:
                    indice.por_nome_nasc[(norm_nome(nome), nasc)] = p["id"]
                fed = federacao_de(e.get("federacao"), desconhecidas)
                if fed:
                    federacoes.setdefault(fed, 0)
                    federacoes[fed] += 1

    def ligar(fonte, ident, uf, civis, urnas, cargos, nome, nascimento=None, ancora_propria=None, sequencial=None):   # ancora_propria: (fonte, id)
        """Acha (ou cria) a pessoa da fonte e anota o método da ligação. Devolve a pessoa."""
        achado = None
        if nascimento and civis and (norm_nome(civis[0]), nascimento) in indice.por_nome_nasc:
            achado = (indice.por_nome_nasc[(norm_nome(civis[0]), nascimento)], "nome+nascimento", "alta")
        elif sequencial and (uf, str(sequencial)) in indice.sequencial_estadual:
            achado = (indice.sequencial_estadual[(uf, str(sequencial))], "sequencial", "alta")
        else:
            r = indice.achar(civis, urnas, uf, cargos, nascimento)
            if r and r[0] == "ambiguo":
                ambiguos.append({"fonte": fonte, "id": str(ident), "nome": nome, "uf": uf, "candidatos": sorted(r[1])})
            elif r:
                achado = r
        if achado:
            p = reg.por_id[achado[0]]
            p["ligacao"][fonte] = [achado[1], achado[2]]
            resumo[fonte][achado[1]] += 1
            return p
        sem_ligacao[fonte] += 1
        return reg.obter(*ancora_propria)

    # --- Câmara
    for did, d in deputados.items():
        civil, nasc = d.get("nomeCivil"), d.get("nascimento")
        p = ligar("camara", did, d["uf"], [civil] if civil else [], [d.get("nome")], FEDERAIS, d.get("nome"), nasc,
                  ancora_propria=("nn", f"{norm_nome(civil)}|{nasc}") if civil and nasc else ("camara", did))
        _preencher(p, civil or d.get("nome"), nasc)
        _guardar_nome(p, d.get("nome"))
        p["camara"] = d["id"]
        p["partidoFonte"] = partido(d.get("partido")) or p["partidoFonte"]
        chaves[("camara", str(d["id"]))] = p["id"]

    # --- Senado
    for s in ler(bruto / "senado.json", []) or []:
        civil = s.get("nomeCivil")
        p = ligar("senado", s["id"], s["uf"], [civil] if civil else [], [s.get("nome")], SENADORES, s.get("nome"),
                  ancora_propria=("senado", s["id"]))
        _preencher(p, civil or s.get("nome"), None, s.get("genero") and sem_acento(s["genero"]))
        _guardar_nome(p, s.get("nome"))
        p["senado"] = str(s["id"])
        p["partidoFonte"] = partido(s.get("partido")) or p["partidoFonte"]
        chaves[("senado", str(s["id"]))] = p["id"]

    # --- Assembleias estaduais
    for pasta in sorted(x for x in (bruto / "estaduais").glob("*") if x.is_dir()):
        uf = pasta.name
        for d in (ler(pasta / "deputados.json", {}) or {}).get("deputados", []):
            civil = d.get("nomeCivil")
            p = ligar("estadual", f"{uf}:{d['id']}", uf, [civil] if civil else [], [d.get("nome")], ESTADUAIS, d.get("nome"),
                      ancora_propria=("estadual", f"{uf}|{d['id']}"), sequencial=d["id"])
            _preencher(p, civil or d.get("nome"))
            _guardar_nome(p, d.get("nome"))
            if [uf, str(d["id"])] not in p["estadual"]:
                p["estadual"].append([uf, str(d["id"])])
            p["partidoFonte"] = partido(d.get("partido")) or p["partidoFonte"]
            chaves[("estadual", uf, str(d["id"]))] = p["id"]

    # --- nomes em registros das Assembleias (dados/estaduais/<UF>/ligacoes.json, gravado pelos coletores)
    registros, resumo_registros = {}, {}
    for pasta in sorted(x for x in (bruto / "estaduais").glob("*") if x.is_dir()):
        tabela = ler(pasta / "ligacoes.json", None)
        if not tabela:
            continue
        uf = pasta.name
        registros[uf] = {"nomes": {n: [*v, chaves.get(("estadual", uf, str(v[0])))] for n, v in tabela.get("nomes", {}).items()},
                         "ambiguos": tabela.get("ambiguos", {}), "semPar": tabela.get("semPar", [])}
        resumo_registros[uf] = dict(Counter(v[1] for v in tabela.get("nomes", {}).values()))

    # --- Ministros de Estado (lista do Planalto): pessoa do núcleo pelo nome civil
    ministros = ligar_ministros(ler(bruto / "ministros" / "planalto.json", {}) or {}, reg,
                                ler(bruto / "ministros" / "licencas.json", {}) or {}, chaves, ambiguos, resumo, sem_ligacao)

    aposentados = ligar_aposentados(ler(bruto / "senado_aposentados.json", {}) or {}, reg, ambiguos, resumo, sem_ligacao)

    pessoas = []
    for pid in sorted(reg.por_id):
        p = reg.por_id[pid]
        tse = sorted(p["tse"], key=lambda t: (t[0], str(t[1])))
        fontes = {k: v for k, v in (("tse", tse), ("camara", p["camara"]), ("senado", p["senado"]), ("estadual", p["estadual"]), ("planalto", p["planalto"])) if v}
        nomes = [v for k, v in p["nomes"].items() if k != norm_nome(p["nome"])]
        atual = p["partidoFonte"] or (tse[-1][3] if tse else None)
        pessoas.append({k: v for k, v in {
            "id": pid, "nome": p["nome"], "nascimento": p["nascimento"], "genero": p["genero"], "nomes": nomes,
            "partido": atual, "fontes": fontes, "ligacao": p["ligacao"]}.items() if v})

    usadas = {pid for pid in seen_partido}
    linhas = []
    for chave, (sigla, nome, numero, outras, suc) in PARTIDOS.items():
        linhas.append({"id": "par_" + chave.lower(), "sigla": sigla, "nome": nome, "numero": numero,
                       "outrasSiglas": list(outras), **({"sucessor": "par_" + suc.lower(), "atual": "par_" + _atual(chave).lower()} if suc else {})})
    for pid in sorted(usadas - {x["id"] for x in linhas}):
        linhas.append({"id": pid, "sigla": pid[4:].upper(), "conhecido": False})
    nomes_partido = {x["id"]: x["sigla"] for x in linhas}
    fed_saida = [{"id": federacao_id(membros), "nome": "/".join(nomes_partido.get(m, m) for m in membros),
                  "membros": list(membros), "eleitos": n}
                 for membros, n in sorted(federacoes.items())]

    return {
        "pessoas": pessoas,
        "partidos": {"partidos": linhas, "federacoes": fed_saida},
        "ligacoes": {"resumo": {f: dict(c) for f, c in resumo.items()}, "semLigacao": dict(sem_ligacao),
                     "ambiguos": ambiguos, "partidosDesconhecidos": sorted(desconhecidas),
                     "registros": registros, "resumoRegistros": resumo_registros},
        "chaves": chaves,
        "ministros": ministros,
        "aposentados": aposentados,
    }


def salvar_nucleo(nucleo: dict, saida: Path) -> None:
    for nome in ("pessoas", "partidos", "ligacoes"):
        salvar(saida / f"{nome}.json", nucleo[nome])
    ligacoes = nucleo["ligacoes"]
    print(f"Pessoas: {len(nucleo['pessoas'])}; ligadas ao TSE: {sum(sum(c.values()) for c in ligacoes['resumo'].values())}, "
          f"sem ligação: {sum(ligacoes['semLigacao'].values())}, ambíguas: {len(ligacoes['ambiguos'])}")
