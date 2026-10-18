"""
Baixa do TSE os eleitos de cada eleição (com bens declarados) e guarda um
resumo por estado em dados/tse/<ano>/<UF>.json (salvo no git).

Eleições já encerradas (2022, 2024) são baixadas uma vez só. A eleição em
andamento (2026) é atualizada a cada poucos dias, até o resultado final.

Uso:
    python scripts/coletar_tse.py                  # todos os anos configurados
    python scripts/coletar_tse.py --anos 2024      # só um ano
    python scripts/coletar_tse.py --forcar         # baixa de novo mesmo com cache

Fonte: https://dadosabertos.tse.jus.br (Candidatos e Bens de candidatos)
"""

import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
import tempfile
import zipfile
from urllib.parse import urlparse
from collections import Counter, defaultdict
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados" / "tse"
CDN = os.environ.get("TSE_CDN", "https://cdn.tse.jus.br/estatistica/sead/odsele")

ANOS = [2018, 2022, 2024, 2026]
# 2018 entra só para dizer quem elegeu os senadores que ainda estão no mandato
SO_CARGOS = {2018: {"SENADOR"}}
MAJORITARIOS = {"PRESIDENTE", "GOVERNADOR", "PREFEITO"}
ANO_EM_ANDAMENTO = 2026
DIAS_ENTRE_ATUALIZACOES = 2

# só guardamos estas colunas na memória (o arquivo de 2024 tem ~460 mil linhas)
COLUNAS = ["SQ_CANDIDATO", "NR_TURNO", "DS_CARGO", "DS_SIT_TOT_TURNO", "SG_UF", "SG_UE", "NM_UE",
           "NR_CANDIDATO", "NM_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO", "SG_FEDERACAO",
           "NM_FEDERACAO", "DT_NASCIMENTO", "DS_GENERO", "DS_GRAU_INSTRUCAO", "DS_OCUPACAO",
           "DS_COR_RACA", "ST_REELEICAO", "NM_COLIGACAO", "CD_ELEICAO", "DS_SITUACAO_CANDIDATURA"]
VERSAO = 8  # aumente quando mudar o processamento, para refazer os anos em cache

ELEITO = {"ELEITO", "ELEITO POR QP", "ELEITO POR MÉDIA", "ELEITO POR MEDIA"}
SEGUNDO_TURNO = {"2º TURNO", "2O TURNO", "2° TURNO"}
# cargo do vice -> cargo do titular da mesma chapa
VICES = {"VICE-PREFEITO": "PREFEITO", "VICE-GOVERNADOR": "GOVERNADOR", "VICE-PRESIDENTE": "PRESIDENTE"}

# fotos só dos cargos estaduais e federais (as de vereador e prefeito somam centenas de MB)
CARGOS_COM_FOTO = {"PRESIDENTE", "VICE-PRESIDENTE", "GOVERNADOR", "VICE-GOVERNADOR",
                   "DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL"}
CDN_FOTOS = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes{ano}/fotos/foto_cand{ano}_{uf}_div.zip"
FOTOS = RAIZ / "site" / "fotos"
LADO_FOTO = 160

AVISOS = 0


def avisar(msg: str) -> None:
    global AVISOS
    AVISOS += 1
    print(f"  ! {msg}", file=sys.stderr)
    if os.environ.get("GITHUB_ACTIONS") and AVISOS <= 8:
        print(f"::warning::{msg[:900]}")


def baixar(url: str) -> Path:
    print(f"Baixando {url}")
    fd, caminho = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    destino = Path(caminho)
    with requests.get(url, stream=True, timeout=300,
                      headers={"User-Agent": "minha-bancada (projeto de transparencia)"}) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for bloco in r.iter_content(1 << 20):
                f.write(bloco)
    print(f"  {destino.stat().st_size / 1e6:.0f} MB")
    return destino


