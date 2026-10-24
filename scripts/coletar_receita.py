"""
Dados cadastrais das empresas que são fornecedoras das cotas e verbas (atividade, abertura, situação, sócios), do CNPJ aberto da
Receita Federal. Guarda só as empresas de site/dados/nucleo/fornecedores.json (tipo PJ) em dados/receita/ (vai para o git; os ZIPs de
dados/receita_bruto/ não).

Só roda na sua máquina: os arquivos mensais somam vários GB (Empresas, Estabelecimentos e Sócios, de 0 a 9) e o Actions só lê o resumo.
Não guarda CPF de sócio: a Receita já o publica mascarado e o projeto só usa o nome e a qualificação. Dado de sócio pessoa física
é público, mas não é cruzado com nenhum político (ver FUTURAS_IMPLEMENTACOES.md, pacote 5.1).

  dados/receita/cnpj/<NN>.json   {raiz do CNPJ (8 dígitos): empresa}, NN = 2 primeiros dígitos da raiz
  dados/receita/tabelas.json     descrição dos códigos usados (CNAE, natureza jurídica, qualificação de sócio, município)
  dados/receita/_coleta.json     competência (AAAA-MM) da base e data da coleta

Uso (antes, rode `python scripts/gerar.py` para existir o núcleo de fornecedores):
    python scripts/coletar_receita.py --listar               # mostra as URLs dos arquivos do mês
    python scripts/coletar_receita.py --baixar               # baixa para dados/receita_bruto/<AAAA-MM>/
    python scripts/coletar_receita.py                        # lê os ZIPs baixados e grava dados/receita/
    python scripts/coletar_receita.py --mes 2026-09

Fonte: https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj (Cadastro Nacional da Pessoa Jurídica, dados abertos;
`RFB_BASE` troca o endereço). Layout dos arquivos: "Metadados do CNPJ", na mesma página da Receita.
"""

import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

import estaduais_comum as comum

RAIZ = Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "dados" / "receita_bruto"
DESTINO = RAIZ / "dados" / "receita"
FORNECEDORES = RAIZ / "site" / "dados" / "nucleo" / "fornecedores.json"
BASE = os.environ.get("RFB_BASE", "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj")
PARTES = range(10)
MAX_SOCIOS = 30
MAX_SECUNDARIOS = 20
VERSAO = 1

csv.field_size_limit(1 << 24)


def arquivos() -> list[str]:
    return [*(f"{g}{i}.zip" for g in ("Empresas", "Estabelecimentos", "Socios") for i in PARTES),
            "Cnaes.zip", "Naturezas.zip", "Qualificacoes.zip", "Municipios.zip"]


def data_receita(texto: str | None) -> str | None:
    """"20190315" -> "2019-03-15"; "0", "00000000" e data que não existe viram None."""
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", (texto or "").strip())
    return comum.data_iso("-".join(m.groups())) if m else None


def codigo(texto: str | None) -> str | None:
    t = (texto or "").strip()
    return t or None


def linhas(zip_path: Path):
    """Linhas (listas de campos, sem cabeçalho, `;`, latin-1) do primeiro arquivo dentro do ZIP."""
    with zipfile.ZipFile(zip_path) as z, z.open(z.namelist()[0]) as f:
        yield from csv.reader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")


def raizes_dos_fornecedores(arq: Path = FORNECEDORES) -> set[str]:
    if not arq.exists():
        sys.exit(f"falta {arq}; rode antes: python scripts/gerar.py")
    return {f["id"][4:] for f in json.loads(arq.read_text(encoding="utf-8")) if f.get("tipo") == "PJ"}


def ler_empresas(pasta: Path, alvo: set[str]) -> dict:
    """Empresas: razão social, natureza jurídica, capital social e porte (arquivos Empresas<N>.zip)."""
    saida = {}
    for i in PARTES:
        for c in linhas(pasta / f"Empresas{i}.zip"):
            if c[0] in alvo and len(c) >= 6:
                saida[c[0]] = {"razaoSocial": comum.compactar(c[1]), "natureza": codigo(c[2]), "capitalSocial": comum.valor_br(c[4]),
                               "porte": codigo(c[5])}
    return saida


def ler_estabelecimentos(pasta: Path, alvo: set[str]) -> dict:
    """Matriz de cada empresa (situação, abertura, atividade, local) e quantos estabelecimentos tem (Estabelecimentos<N>.zip)."""
    saida = {}
    for i in PARTES:
        for c in linhas(pasta / f"Estabelecimentos{i}.zip"):
            if c[0] not in alvo or len(c) < 21:
                continue
            e = saida.setdefault(c[0], {"estabelecimentos": 0})
            e["estabelecimentos"] += 1
            if c[3] == "1":   # matriz
                e.update(situacao=codigo(c[5]), situacaoData=data_receita(c[6]), abertura=data_receita(c[10]), cnaePrincipal=codigo(c[11]),
                         cnaesSecundarios=[x for x in c[12].split(",") if x][:MAX_SECUNDARIOS], uf=codigo(c[19]), municipio=codigo(c[20]))
    return saida


