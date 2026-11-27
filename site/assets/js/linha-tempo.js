/* Linha do tempo única da ficha de uma proposição: informes, situações, despachos, relatorias, emendas e documentos (Senado) ou
   movimentações (Câmara) e as votações, agrupados por dia, com os marcos à vista e a rotina atrás de "Tudo". */
import { esc, urlSegura } from "./util.js";
import { SENADO_API, CAMARA_API, fontes, linkParlamentar, linkTramitacao } from "./apis.js";
import { barraPlacar } from "./votacoes.js";
import { marcarTermos } from "./glossario.js";

const DOC_SENADO = "https://legis.senado.leg.br/sdleg-getter/dadosabertos/documento/";
export const docSenado = (x) => (!x ? null : x.startsWith("http") ? x : DOC_SENADO + x);   // o coletor guarda só o código do documento
export const DOC_PRINCIPAL = /^(Projeto|Parecer|Relatório Legislativo|Texto|Substitutivo|Autógrafo)/i;

export const TIPOS_SESSAO = {
  DOR: "Sessão Deliberativa Ordinária", DEX: "Sessão Deliberativa Extraordinária", NDO: "Sessão Não Deliberativa Ordinária",
  NDE: "Sessão Não Deliberativa Extraordinária", SOL: "Sessão Solene", ESP: "Sessão Especial", CON: "Sessão Conjunta", PRE: "Sessão Preparatória",
};
const COLEGIADOS = { PLEN: "Plenário do Senado" };
const DIAS_SEMANA = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"];
const EMENDAS_EM_MARCO = 10;   // dia com tantas emendas ou mais: o prazo de emendas é um marco, não rotina

/* Primeira regra que casa vence. `quando` vê o texto sem acento e em minúsculas; `origem` (opcional) limita a regra a um tipo de fato.
   Marco: apresentação, despacho, relator, parecer, urgência, pauta, votação, aprovação/rejeição, remessa, norma, arquivamento.
   Rotina: emenda ou requerimento recebido, listagem, avulso, publicação, juntada. Sem regra: rotina. */