def linhas_csv(zip_path: Path):
    """Lê os CSVs de dentro do zip. Se houver o arquivo nacional (_BRASIL),
    usa só ele, para não contar ninguém duas vezes."""
    with zipfile.ZipFile(zip_path) as z:
        nomes = [n for n in z.namelist() if n.lower().endswith(".csv")]
        brasil = [n for n in nomes if n.upper().endswith("_BRASIL.CSV")]
        for nome in brasil or nomes:
            with z.open(nome) as bruto:
                texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
                leitor = csv.reader(texto, delimiter=";", quotechar='"')
                cabecalho = next(leitor)
                for linha in leitor:
                    yield dict(zip(cabecalho, linha))


def limpo(v: str | None) -> str | None:
    v = (v or "").strip()
    return None if not v or v.startswith("#NULO") or v in ("-1", "-3", "-4", "#NE", "#NE#") else v


def numero(v: str) -> float:
    v = (v or "0").strip()
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return 0.0


def titulo(s: str | None) -> str | None:
    """'SÃO JOSÉ DOS CAMPOS' -> 'São José dos Campos'"""
    if not s:
        return s
    pequenas = {"de", "da", "do", "das", "dos", "e"}
    partes = s.lower().split()
    return " ".join(p if (i and p in pequenas) else p[:1].upper() + p[1:] for i, p in enumerate(partes))


def frase(s: str | None) -> str | None:
    """'SUPERIOR COMPLETO' -> 'Superior completo'"""
    return s[:1].upper() + s[1:].lower() if s else s


def url_rede(v: str | None) -> str | None:
    """Só aceita endereços http(s); o TSE traz também @usuario e texto solto."""
    v = (v or "").strip()
    if not v or v.startswith("#"):
        return None
    if not v.lower().startswith(("http://", "https://")):
        v = "https://" + v.lstrip("@/")
    try:
        partes = urlparse(v)
    except ValueError:
        return None
    return v if partes.netloc and "." in partes.netloc else None


def coletar_redes(ano: int, eleitos: dict) -> None:
    """Redes sociais e sites que cada candidato declarou ao registrar a candidatura."""
    base = f"{CDN}/consulta_cand/rede_social_candidato_{ano}"
    # 2022 vem um arquivo por UF; 2024 e 2026, um só
    urls = [f"{base}_{uf}.zip" for uf in sorted({e["uf"] for e in eleitos.values()})] if ano == 2022 else [f"{base}.zip"]
    for url in urls:
        try:
            z = baixar(url)
        except Exception as e:
            avisar(f"redes sociais de {ano} ({url.rsplit('/', 1)[-1]}): {e}")
            continue
        for l in linhas_csv(z):
            e = eleitos.get(l.get("SQ_CANDIDATO"))
            link = url_rede(l.get("DS_URL"))
            if e and link and link not in e["redes"]:
                e["redes"].append(link)
        z.unlink()
    print(f"  com redes sociais: {sum(1 for e in eleitos.values() if e['redes'])}")


def coletar_fotos(ano: int, eleitos: dict) -> None:
    """Fotos oficiais da candidatura, reduzidas, só de quem ocupa cargo estadual ou federal."""
    from PIL import Image
    por_uf = defaultdict(list)
    for e in eleitos.values():
        if e["cargo"] in CARGOS_COM_FOTO:
            por_uf[e["uf"]].append(e)
    pasta = FOTOS / str(ano)
    pasta.mkdir(parents=True, exist_ok=True)
    for uf, lista in sorted(por_uf.items()):
        try:
            z = baixar(CDN_FOTOS.format(ano=ano, uf=uf))
        except Exception as ex:
            avisar(f"fotos de {ano}/{uf}: {ex}")
            continue
        with zipfile.ZipFile(z) as arq:
            nomes = {n.rsplit("/", 1)[-1]: n for n in arq.namelist() if n.lower().endswith(".jpg")}
            for e in lista:
                nome = nomes.get(f"F{uf}{e['sq']}_div.jpg") or nomes.get(f"FBR{e['sq']}_div.jpg")
                if not nome:
                    continue
                try:
                    with arq.open(nome) as f:
                        img = Image.open(f).convert("RGB")
                    img.thumbnail((LADO_FOTO, LADO_FOTO))
                    img.save(pasta / f"{e['sq']}.jpg", quality=80, optimize=True)
                    e["foto"] = f"fotos/{ano}/{e['sq']}.jpg"
                except Exception as ex:
                    avisar(f"foto {e['sq']}: {ex}")
        z.unlink()
    print(f"  com foto: {sum(1 for e in eleitos.values() if e['foto'])}")


