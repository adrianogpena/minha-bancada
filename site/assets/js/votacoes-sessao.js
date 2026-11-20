/* Votações de um dia, agrupadas por sessão, em cartões: tipo, título, resultado, barra com números,
   "O que isso significou", texto oficial e ações. Gancho `votacoesDoDia` de linhaDoTempoHtml. */
import { esc } from "./util.js";
import { VOTOS } from "./comum.js";
import { SENADO_API, CAMARA_API } from "./apis.js";
import { classificarVotacao, rotuloResultado, significado } from "./significado.js";
import { marcarTermos } from "./glossario.js";
import { semFonte } from "./ficha.js";

const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

export const ETIQUETAS = {
  "requerimento": "Requerimento", "texto-principal": "Texto principal", "destaque-emenda": "Destaque · emenda",
  "destaque-trecho": "Destaque · trecho do texto", "turno-suplementar": "Turno suplementar", "emenda": "Emenda",
  "redacao-final": "Redação final", "outro": "Votação",
};

const soma = (placar) => Object.values(placar || {}).reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0);
const temPlacar = (v) => v.nominal && v.placar && ["sim", "nao", "abstencao", "obstrucao", "secreto", "art17", "outro"].some((k) => v.placar[k] > 0);

/* Segmentos e legenda do placar: [chave, rótulo, n, cor]. Presidente junta art17 e outro. */
function partes(v, tipo) {
  const p = v.placar || {}, trecho = tipo === "destaque-trecho";
  const presidente = (p.art17 || 0) + (p.outro || 0), ausente = v.ausentes ?? p.ausente ?? 0;
  return [
    ["sim", trecho ? "Sim (manter)" : "Sim", p.sim || 0, VOTOS.sim.cor, true],
    ["nao", trecho ? "Não (retirar)" : "Não", p.nao || 0, VOTOS.nao.cor, true],
    ["abstencao", "Abstenção", p.abstencao || 0, VOTOS.abstencao.cor, true],
    ["obstrucao", "Obstrução", p.obstrucao || 0, VOTOS.obstrucao.cor, false],
    ["secreto", "Voto secreto", p.secreto || 0, VOTOS.secreto.cor, false],
    ["presidente", "Presidente", presidente, VOTOS.secreto.cor, false],
    ["ausente", "Não votaram", ausente, VOTOS.ausente.cor, false],
  ];
}

/* Barra com o número dentro do segmento quando ele tem 5% ou mais do total, e a legenda. */
export function barraComNumeros(placar, { destaqueTrecho = false, ausentes = 0 } = {}) {
  const v = { placar, ausentes };
  const itens = partes(v, destaqueTrecho ? "destaque-trecho" : "outro");
  const total = itens.reduce((a, i) => a + i[2], 0) || 1;
  const resumo = itens.filter((i) => i[2]).map((i) => `${i[1]} ${i[2]}`).join(", ");
  return `<div class="placar" role="img" aria-label="${esc(resumo)}">${itens.filter((i) => i[2]).map(([, r, n, cor]) =>
    `<i style="flex:${n};background:${cor}">${n / total >= 0.05 ? n : ""}</i>`).join("")}</div>
    <ul class="legenda">${itens.filter((i) => i[4] || i[2]).map(([, r, n, cor]) => `<li style="--c:${cor}">${esc(r)} ${n}</li>`).join("")}</ul>`;
}

const norm = (s) => String(s ?? "").replace(/[°º]/g, "º");

/* Informes do Senado cujo texto cita o número do requerimento ou da emenda. */
function informesDoTexto(t, dia) {
  return (t?.informes || []).filter((i) => !dia || String(i[0]).slice(0, 10) <= dia).map((i) => ({ quando: i[0], texto: norm(i[2]) }));
}

function contextoDe(v, tipo, dia, t) {
  const contexto = {}, extras = [];
  const informes = informesDoTexto(t, dia), desc = norm(v.descricao);
  if (tipo === "requerimento") {
    const num = desc.match(/Requerimento nº (\d+)/i)?.[1];
    const inf = num && informes.find((i) => new RegExp(`Requerimento nº ${num}\\b`, "i").test(i.texto));
    const assunto = inf?.texto.match(/\b(urgência|adiamento)\b/i)?.[1];
    if (assunto) contexto.assunto = assunto.toLowerCase();
  }
  if (tipo === "destaque-emenda" || tipo === "destaque-trecho") {
    let inf = null;
    if (tipo === "destaque-emenda") {
      const num = desc.match(/Emenda nº (\d+)/i)?.[1];
      if (num) {
        inf = informes.find((i) => /destaque/i.test(i.texto) && new RegExp(`Emenda nº ${num}\\b`).test(i.texto));
        const em = (t?.emendas || []).find((e) => String(e[0]) === num);
        const autor = em?.[1] && String(em[1]).replace(/^Senador(a)?\s+/i, "");
        if (autor) contexto.autor = autor;
      }
    } else {
      const art = desc.match(/Art\.\s*(\d+º?(?:-[A-Z])?)/i)?.[1];
      if (art) inf = informes.find((i) => /destaque/i.test(i.texto) && new RegExp(`art\\. ${art}(?![\\d-])`, "i").test(i.texto));
    }
    const rq = inf?.texto.match(/Requerimento nº (\d+)/i)?.[1];
    const quem = inf?.texto.match(/,\s*d[ao]s?\s+(.+?),\s*que solicita/i)?.[1];
    if (rq && quem) extras.push(`Votação separada pedida por ${esc(quem)} (RQS ${esc(rq)}).`);
  }
  return { contexto, extras };
}

