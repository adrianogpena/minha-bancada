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
"""

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from gerar_politicos import ler, salvar

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


FEDERAIS = {"DEPUTADO FEDERAL"}
SENADORES = {"SENADOR"}
ESTADUAIS = {"DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL"}


def _id_pessoa(ancora: str) -> str:
    return "pes_" + hashlib.sha1(ancora.encode("utf-8")).hexdigest()[:12]


class _Registro:
    def __init__(self):
        self.por_id = {}
        self.ancoras = {}

    def obter(self, ancora: str) -> dict:
        pid = _id_pessoa(ancora)
        if pid in self.por_id:
            if self.ancoras[pid] != ancora:
                raise RuntimeError(f"colisão de id de pessoa: {ancora!r} e {self.ancoras[pid]!r}")
            return self.por_id[pid]
        self.ancoras[pid] = ancora
        p = self.por_id[pid] = {"id": pid, "nome": None, "nascimento": None, "genero": None, "nomes": {},
                                "tse": [], "camara": None, "senado": None, "estadual": [], "ligacao": {}, "partidoFonte": None}
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


def construir(deputados: dict, bruto: Path) -> dict:
    """Devolve {pessoas, partidos, ligacoes, chaves}. `chaves` liga a fonte à pessoa, em memória:
    ("tse", ano, sequencial), ("camara", id), ("senado", id) e ("estadual", uf, id) -> id da pessoa."""
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
                p = reg.obter(f"nn|{norm_nome(nome)}|{nasc}" if nome and nasc else f"tse|{ano}|{e['sequencial']}")
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

    def ligar(fonte, ident, uf, civis, urnas, cargos, nome, nascimento=None, ancora_propria=None, sequencial=None):
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
        return reg.obter(ancora_propria)

    # --- Câmara
    for did, d in deputados.items():
        civil, nasc = d.get("nomeCivil"), d.get("nascimento")
        p = ligar("camara", did, d["uf"], [civil] if civil else [], [d.get("nome")], FEDERAIS, d.get("nome"), nasc,
                  ancora_propria=f"nn|{norm_nome(civil)}|{nasc}" if civil and nasc else f"camara|{did}")
        _preencher(p, civil or d.get("nome"), nasc)
        _guardar_nome(p, d.get("nome"))
        p["camara"] = d["id"]
        p["partidoFonte"] = partido(d.get("partido")) or p["partidoFonte"]
        chaves[("camara", str(d["id"]))] = p["id"]

    # --- Senado
    for s in ler(bruto / "senado.json", []) or []:
        civil = s.get("nomeCivil")
        p = ligar("senado", s["id"], s["uf"], [civil] if civil else [], [s.get("nome")], SENADORES, s.get("nome"),
                  ancora_propria=f"senado|{s['id']}")
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
                      ancora_propria=f"estadual|{uf}|{d['id']}", sequencial=d["id"])
            _preencher(p, civil or d.get("nome"))
            _guardar_nome(p, d.get("nome"))
            if [uf, str(d["id"])] not in p["estadual"]:
                p["estadual"].append([uf, str(d["id"])])
            p["partidoFonte"] = partido(d.get("partido")) or p["partidoFonte"]
            chaves[("estadual", uf, str(d["id"]))] = p["id"]

    pessoas = []
    for pid in sorted(reg.por_id):
        p = reg.por_id[pid]
        tse = sorted(p["tse"], key=lambda t: (t[0], str(t[1])))
        fontes = {k: v for k, v in (("tse", tse), ("camara", p["camara"]), ("senado", p["senado"]), ("estadual", p["estadual"])) if v}
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
    fed_saida = [{"id": "fed_" + "_".join(m[4:] for m in membros), "nome": "/".join(nomes_partido.get(m, m) for m in membros),
                  "membros": list(membros), "eleitos": n}
                 for membros, n in sorted(federacoes.items())]

    return {
        "pessoas": pessoas,
        "partidos": {"partidos": linhas, "federacoes": fed_saida},
        "ligacoes": {"resumo": {f: dict(c) for f, c in resumo.items()}, "semLigacao": dict(sem_ligacao),
                     "ambiguos": ambiguos, "partidosDesconhecidos": sorted(desconhecidas)},
        "chaves": chaves,
    }


def salvar_nucleo(nucleo: dict, saida: Path) -> None:
    for nome in ("pessoas", "partidos", "ligacoes"):
        salvar(saida / f"{nome}.json", nucleo[nome])
    ligacoes = nucleo["ligacoes"]
    print(f"Pessoas: {len(nucleo['pessoas'])}; ligadas ao TSE: {sum(sum(c.values()) for c in ligacoes['resumo'].values())}, "
          f"sem ligação: {sum(ligacoes['semLigacao'].values())}, ambíguas: {len(ligacoes['ambiguos'])}")
