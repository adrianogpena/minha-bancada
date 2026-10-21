"""
Monta o e-mail com o que mudou nos dados entre duas versões do repositório
(a execução diária faz um commit "Dados atualizados em AAAA-MM-DD"). Ignora o
que é só ruído de coleta (datas de coleta, links de redes sociais do TSE).
Gera resumo.html e resumo.txt; com --enviar, manda por SMTP usando as variáveis
SMTP_HOST, SMTP_PORT, SMTP_USUARIO, SMTP_SENHA e EMAIL_PARA.

Uso:
    python scripts/resumo_email.py [ANTES [DEPOIS]] [--saida PASTA] [--enviar]
    (padrão: HEAD~1 e HEAD)
"""

import argparse
import html
import json
import os
import smtplib
import subprocess
from collections import Counter, defaultdict
from email.message import EmailMessage
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SITE = "https://adrianogpena.github.io/minha-bancada/"
LIMITE = 12  # itens listados por seção; o resto vira "e mais N"
TIPOS_DESTAQUE = ("PL", "PLP", "PEC", "PDL", "MPV")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=RAIZ, text=True)


def carregar(rev: str, caminho: str):
    try:
        return json.loads(git("show", f"{rev}:{caminho}"))
    except (subprocess.CalledProcessError, ValueError):
        return None


def arquivos(antes: str, depois: str, prefixo: str) -> list[str]:
    return git("diff", "--name-only", antes, depois, "--", prefixo).split()