export const REGRAS_EVENTO = [
  { origem: "despacho", quando: /^/, marco: true, etiqueta: "Despacho" },
  { origem: "relatoria", quando: /^/, marco: true, etiqueta: "Relator" },
  { origem: "relatoria-fim", quando: /^/, marco: false, etiqueta: "Relatoria" },
  { origem: "apresentacao", quando: /^/, marco: true, etiqueta: "Apresentado" },
  { origem: "emendas", quando: /^/, marco: false, etiqueta: "Emendas" },
  { origem: "situacao", quando: /aprovad|rejeitad/, marco: true, etiqueta: "Resultado" },
  { origem: "situacao", quando: /arquivad|transformad|sancionad|vetad|promulgad/, marco: true, etiqueta: "Situação" },
  { origem: "situacao", quando: /^/, marco: false, etiqueta: "Situação" },
  { quando: /^\(sessao/, marco: true, etiqueta: "Sessão" },
  { quando: /urgencia/, marco: true, etiqueta: "Urgência" },
  { quando: /^recebid[oa]s? (?:(?:o|a|os|as|novo) )?(?:requerimento|emenda|oficio)/, marco: false, etiqueta: "Requerimento" },
  { quando: /encaminhando autografo|remetid[oa] (?:o )?(?:oficio|autografo)|remetid[oa] a camara|remessa/, marco: true, etiqueta: "Remessa" },
  { quando: /ordem do dia|\bpauta\b/, marco: true, etiqueta: "Pauta" },
  { quando: /designad[oa] relator|relator designad/, marco: true, etiqueta: "Relator" },
  { quando: /parecer/, marco: true, etiqueta: "Parecer" },
  { quando: /relatorio/, marco: true, etiqueta: "Relatório" },
  { quando: /sancionad|vetad|promulgad|transformad[oa] em (?:norma|lei)|norma juridica/, marco: true, etiqueta: "Norma" },
  { quando: /arquivad/, marco: true, etiqueta: "Arquivado" },
  { quando: /despacho|distribuic|distribuid/, marco: true, etiqueta: "Despacho" },
  { origem: "camara", quando: /votacao/, marco: true, etiqueta: "Votação" },
  { quando: /\b(?:aprovad[oa]|rejeitad[oa])\b/, marco: true, etiqueta: "Resultado" },
  { quando: /apresentacao d[eao]|apresentad[oa]/, marco: true, etiqueta: "Apresentado" },
];

const simples = (s) => String(s ?? "").normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
export function classificarEvento(origem, texto) {
  const t = simples(texto).trim();
  const r = REGRAS_EVENTO.find((x) => (!x.origem || x.origem === origem) && x.quando.test(t));
  return r ? { marco: r.marco, etiqueta: r.etiqueta } : { marco: false, etiqueta: "" };
}

const diaIso = (q) => String(q || "").slice(0, 10);
const quandoIso = (q) => String(q || "").replace("T", " ").slice(0, 16);
const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

export function tituloDoDia(dia) {
  if (!dia) return "Sem data";
  const [a, m, d] = dia.split("-");
  const semana = DIAS_SEMANA[new Date(`${dia}T12:00:00Z`).getUTCDay()];
  return `${semana}, ${d}/${m}/${a}`;
}

/* Emendas do mesmo dia numa linha só: sem id do autor na fonte, o nome vai como veio (sem link). */
function linhaDeEmendas(dia, emendas) {
  const porAutor = new Map();
  for (const e of emendas) { const a = e[1] || "sem autoria"; porAutor.set(a, (porAutor.get(a) || 0) + 1); }
  const nums = emendas.map((e) => parseInt(e[0], 10)).filter(Number.isFinite);
  const faixa = nums.length > 1 ? ` (nº ${Math.min(...nums)} a ${Math.max(...nums)})` : nums.length ? ` (nº ${nums[0]})` : "";
  const autores = [...porAutor.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "pt-BR"));
  const quem = autores.length === 1 && autores[0][0] === "sem autoria" ? "Emendas sem autoria informada" : `${plural(autores.length, "senador apresenta", "senadores apresentam")} ${plural(emendas.length, "emenda", "emendas")}${faixa}`;
  return {
    quando: dia, origem: "emendas", marco: emendas.length >= EMENDAS_EM_MARCO, etiqueta: "Emendas", docs: [],
    html: `${esc(quem)}.<details class="detalhes"><summary>Quem apresentou</summary><ul>${autores.map(([a, n]) => `<li>${esc(a)}: ${n}</li>`).join("")}</ul></details>`,
  };
}

const ehEmendaRecebida = (desc) => /^recebid[oa]s? (?:(?:o|a|os|as) )?emendas?\b/.test(simples(desc).trim());

function eventosDoSenado(t, f, autores) {
  const ev = [];
  const informes = t.informes || [], relatorias = t.relatorias || [], emendas = t.emendas || [];
  const diasComEmenda = new Set(emendas.map((e) => e[2]).filter(Boolean));
  const diasDeRelator = new Set(relatorias.map((r) => r[7]).filter(Boolean));
  const comEtiqueta = (origem, quando, texto, html) => ({ quando, origem, ...classificarEvento(origem, texto), html, docs: [] });

  if (f?.ap) ev.push({ quando: f.ap, origem: "apresentacao", ...classificarEvento("apresentacao", ""), docs: [],
    html: autores?.html ? `${autores.html} ${autores.n > 1 ? "apresentam" : "apresenta"} o projeto.` : "O projeto é apresentado." });
  for (const [quando, , desc] of informes) {
    const dia = diaIso(quando);
    if (ehEmendaRecebida(desc) && diasComEmenda.has(dia)) continue;
    if (/^designad[oa] relator/.test(simples(desc)) && diasDeRelator.has(dia)) continue;
    ev.push(comEtiqueta("informe", quandoIso(quando), desc, esc(desc || "")));
  }
  for (const [ini, , , desc] of t.situacoes || []) {
    if (desc) ev.push(comEtiqueta("situacao", ini, desc, `Situação: ${esc(desc.toLowerCase())}.`));
  }
  for (const [dia, prov, destinos, terminativa] of t.despachos || []) {
    ev.push(comEtiqueta("despacho", dia, prov || "", `${esc(prov || "Despacho")}${(destinos || []).length ? ` (${esc(destinos.join(", "))})` : ""}${terminativa ? ", em caráter terminativo" : ""}.`));
  }
  for (const [cod, nome, pt, uf, sigla, colegiado, tipo, desde, ate, fim] of relatorias) {
    const quem = cod ? `<a href="${esc(linkParlamentar("senado", cod))}">${esc(nome)}</a>` : esc(nome);
    const sg = [pt, uf].filter(Boolean).join("/");
    if (desde) ev.push(comEtiqueta("relatoria", desde, "", `${quem}${sg ? ` (${esc(sg)})` : ""}, ${esc((tipo || "relator").toLowerCase())} em ${esc(colegiado || COLEGIADOS[sigla] || sigla || "")}.`));
    if (ate) ev.push(comEtiqueta("relatoria-fim", ate, "", `Fim da relatoria de ${esc(nome)}${fim ? `: ${esc(fim.toLowerCase())}` : ""}.`));
  }
  const porDia = new Map();
  for (const e of emendas) if (e[2]) (porDia.get(e[2]) || porDia.set(e[2], []).get(e[2])).push(e);
  for (const [dia, lista] of porDia) ev.push(linhaDeEmendas(dia, lista));
  return ev;
}

