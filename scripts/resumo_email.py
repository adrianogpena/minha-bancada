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
import shutil
import smtplib
import subprocess
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote

import cadastro_proposicoes
import nomes_legados
from fuso import BRASILIA

RAIZ = Path(__file__).resolve().parent.parent
GIT = shutil.which("git") or "git"
SITE = "https://adrianogpena.github.io/minha-bancada/"
LIMITE = 12  # itens listados por seção; o resto vira "e mais N"
TIPOS_DESTAQUE = ("PL", "PLP", "PEC", "PDL", "MPV")
JANELA_ATO_DIAS = 3  # só é novidade o que tem data do ato até 3 dias antes da coleta (ou nenhuma data); o resto fica só no site


def na_janela(data_ato, dia_coleta: str | None) -> bool:
    """Se uma novidade com essa data do ato entra no histórico, no RSS e no e-mail: data até JANELA_ATO_DIAS antes do dia da coleta,
    ou sem data (ou data ilegível, ou dia da coleta desconhecido), que na dúvida entra."""
    try:
        return (date.fromisoformat(dia_coleta) - date.fromisoformat(str(data_ato)[:10])).days <= JANELA_ATO_DIAS
    except (TypeError, ValueError):
        return True


def link_historico(data: str, locais=None, periodo: str = "dia") -> str:
    """Página do histórico (detalhes e fontes) para um dia AAAA-MM-DD, filtrada por códigos de local ou político quando houver.
    `periodo` "semana" ou "mes": a página abre a semana ou o mês que contém `data`."""
    pagina = (date.fromisoformat(data) + timedelta(days=1)).isoformat()   # `data` é o dia dos fatos; o histórico leva o dia da coleta
    return (f"{SITE}historico.html?dia={pagina}" + (f"&periodo={periodo}" if periodo != "dia" else "")
            + (f"&locais={quote(','.join(sorted({'BR' if c == 'FEDERAL' else c for c in locais})), safe=',:')}" if locais and "BR" not in locais else ""))


def cont(n: int, um: str, varios: str) -> str:
    """"1 novo", "3 novos"; vazio quando n é 0, para não listar zeros nos títulos."""
    return f"{n} {um if n == 1 else varios}" if n else ""


def juntar(*partes: str) -> str:
    return ", ".join(p for p in partes if p)


def git(*args: str) -> str:
    return subprocess.check_output([GIT, *args], cwd=RAIZ, text=True)


def dia_dos_fatos(timestamp: int) -> str:
    """Dia (AAAA-MM-DD, Brasília) a que pertence uma coleta feita no instante `timestamp`: a coleta roda de madrugada e traz o dia anterior."""
    return (datetime.fromtimestamp(timestamp, BRASILIA).date() - timedelta(days=1)).isoformat()


def dia_do_commit(rev: str, *caminhos: str) -> str | None:
    """Dia dos fatos do commit `rev` (ou do último que mexeu em `caminhos`); None se não houver."""
    ts = git("log", "-1", "--format=%ct", rev, *(["--", *caminhos] if caminhos else [])).strip()
    return dia_dos_fatos(int(ts)) if ts else None


def dia_da_coleta(rev: str) -> str | None:
    """Dia (AAAA-MM-DD, Brasília) em que rodou a coleta do commit `rev`: o dia seguinte ao dos fatos."""
    fatos = dia_do_commit(rev)
    return (date.fromisoformat(fatos) + timedelta(days=1)).isoformat() if fatos else None


def carregar(rev: str, caminho: str):
    try:
        return nomes_legados.atualizar(caminho, json.loads(git("show", f"{rev}:{caminho}")))
    except (subprocess.CalledProcessError, ValueError):
        return None


def arquivos(antes: str, depois: str, prefixo: str) -> list[str]:
    return git("diff", "--name-only", antes, depois, "--", prefixo).split()