def ler_socios(pasta: Path, alvo: set[str]) -> dict:
    """Sócios [nome, qualificação, entrada na sociedade, tipo (1 empresa, 2 pessoa física, 3 estrangeiro)] (Socios<N>.zip)."""
    saida = {}
    for i in PARTES:
        for c in linhas(pasta / f"Socios{i}.zip"):
            if c[0] in alvo and len(c) >= 6 and comum.compactar(c[2]):
                saida.setdefault(c[0], []).append([comum.compactar(c[2]), codigo(c[4]), data_receita(c[5]), codigo(c[1])])
    return {r: sorted(s, key=lambda x: (x[2] or "9999", x[0]))[:MAX_SOCIOS] for r, s in saida.items()}


def ler_tabela(zip_path: Path) -> dict:
    return {c[0]: comum.compactar(c[1]) for c in linhas(zip_path) if len(c) >= 2}


def montar(pasta: Path, alvo: set[str]) -> tuple[dict, dict]:
    """({raiz: empresa}, tabelas com a descrição dos códigos usados)."""
    empresas, estab, socios = ler_empresas(pasta, alvo), ler_estabelecimentos(pasta, alvo), ler_socios(pasta, alvo)
    saida = {}
    for raiz in sorted(set(empresas) | set(estab)):
        e = {**empresas.get(raiz, {}), **estab.get(raiz, {}), "socios": socios.get(raiz)}
        saida[raiz] = {k: v for k, v in e.items() if v not in (None, [], "")}
    tabelas = {"cnae": ler_tabela(pasta / "Cnaes.zip"), "natureza": ler_tabela(pasta / "Naturezas.zip"),
               "qualificacao": ler_tabela(pasta / "Qualificacoes.zip"), "municipio": ler_tabela(pasta / "Municipios.zip")}
    usados = {"cnae": {c for e in saida.values() for c in [e.get("cnaePrincipal"), *e.get("cnaesSecundarios", ())] if c},
              "natureza": {e["natureza"] for e in saida.values() if e.get("natureza")},
              "qualificacao": {s[1] for e in saida.values() for s in e.get("socios", ()) if s[1]},
              "municipio": {e["municipio"] for e in saida.values() if e.get("municipio")}}
    return saida, {k: {c: tabelas[k][c] for c in sorted(usados[k]) if c in tabelas[k]} for k in tabelas}


def salvar(saida: dict, tabelas: dict, competencia: str, destino: Path = DESTINO) -> None:
    pasta = destino / "cnpj"
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in pasta.glob("*.json"):
        antigo.unlink()
    partes = {}
    for raiz, e in saida.items():
        partes.setdefault(raiz[:2], {})[raiz] = e
    for nn, mapa in partes.items():
        (pasta / f"{nn}.json").write_text(json.dumps(mapa, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (destino / "tabelas.json").write_text(json.dumps(tabelas, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (destino / "_coleta.json").write_text(json.dumps({
        "competencia": competencia, "coletadoEm": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "empresas": len(saida),
        "fonte": BASE, "versao": VERSAO}), encoding="utf-8")


def competencia_local(mes: str | None) -> str:
    if mes:
        return mes
    meses = sorted(p.name for p in BRUTO.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]") if p.is_dir()) if BRUTO.exists() else []
    if not meses:
        sys.exit(f"nada em {BRUTO}; rode: python scripts/coletar_receita.py --baixar --mes AAAA-MM")
    return meses[-1]


def baixar(mes: str) -> None:
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = "minha-bancada (projeto de transparencia)"
    for nome in arquivos():
        destino = BRUTO / mes / nome
        url = f"{BASE}/{mes}/{nome}"
        tam = s.head(url, allow_redirects=True, timeout=60)
        if tam.status_code != 200:
            print(f"  ! {url}: HTTP {tam.status_code}", file=sys.stderr)
            continue
        esperado = int(tam.headers.get("Content-Length", 0))
        if destino.exists() and destino.stat().st_size == esperado:
            print(f"já baixado: {nome}")
            continue
        print(f"Baixando {url} ({esperado / 1e6:.0f} MB)")
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_suffix(".tmp")
        with s.get(url, stream=True, timeout=300) as r, open(tmp, "wb") as f:
            r.raise_for_status()
            for bloco in r.iter_content(1 << 20):
                f.write(bloco)
        if esperado and tmp.stat().st_size != esperado:
            tmp.unlink()
            raise OSError(f"{nome}: tamanho diferente do esperado ({esperado})")
        tmp.replace(destino)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mes", help="competência AAAA-MM (padrão: a mais recente já baixada)")
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--baixar", action="store_true")
    a = ap.parse_args()
    if a.listar or a.baixar:
        mes = a.mes or sys.exit("informe --mes AAAA-MM")
        if a.listar:
            print("\n".join(f"{BASE}/{mes}/{n}" for n in arquivos()))
        else:
            baixar(mes)
        return
    mes = competencia_local(a.mes)
    alvo = raizes_dos_fornecedores()
    print(f"Receita {mes}: {len(alvo)} empresas fornecedoras")
    saida, tabelas = montar(BRUTO / mes, alvo)
    salvar(saida, tabelas, mes)
    print(f"  {len(saida)} encontradas, gravadas em {DESTINO}")


if __name__ == "__main__":
    main()
