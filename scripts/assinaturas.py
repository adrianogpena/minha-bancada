"""
Aviso por e-mail do "Fique informado", com e-mail criptografado de ponta a ponta.

O navegador de quem assina cifra {e-mail, escolhas, token} com a chave pública (site/chave_publica.json) e
manda para o Apps Script (assinaturas/apps_script.gs), que só guarda texto cifrado. Só este script, rodando no
GitHub Actions com a chave privada (segredo ASSINANTES_CHAVE_PRIVADA), consegue ler. Ele:
  1. decifra as linhas e junta as do mesmo e-mail (vale a confirmada mais nova);
  2. manda o e-mail de confirmação das novas (uma por e-mail e dia) e apaga as linhas substituídas ou ilegíveis;
  3. manda a cada assinante confirmado só o que mudou no escopo dele (mesma seleção dos feeds RSS, scripts/feeds.py):
     todo dia (diário), na segunda-feira com a semana anterior (semanal) ou no dia 1 com o mês anterior (mensal).
Nada que identifique alguém vai para o log. Variáveis: ASSINANTES_URL, ASSINANTES_CHAVE, ASSINANTES_CHAVE_PRIVADA
e as SMTP_* de resumo_email.py.

Uso:
    python scripts/assinaturas.py [ANTES [DEPOIS]] [--arquivo linhas.json] [--saida PASTA] [--enviar] [--so-confirmacoes]
(--arquivo lê as linhas cifradas de um JSON em vez do Apps Script; sem --enviar nada é mandado nem marcado;
--so-confirmacoes manda só os e-mails de confirmação, sem o aviso das mudanças, e dispensa o histórico do git:
é o que .github/workflows/confirmacoes.yml roda a cada 15 minutos)
"""

import argparse
import base64
import hashlib
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import feeds
import resumo_email as r

LOCAL = re.compile(r"^(BR|(UF|MUN):[A-Z]{2})$")
POLITICO = re.compile(r"^(pres|dep:\d+|gov:[A-Z]{2}|est:[A-Z]{2}:\d+|pref:[A-Z]{2})$")
EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
ROTULO_INVALIDO = re.compile(r"[^\w ():,.·—-]")
TOKEN = re.compile(r"^[0-9a-f]{64}$")
FREQUENCIAS = ("diario", "semanal", "mensal")   # cadastro sem "freq" (anterior ao dropdown) vale diário


def chamar(url: str, **params) -> object:
    if not url.startswith("https://"):
        raise ValueError("ASSINANTES_URL precisa ser https")
    with urllib.request.urlopen(f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params)}", timeout=60) as resp:
        return json.load(resp)