def coletar_votos(ano: int, eleitos: dict) -> None:
    """Votos de cada eleito (e a data da eleição) por turno, somando as zonas eleitorais.
    Nos cargos majoritários calcula também a porcentagem dos votos válidos."""
    ids = set(eleitos)
    for e in eleitos.values():
        if e.get("chapaSq"):
            ids.add(e["chapaSq"])
    votos = defaultdict(dict)        # sq -> {turno: [data, votos]}
    totais = defaultdict(float)      # (cargo, ue, turno) -> votos válidos
    zip_votos = baixar(f"{CDN}/votacao_candidato_munzona/votacao_candidato_munzona_{ano}.zip")
    for l in linhas_csv(zip_votos):
        cargo = (l.get("DS_CARGO") or "").strip().upper()
        if cargo in SO_CARGOS.get(ano, {cargo}) and cargo:
            turno = int(l.get("NR_TURNO") or 1)
            qt = numero(l.get("QT_VOTOS_NOMINAIS_VALIDOS") or l.get("QT_VOTOS_NOMINAIS"))
            if cargo in MAJORITARIOS:
                totais[(cargo, l["SG_UE"].strip(), turno)] += qt
            sq = l.get("SQ_CANDIDATO")
            if sq in ids:
                d = votos[sq].setdefault(turno, [limpo(l.get("DT_ELEICAO")), 0.0])
                d[1] += qt
    zip_votos.unlink()

    def data_iso(v):
        if v and "/" in v:
            d, m, a = v.split("/")
            return f"{a}-{m}-{d}"
        return v

    for e in eleitos.values():
        fonte_sq = e.get("chapaSq") or e["sq"]
        turnos = []
        for turno, (data, qt) in sorted(votos.get(fonte_sq, {}).items()):
            total = totais.get((e["cargo"].replace("VICE-", ""), e["ue"], turno))
            turnos.append({"turno": turno, "data": data_iso(data), "votos": int(qt),
                           "pct": round(100 * qt / total, 2) if total else None})
        e["votos"] = turnos
    print(f"  com votos: {sum(1 for e in eleitos.values() if e['votos'])}")