function eventosDaCamara(t) {
  return (t.eventos || []).map(([dia, orgao, tipo, , despacho]) => {
    const texto = `${tipo || "Movimentação"}${despacho ? `: ${despacho}` : ""}`;
    return { quando: quandoIso(dia), origem: "camara", ...classificarEvento("camara", `${tipo || ""} ${despacho || ""}`),
      html: `${esc(texto)}${orgao ? ` <span class="quando">(${esc(orgao)})</span>` : ""}`, docs: [], orgao };
  });
}

/* Documentos do dia: os principais viram link no marco do dia que mais combina; o resto, numa linha de rotina. */
function distribuirDocumentos(dias, documentos) {
  const alvo = (tipo) => (/^(Projeto|Proposta|Medida)/i.test(tipo) ? "Apresentado" : /^Relat/i.test(tipo) ? "Relat" : /^Parecer/i.test(tipo) ? "Parecer" : "");
  const porDia = new Map();
  for (const d of documentos) (porDia.get(d[0] || "") || porDia.set(d[0] || "", []).get(d[0] || "")).push(d);
  for (const [dia, lista] of porDia) {
    const d = dias.get(dia) || dias.set(dia, novoDia(dia)).get(dia);
    const resto = [];
    for (const doc of lista) {
      const href = docSenado(doc[4]);
      if (!href || !urlSegura(href)) continue;
      const link = { rotulo: `${doc[1] || "Documento"}${doc[2] && doc[2] !== doc[1] ? ` (${doc[2]})` : ""}`, href };
      const dest = DOC_PRINCIPAL.test(doc[1] || "") ? (d.eventos.find((e) => e.marco && alvo(doc[1]) && e.etiqueta.startsWith(alvo(doc[1]))) || d.eventos.find((e) => e.marco)) : null;
      if (dest) dest.docs.push(link); else resto.push(link);
    }
    if (resto.length) d.eventos.push({ quando: `${dia} 23:59`, origem: "documentos", marco: false, etiqueta: "Documentos", docs: [],
      html: `<details class="detalhes"><summary>${plural(resto.length, "documento", "documentos")}</summary><ul>${resto.map((l) => `<li><a href="${esc(l.href)}" rel="noopener">${esc(l.rotulo)}</a></li>`).join("")}</ul></details>` });
  }
}

const novoDia = (dia) => ({ dia, sessao: "", marco: false, eventos: [], votacoes: [] });

function sessaoDoDia(d, informes) {
  const sessoes = [];
  for (const v of d.votacoes) {
    const s = v.sessao;
    const nome = s ? `${TIPOS_SESSAO[s.tipo] || "Sessão"}${s.numero ? ` nº ${s.numero}` : ""}` : "";
    if (nome && !sessoes.includes(nome)) sessoes.push(nome);
  }
  if (sessoes.length) return sessoes.join(" · ");
  for (const [quando, , desc] of informes) {
    if (diaIso(quando) !== d.dia) continue;
    const m = /^\((Sess[ãa]o [^()]*?)(?:\s+-\s+|\s+de \d+ de \S+ de \d{4}|\))/.exec(desc || "");
    if (m) return m[1];
  }
  return "";
}

