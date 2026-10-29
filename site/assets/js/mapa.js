/* Mapa do Brasil, eleitorado e perfil das casas legislativas. */
import { esc, carregar, numeroBr, urlSegura } from "./util.js";
import { foto } from "./comum.js";
import { TSE_CDN, arquivoTse, UFS } from "./apis.js";

export const GRUPOS = [
  { titulo: "Presidência da República", ordens: [1, 2] },
  { titulo: "Senado Federal", ordens: [3] },
  { titulo: "Câmara dos Deputados", ordens: [4] },
  { titulo: "Governo do estado", ordens: [5, 6] },
  { titulo: (uf) => (uf === "DF" ? "Câmara Legislativa" : "Assembleia Legislativa"), ordens: [7] },
  { titulo: "Prefeitura", ordens: [8, 9], municipal: true },
  { titulo: "Câmara Municipal", ordens: [10], municipal: true },
];


export function linkPolitico(x) {
  return urlSegura(x.pagina, true) || `politico.html?f=${encodeURIComponent(x.arquivoFicha)}&i=${encodeURIComponent(x.id)}`;
}

function etiquetaEstado(e) {
  if (e === "eleito") return `<span class="etiqueta">Eleito em 2026</span>`;
  if (e === "2turno") return `<span class="etiqueta segundo">No 2º turno</span>`;
  return "";
}

export function linhaPolitico(x) {
  return `<li><a class="linha-pol" href="${esc(linkPolitico(x))}">
    ${foto({ nome: x.nome || "?", foto: x.foto })}
    <span><span class="nome">${esc(x.nome)}</span><br><span class="sigla">${esc(x.cargo)}${x.partido ? `, ${esc(x.partido)}` : ""}${x.municipio ? ` em ${esc(x.municipio)}` : x.uf ? `, ${esc(x.uf)}` : ""}</span></span>
    ${etiquetaEstado(x.estado)}
  </a></li>`;
}

/* Desenha um GeoJSON do IBGE como SVG (projeção simples, corrigida pela latitude média). */
export function svgMapa(fc, idDe) {
  const poligonos = (g) => (g.type === "Polygon" ? [g.coordinates] : g.coordinates);
  let x0 = 180, x1 = -180, y0 = 90, y1 = -90;
  for (const f of fc.features) for (const poli of poligonos(f.geometry)) for (const anel of poli) for (const [x, y] of anel) {
    if (x < x0) x0 = x;
    if (x > x1) x1 = x;
    if (y < y0) y0 = y;
    if (y > y1) y1 = y;
  }
  const k = Math.cos((((y0 + y1) / 2) * Math.PI) / 180), escala = 1000 / ((x1 - x0) * k);
  const px = (x) => Math.round((x - x0) * k * escala * 10) / 10, py = (y) => Math.round((y1 - y) * escala * 10) / 10;
  const caminhos = fc.features.map((f) => {
    const d = poligonos(f.geometry).map((poli) => poli.map((anel) => "M" + anel.map(([x, y]) => `${px(x)} ${py(y)}`).join("L") + "Z").join("")).join("");
    return `<path d="${d}" data-id="${esc(idDe(f))}" tabindex="0" role="link"></path>`;
  });
  return `<svg viewBox="0 0 ${px(x1)} ${py(y0)}" xmlns="http://www.w3.org/2000/svg">${caminhos.join("")}</svg>`;
}

/* Perfil do eleitorado (TSE) do estado ou município escolhido: total e divisão por gênero, faixa etária e escolaridade. */
const FAIXAS = ["16 e 17 anos", "18 a 24", "25 a 34", "35 a 44", "45 a 54", "55 a 64", "65 a 74", "75 ou mais"];
const ESCOLARIDADE = ["Analfabeto", "Lê e escreve", "Fundamental incompleto", "Fundamental completo", "Médio incompleto", "Médio completo", "Superior incompleto", "Superior completo"];
const eleitoradoUf = {};
export async function desenharEleitorado(el, uf, mun, nomeLocal) {
  if (!uf) { el.hidden = true; return; }
  try { eleitoradoUf[uf] ||= await carregar(`dados/eleitorado/${uf}.json`); } catch (e) { el.hidden = true; return; }
  const { ano, locais } = eleitoradoUf[uf];
  const r = locais[mun || "_uf"];
  if (!r || !r.total) { el.hidden = true; return; }
  const porcento = (v, base) => (base ? `${((100 * v) / base).toFixed(1).replace(".", ",")}%` : "");
  const barras = (rotulos, valores, base) => `<div class="barras">${rotulos.map((r, i) => `<div><div class="barra-rotulo"><span>${esc(r)}</span>
    <b>${numeroBr(valores[i])} · ${porcento(valores[i], base)}</b></div><div class="barra"><i style="width:${base ? (100 * valores[i]) / base : 0}%"></i></div></div>`).join("")}</div>`;
  const faixas = r.porFaixaEtaria.reduce((a, b) => a + b, 0), escolas = r.porEscolaridade.reduce((a, b) => a + b, 0), genero = r.porGenero[0] + r.porGenero[1];
  el.innerHTML = `<summary>Eleitorado de ${esc(nomeLocal)}: <b>${numeroBr(r.total)}</b> eleitores (${esc(ano)})</summary>
    <h3>Gênero</h3>${barras(["Mulheres", "Homens"], [r.porGenero[1], r.porGenero[0]], genero)}
    <h3>Faixa etária</h3>${barras(FAIXAS, r.porFaixaEtaria, faixas)}
    <h3>Escolaridade</h3>${barras(ESCOLARIDADE, r.porEscolaridade, escolas)}
    <p class="fonte-link"><span class="rotulo-fonte">Fonte</span> <a href="${TSE_CDN}/perfil_eleitorado/perfil_eleitorado_${ano}.zip" rel="noopener">Perfil do eleitorado ${esc(ano)} (TSE)</a>.
    Os percentuais de cada grupo são sobre quem tem a informação registrada.</p>`;
  el.hidden = false;
}

