"""
Núcleo de fornecedores: um id por empresa ou pessoa que recebe das cotas e verbas, e o ranking nacional.

  site/dados/nucleo/fornecedores.json   [{id, tipo, nome, nomes, documento, cnpjs, estabelecimentos}] (todos que aparecem)
  site/dados/fornecedores.json          ranking do ano: o que cada fornecedor recebeu da Câmara, do Senado e das Assembleias

Fontes: despesas da cota dos deputados federais, CEAPS dos senadores (dados/senado_ceaps.json) e as verbas indenizatórias
das Assembleias (dados/estaduais/<UF>/verbas_<ano>.json). Não acessa a internet; chamado pelo scripts/gerar.py.

Normalização:
  documento   só dígitos, com o zero à esquerda que as planilhas perdem (CNPJ de 13 dígitos, CPF de 10) e com o dígito
              verificador conferido; documento mascarado, zerado ou inválido é tratado como ausente
  empresa     CNPJ da mesma empresa (os 8 primeiros dígitos) vira um fornecedor só: matriz e filiais somam juntas
  nome        sem acento, caixa, pontuação nem forma jurídica (S/A, LTDA, ME…); serve para achar o documento de uma
              despesa sem CNPJ quando o mesmo nome aparece com um único documento em outra linha
  PF          CPF não aparece inteiro: id por hash e documento mascarado (***.123.456-**)
Id (ids.py): "for_<8 dígitos do CNPJ>" (o próprio identificador público), "for_pf_<hash do CPF>" ou, sem documento, "for_n_<hash do
nome padronizado>". O CPF e o nome-chave não são guardados inteiros no registro: ficam o documento mascarado e os nomes como vieram.
"""

import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from gerar_politicos import ler, salvar
from ids import gerar_id

FORNECEDORES_NO_RANKING = 300
POLITICOS_POR_FORNECEDOR = 5
FORMAS_JURIDICAS = {"SA", "LTDA", "ME", "EPP", "EIRELI", "MEI", "SS", "CIA", "COMERCIO", "DE"}   # tirados do fim e do meio só na chave de comparação


def _digito(base: list[int], pesos: list[int]) -> int:
    resto = sum(a * b for a, b in zip(base, pesos, strict=False)) % 11
    return 0 if resto < 2 else 11 - resto


def cpf_valido(d: str) -> bool:
    n = [int(c) for c in d]
    return len(d) == 11 and len(set(d)) > 1 and _digito(n[:9], list(range(10, 1, -1))) == n[9] and _digito(n[:10], list(range(11, 1, -1))) == n[10]


def cnpj_valido(d: str) -> bool:
    n = [int(c) for c in d]
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    return (len(d) == 14 and len(set(d)) > 1 and _digito(n[:12], p1) == n[12]
            and _digito(n[:13], [6, *p1]) == n[13])


def documento(bruto) -> tuple[str, str] | None:
    """("cnpj", 14 dígitos) ou ("cpf", 11 dígitos) para o que a fonte trouxe (com ou sem pontuação, com zeros perdidos);
    None se vazio, mascarado ou com dígito verificador inválido."""
    texto = str(bruto or "")
    if "*" in texto:
        return None
    d = re.sub(r"\D", "", texto)
    if not d or len(d) > 14:
        return None
    if len(d) <= 11 and cpf_valido(d.zfill(11)):
        return "cpf", d.zfill(11)
    return ("cnpj", d.zfill(14)) if cnpj_valido(d.zfill(14)) else None


def mascarar_cpf(cpf: str) -> str:
    return f"***.{cpf[3:6]}.{cpf[6:9]}-**"


def formatar_cnpj(c: str) -> str:
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def nome_chave(nome: str | None) -> str:
    """Nome para comparar: maiúsculo, sem acento, pontuação nem forma jurídica ("TIM S/A", "tim s.a." -> "TIM")."""
    t = " ".join(re.sub(r"[^A-Z0-9 ]", " ", sem_acento(nome or "").upper().replace("&", " E ")).split())
    t = re.sub(r"\bS A\b", "SA", t)
    return " ".join(x for x in t.split() if x not in FORMAS_JURIDICAS)


def nome_exibido(variantes: Counter) -> str:
    """A grafia de maior valor, preferindo a que não está toda em minúsculas; sem espaço duplo nem ponto solto."""
    def limpo(n):
        n = re.sub(r"\s+", " ", n).strip(" .-")
        return n.title() if n and n == n.lower() else n
    ordem = sorted(variantes.items(), key=lambda kv: (kv[0].strip().islower(), -kv[1], -len(kv[0])))
    return limpo(ordem[0][0]) if ordem else ""