def cortar(texto: str, n: int = 160) -> str:
    texto = " ".join((texto or "").split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def materias(antes: str, depois: str, prefixo: str, nome_arquivo: str, dia_coleta: str | None = None):
    """Novas matérias (com data de apresentação dentro da janela) e mudanças de situação em dados/<prefixo>/<UF>/<nome_arquivo>."""
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
                if na_janela(m.get("dataApresentacao"), dia_coleta):
                    novas[uf].append(m)
            elif m.get("situacao") != mx[k].get("situacao"):
                mudou[uf].append((m, mx[k].get("situacao")))
    return novas, mudou


def objetos_em(rev: str, arquivos_deputados: dict | None = None) -> dict:
    """{id: {id, siglaTipo, numero, ano, ementa}} das proposições da Câmara em `rev`: o cadastro (dados/proposicoes_cadastro/)
    e, para commits antigos, os objetos que os arquivos de deputado ainda traziam (`arquivos_deputados`: {caminho: conteúdo})."""
    try:
        caminhos = git("ls-tree", "-r", "--name-only", rev, "--", "dados/proposicoes_cadastro").split()
    except subprocess.CalledProcessError:
        caminhos = []
    anos = {int(Path(c).stem) if Path(c).stem.isdigit() else None: carregar(rev, c) for c in caminhos}
    meta = cadastro_proposicoes.ler_anos(anos)
    for conteudo in (arquivos_deputados or {}).values():
        for p in cadastro_proposicoes.itens_legados(conteudo):
            meta.setdefault(p["id"], p)
    return meta


def camara(antes: str, depois: str, dia_coleta: str | None = None):
    """Proposições novas dentro da janela, sem repetir as de vários autores; "idsDeputados" lista os deputados (ids da Câmara) que constam como autores."""
    novas, depois_ = {}, {}
    for f in arquivos(antes, depois, "dados/proposicoes"):
        x, y = carregar(antes, f), carregar(depois, f)
        depois_[f] = y
        ids = set(cadastro_proposicoes.ids_de(x))
        for pid in cadastro_proposicoes.ids_de(y):
            if pid not in ids:
                novas.setdefault(pid, []).append(int(Path(f).stem))
    meta = objetos_em(depois, depois_) if novas else {}
    detalhe = (carregar(depois, "dados/proposicoes_detalhe.json") or {}) if novas else {}
    return [{**meta[pid], "idsDeputados": deps} for pid, deps in novas.items()
            if pid in meta and na_janela((detalhe.get(str(pid)) or {}).get("dataApresentacao"), dia_coleta)]


def contar(antes: str, depois: str, caminho: str):
    x, y = carregar(antes, caminho), carregar(depois, caminho)
    return len(x or []), len(y or [])


def senado_novas(antes: str, depois: str, dia_coleta: str | None) -> tuple[int, int]:
    """(0, matérias novas do Senado dentro da janela): o formato (antes, depois) é o das contagens, e quem lê só subtrai."""
    x, y = carregar(antes, "dados/senado_materias.json") or {}, carregar(depois, "dados/senado_materias.json") or {}
    return 0, sum(1 for k, m in y.items() if k not in x and na_janela(m.get("dataApresentacao") or m.get("dataSituacao"), dia_coleta))


def coletar(antes: str, depois: str, dia_coleta: str | None = None) -> dict:
    """`dia_coleta` (AAAA-MM-DD, ver dia_da_coleta): de onde se conta a janela da data do ato. Sem ele não há janela: serve aos resumos
    de semana e de mês, que cobrem mais de um dia."""
    d = {"antes": antes, "depois": depois}
    d["camara"] = camara(antes, depois, dia_coleta)
    d["detalhe"] = contar(antes, depois, "dados/proposicoes_detalhe.json")
    d["senado"] = senado_novas(antes, depois, dia_coleta)
    x, y = carregar(antes, "dados/executivo.json") or [], carregar(depois, "dados/executivo.json") or []
    ids = {i["id"] for i in x}
    d["executivo"] = [i for i in y if i["id"] not in ids and na_janela(i.get("dataApresentacao") or i.get("dataSituacao"), dia_coleta)]
    situacao = {i["id"]: i.get("situacao") for i in x}
    d["executivo_situacao"] = [(i, situacao[i["id"]]) for i in y if i["id"] in situacao and i.get("situacao") != situacao[i["id"]] and na_janela(i.get("dataSituacao"), dia_coleta)]
    d["estaduais"] = materias(antes, depois, "dados/estaduais", "materias_2026.json", dia_coleta)
    d["governo"] = materias(antes, depois, "dados/estaduais", "governo_2026.json", dia_coleta)
    d["municipais"] = materias(antes, depois, "dados/municipais", "prefeitura_2026.json", dia_coleta)
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
        s.append((f"Câmara dos Deputados — {cont(len(cam), 'proposição nova', 'proposições novas')}", itens))
    ntot = d["senado"][1] - d["senado"][0]
    if ntot:
        s.append((f"Senado — {cont(ntot, 'matéria nova', 'matérias novas')}", []))
    if d["executivo"] or d["executivo_situacao"]:
        itens = [f"{i['tipo']} {i['numero']}/{i['ano']} — {cortar(i.get('ementa'))}" for i in d["executivo"]]
        itens += [f"{i['tipo']} {i['numero']}/{i['ano']}: {a or '—'} → {i.get('situacao') or '—'}" for i, a in d["executivo_situacao"]]
        s.append((f"Executivo — {juntar(cont(len(d['executivo']), 'novo', 'novos'), cont(len(d['executivo_situacao']), 'com nova situação', 'com nova situação'))}", itens))
    for chave, titulo in (("estaduais", "Assembleia"), ("governo", "Governo do estado, projetos enviados à Assembleia"), ("municipais", "Câmara da capital")):
        novas, mudou = d[chave]
        for uf in sorted(set(novas) | set(mudou)):
            itens = [f"{m.get('tipo', '')} {m.get('numero', '')}/{m.get('ano', '')} ({m.get('dataApresentacao', '')}) — {cortar(m.get('ementa'))}".strip() for m in novas[uf][:LIMITE]]
            if len(novas[uf]) > LIMITE:
                itens.append(f"…e mais {len(novas[uf]) - LIMITE}")
            itens += [f"{m.get('tipo', '')} {m.get('numero', '')}/{m.get('ano', '')}: {a or '—'} → {m.get('situacao') or '—'}" for m, a in mudou[uf][:LIMITE]]
            s.append((f"{titulo} {uf} — {juntar(cont(len(novas[uf]), 'nova', 'novas'), cont(len(mudou[uf]), 'com nova situação', 'com nova situação'))}", itens))
    if d["votacoes"]:
        s.append(("Votações estaduais atualizadas", [", ".join(d["votacoes"])]))
    if d["tse"]:
        s.append((f"TSE — {cont(len(d['tse']), 'arquivo recoletado', 'arquivos recoletados')}", ["Sem eleitos novos; só atualização de redes sociais e bens."]))
    return s


def resumo_curto(d: dict, limite: int = 3) -> str:
    """O que mudou em poucas palavras, para título de item de feed e assunto de e-mail (leitores cortam em ~40 caracteres): "Câmara 4 · Senado 1"."""
    cam = len(d["camara"])
    partes = [("Câmara", cam), ("Senado", d["senado"][1] - d["senado"][0]), ("Executivo", len(d["executivo"]) + len(d["executivo_situacao"]))]
    for chave, nome in (("estaduais", "Assembleia"), ("governo", "Governo"), ("municipais", "Capital")):
        novas, mudou = d[chave]
        ufs = sorted(u for u in set(novas) | set(mudou) if novas.get(u) or mudou.get(u))
        if ufs:
            partes.append((f"{nome} {ufs[0]}" if len(ufs) == 1 else nome, sum(len(novas.get(u, [])) + len(mudou.get(u, [])) for u in ufs)))
    textos = [f"{n_} {q}" for n_, q in partes if q]
    if d["votacoes"]:
        textos.append("Votações " + ",".join(d["votacoes"]))
    if d["tse"]:
        textos.append("TSE")
    if len(textos) > limite:
        textos = textos[:limite] + [f"+{len(textos) - limite}"]
    return " · ".join(textos)


def resumo_longo(d: dict) -> str:
    """Os títulos das seções em uma linha, para abrir o corpo do item de feed (a prévia que o leitor mostra)."""
    return " · ".join(a.replace(" — ", ": ") for a, _ in linhas(d))


def montar(d: dict, titulo: str, rodape: tuple[str, str] = ("", ""), detalhes: str | None = None, sumario: bool = True, periodo: str = "dia") -> tuple[str, str]:
    """`detalhes`: link da página do histórico, com todos os itens e as fontes. `periodo` ("dia", "semana" ou "mes") diz o que o link abre."""
    secoes = linhas(d)
    if not secoes:
        txt = "Nenhum dado novo nesta execução."
        return f"<p>{txt}</p>", txt
    h = [f"<h1 style='font:600 20px Arial'>{html.escape(titulo)}</h1>"]
    t = [titulo, "=" * len(titulo)]
    if sumario:
        h.append("<ul style='font:14px Arial;padding-left:18px'>" + "".join(f"<li>{html.escape(a)}</li>" for a, _ in secoes) + "</ul>")
    for a, itens in secoes:
        h.append(f"<h2 style='font:600 16px Arial;margin:22px 0 6px;border-bottom:1px solid #ddd'>{html.escape(a)}</h2>")
        if itens:
            h.append("<ul style='font:13px Arial;color:#333;padding-left:18px'>" + "".join(f"<li style='margin:3px 0'>{html.escape(i)}</li>" for i in itens) + "</ul>")
        t += ["", a] + [f"  - {i}" for i in itens]
    if detalhes:
        pedido = {"semana": "Veja cada item da semana, com a fonte oficial", "mes": "Veja cada item do mês, com a fonte oficial"}.get(periodo, "Veja cada item, com a fonte oficial")
        nome = {"semana": "Abrir o histórico da semana", "mes": "Abrir o histórico do mês"}.get(periodo, "Abrir o histórico do dia")
        h.append(f"<p style='font:14px Arial'><b>Quer mais detalhes?</b> {pedido}: <a href='{html.escape(detalhes)}'>{nome}</a></p>")
        t += ["", f"Quer mais detalhes? {pedido}: {detalhes}"]
    h.append(f"<p style='font:12px Arial;color:#666'>Ver no site: <a href='{SITE}'>{SITE}</a></p>{rodape[0]}")
    t += ["", f"Ver no site: {SITE}"] + ([rodape[1]] if rodape[1] else [])
    return "<div style='max-width:680px;margin:auto'>" + "".join(h) + "</div>", "\n".join(t)


def mensagem(assunto: str, destino: str, corpo_html: str, corpo_txt: str, extra: dict | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = assunto, os.environ["SMTP_USUARIO"], destino
    for k, v in (extra or {}).items():
        msg[k] = v
    msg.set_content(corpo_txt)
    msg.add_alternative(corpo_html, subtype="html")
    return msg


def smtp():
    s = smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "465")))
    s.login(os.environ["SMTP_USUARIO"], os.environ["SMTP_SENHA"])
    return s


def enviar(assunto: str, corpo_html: str, corpo_txt: str) -> None:
    with smtp() as s:
        s.send_message(mensagem(assunto, os.environ["EMAIL_PARA"], corpo_html, corpo_txt))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("antes", nargs="?", default="HEAD~1")
    p.add_argument("depois", nargs="?", default="HEAD")
    p.add_argument("--saida", default=".")
    p.add_argument("--enviar", action="store_true")
    a = p.parse_args()
    data = dia_do_commit(a.depois)
    titulo = f"Minha Bancada — o que mudou em {data[8:]}/{data[5:7]}/{data[:4]}"
    d = coletar(a.antes, a.depois, dia_da_coleta(a.depois))
    h, t = montar(d, titulo, detalhes=link_historico(data))
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "resumo.html").write_text(f"<!doctype html><meta charset=utf-8><title>{titulo}</title>{h}", encoding="utf-8")
    (saida / "resumo.txt").write_text(t, encoding="utf-8")
    print(t)
    if a.enviar:
        enviar(titulo, h, t)


if __name__ == "__main__":
    main()