/* Quem é cada Casa: perfil dos eleitos (TSE) ao lado do perfil do eleitorado, quando existe. */
const perfisCasas = {};
const FONTES_ELEITOS = { estadual: [2022], federal: [2022], senado: [2018, 2022], municipal: [2024] };
export async function desenharPerfilCasas(el, uf, mun, nomeLocal) {
  el.innerHTML = "";
  if (!uf) return;
  try { perfisCasas[uf] ||= await carregar(`dados/perfil_casas/${uf}.json`); } catch { return; }
  let local = null;
  try { eleitoradoUf[uf] ||= await carregar(`dados/eleitorado/${uf}.json`); local = eleitoradoUf[uf].locais[mun || "_uf"]; } catch { /* sem eleitorado: mostra só os eleitos */ }
  const casas = perfisCasas[uf];
  const lista = mun
    ? [[`Câmara Municipal de ${nomeLocal}`, casas.municipal && casas.municipal[mun], "municipal", local]]
    : [[uf === "DF" ? "Câmara Legislativa" : `Assembleia Legislativa (${UFS[uf]})`, casas.estadual, "estadual", local],
       [`Bancada de ${UFS[uf]} na Câmara dos Deputados`, casas.federal, "federal", local], [`Senadores de ${UFS[uf]}`, casas.senado, "senado", local]];
  el.innerHTML = lista.map(([titulo, p, chave, eleitorado]) => perfilCasaHtml(titulo, p, chave, eleitorado ? eleitoradoUf[uf].ano : null, eleitorado)).join("");
}
function perfilCasaHtml(titulo, p, chave, anoEleitorado, eleitorado) {
  if (!p || !p.total) return "";
  const soma = (v) => v.reduce((a, b) => a + b, 0);
  const porcento = (v, base) => (base ? `${((100 * v) / base).toFixed(1).replace(".", ",")}%` : "0%");
  const barras = (rotulos, eleitos, eleitores) => {
    const be = soma(eleitos), bl = eleitores ? soma(eleitores) : 0;
    return `<div class="barras">${rotulos.map((r, i) => `<div><div class="barra-rotulo"><span>${esc(r)}</span>
      <b>${numeroBr(eleitos[i])} eleitos · ${porcento(eleitos[i], be)}${bl ? ` · eleitorado ${porcento(eleitores[i], bl)}` : ""}</b></div>
      <div class="barra"><i style="width:${be ? (100 * eleitos[i]) / be : 0}%"></i></div>
      ${bl ? `<div class="barra ref"><i style="width:${(100 * eleitores[i]) / bl}%"></i></div>` : ""}</div>`).join("")}</div>`;
  };
  const e = eleitorado;
  const racaTotal = soma(p.raca.map(([, n]) => n));
  const anos = FONTES_ELEITOS[chave];
  return `<details class="eleitorado"><summary>Perfil dos eleitos: ${esc(titulo)} (<b>${numeroBr(p.total)}</b>)</summary>
    ${e ? `<p class="legenda-barras">Barra larga: eleitos. Barra fina: eleitorado (${esc(anoEleitorado)}).</p>` : ""}
    <h3>Gênero</h3>${barras(["Mulheres", "Homens"], [p.genero[1], p.genero[0]], e && [e.porGenero[1], e.porGenero[0]])}
    <h3>Idade na eleição</h3>${barras(FAIXAS, p.faixas, e && e.porFaixaEtaria)}
    <h3>Escolaridade</h3>${barras(ESCOLARIDADE, p.instrucao, e && e.porEscolaridade)}
    ${racaTotal ? `<h3>Cor ou raça declarada</h3><ul class="lista-eleicao">${p.raca.map(([r, n]) => `<li>${esc(r)}: <b>${numeroBr(n)}</b> (${porcento(n, racaTotal)})</li>`).join("")}</ul>` : ""}
    ${p.ocupacoes.length ? `<h3>Ocupações mais declaradas</h3><ul class="lista-eleicao">${p.ocupacoes.map(([o, n]) => `<li>${esc(o)}: <b>${numeroBr(n)}</b></li>`).join("")}</ul>` : ""}
    <p class="fonte-link"><span class="rotulo-fonte">Fonte</span> ${anos.map((a) => `<a href="${arquivoTse("consulta_cand", { ano: a })}" rel="noopener">Candidatos ${a} (TSE)</a>`).join(" · ")}${e ? ` · <a href="${TSE_CDN}/perfil_eleitorado/perfil_eleitorado_${anoEleitorado}.zip" rel="noopener">Perfil do eleitorado ${esc(anoEleitorado)} (TSE)</a>` : ""}.
    ${p.composicao === "atual"
      ? `Dados da candidatura de ${anos.join(" e ")} dos deputados em exercício hoje, suplentes que assumiram inclusive (${numeroBr(p.total)} de ${numeroBr(p.emExercicio)} ligados ao registro do TSE).`
      : `Dados da candidatura: os eleitos de ${anos.join(" e ")}, sem contar suplentes que assumiram depois.`} A raça e a ocupação não existem no perfil do eleitorado.
    Escolaridade e idade do eleitorado seguem as mesmas faixas; o eleitorado de ${esc(anoEleitorado || "")} pode diferir do ano da eleição.</p></details>`;
}
