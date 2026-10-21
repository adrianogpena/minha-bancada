"""
"Fique informado": manda a cada assinante só o que mudou no que ele escolheu acompanhar.

Quem assina (página informado.html) fica numa planilha do Google, atrás do script
assinaturas/apps_script.gs. Aqui a lista vem por ASSINANTES_URL + ASSINANTES_CHAVE (ou de um
arquivo, com --arquivo). Cada assinante tem:

    {"email": ..., "token": ..., "locais": ["BR", "UF:SP", "MUN:SP"], "politicos": ["pres", "dep:204554"],
     "rotulos": ["Brasil", "Estado: São Paulo", ...]}

locais      BR = Câmara, Senado e Presidência; UF:<sigla> = Assembleia, governo, bancada federal e capital
            (se houver dados) do estado; MUN:<sigla> = só a capital do estado
politicos   pres = Presidente; dep:<id da Câmara>; gov:<UF>; est:<UF>:<id no SAPL>; pref:<UF> = prefeito da capital
(os códigos de politicos saem do campo "a" de site/dados/indice/<UF>.json, que o site grava em gerar_politicos.py)

Quem não tem nada novo no escopo não recebe e-mail. Usa as mesmas variáveis SMTP_* de resumo_email.py.

Uso:
    python scripts/assinaturas.py [ANTES [DEPOIS]] [--arquivo assinantes.json] [--saida PASTA] [--enviar]
"""

import argparse
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

import resumo_email as r

INDICE = r.RAIZ / "site" / "dados" / "indice"
LOCAL = re.compile(r"^(BR|(UF|MUN):[A-Z]{2})$")
POLITICO = re.compile(r"^(pres|dep:\d+|gov:[A-Z]{2}|est:[A-Z]{2}:\d+|pref:[A-Z]{2})$")


def baixar_assinantes() -> list[dict]:
    url, chave = os.environ.get("ASSINANTES_URL"), os.environ.get("ASSINANTES_CHAVE")
    if not url or not chave:
        return []
    with urllib.request.urlopen(f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode({'acao': 'lista', 'chave': chave})}", timeout=60) as resp:
        return json.load(resp)


def deputados_por_uf() -> dict[str, set[int]]:
    """UF -> ids (da Câmara) dos deputados federais, a partir do índice que gerar.py acabou de montar."""
    mapa = {}
    for arq in INDICE.glob("[A-Z][A-Z].json"):
        if arq.stem == "BR":
            continue
        itens = json.loads(arq.read_text(encoding="utf-8"))
        mapa[arq.stem] = {int(x["i"]) for x in itens if str(x.get("h", "")).startswith("deputado.html")}
    return mapa


def regras_de(a: dict) -> set[str]:
    return {x for x in a.get("locais", []) if isinstance(x, str) and LOCAL.match(x)} | \
        {x for x in a.get("politicos", []) if isinstance(x, str) and POLITICO.match(x)}


def selecionar(d: dict, regras: set[str], deps_uf: dict[str, set[int]]) -> dict:
    """Parte de coletar() que cabe nas regras de um assinante, no mesmo formato."""
    br = "BR" in regras
    ufs = {x[3:] for x in regras if x.startswith("UF:")}
    deps = {int(x[4:]) for x in regras if x.startswith("dep:")}
    for uf in ufs:
        deps |= deps_uf.get(uf, set())

    def por_uf(chave: str, tudo, itens=lambda uf, m: False):
        """tudo(uf) diz se o estado inteiro entra; senão, entra o que `itens` aprovar."""
        novas, mudou = d[chave]
        n, m = defaultdict(list), defaultdict(list)
        for uf in set(novas) | set(mudou):
            if tudo(uf):
                n[uf], m[uf] = novas.get(uf, []), mudou.get(uf, [])
            else:
                n[uf] = [x for x in novas.get(uf, []) if itens(uf, x)]
                m[uf] = [x for x in mudou.get(uf, []) if itens(uf, x[0])]
        return (defaultdict(list, {k: v for k, v in n.items() if v or m[k]}),
                defaultdict(list, {k: v for k, v in m.items() if v or n.get(k)}))

    pres = br or "pres" in regras
    return {
        **d,
        "camara": [i for i in d["camara"] if br or deps & set(i["deps"])],
        "senado": d["senado"] if br else (0, 0),
        "detalhe": (0, 0),
        "executivo": d["executivo"] if pres else [],
        "executivo_sit": d["executivo_sit"] if pres else [],
        "estaduais": por_uf("estaduais", lambda uf: uf in ufs,
                            lambda uf, m: any(f"est:{uf}:{p}" in regras for p in m.get("dep", []))),
        "governo": por_uf("governo", lambda uf: uf in ufs or f"gov:{uf}" in regras),
        "municipais": por_uf("municipais", lambda uf: uf in ufs or f"MUN:{uf}" in regras or f"pref:{uf}" in regras),
        "votacoes": [uf for uf in d["votacoes"] if uf in ufs],
        "tse": [],
    }


