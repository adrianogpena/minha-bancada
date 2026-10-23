/* Fonte: qualquer JSON de API pública em forma legível. */
import { $, esc, data, param } from "./util.js";
import { HOST_API, urlLegivel } from "./apis.js";

/* ---------- fonte: qualquer JSON de API pública, em forma legível ---------- */
const ROTULOS_FONTE = { uri: "Endereço (API)", id: "Código", nome: "Nome", sigla: "Sigla", siglaPartido: "Partido", siglaUf: "UF", data: "Data", dataHoraRegistro: "Registrado em", descricao: "Descrição", ementa: "Ementa", aprovacao: "Aprovada", codigo: "Código", urlFoto: "Foto" };
const rotuloFonte = (k) => ROTULOS_FONTE[k] || k.replace(/([a-z0-9])([A-Z])/g, "$1 $2").replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const ehData = (s) => /^\d{4}-\d{2}-\d{2}(T[\d:.]+Z?)?$/.test(s);

function valorFonte(v) {
  if (v == null || v === "") return `<span class="quando">—</span>`;
  if (typeof v === "boolean") return v ? "Sim" : "Não";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : esc(v.toLocaleString("pt-BR")); // anos e códigos não levam separador
  if (typeof v === "string") {
    if (/^https?:\/\/\S+$/.test(v)) {
      const l = urlLegivel(v);
      return /\.(jpe?g|png|gif)$/i.test(v) ? `<a href="${esc(v)}" rel="noopener">imagem</a>`
        : `<a href="${esc(v)}" rel="noopener">${esc(v.replace(/^https?:\/\/(www\.)?/, ""))}</a>${l ? ` <a class="ver-legivel" href="${esc(l)}">ver legível</a>` : ""}`;
    }
    if (ehData(v)) return esc(data(v)) + (v.length > 10 ? `<span class="quando">, ${esc(v.slice(11, 16))}</span>` : "");
    return esc(v);
  }
  if (Array.isArray(v)) return tabelaFonte(v);
  return fichaFonte(v);
}

function fichaFonte(o) {
  const chaves = Object.keys(o);
  return chaves.length ? `<dl class="ficha">${chaves.map((k) => `<dt>${esc(rotuloFonte(k))}</dt><dd>${valorFonte(o[k])}</dd>`).join("")}</dl>` : `<span class="quando">—</span>`;
}

function tabelaFonte(lista) {
  if (!lista.length) return `<span class="quando">(vazio)</span>`;
  if (lista.some((x) => x == null || typeof x !== "object")) return lista.map((x) => valorFonte(x)).join("<br>");
  const cols = [...new Set(lista.flatMap((x) => Object.keys(x)))];
  const simples = cols.filter((c) => lista.every((x) => x[c] == null || typeof x[c] !== "object"));
  // objetos com muitos campos ou colunas aninhadas ficam melhor como fichas empilhadas
  if (cols.length > 8 || simples.length < cols.length) {
    return lista.map((x, i) => `<details${lista.length === 1 ? " open" : ""}><summary>Item ${i + 1}${x.nome || x.id ? `: ${esc(x.nome || x.id)}` : ""}</summary>${fichaFonte(x)}</details>`).join("");
  }
  return `<div class="rolagem"><table class="tabela tabela-fonte"><thead><tr>${cols.map((c) => `<th>${esc(rotuloFonte(c))}</th>`).join("")}</tr></thead><tbody>${
    lista.map((x) => `<tr>${cols.map((c) => `<td>${valorFonte(x[c])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

export async function paginaFonte() {
  const alvo = $("#conteudo");
  const bruto = param("u");
  const aviso = (t) => (alvo.innerHTML = `<p class="aviso">${esc(t)}</p>`);
  let u;
  try { u = new URL(bruto); } catch { return aviso("Endereço inválido."); }
  // só abre APIs públicas de órgãos do governo, e só leitura
  if (u.protocol !== "https:" || !HOST_API.test(u.hostname) || !urlLegivel(bruto)) return aviso("Esta página só mostra dados de APIs públicas de órgãos do governo (.leg.br, .gov.br, .jus.br).");
  document.title = `Dados de ${u.hostname} | Minha Bancada`;
  alvo.innerHTML = `<p class="vazio">Carregando…</p>`;
  let j;
  try {
    const r = await fetch(u, { headers: { Accept: "application/json" } });
    if (!r.ok) throw new Error(`A fonte respondeu ${r.status}`);
    j = await r.json();
  } catch (e) {
    return alvo.innerHTML = `<p class="aviso">Não foi possível ler ${esc(u.hostname)}: ${esc(e.message)}. A fonte pode estar fora do ar, ou não devolver JSON.
      <a href="${esc(bruto)}" rel="noopener">Abrir direto na fonte</a>.</p>`;
  }
  const links = Array.isArray(j?.links) ? j.links : [];
  const rel = (n) => links.find((l) => l.rel === n)?.href;
  const conteudo = j && typeof j === "object" && "dados" in j ? j.dados : j;
  const nav = ["previous", "next"].map((n) => [n, rel(n)]).filter(([, h]) => h && urlLegivel(h))
    .map(([n, h]) => `<a class="mais" href="${esc(urlLegivel(h))}">${n === "next" ? "Próxima página" : "Página anterior"}</a>`).join(" ");
  alvo.innerHTML = `
    <section class="abertura">
      <p>Dados de ${esc(u.hostname)}</p>
      <h1 style="max-width:none;font-size:clamp(24px,4vw,36px)">${esc(decodeURIComponent(u.pathname).replace(/^\/(api\/v\d+|dadosabertos)\//, "").replace(/\/$/, "") || "Dados")}</h1>
      <p class="texto-longo">Versão legível do que a fonte oficial devolve. Nada aqui é alterado pelo site.
        <a href="${esc(bruto)}" rel="noopener">Ver o JSON original</a>.</p>
    </section>
    <section class="painel">${typeof conteudo === "object" && conteudo !== null ? valorFonte(conteudo) : esc(String(conteudo))}${nav ? `<p>${nav}</p>` : ""}</section>`;
}