def cortar(texto: str, n: int = 160) -> str:
    texto = " ".join((texto or "").split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def materias(antes: str, depois: str, prefixo: str, nome_arquivo: str):
    """Novas matérias e mudanças de situação em dados/<prefixo>/<UF>/<nome_arquivo>."""
    novas, mudou = defaultdict(list), defaultdict(list)
    for f in arquivos(antes, depois, prefixo):
        if not f.endswith(nome_arquivo):
            continue
        uf = f.split("/")[2]
        x, y = carregar(antes, f), carregar(depois, f)
        if not y:
            continue
        mx, my = (x or {}).get("materias", {}), y.get("materias", {})
        for k, m in my.items():
            if k not in mx:
                novas[uf].append(m)
            elif m.get("sit") != mx[k].get("sit"):
                mudou[uf].append((m, mx[k].get("sit")))
    return novas, mudou


def camara(antes: str, depois: str):
    novas = []
    for f in arquivos(antes, depois, "dados/proposicoes"):
        x, y = carregar(antes, f), carregar(depois, f)
        ids = {i["id"] for i in (x or {}).get("itens", [])}
        novas += [i for i in (y or {}).get("itens", []) if i["id"] not in ids]
    return novas


def contar(antes: str, depois: str, caminho: str):
    x, y = carregar(antes, caminho), carregar(depois, caminho)
    return len(x or []), len(y or [])


def coletar(antes: str, depois: str) -> dict:
    d = {"antes": antes, "depois": depois}
    d["camara"] = camara(antes, depois)
    d["detalhe"] = contar(antes, depois, "dados/proposicoes_detalhe.json")
    d["senado"] = contar(antes, depois, "dados/senado_materias.json")
    x, y = carregar(antes, "dados/executivo.json") or [], carregar(depois, "dados/executivo.json") or []
    ids = {i["id"] for i in x}
    d["executivo"] = [i for i in y if i["id"] not in ids]
    sit = {i["id"]: i.get("sit") for i in x}
    d["executivo_sit"] = [(i, sit[i["id"]]) for i in y if i["id"] in sit and i.get("sit") != sit[i["id"]]]
    d["estaduais"] = materias(antes, depois, "dados/estaduais", "materias_2026.json")
    d["municipais"] = materias(antes, depois, "dados/municipais", "prefeitura_2026.json")
    d["votacoes"] = sorted({f.split("/")[2] for f in arquivos(antes, depois, "dados/estaduais") if f.endswith("votacoes.json")})
    d["tse"] = [f for f in arquivos(antes, depois, "dados/tse") if "_coleta" not in f]
    return d


def linhas(d: dict) -> list[tuple[str, list[str]]]:
    """Seções (título, itens de texto simples)."""
    s = []
    cam = d["camara"]
    tipos = Counter(i["siglaTipo"] for i in cam)
    if cam:
        dest = [i for i in cam if i["siglaTipo"] in TIPOS_DESTAQUE]
        itens = [f"{i['siglaTipo']} {i['numero']}/{i['ano']} — {cortar(i.get('ementa'))}" for i in dest[:LIMITE]]
        if len(dest) > LIMITE:
            itens.append(f"…e mais {len(dest) - LIMITE} projetos")
        resto = ", ".join(f"{n} {t}" for t, n in tipos.most_common() if t not in TIPOS_DESTAQUE)
        if resto:
            itens.append(f"Outros: {resto}")
        s.append((f"Câmara dos Deputados — {len(cam)} proposições novas", itens))
    ntot = d["senado"][1] - d["senado"][0]
    if ntot:
        s.append((f"Senado — {ntot} matérias novas", []))
    if d["executivo"] or d["executivo_sit"]:
        itens = [f"{i['tipo']} {i['numero']}/{i['ano']} — {cortar(i.get('ementa'))}" for i in d["executivo"]]
        itens += [f"{i['tipo']} {i['numero']}/{i['ano']}: {a or '—'} → {i.get('sit') or '—'}" for i, a in d["executivo_sit"]]
        s.append((f"Executivo — {len(d['executivo'])} novos, {len(d['executivo_sit'])} com nova situação", itens))
    for chave, titulo in (("estaduais", "Assembleia"), ("municipais", "Câmara da capital")):
        novas, mudou = d[chave]
        for uf in sorted(set(novas) | set(mudou)):
            itens = [f"{m.get('t', '')} {m.get('n', '')}/{m.get('a', '')} ({m.get('ap', '')}) — {cortar(m.get('e'))}".strip() for m in novas[uf][:LIMITE]]
            if len(novas[uf]) > LIMITE:
                itens.append(f"…e mais {len(novas[uf]) - LIMITE}")
            itens += [f"{m.get('t', '')} {m.get('n', '')}/{m.get('a', '')}: {a or '—'} → {m.get('sit') or '—'}" for m, a in mudou[uf][:LIMITE]]
            s.append((f"{titulo} {uf} — {len(novas[uf])} novas, {len(mudou[uf])} com nova situação", itens))
    if d["votacoes"]:
        s.append(("Votações estaduais atualizadas", [", ".join(d["votacoes"])]))
    if d["tse"]:
        s.append((f"TSE — {len(d['tse'])} arquivos recoletados", ["Sem eleitos novos; só atualização de redes sociais e bens."]))
    return s


def montar(d: dict, titulo: str) -> tuple[str, str]:
    secoes = linhas(d)
    if not secoes:
        txt = "Nenhum dado novo nesta execução."
        return f"<p>{txt}</p>", txt
    h = [f"<h1 style='font:600 20px Arial'>{html.escape(titulo)}</h1>"]
    t = [titulo, "=" * len(titulo)]
    h.append("<ul style='font:14px Arial;padding-left:18px'>" + "".join(f"<li>{html.escape(a)}</li>" for a, _ in secoes) + "</ul>")
    for a, itens in secoes:
        h.append(f"<h2 style='font:600 16px Arial;margin:22px 0 6px;border-bottom:1px solid #ddd'>{html.escape(a)}</h2>")
        if itens:
            h.append("<ul style='font:13px Arial;color:#333;padding-left:18px'>" + "".join(f"<li style='margin:3px 0'>{html.escape(i)}</li>" for i in itens) + "</ul>")
        t += ["", a] + [f"  - {i}" for i in itens]
    h.append(f"<p style='font:12px Arial;color:#666'>Ver no site: <a href='{SITE}'>{SITE}</a></p>")
    t += ["", f"Ver no site: {SITE}"]
    return "<div style='max-width:680px;margin:auto'>" + "".join(h) + "</div>", "\n".join(t)


def enviar(assunto: str, corpo_html: str, corpo_txt: str) -> None:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = assunto, os.environ["SMTP_USUARIO"], os.environ["EMAIL_PARA"]
    msg.set_content(corpo_txt)
    msg.add_alternative(corpo_html, subtype="html")
    with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "465"))) as s:
        s.login(os.environ["SMTP_USUARIO"], os.environ["SMTP_SENHA"])
        s.send_message(msg)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("antes", nargs="?", default="HEAD~1")
    p.add_argument("depois", nargs="?", default="HEAD")
    p.add_argument("--saida", default=".")
    p.add_argument("--enviar", action="store_true")
    a = p.parse_args()
    data = git("log", "-1", "--format=%cs", a.depois).strip()
    titulo = f"Minha Bancada — o que mudou em {data[8:]}/{data[5:7]}/{data[:4]}"
    h, t = montar(coletar(a.antes, a.depois), titulo)
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "resumo.html").write_text(f"<!doctype html><meta charset=utf-8><title>{titulo}</title>{h}", encoding="utf-8")
    (saida / "resumo.txt").write_text(t, encoding="utf-8")
    print(t)
    if a.enviar:
        enviar(titulo, h, t)


if __name__ == "__main__":
    main()