def coletar_ano(ano: int) -> None:
    pasta = DADOS / str(ano)
    zip_cand = baixar(f"{CDN}/consulta_cand/consulta_cand_{ano}.zip")

    # 1) fica com a linha do último turno de cada candidato
    candidatos: dict[str, dict] = {}
    obrigatorias = {"SQ_CANDIDATO", "DS_CARGO", "DS_SIT_TOT_TURNO", "SG_UF", "SG_UE", "NM_UE", "NR_CANDIDATO"}
    verificado = False
    for l in linhas_csv(zip_cand):
        if not verificado:
            faltando = obrigatorias - l.keys()
            if faltando:
                raise SystemExit(f"Colunas ausentes no arquivo do TSE {ano}: {sorted(faltando)}. "
                                 f"Colunas encontradas: {sorted(l.keys())[:60]}")
            verificado = True
        sq = l["SQ_CANDIDATO"]
        try:
            turno = int(l.get("NR_TURNO") or 1)
        except ValueError:
            turno = 1
        atual = candidatos.get(sq)
        if atual is None or turno >= atual["_turno"]:
            enxuto = {k: l.get(k) for k in COLUNAS}
            enxuto["_turno"] = turno
            candidatos[sq] = enxuto
    zip_cand.unlink()
    print(f"  candidaturas: {len(candidatos)}")

    # 2) titulares eleitos (ou no 2º turno), para achar os vices da mesma chapa
    def situacao(l):
        s = (l.get("DS_SIT_TOT_TURNO") or "").strip().upper()
        if s in ELEITO or (s.startswith("ELEITO") and "NÃO" not in s):
            return "eleito"
        if s in SEGUNDO_TURNO or ("TURNO" in s and "2" in s):
            return "2turno"
        return None

    # enquanto o 2º turno não acontece, os finalistas de presidente e governador
    # já têm uma linha de 2º turno, ainda sem resultado (#NULO)
    if ano == ANO_EM_ANDAMENTO:
        for l in candidatos.values():
            if (l["DS_CARGO"].strip().upper() in ("PRESIDENTE", "GOVERNADOR") and l["_turno"] == 2
                    and (l.get("DS_SIT_TOT_TURNO") or "").strip().upper().startswith("#NULO")):
                l["DS_SIT_TOT_TURNO"] = "2º TURNO"
        finalistas = Counter(l["SG_UE"] for l in candidatos.values()
                             if l["DS_CARGO"].strip().upper() in ("PRESIDENTE", "GOVERNADOR") and situacao(l) == "2turno")
        estranhos = {ue: n for ue, n in finalistas.items() if n != 2}
        if estranhos:
            avisar(f"TSE {ano}: lugares com número de finalistas diferente de 2: {estranhos}")

    chapas = {}
    titulares = {}
    for sq, l in candidatos.items():
        cargo = l["DS_CARGO"].strip().upper()
        if cargo in VICES.values() and situacao(l):
            chapas[(cargo, l["SG_UE"], l["NR_CANDIDATO"])] = situacao(l)
            titulares[(cargo, l["SG_UE"], l["NR_CANDIDATO"])] = sq

    # se uma chapa tem mais de um vice registrado (troca antes da eleição),
    # fica o registro mais recente: o substituto recebe número de registro maior
    vice_da_chapa = {}
    for sq, l in candidatos.items():
        cargo = l["DS_CARGO"].strip().upper()
        if cargo in VICES:
            chave = (cargo, l["SG_UE"], l["NR_CANDIDATO"])
            atual = vice_da_chapa.get(chave)
            if atual is None or (l["_turno"], int(sq)) > (candidatos[atual]["_turno"], int(atual)):
                vice_da_chapa[chave] = sq

    eleitos = {}
    for sq, l in candidatos.items():
        cargo = l["DS_CARGO"].strip().upper()
        if cargo in VICES:
            if vice_da_chapa.get((cargo, l["SG_UE"], l["NR_CANDIDATO"])) != sq:
                continue
            sit = chapas.get((VICES[cargo], l["SG_UE"], l["NR_CANDIDATO"]))
        else:
            sit = situacao(l)
        if not sit or "SUPLENTE" in cargo or cargo not in SO_CARGOS.get(ano, {cargo}):
            continue
        chapa_sq = titular_nome = None
        if cargo in VICES:
            chapa_sq = titulares.get((VICES[cargo], l["SG_UE"], l["NR_CANDIDATO"]))
            if chapa_sq:
                tl = candidatos[chapa_sq]
                titular_nome = titulo(limpo(tl.get("NM_URNA_CANDIDATO"))) or titulo(limpo(tl.get("NM_CANDIDATO")))
        uf = l["SG_UF"].strip().upper()
        nascimento = limpo(l.get("DT_NASCIMENTO"))
        if nascimento and "/" in nascimento:
            d, m, a = nascimento.split("/")
            nascimento = f"{a}-{m}-{d}"
        eleitos[sq] = {
            "sq": sq,
            "nome": titulo(limpo(l.get("NM_CANDIDATO"))),
            "urna": titulo(limpo(l.get("NM_URNA_CANDIDATO"))) or titulo(limpo(l.get("NM_CANDIDATO"))),
            "cargo": cargo,
            "situacao": sit,
            "partido": limpo(l.get("SG_PARTIDO")),
            "federacao": limpo(l.get("SG_FEDERACAO")) or limpo(l.get("NM_FEDERACAO")),
            "numero": limpo(l.get("NR_CANDIDATO")),
            "uf": uf,
            "ue": l["SG_UE"].strip(),
            "municipio": titulo(limpo(l.get("NM_UE"))) if cargo in ("VEREADOR", "PREFEITO", "VICE-PREFEITO") else None,
            "nascimento": nascimento,
            "genero": limpo(l.get("DS_GENERO")),
            "instrucao": frase(limpo(l.get("DS_GRAU_INSTRUCAO"))),
            "ocupacao": frase(limpo(l.get("DS_OCUPACAO"))),
            "corRaca": frase(limpo(l.get("DS_COR_RACA"))),
            "reeleicao": (l.get("ST_REELEICAO") or "").strip().upper() == "S",
            "coligacao": titulo(limpo(l.get("NM_COLIGACAO"))),
            "eleicao": limpo(l.get("CD_ELEICAO")),
            "resultado": frase(limpo(l.get("DS_SIT_TOT_TURNO"))),
            "chapaSq": chapa_sq,
            "titular": titular_nome,
            "votos": [],
            "bens": [],
            "totalBens": 0.0,
            "redes": [],
            "foto": None,
        }
    del candidatos
    print(f"  eleitos{' e no 2º turno' if ano == ANO_EM_ANDAMENTO else ''}: {len(eleitos)}")
    if not eleitos:
        raise SystemExit(f"Nenhum eleito encontrado em {ano}; algo mudou no arquivo do TSE.")

    try:
        coletar_votos(ano, eleitos)
    except Exception as e:
        avisar(f"votos de {ano}: {e}")
    if ano in SO_CARGOS:
        salvar_ano(ano, pasta, eleitos)
        return

    # 3) bens declarados, só dos eleitos
    try:
        zip_bens = baixar(f"{CDN}/bem_candidato/bem_candidato_{ano}.zip")
        for l in linhas_csv(zip_bens):
            e = eleitos.get(l.get("SQ_CANDIDATO"))
            if not e:
                continue
            valor = numero(l.get("VR_BEM_CANDIDATO"))
            e["totalBens"] += valor
            e["bens"].append([frase(limpo(l.get("DS_TIPO_BEM_CANDIDATO"))) or "Outros",
                              (limpo(l.get("DS_BEM_CANDIDATO")) or "")[:160], round(valor, 2)])
        zip_bens.unlink()
    except Exception as e:
        avisar(f"bens de {ano}: {e}")
    for e in eleitos.values():
        e["totalBens"] = round(e["totalBens"], 2)
        e["bens"].sort(key=lambda b: -b[2])

    # 4) redes sociais declaradas e fotos
    try:
        coletar_redes(ano, eleitos)
    except Exception as e:
        avisar(f"redes sociais de {ano}: {e}")
    try:
        coletar_fotos(ano, eleitos)
    except Exception as e:
        avisar(f"fotos de {ano}: {e}")

    salvar_ano(ano, pasta, eleitos)