/* O modelo da linha do tempo. `votacoes`: a lista da ficha (cada uma com `data`, `hora?`, `sessao?`...), na ordem original, cujo índice vira `i`.
   `autores`: {html, n} dos autores já formatados pela ficha (só para o evento de apresentação no Senado). */
export function montarLinhaDoTempo({ senado, t, votacoes = [], f = {}, p = {}, autores = null }) {
  const dias = new Map();
  const dia = (k) => dias.get(k) || dias.set(k, novoDia(k)).get(k);
  const eventos = t ? (senado ? eventosDoSenado(t, f, autores) : eventosDaCamara(t)) : [];
  eventos.forEach((e, n) => { e.n = n; dia(diaIso(e.quando)).eventos.push(e); });
  if (t && senado) distribuirDocumentos(dias, t.documentos || []);
  votacoes.forEach((v, i) => dia(diaIso(v.data)).votacoes.push({ ...v, i }));

  const lista = [...dias.values()].sort((a, b) => (a.dia && b.dia ? a.dia.localeCompare(b.dia) : a.dia ? -1 : b.dia ? 1 : 0));
  for (const d of lista) {
    d.eventos.sort((a, b) => (a.quando < b.quando ? -1 : a.quando > b.quando ? 1 : (a.n ?? 0) - (b.n ?? 0)));
    d.votacoes.sort((a, b) => (a.sessao?.sequencial ?? 0) - (b.sessao?.sequencial ?? 0) || String(a.hora || "").localeCompare(String(b.hora || "")) || a.i - b.i);
    d.marco = d.votacoes.length > 0 || d.eventos.some((e) => e.marco);
    d.sessao = senado ? sessaoDoDia(d, t?.informes || []) : [...new Set(d.eventos.map((e) => e.orgao).filter(Boolean))].join(", ");
    if (senado && !d.sessao && d.marco && d.eventos.length) {
      const col = [...new Set((t?.informes || []).filter((i) => diaIso(i[0]) === d.dia).map((i) => i[1]).filter(Boolean))];
      if (col.length === 1) d.sessao = COLEGIADOS[col[0]] || col[0];
    }
    const htmls = marcarTermos(d.eventos.map((e) => e.html).join("\u0001")).split("\u0001");
    d.eventos.forEach((e, i) => { e.html = htmls[i] ?? e.html; });
  }

  const id = String(p.k || "").slice(2) || "";
  const rotulo = p.t ? `${p.t} ${p.n}/${p.a}` : "";
  let outraCasa = null;
  if (senado && (f.cn || f.cd || f.cdx)) outraCasa = { nome: "Câmara dos Deputados", rotulo: f.cn || "", href: f.cd ? `proposicao.html?k=c-${encodeURIComponent(f.cd)}` : f.cdx ? linkTramitacao(f.cdx) : null };
  else if (!senado && f.sf) outraCasa = { nome: "Senado Federal", rotulo, href: `proposicao.html?k=s-${encodeURIComponent(f.sf)}` };

  const api = `${SENADO_API}/processo`;
  const enc = encodeURIComponent(id);
  const origens = senado
    ? [["Matéria (informes, situações, despachos, documentos)", t?.processo ? `${api}/${encodeURIComponent(t.processo)}` : null], ["Relatoria", `${api}/relatoria?codigoMateria=${enc}`],
       ["Emendas", `${api}/emenda?codigoMateria=${enc}`], ["Votações", `${SENADO_API}/votacao?codigoMateria=${enc}`]]
    : [["Tramitações (API da Câmara)", t ? `${CAMARA_API}/proposicoes/${enc}/tramitacoes` : null]];
  return { dias: lista, total: senado ? (t?.informes || []).length : (t?.eventos || []).length, outraCasa, fontes: origens };
}