def _linhas(deputados: dict, bruto: Path, nucleo: dict):
    """Despesas do ano como (casa, uf, id do político, nome, partido, valor, fornecedor, documento bruto, chave da pessoa).
    Devolve também o ano e quantas linhas cada casa trouxe."""
    chaves = nucleo["chaves"]
    ceaps = ler(bruto / "senado_ceaps.json", {}) or {}
    ano = (next((d["despesas"]["ano"] for d in deputados.values() if d.get("despesas")), None) or ceaps.get("ano")
           or max([int(m.group(1)) for a in (bruto / "estaduais").glob("*/verbas_*.json") if (m := re.search(r"_(\d{4})\.json$", a.name))] or [0]) or None)
    linhas = []
    for did, d in deputados.items():
        if d.get("despesas", {}).get("ano") != ano:
            continue
        for i in d["despesas"]["itens"]:
            linhas.append(("camara", d["uf"], str(did), d["nome"], d.get("partido"), i.get("valor") or 0, i.get("fornecedor"), i.get("cnpj"),
                           chaves.get(("camara", str(did)))))
    if ceaps.get("ano") == ano:
        senadores = {str(s["id"]): s for s in ler(bruto / "senado.json", []) or []}
        for sid, itens in ceaps["itens"].items():
            s = senadores.get(sid, {})
            for i in itens:
                linhas.append(("senado", s.get("uf"), sid, s.get("nome") or sid, s.get("partido"), i.get("valor") or 0, i.get("fornecedor"),
                               i.get("cnpj"), chaves.get(("senado", sid))))
    for pasta in sorted(p for p in (bruto / "estaduais").glob("*") if p.is_dir()):
        arq = pasta / f"verbas_{ano}.json"
        if not arq.exists():
            continue
        deps = {str(d["id"]): d for d in (ler(pasta / "deputados.json", {}) or {}).get("deputados", [])}
        for i in ler(arq, {}).get("itens", []):
            did = str(i.get("idDeputado"))
            d = deps.get(did, {})
            if not isinstance(i.get("valor"), (int, float)):
                continue
            linhas.append(("estadual", pasta.name, did, d.get("nome") or did, d.get("partido"), i["valor"], i.get("fornecedor"), i.get("cnpj"),
                           chaves.get(("estadual", pasta.name, did))))
    return ano, linhas


def _pagina(casa: str, uf: str | None, did: str, pessoa: dict | None) -> str | None:
    if casa == "camara":
        return f"deputado.html?id={did}"
    if casa == "senado":
        return f"politico.html?f=senado&i={did}"
    for ano, seq, cargo, _ in (pessoa or {}).get("fontes", {}).get("tse", []):
        if ano == 2022 and cargo in ("DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL"):
            return f"politico.html?f=t/2022/{uf}&i={seq}"
    return None


