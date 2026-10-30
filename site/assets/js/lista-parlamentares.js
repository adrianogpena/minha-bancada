/* Lista de parlamentares de uma Casa (Câmara, Senado): filtros, ordenação e endereço compartilhável. Cada Casa declara só as colunas e os ordenadores. */
import { $, esc, reais, semAcento, carregar } from "./util.js";
import { foto, erro } from "./comum.js";

/* Aplica busca, UF e partido e ordena; `ordenadores[ordem]` é um comparador. */
export function filtrarLista(itens, { busca = "", uf = "", partido = "", ordem = "nome" }, ordenadores) {
  const b = semAcento(busca.trim());
  return itens
    .filter((d) => (!uf || d.uf === uf) && (!partido || d.partido === partido) && (!b || semAcento(d.nome).includes(b)))
    .sort(ordenadores[ordem] || ordenadores.nome);
}

/* Endereço com só os filtros que fogem do padrão. */
export function consultaDaLista({ busca = "", uf = "", partido = "", ordem = "nome" }) {
  const q = new URLSearchParams();
  if (busca.trim()) q.set("busca", busca.trim());
  if (uf) q.set("uf", uf);
  if (partido) q.set("partido", partido);
  if (ordem !== "nome") q.set("ordem", ordem);
  return q.toString();
}

/* Média de `valor(d)` (número ou null) por grupo (`chave`: "partido" ou "uf"), só com quem tem valor. */
export function mediasPor(itens, chave, valor) {
  const soma = new Map();
  for (const d of itens) {
    const v = valor(d);
    if (v == null || !d[chave]) continue;
    const g = soma.get(d[chave]) || { t: 0, n: 0 };
    g.t += v; g.n += 1; soma.set(d[chave], g);
  }
  return (d) => { const g = soma.get(d[chave]); return g ? { media: g.t / g.n, n: g.n } : null; };
}

/* Dica de comparação: como o valor do item se situa na média do partido e na da bancada do estado. */
export function dicaComparativa(d, partido, estado, fmt) {
  const p = partido(d), u = estado(d);
  return [p && `média do partido (${p.n}): ${fmt(p.media)}`, u && `média da bancada de ${d.uf} (${u.n}): ${fmt(u.media)}`].filter(Boolean).join("; ");
}

/* Célula de métrica: valor em destaque e legenda embaixo. `titulo` vira dica ao passar o mouse. */
export const metrica = (valor, legenda, { largo = false, titulo = "" } = {}) =>
  `<span class="metrica${largo ? " so-largo" : ""}"${titulo ? ` title="${esc(titulo)}"` : ""}><b>${valor}</b><span>${legenda}</span></span>`;

export const celulaEmendas = (d) => metrica(d.empenhado ? reais(d.empenhado) : "—", d.empenhado ? `${reais(d.pago || 0)} pagos` : "sem emendas ligadas", { largo: true, titulo: "Emendas ao orçamento federal ligadas pelo nome ao autor, somando os anos coletados: valor empenhado e valor já pago" });

/* HTML da célula de uma coluna; a que corresponde à ordenação escolhida (`ordens` da coluna) leva a classe `ativa`, que o celular usa para mostrá-la. */
export function celulaDaColuna(c, d, dica, ordem) {
  const html = c.celula(d, dica);
  return c.ordens?.includes(ordem) ? html.replace('class="metrica', 'class="metrica ativa') : html;
}

/*
 config: { arquivo, singular, plural, href(d), sub(d) (texto pequeno depois do nome), 
           colunas: [{ rotulo, largo, ordens (opções de ordenação que ela explica), celula(d, dica), valor(d) e formato(n) (opcionais: dica com a média do partido e do estado) }], ordenadores }
 A primeira coluna fica visível no celular; as demais só em tela larga (`largo`).
*/
export async function listaParlamentares(config) {
  const alvo = $("#resultado");
  let itens;
  try { itens = await carregar(config.arquivo); } catch (e) { return erro(alvo, e); }

  const opcoes = (campo) => [...new Set(itens.map((d) => d[campo]).filter(Boolean))].sort();
  $("#uf").insertAdjacentHTML("beforeend", opcoes("uf").map((u) => `<option>${esc(u)}</option>`).join(""));
  $("#partido").insertAdjacentHTML("beforeend", opcoes("partido").map((p) => `<option>${esc(p)}</option>`).join(""));

  const q = new URLSearchParams(location.search);
  for (const k of ["busca", "uf", "partido", "ordem"]) if (q.get(k)) $("#" + k).value = q.get(k);

  // comparação com a média do partido e da bancada do estado, para a coluna que declara `valor` e `formato`
  const comparadores = new Map(config.colunas.filter((c) => c.valor).map((c) => [c, [mediasPor(itens, "partido", c.valor), mediasPor(itens, "uf", c.valor)]]));
  const comparar = (c, d) => (comparadores.has(c) && c.valor(d) != null ? dicaComparativa(d, ...comparadores.get(c), c.formato) : "");

  function desenhar() {
    const estado = { busca: $("#busca").value, uf: $("#uf").value, partido: $("#partido").value, ordem: $("#ordem").value };
    const filtrados = filtrarLista(itens, estado, config.ordenadores);
    const consulta = consultaDaLista(estado);
    history.replaceState(null, "", consulta ? "?" + consulta : location.pathname);

    $("#contagem").textContent = `${filtrados.length} de ${itens.length} ${config.plural} em exercício`;
    if (!filtrados.length) { alvo.innerHTML = `<p class="vazio">Nenhum ${config.singular} com esses filtros. Tente limpar a busca ou escolher outro estado.</p>`; return; }
    alvo.innerHTML = `
      <div class="cabecalho-lista" style="--metricas:${config.colunas.length}" aria-hidden="true"><span></span><span>${esc(config.rotuloNome)}</span>${config.colunas.map((c) => `<span${c.largo ? ` class="so-largo"` : ""}>${esc(c.rotulo)}</span>`).join("")}</div>
      <ul class="lista">${filtrados.map((d) => `
        <li><a class="linha-dep" style="--metricas:${config.colunas.length}" href="${esc(config.href(d))}">
          ${foto(d)}
          <span><span class="nome">${esc(d.nome)}</span><br><span class="sigla">${config.sub(d)}</span></span>
          ${config.colunas.map((c) => celulaDaColuna(c, d, comparar(c, d), estado.ordem)).join("")}
        </a></li>`).join("")}</ul>`;
  }
  ["busca", "uf", "partido", "ordem"].forEach((id) => $("#" + id).addEventListener("input", desenhar));
  desenhar();
}