def decifrar(linha: dict, privada) -> dict | None:
    """Conteúdo da linha ou None se estiver ilegível ou mal formado."""
    try:
        chave = privada.decrypt(base64.b64decode(linha["k"]), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
        d = json.loads(AESGCM(chave).decrypt(base64.b64decode(linha["iv"]), base64.b64decode(linha["c"]), None))
        email, token = str(d["email"]).strip(), str(d["token"])
        if not EMAIL.match(email) or len(email) > 120 or not TOKEN.match(token) or hashlib.sha256(token.encode()).hexdigest() != linha["h"]:
            return None
        locais = [x for x in d.get("locais", []) if isinstance(x, str) and LOCAL.match(x)][:30]
        politicos = [x for x in d.get("politicos", []) if isinstance(x, str) and POLITICO.match(x)][:60]
        if not locais and not politicos:
            return None
        freq = d.get("freq") if d.get("freq") in FREQUENCIAS else "diario"
        return {"email": email, "token": token, "freq": freq, "regras": set(locais) | set(politicos),
                "rotulos": [t for t in (ROTULO_INVALIDO.sub("", str(x))[:120].strip() for x in d.get("rotulos", [])) if t][:len(locais) + len(politicos)], "h": linha["h"], "criado": linha.get("criado", ""),
                "confirmado": bool(linha.get("confirmado")), "enviada": bool(linha.get("enviada"))}
    except Exception:
        return None


def organizar(linhas: list[dict], privada) -> tuple[list[dict], list[dict], list[str]]:
    """(ativos, a confirmar, hashes a apagar). Por e-mail: vale a linha confirmada mais nova; a pendente mais nova só se for mais nova que ela."""
    por_email, apagar = defaultdict(list), []
    for linha in linhas:
        d = decifrar(linha, privada)
        if d:
            por_email[d["email"].lower()].append(d)
        else:
            apagar.append(linha["h"])
    ativos, pendentes = [], []
    for itens in por_email.values():
        itens.sort(key=lambda x: x["criado"], reverse=True)
        conf = next((x for x in itens if x["confirmado"]), None)
        pend = next((x for x in itens if not x["confirmado"] and (not conf or x["criado"] > conf["criado"])), None)
        if conf:
            ativos.append(conf)
        if pend and not pend["enviada"]:
            pendentes.append(pend)
        apagar += [x["h"] for x in itens if x is not conf and x is not pend]
    return ativos, pendentes, apagar


def janela(freq: str, data: str) -> tuple[str, str] | None:
    """(início, título) do período que o aviso `freq` cobre quando o último dia dos fatos é `data` (AAAA-MM-DD), ou None se não é dia de enviar.
    A coleta roda de madrugada e traz o dia anterior: o semanal sai na segunda-feira (`data` é domingo) e cobre segunda a domingo;
    o mensal sai no dia 1 (`data` é o último dia do mês) e cobre o mês inteiro."""
    dia = date.fromisoformat(data)
    br = lambda d: d.strftime("%d/%m/%Y")
    if freq == "semanal" and dia.weekday() == 6:
        ini = dia - timedelta(days=6)
        return ini.isoformat(), f"Minha Bancada — suas atualizações da semana, de {br(ini)} a {br(dia)}"
    if freq == "mensal" and (dia + timedelta(days=1)).day == 1:
        return dia.replace(day=1).isoformat(), f"Minha Bancada — suas atualizações de {dia.month:02d}/{dia.year}"
    return None


def commit_antes_de(inicio: str, depois: str) -> str:
    """Último commit anterior à coleta que trouxe o dia `inicio` (a da madrugada seguinte, em Brasília); sem ele (histórico raso), o mais antigo disponível."""
    coleta = date.fromisoformat(inicio) + timedelta(days=1)
    return r.git("rev-list", "-1", f"--before={coleta.isoformat()}T00:00:00-03:00", depois).strip() or r.git("rev-list", "--max-parents=0", depois).split()[-1]


def link(acao: str, token: str) -> str:
    base = os.environ["ASSINANTES_URL"]
    return f"{base}{'&' if '?' in base else '?'}{urllib.parse.urlencode({'acao': acao, 't': token})}"


def rodape(a: dict) -> tuple[str, str]:
    cancelar = link("cancelar", a["token"])
    h = "<p style='font:12px Arial;color:#666;border-top:1px solid #ddd;padding-top:10px'>"
    t = ""
    if a["rotulos"]:
        h += f"Você acompanha: {html.escape('; '.join(a['rotulos']))}.<br>"
        t += f"Você acompanha: {'; '.join(a['rotulos'])}.\n"
    freq = {"diario": "diário", "semanal": "semanal", "mensal": "mensal"}[a.get("freq", "diario")]
    h += f"Frequência do aviso: {freq}. Para mudar, faça um novo cadastro na página Fique informado.<br>"
    t += f"Frequência do aviso: {freq}. Para mudar, faça um novo cadastro na página Fique informado.\n"
    return h + f"Não quer mais receber?<a href='{html.escape(cancelar)}'>Cancelar o aviso</a>.</p>", t + f"Cancelar o aviso: {cancelar}"


def confirmacao(a: dict) -> tuple[str, str]:
    url = link("confirmar", a["token"])
    itens = "".join(f"<li>{html.escape(x)}</li>" for x in a["rotulos"])
    return (f"<div style='font:15px Arial;max-width:560px'><p>Alguém (esperamos que você) pediu para receber por e-mail o que muda nos dados do Minha Bancada:</p>"
            f"<ul>{itens}</ul><p><a href='{html.escape(url)}'>Confirmar meu e-mail</a></p>"
            "<p style='color:#666'>Se não foi você, ignore esta mensagem: nada será enviado. O pedido expira em 7 dias.</p></div>",
            "Alguém (esperamos que você) pediu para receber por e-mail o que muda nos dados do Minha Bancada:\n\n- "
            + "\n- ".join(a["rotulos"]) + f"\n\nPara confirmar, abra: {url}\n\nSe não foi você, ignore esta mensagem. O pedido expira em 7 dias.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("antes", nargs="?", default="HEAD~1")
    p.add_argument("depois", nargs="?", default="HEAD")
    p.add_argument("--arquivo")
    p.add_argument("--saida")
    p.add_argument("--enviar", action="store_true")
    p.add_argument("--so-confirmacoes", action="store_true")
    a = p.parse_args()

    pem = os.environ.get("ASSINANTES_CHAVE_PRIVADA", "")
    if not pem or not os.environ.get("ASSINANTES_URL"):
        print("Segredos do aviso por e-mail não configurados; pulando.")
        return
    privada = serialization.load_pem_private_key(pem.encode(), password=None)
    linhas = json.loads(Path(a.arquivo).read_text(encoding="utf-8")) if a.arquivo else chamar(os.environ["ASSINANTES_URL"], acao="lista", chave=os.environ["ASSINANTES_CHAVE"])
    ativos, pendentes, apagar = organizar(linhas, privada)
    print(f"{len(linhas)} linhas: {len(ativos)} assinantes ativos, {len(pendentes)} a confirmar, {len(apagar)} a apagar.")

    envios = []
    if ativos and not a.so_confirmacoes:
        data = r.dia_do_commit(a.depois)
        titulo = f"Minha Bancada — suas atualizações de {data[8:]}/{data[5:7]}/{data[:4]}"
        completo, deps_uf = r.coletar(a.antes, a.depois), feeds.deputados_por_uf()
        if not deps_uf:
            print("Aviso: site/dados/indice ausente; avisos por estado não incluem a bancada federal.", file=sys.stderr)
        periodos = {}   # freq -> (título, mudanças do período) ou None; calculado uma vez por frequência
        for ass in ativos:
            freq = ass["freq"]
            if freq == "diario":
                tit, dados, inicio, periodo = titulo, completo, data, "dia"
            else:
                if freq not in periodos:
                    j = janela(freq, data)
                    periodos[freq] = j and (j[1], r.coletar(commit_antes_de(j[0], a.depois), a.depois), j[0], "semana" if freq == "semanal" else "mes")
                if not periodos[freq]:
                    continue
                tit, dados, inicio, periodo = periodos[freq]
            parte = feeds.selecionar(dados, ass["regras"], deps_uf)
            if not feeds.vazio(parte):
                h, t = r.montar(parte, tit, rodape(ass), detalhes=r.link_historico(inicio, ass["regras"], periodo), periodo=periodo)
                envios.append((ass, tit, h, t, {"List-Unsubscribe": f"<{link('cancelar', ass['token'])}>"}))
    for ass in pendentes:
        h, t = confirmacao(ass)
        envios.append((ass, "Confirme seu aviso do Minha Bancada", h, t, {}))
    print(f"{len(envios)} e-mails a enviar ({len(pendentes)} de confirmação).")

    if a.saida:
        pasta = Path(a.saida)
        pasta.mkdir(parents=True, exist_ok=True)
        for n, (ass, assunto, h, *_) in enumerate(envios):
            (pasta / f"{n}.html").write_text(f"<!doctype html><meta charset=utf-8><title>{html.escape(assunto)}</title><p>Para: {html.escape(ass['email'])}</p>{h}", encoding="utf-8")
    if not a.enviar:
        return
    falhas = 0
    if envios:
        with r.smtp() as s:
            for n, (ass, assunto, h, t, extra) in enumerate(envios):
                try:
                    s.send_message(r.mensagem(assunto, ass["email"], h, t, extra))
                    if assunto.startswith("Confirme") and not a.arquivo:
                        chamar(os.environ["ASSINANTES_URL"], acao="marcar", chave=os.environ["ASSINANTES_CHAVE"], h=ass["h"])
                except Exception as e:  # um endereço ruim não pode impedir os outros; sem endereço no log
                    falhas += 1
                    print(f"Falha no envio {n}: {type(e).__name__}", file=sys.stderr)
    if apagar and not a.arquivo:
        for i in range(0, len(apagar), 20):   # o endereço tem limite de tamanho
            chamar(os.environ["ASSINANTES_URL"], acao="apagar", chave=os.environ["ASSINANTES_CHAVE"], h=",".join(apagar[i:i + 20]))
    print(f"Enviados: {len(envios) - falhas}; falhas: {falhas}")


if __name__ == "__main__":
    main()