function fonteDe(v, senado) {
  if (senado) return v.propId ? `<a class="fonte" href="${esc(`${SENADO_API}/votacao?codigoMateria=${encodeURIComponent(v.propId)}`)}" rel="noopener">Fonte: votação na API do Senado</a>` : semFonte();
  return v.id ? `<a class="fonte" href="${esc(`${CAMARA_API}/votacoes/${encodeURIComponent(v.id)}`)}" rel="noopener">Fonte: votação na API da Câmara</a>` : semFonte();
}

function cartao(v, { senado, t, dia }) {
  const { tipo, titulo } = classificarVotacao(v.descricao);
  const { contexto, extras } = contextoDe(v, tipo, dia, t);
  const comPlacar = temPlacar(v);
  const rotulo = comPlacar ? rotuloResultado({ tipo, aprovada: v.aprovada, placar: v.placar }) : "";
  const tit = marcarTermos(esc(contexto.autor && tipo === "destaque-emenda" ? `${titulo}, de ${contexto.autor}` : titulo || v.descricao || "Votação"));
  const sig = significado({ texto: v.descricao, aprovada: v.aprovada, tipo, contexto });
  const frase = [sig, ...extras].filter(Boolean).join(" ");
  const res = rotulo ? `<span class="resultado ${v.aprovada ? "ok" : "nok"}">${esc(rotulo)}</span>`
    : v.aprovada === 1 || v.aprovada === 0 ? `<span class="resultado ${v.aprovada ? "ok" : "nok"}">${v.aprovada ? "Aprovada" : "Rejeitada"}</span>` : "";
  return `<article class="voto-card">
    <span class="etiqueta">${esc(ETIQUETAS[tipo] || ETIQUETAS.outro)}</span>
    <h4>${tit}</h4>
    ${res}
    ${comPlacar ? barraComNumeros(v.placar, { destaqueTrecho: tipo === "destaque-trecho", ausentes: v.ausentes ?? v.placar.ausente ?? 0 })
      : `<p class="simbolica">Votação simbólica, sem placar individual.</p>`}
    ${frase ? `<p class="significado"><b>O que isso significou:</b> ${frase}</p>` : ""}
    ${v.orientacoes ? `<p class="oficial">Orientação das lideranças: ${Object.entries(v.orientacoes).map(([b, o]) => `${esc(b)} ${esc(o)}`).join(" · ")}.</p>` : ""}
    ${v.descricao ? `<p class="oficial">Texto oficial: “${esc(v.descricao)}”</p>` : ""}
    <div class="acoes">${v.nominal ? `<button type="button" class="mais" data-i="${v.i}">Ver quem votou</button>` : ""}${fonteDe(v, senado)}</div>
    ${v.nominal ? `<div id="votos-${v.i}"></div>` : ""}
  </article>`;
}

/* Sessões do dia: Senado por número + tipo da sessão (ordem pelo sequencial); Câmara por data + órgão. */
function sessoes(votacoes, senado) {
  const mapa = new Map();
  for (const v of votacoes) {
    const chave = senado ? `${v.sessao?.numero ?? ""}|${v.sessao?.tipo ?? ""}` : `${v.data ?? ""}|${v.orgao ?? ""}`;
    if (!mapa.has(chave)) mapa.set(chave, []);
    mapa.get(chave).push(v);
  }
  const seq = (v) => v.sessao?.sequencial ?? 0;
  return [...mapa.values()].map((l) => (senado ? [...l].sort((a, b) => seq(a) - seq(b)) : l));
}

export function votacoesDoDia(dia, { senado = false, t = null } = {}) {
  return sessoes(dia.votacoes || [], senado).map((lista) => `<div class="sessao-votos">
    <p>${plural(lista.length, "votação", "votações")} nesta sessão</p>
    ${lista.map((v) => cartao(v, { senado, t, dia: dia.dia })).join("")}
  </div>`).join("");
}