def vazio(d: dict) -> bool:
    return not r.linhas(d)


def rodape(a: dict) -> tuple[str, str]:
    base = os.environ.get("ASSINANTES_URL", "")
    cancelar = f"{base}{'&' if '?' in base else '?'}{urllib.parse.urlencode({'acao': 'cancelar', 't': a['token']})}" if base and a.get("token") else ""
    rotulos = [str(x) for x in a.get("rotulos", [])][:30]
    h = "<p style='font:12px Arial;color:#666;border-top:1px solid #ddd;padding-top:10px'>"
    t = ""
    if rotulos:
        h += f"Você acompanha: {html.escape('; '.join(rotulos))}.<br>"
        t += f"Você acompanha: {'; '.join(rotulos)}.\n"
    if cancelar:
        h += f"Não quer mais receber? <a href='{html.escape(cancelar)}'>Cancelar o aviso</a>."
        t += f"Cancelar o aviso: {cancelar}"
    return h + "</p>", t


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("antes", nargs="?", default="HEAD~1")
    p.add_argument("depois", nargs="?", default="HEAD")
    p.add_argument("--arquivo", help="lista de assinantes em JSON, em vez de ASSINANTES_URL")
    p.add_argument("--saida", help="grava os e-mails em PASTA/<n>.html para conferir")
    p.add_argument("--enviar", action="store_true")
    a = p.parse_args()

    assinantes = json.loads(Path(a.arquivo).read_text(encoding="utf-8")) if a.arquivo else baixar_assinantes()
    if not assinantes:
        print("Nenhum assinante.")
        return
    data = r.git("log", "-1", "--format=%cs", a.depois).strip()
    titulo = f"Minha Bancada — suas atualizações de {data[8:]}/{data[5:7]}/{data[:4]}"
    completo, deps_uf = r.coletar(a.antes, a.depois), deputados_por_uf()
    if not deps_uf:
        print("Aviso: site/dados/indice ausente; avisos por estado não incluem a bancada federal.", file=sys.stderr)

    envios = []
    for n, ass in enumerate(assinantes):
        email, regras = str(ass.get("email", "")).strip(), regras_de(ass)
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) or not regras:
            continue
        parte = selecionar(completo, regras, deps_uf)
        if vazio(parte):
            continue
        h, t = r.montar(parte, titulo, rodape(ass))
        envios.append((n, email, h, t, ass))
    print(f"{len(assinantes)} assinantes; {len(envios)} com novidades.")

    if a.saida:
        pasta = Path(a.saida)
        pasta.mkdir(parents=True, exist_ok=True)
        for n, email, h, t, _ in envios:
            (pasta / f"{n}.html").write_text(f"<!doctype html><meta charset=utf-8><title>{email}</title>{h}", encoding="utf-8")
    if a.enviar and envios:
        falhas = 0
        with r.smtp() as s:
            for n, email, h, t, ass in envios:
                cancelar = rodape(ass)[1].rpartition(": ")[2].strip()
                extra = {"List-Unsubscribe": f"<{cancelar}>"} if cancelar.startswith("http") else {}
                try:
                    s.send_message(r.mensagem(titulo, email, h, t, extra))
                except Exception as e:  # um endereço ruim não pode impedir os outros
                    falhas += 1
                    print(f"Falha ao enviar para o assinante da linha {n}: {e}", file=sys.stderr)
        print(f"Enviados: {len(envios) - falhas}; falhas: {falhas}")


if __name__ == "__main__":
    main()