def construir(deputados: dict, bruto: Path, nucleo: dict) -> dict:
    """Devolve {entidades, ranking}. `nucleo` é o resultado de identidades.construir()."""
    ano, linhas = _linhas(deputados, bruto, nucleo)
    pessoas = {p["id"]: p for p in nucleo["pessoas"]}

    # nome -> documento único (entre as despesas que têm documento), para recuperar as que vieram sem
    docs_do_nome = defaultdict(set)
    for _, _, _, _, _, _, nome, bruto_doc, _ in linhas:
        doc = documento(bruto_doc)
        if doc and nome_chave(nome):
            docs_do_nome[nome_chave(nome)].add(_raiz(doc))
    stats = Counter()
    sem_identificacao = 0.0
    forn = {}

    for casa, uf, did, pnome, ppartido, valor, nome, bruto_doc, pessoa in linhas:
        doc = documento(bruto_doc)
        chave_n = nome_chave(nome)
        ident = _raiz(doc) if doc else None
        if doc:
            stats["comDocumento"] += 1
        elif re.sub(r"\D", "", str(bruto_doc or "")):
            stats["documentoInvalido"] += 1
        elif chave_n and len(docs_do_nome.get(chave_n, ())) == 1:
            ident = next(iter(docs_do_nome[chave_n]))
            stats["documentoPeloNome"] += 1
        if ident:
            id_ = "for_" + ident[1] if ident[0] == "cnpj" else gerar_id("for_pf", "cpf", ident[1])
            tipo = "PJ" if ident[0] == "cnpj" else "PF"
        elif chave_n:
            ident, id_, tipo = ("n", chave_n), gerar_id("for_n", "nome", chave_n), None
            stats["semDocumento"] += 1
        else:
            stats["semNome"] += 1
            sem_identificacao += valor
            continue
        f = forn.get(ident)
        if f is None:
            f = forn[ident] = {"id": id_, "tipo": tipo, "nomes": Counter(), "docs": Counter(), "total": 0.0, "notas": 0,
                               "casas": Counter(), "politicos": defaultdict(float), "info": {}}
        f["nomes"][nome or ""] += abs(valor) or 1
        if doc:
            f["docs"][doc[1]] += abs(valor) or 1
        f["total"] += valor
        f["notas"] += 1
        f["casas"][casa] += valor
        quem = (casa, uf, did)
        f["politicos"][quem] += valor
        f["info"][quem] = (pnome, ppartido, pessoa)

    entidades, ranking = [], []
    for f in forn.values():
        docs = sorted(f["docs"], key=lambda d: -f["docs"][d])
        cnpjs = [d for d in docs if len(d) == 14]
        principal = (next((c for c in cnpjs if c[8:12] == "0001"), cnpjs[0]) if cnpjs else (docs[0] if docs else None))
        mostrado = formatar_cnpj(principal) if f["tipo"] == "PJ" else mascarar_cpf(principal) if f["tipo"] == "PF" else None
        nome = nome_exibido(f["nomes"])
        grafias = sorted({n for n in (re.sub(r"\s+", " ", x).strip() for x in f["nomes"]) if n and nome_chave(n) != nome_chave(nome)})
        entidades.append({k: v for k, v in {"id": f["id"], "tipo": f["tipo"], "nome": nome, "nomes": grafias[:10], "documento": mostrado,
                                            "estabelecimentos": len(cnpjs) or None}.items() if v})
        ranking.append((f, nome, mostrado))

    ranking.sort(key=lambda t: -t[0]["total"])
    topo = []
    for f, nome, mostrado in ranking[:FORNECEDORES_NO_RANKING]:
        maiores = sorted(f["politicos"].items(), key=lambda kv: -kv[1])[:POLITICOS_POR_FORNECEDOR]
        topo.append({k: v for k, v in {
            "id": f["id"], "nome": nome, "documento": mostrado, "tipo": f["tipo"], "total": round(f["total"], 2), "notas": f["notas"],
            "politicos": len(f["politicos"]), "porCasa": {c: round(v, 2) for c, v in f["casas"].items()},
            "semDocumento": True if not f["tipo"] else None,
            "maioresPoliticos": [{"nome": f["info"][q][0], "partido": f["info"][q][1], "uf": q[1], "casa": q[0], "valor": round(v, 2),
                                  "pessoa": f["info"][q][2], "pagina": _pagina(q[0], q[1], q[2], pessoas.get(f["info"][q][2]))}
                                 for q, v in maiores],
        }.items() if v is not None})
    entidades.sort(key=lambda e: e["id"])
    por_casa = Counter()
    for f, _, _ in ranking:
        por_casa.update(f["casas"])
    return {
        "entidades": entidades,
        "ranking": {"ano": ano, "fornecedores": topo,
                    "resumo": {"total": round(sum(f["total"] for f, _, _ in ranking), 2), "fornecedores": len(entidades),
                               "porCasa": {c: round(v, 2) for c, v in por_casa.items()},
                               "linhas": dict(stats), "totalSemDocumento": round(sum(f["total"] for f, _, _ in ranking if not f["tipo"]), 2),
                               "totalSemIdentificacao": round(sem_identificacao, 2)}},
    }


def _raiz(doc: tuple) -> tuple:
    return ("cnpj", doc[1][:8]) if doc[0] == "cnpj" else doc


def salvar_fornecedores(res: dict, saida: Path) -> None:
    salvar(saida / "nucleo" / "fornecedores.json", res["entidades"])
    salvar(saida / "fornecedores.json", res["ranking"])
    r = res["ranking"]["resumo"]
    print(f"Fornecedores: {r['fornecedores']} no ano {res['ranking']['ano']}; {r['linhas'].get('documentoPeloNome', 0)} despesas "
          f"ganharam o documento pelo nome, {r['linhas'].get('semDocumento', 0)} seguem sem")
