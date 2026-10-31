/* Ministros dos tribunais superiores (dados/tribunais.json; scripts/coletar_tribunais.py, coletar_relatorias.py e gerar_tribunais.py). */
import { $, esc, data, carregar, numeroBr, urlSegura } from "./util.js";
import { erro } from "./comum.js";
import { fontes, linkParlamentar } from "./apis.js";

const WIKI = "https://pt.wikipedia.org/wiki/";

export function quandoPosse(m) {
  if (m.posse) return data(m.posse, true);
  return m.posseTexto ? esc(m.posseTexto) : "—";
}

/* "2026: 1.234 · 2025: 890" a partir de {ano: n}; vazio quando não há contagem. */
export function textoRelatorias(r) {
  const anos = Object.keys(r || {}).sort().reverse();
  return anos.map((a) => `${esc(a)}: <b>${numeroBr(r[a])}</b>`).join(" · ");
}

function recentes(lista) {
  if (!lista || !lista.length) return "";
  const itens = lista.map((x) => {
    const rotulo = `${esc(x.tipo)} ${esc(x.numero)}/${esc(x.ano)}${x.colegiado ? ` (${esc(x.colegiado)})` : ""}, sessão de ${esc(data(x.data, true))}`;
    return `<li>${urlSegura(x.url) ? `<a href="${esc(x.url)}" rel="noopener">${rotulo}</a>` : rotulo}</li>`;
  }).join("");
  return `<details><summary>Últimos acórdãos relatados</summary><ul class="lista-simples">${itens}</ul></details>`;
}

function celulaNome(m) {
  const wiki = m.wiki ? ` <a class="ver-legivel" href="${esc(WIKI + encodeURI(m.wiki))}" rel="noopener">Wikipédia</a>` : "";
  const ficha = m.parlamentar ? ` <a class="ver-legivel" href="${esc(linkParlamentar(m.parlamentar.casa, m.parlamentar.id))}">ficha de parlamentar</a>` : "";
  return `${esc(m.nome)}${m.categoria ? `<br><span class="quando">${esc(m.categoria)}</span>` : ""}${wiki}${ficha}`;
}

function linhaMinistro(m, comRelatorias) {
  const conf = comRelatorias ? (m.confirmado ? `<span class="resultado r-aprovada">Relatou no ano</span>` : `<span class="resultado r-sem">Sem relatoria recente</span>`) : "";
  return `<tr><td>${celulaNome(m)}</td><td>${quandoPosse(m)}</td><td>${esc(m.nomeadoPor || "—")}</td><td>${esc(m.vaga || "—")}</td>
    ${comRelatorias ? `<td>${textoRelatorias(m.relatorias) || "—"} ${conf}${recentes(m.recentes)}</td>` : ""}</tr>`;
}

function outros(t) {
  if (!t.outrosRelatores || !t.outrosRelatores.length) return "";
  const itens = t.outrosRelatores.map((o) => `<li>${esc(o.nome)}<br><span class="quando">Relatorias: ${textoRelatorias(o.relatorias)}</span>${recentes(o.recentes)}</li>`).join("");
  return `<h3>Outros relatores</h3>
    <p class="nota-lista">Quem relatou acórdãos desde 2023 e não está na lista acima: ministros-substitutos, juízes convocados e ministros que já saíram.
      Ficam aqui porque a fonte oficial publica só o nome do relator, sem o cargo.</p>
    <ul class="lista-simples">${itens}</ul>`;
}

function blocoTribunal(t) {
  const comRelatorias = !!t.relatorias;
  const grupos = [...new Set(t.ministros.map((m) => m.categoria || ""))];
  const cabecalho = `<tr><th>Ministro</th><th>Posse</th><th>Nomeado por</th><th>Vaga</th>${comRelatorias ? "<th>Relatorias (acórdãos)</th>" : ""}</tr>`;
  const tabela = (lista) => `<div class="rolagem"><table class="tabela"><thead>${cabecalho}</thead>
    <tbody>${lista.map((m) => linhaMinistro(m, comRelatorias)).join("")}</tbody></table></div>`;
  const corpo = grupos.length > 1
    ? grupos.map((g) => `<h3>${esc(g || "Ministros")}</h3>${tabela(t.ministros.filter((m) => (m.categoria || "") === g).map((m) => ({ ...m, categoria: "" })))}`).join("")
    : tabela(t.ministros);
  const saidas = t.saidas.length
    ? `<p class="nota-lista">Saíram da tabela desde que a coleta começou: ${t.saidas.map((s) => `${esc(s.nome)} (até ${esc(data(s.vistoAte, true))})`).join(", ")}.</p>` : "";
  const oficial = comRelatorias ? [[t.relatorias.rotulo, t.relatorias.url]] : [];
  return `<section id="${esc(t.sigla)}"><h2>${esc(t.sigla)} · ${esc(t.nome)}</h2>
    <p class="contagem">${t.ministros.length} ministros${comRelatorias && t.relatorias.ate ? ` · relatorias até a sessão de ${esc(data(t.relatorias.ate, true))}` : ""}</p>${corpo}${saidas}${outros(t)}
    ${fontes([[`Composição do ${t.sigla} (site oficial)`, t.fonte], ["Tabela da Wikipédia usada na coleta", t.wikipedia], ...oficial])}</section>`;
}

export async function paginaTribunais() {
  const alvo = $("#conteudo");
  let lista;
  try { lista = await carregar("dados/tribunais.json"); } catch (e) { return erro(alvo, e); }
  alvo.innerHTML = `
    <section class="abertura"><h1>Tribunais superiores</h1>
      <p>Os ministros em exercício do STF, STJ, TST, TSE, STM e TCU. O TSE inclui os substitutos. No TCU e no STJ, a fonte oficial de acórdãos confere a lista e conta quanto cada ministro relata.</p></section>
    <p class="nota-lista">Os sites dos tribunais bloqueiam a coleta automática. A lista, a posse e quem nomeou vêm da tabela "Composição atual" da Wikipédia de cada tribunal, lida todo dia;
      confira no site oficial, linkado em cada tribunal. Onde há fonte oficial (relatorias do TCU e do STJ), ela aparece ao lado.
      Votos em julgamentos do STF, TST, TSE e STM, decisões monocráticas e pedidos de vista ainda não estão no site: essas fontes não respondem à coleta.</p>
    ${lista.map(blocoTribunal).join("")}`;
}