/* Votações do dia, uma por linha (a g7 troca por cartões). O botão "Ver quem votou" é tratado por paginaProposicao. */
export function votacoesPadrao(dia) {
  return `<div class="sessao-votos"><p>${plural(dia.votacoes.length, "votação", "votações")} neste dia</p><ul class="itens">${dia.votacoes.map((v) => `<li>
      <span class="quando">${v.hora ? `${esc(v.hora)}` : ""}${v.orgao ? `${v.hora ? " · " : ""}${esc(v.orgao)}` : ""}${v.aprovada === 1 ? `${v.hora || v.orgao ? ", " : ""}aprovada` : v.aprovada === 0 ? `${v.hora || v.orgao ? ", " : ""}rejeitada` : ""}</span>
      <span class="texto">${esc(v.descricao || "Votação")}${v.nominal ? barraPlacar(v.placar) : `<span class="quando">Votação simbólica ou em comissão: sem voto individual.</span>`}
        ${v.orientacoes ? `<br><span class="quando">Orientação das lideranças: ${Object.entries(v.orientacoes).map(([b, o]) => `${esc(b)} ${esc(o)}`).join(" · ")}.</span>` : ""}</span>
      ${v.nominal ? `<button type="button" class="mais" data-i="${v.i}">Ver quem votou</button><div id="votos-${v.i}"></div>` : ""}</li>`).join("")}</ul></div>`;
}

function eventoHtml(e) {
  const docs = e.docs.length ? ` ${e.docs.map((l) => `<a href="${esc(l.href)}" rel="noopener">${esc(l.rotulo)}</a>`).join(" · ")}` : "";
  return `<li${e.marco ? "" : ` class="rotina"`}>${e.etiqueta ? `<span class="etiqueta">${esc(e.etiqueta)}</span>` : ""}${e.html}${docs}</li>`;
}

function diaHtml(d, votacoesDoDia) {
  const rotina = d.eventos.filter((e) => !e.marco).length;
  const cls = `dia${d.marco ? " marco-dia" : " so-rotina"}`;
  return `<li class="${cls}"${d.dia ? ` data-dia="${esc(d.dia)}"` : ""}>
    <h3>${esc(tituloDoDia(d.dia))}</h3>
    ${d.sessao ? `<p class="sessao">${esc(d.sessao)}</p>` : ""}
    ${d.eventos.length ? `<ul class="eventos">${d.eventos.map(eventoHtml).join("")}</ul>` : ""}
    ${d.votacoes.length ? votacoesDoDia(d) : ""}
    ${rotina ? `<p class="recolhidos">+ ${plural(rotina, "evento", "eventos")} de rotina (mostrar com “Tudo”)</p>` : ""}
  </li>`;
}

export function linhaDoTempoHtml(modelo, { votacoesDoDia = votacoesPadrao } = {}) {
  const futuro = modelo.outraCasa ? `<li class="dia futuro">
    <h3>${modelo.outraCasa.href ? `<a href="${esc(modelo.outraCasa.href)}">${esc(modelo.outraCasa.nome)}</a>` : esc(modelo.outraCasa.nome)}</h3>
    <p class="sessao">${esc([modelo.outraCasa.rotulo, "em tramitação"].filter(Boolean).join(" · "))}</p></li>` : "";
  return `<div class="linha-tempo so-marcos">
    <div class="controles">
      <div class="segmentado" role="group" aria-label="O que mostrar">
        <button type="button" data-filtro="marcos" aria-pressed="true">Só os marcos</button>
        <button type="button" data-filtro="tudo" aria-pressed="false">Tudo (${modelo.total} movimentações)</button>
      </div>
      <button type="button" class="botao" data-inverter aria-pressed="false">↑↓ Mais recente primeiro</button>
    </div>
    <ol class="tempo">${modelo.dias.map((d) => diaHtml(d, votacoesDoDia)).join("")}${futuro}</ol>
    ${fontes(modelo.fontes || [])}
  </div>`;
}

/* Liga os filtros ("Só os marcos" / "Tudo") e a inversão; o filtro é uma classe do contêiner da linha do tempo. */
export function ligarLinhaDoTempo(raiz = document) {
  const caixa = raiz.querySelector(".linha-tempo");
  if (!caixa) return;
  const filtros = caixa.querySelectorAll("[data-filtro]");
  for (const b of filtros) {
    b.addEventListener("click", () => {
      caixa.classList.toggle("so-marcos", b.dataset.filtro === "marcos");
      for (const o of filtros) o.setAttribute("aria-pressed", String(o === b));
    });
  }
  const inverter = caixa.querySelector("[data-inverter]"), lista = caixa.querySelector(".tempo");
  if (inverter) inverter.addEventListener("click", () => {
    const on = !lista.classList.contains("invertido");
    lista.classList.toggle("invertido", on);
    inverter.setAttribute("aria-pressed", String(on));
  });
}
