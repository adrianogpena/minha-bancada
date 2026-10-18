"""
Baixa do TSE os arquivos brutos (ZIP com CSV) que ainda não usamos no site e
registra cada download no CHANGELOG.md (data, URL, tamanho e SHA-256).

Os ZIPs vão para dados/tse_bruto/<conjunto>/ (fora do git: somam alguns GB).

Uso:
    python scripts/baixar_tse.py --listar                       # mostra URLs e tamanhos, sem baixar
    python scripts/baixar_tse.py                                # todos os conjuntos, 2022 e 2024
    python scripts/baixar_tse.py perfil_eleitorado --anos 2024  # só um conjunto/ano
    python scripts/baixar_tse.py votacao_secao --ufs SP RJ      # só algumas UFs (conjuntos por UF)

Fonte: https://dadosabertos.tse.jus.br
"""

import argparse
import datetime as dt
import hashlib
import os
import sys
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "dados" / "tse_bruto"
CHANGELOG = RAIZ / "CHANGELOG.md"
CDN = os.environ.get("TSE_CDN", "https://cdn.tse.jus.br/estatistica/sead/odsele")
ANOS = [2022, 2024]
UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI",
       "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO", "ZZ", "BR"]  # ZZ = exterior; BR = presidente (só 2022)

# conjunto -> (pasta no CDN, modelo do nome do arquivo, um arquivo por UF?, o que é)
CONJUNTOS = {
    "prestacao_contas": ("prestacao_contas", "prestacao_de_contas_eleitorais_candidatos_{ano}", False,
                         "Prestação de contas de campanha: receitas e despesas dos candidatos, com doadores"),
    "votacao_partido_munzona": ("votacao_partido_munzona", "votacao_partido_munzona_{ano}", False,
                                "Votos do partido por município e zona"),
    "votacao_secao": ("votacao_secao", "votacao_secao_{ano}_{uf}", True, "Votos por seção eleitoral"),
    "perfil_eleitorado": ("perfil_eleitorado", "perfil_eleitorado_{ano}", False,
                          "Perfil do eleitorado por município (idade, gênero, instrução)"),
    "detalhe_votacao_munzona": ("detalhe_votacao_munzona", "detalhe_votacao_munzona_{ano}", False,
                                "Comparecimento, brancos e nulos por município e zona"),
    "consulta_coligacao": ("consulta_coligacao", "consulta_coligacao_{ano}", False, "Coligações e federações"),
    "consulta_vagas": ("consulta_vagas", "consulta_vagas_{ano}", False, "Vagas (cadeiras em disputa) por cargo"),
    "eleitorado_locais_votacao": ("eleitorado_locais_votacao", "eleitorado_local_votacao_{ano}", False,
                                  "Locais de votação com endereço e coordenadas (latitude/longitude)"),
    "motivo_cassacao": ("motivo_cassacao", "motivo_cassacao_{ano}", False,
                        "Motivos de indeferimento/cassação de candidaturas (pouco útil para eleitos)"),
}

CABECALHO_TSE = "## Downloads do TSE (script `scripts/baixar_tse.py`)\n"


def tamanho_remoto(s: requests.Session, url: str) -> int | None:
    r = s.head(url, allow_redirects=True, timeout=60)
    if r.status_code != 200:
        return None
    return int(r.headers.get("Content-Length", 0))


def registrar(url: str, destino: Path, tamanho: int, sha: str) -> None:
    linha = (f"- {dt.datetime.now():%Y-%m-%d %H:%M}: `{destino.relative_to(RAIZ).as_posix()}` ← {url} "
             f"({tamanho / 1e6:.1f} MB, sha256 `{sha[:16]}…`)\n")
    texto = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else ""
    if CABECALHO_TSE not in texto:
        texto += ("\n" if texto and not texto.endswith("\n\n") else "") + CABECALHO_TSE + "\n"
    CHANGELOG.write_text(texto + linha, encoding="utf-8")


def baixar(s: requests.Session, url: str, destino: Path, esperado: int) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp")
    h = hashlib.sha256()
    with s.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for bloco in r.iter_content(1 << 20):
                f.write(bloco)
                h.update(bloco)
    if tmp.stat().st_size != esperado:
        tmp.unlink()
        raise IOError(f"tamanho diferente do esperado ({esperado})")
    tmp.replace(destino)
    registrar(url, destino, esperado, h.hexdigest())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("conjuntos", nargs="*", help="padrão: todos")
    ap.add_argument("--anos", nargs="+", type=int, default=ANOS)
    ap.add_argument("--ufs", nargs="+", default=UFS, help="só vale para conjuntos por UF (votacao_secao)")
    ap.add_argument("--listar", action="store_true", help="só mostra URL e tamanho")
    a = ap.parse_args()
    nomes = a.conjuntos or list(CONJUNTOS)
    erro = [n for n in nomes if n not in CONJUNTOS]
    if erro:
        sys.exit(f"conjunto desconhecido: {erro}. Opções: {', '.join(CONJUNTOS)}")

    s = requests.Session()
    s.headers["User-Agent"] = "minha-bancada (projeto de transparencia)"
    total = 0
    for nome in nomes:
        pasta, modelo, por_uf, _ = CONJUNTOS[nome]
        for ano in a.anos:
            for uf in (a.ufs if por_uf else [None]):
                arquivo = modelo.format(ano=ano, uf=uf) + ".zip"
                url = f"{CDN}/{pasta}/{arquivo}"
                destino = DESTINO / nome / arquivo
                tam = tamanho_remoto(s, url)
                if tam is None:
                    print(f"  ! {url}: não existe (404)", file=sys.stderr)
                    continue
                total += tam
                if a.listar:
                    print(f"{tam / 1e6:9.1f} MB  {url}")
                elif destino.exists() and destino.stat().st_size == tam:
                    print(f"já baixado: {destino.name}")
                else:
                    print(f"Baixando {url} ({tam / 1e6:.1f} MB)")
                    baixar(s, url, destino, tam)
    print(f"Total: {total / 1e6:.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