def salvar_ano(ano: int, pasta: Path, eleitos: dict) -> None:
    # 5) salva por UF (BR = presidente e vice)
    por_uf = defaultdict(list)
    for e in eleitos.values():
        por_uf[e["uf"]].append(e)
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in pasta.glob("*.json"):
        antigo.unlink()
    for uf, lista in por_uf.items():
        lista.sort(key=lambda e: (e["cargo"], e["municipio"] or "", e["urna"] or ""))
        (pasta / f"{uf}.json").write_text(json.dumps(lista, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (pasta / "_coleta.json").write_text(json.dumps({
        "coletadoEm": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "eleitos": len(eleitos),
        "versao": VERSAO,
    }), encoding="utf-8")
    print(f"  salvo em {pasta} ({len(por_uf)} arquivos)")


def precisa_coletar(ano: int, forcar: bool) -> bool:
    marca = DADOS / str(ano) / "_coleta.json"
    if forcar or not marca.exists():
        return True
    info = json.loads(marca.read_text())
    if info.get("versao", 1) < VERSAO:
        return True
    if ano != ANO_EM_ANDAMENTO:
        return False
    quando = dt.datetime.fromisoformat(info["coletadoEm"])
    return dt.datetime.now(dt.timezone.utc) - quando > dt.timedelta(days=DIAS_ENTRE_ATUALIZACOES)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--anos", type=int, nargs="+", default=ANOS)
    p.add_argument("--forcar", action="store_true")
    a = p.parse_args()
    for ano in a.anos:
        if not precisa_coletar(ano, a.forcar):
            print(f"TSE {ano}: em cache, nada a fazer")
            continue
        try:
            coletar_ano(ano)
        except SystemExit as e:
            avisar(str(e))
        except Exception as e:
            avisar(f"TSE {ano}: {e}")


if __name__ == "__main__":
    main()
