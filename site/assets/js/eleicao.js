/* Painel da eleição e mapas dos locais de votação (Leaflet). */
import { esc, data, carregar, numeroBr } from "./util.js";
import { divulgaUrl, CODIGO_ELEITORAL_URL, ARTIGO_ELEICAO, MAJORITARIOS, linkCF, semFonte, rotuloResultado, blocoCampanha, blocoDisputa, blocoPartido, blocoAlianca, blocoOndeVotou } from "./ficha.js";
import { TSE_CDN, fontes, UFS, COD_UF, MALHAS, SENADO_API } from "./apis.js";
import { svgMapa } from "./mapa.js";

/* Mapas dos locais de votação (Leaflet, carregado só quando aparece um mapa na tela). */
const LEAFLET = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4";
let leafletPronto;
function carregarLeaflet() {
  leafletPronto ||= new Promise((ok, falha) => {
    const css = document.createElement("link");
    css.rel = "stylesheet"; css.href = `${LEAFLET}/leaflet.min.css`;
    const js = document.createElement("script");
    js.src = `${LEAFLET}/leaflet.min.js`; js.onload = () => ok(window.L); js.onerror = falha;
    document.head.append(css, js);
  });
  return leafletPronto;
}
function desenharMapaVotos(el) {
  carregarLeaflet().then((L) => {
    const pontos = JSON.parse(el.dataset.pontos);
    const mapa = L.map(el, { scrollWheelZoom: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(mapa);
    const maximo = Math.max(...pontos.map((p) => p[3]));
    const grupo = L.featureGroup(pontos.map(([nome, la, lo, v]) => L.circleMarker([la, lo], { radius: 6 + 14 * Math.sqrt(v / maximo), weight: 1, fillOpacity: 0.55 })
      .bindTooltip(`${nome}: ${numeroBr(v)} votos`))).addTo(mapa);
    mapa.fitBounds(grupo.getBounds().pad(0.2), { maxZoom: 15 });
  }).catch(() => { el.textContent = "Não foi possível carregar o mapa."; });
}
/* Mapa colorido por município (malha do IBGE; código TSE -> IBGE em dados/municipios_ibge.json). */
let ibgeDeTse;
async function desenharMapaMunicipios(el) {
  try {
    ibgeDeTse ||= await carregar("dados/municipios_ibge.json");
    const tseDeIbge = Object.fromEntries(Object.entries(ibgeDeTse).map(([t, i]) => [i, t]));
    const fc = await carregar(`${MALHAS}/estados/${COD_UF[el.dataset.uf]}?formato=application/vnd.geo+json&intrarregiao=municipio&qualidade=minima`);
    const votos = new Map(JSON.parse(el.dataset.votosPorMunicipio).map(([c, v]) => [String(c).padStart(5, "0"), v]));
    const maximo = Math.max(...votos.values());
    el.innerHTML = svgMapa(fc, (f) => tseDeIbge[f.properties.codarea] || "");
    const nomes = new Map(fc.features.map((f) => [tseDeIbge[f.properties.codarea], f.properties.nome]));
    el.querySelectorAll("path").forEach((p) => {
      const v = votos.get(p.dataset.id) || 0;
      p.removeAttribute("tabindex"); p.removeAttribute("role");
      p.style.fill = v ? `color-mix(in srgb, var(--marca) ${Math.round(12 + 88 * Math.sqrt(v / maximo))}%, var(--superficie))` : "var(--ausente)";
      p.insertAdjacentHTML("afterbegin", `<title>${esc(nomes.get(p.dataset.id) || "")}: ${numeroBr(v)} votos</title>`);
    });
  } catch (err) { el.textContent = "Não foi possível carregar o mapa."; }
}
if (window.IntersectionObserver) {
  const visto = new IntersectionObserver((itens) => itens.forEach((i) => {
    if (!i.isIntersecting) return;
    visto.unobserve(i.target);
    (i.target.classList.contains("mapa-mun") ? desenharMapaMunicipios : desenharMapaVotos)(i.target);
  }));
  new MutationObserver(() => document.querySelectorAll(".mapa-votos:not([data-visto]), .mapa-mun:not([data-visto])").forEach((el) => { el.dataset.visto = "1"; visto.observe(el); }))
    .observe(document.body, { childList: true, subtree: true });
}

/* Aba "Quem o elegeu?": votação (ano, data, resultado) ou, para suplente, quem ele substituiu e desde quando. */
export function painelEleicao(nome, e, o = {}) {
  const cargoTse = (e && e.cargoTse) || o.cargoTse;
  const ehVice = /^VICE-/.test(cargoTse || "");
  const fontesLista = [...(o.fontes || [])];
  let corpo = "";
  if (o.suplente) {
    corpo += `<p><b>${esc(nome)}</b> exerce o mandato como <b>${esc((o.condicao || "suplente").toLowerCase())}</b>${o.titular ? `, no lugar de <b>${esc(o.titular)}</b>` : ""}${o.desde ? `, desde ${esc(data(o.desde, true))}` : ""}.</p>`;
    if (!o.titular) corpo += `<p>${semFonte("não sabemos quem foi substituído")}</p>`;
    if (!o.desde) corpo += `<p>${semFonte("data em que assumiu")}</p>`;
    corpo += `<p>O suplente é eleito junto com o titular, na mesma chapa, e assume quando o titular se afasta${o.titular ? `. A eleição abaixo é a da chapa de ${esc(o.titular)}` : ""}.</p>`;
    fontesLista.push(["Constituição Federal, art. 56", linkCF(56)]);
  }
  if (e && e.votos && e.votos.length) {
    const local = e.municipio ? `${e.municipio} (${e.uf})` : e.uf === "BR" ? "todo o Brasil" : UFS[e.uf] || e.uf;
    corpo += `<h3>Eleição de ${esc(e.ano)}</h3>`;
    if (ehVice && e.titular) corpo += `<p>${esc(nome)} foi eleito na chapa de <b>${esc(e.titular)}</b>: o eleitor vota na chapa inteira, então os votos abaixo são os da chapa.</p>`;
    corpo += `<ul class="lista-eleicao">${e.votos.map((v) => `<li><span class="quando">${v.turno}º turno${v.data ? `, ${esc(data(v.data, true))}` : ""}</span>
      <b>${numeroBr(v.votos)} votos</b>${v.percentual != null ? ` (${String(v.percentual).replace(".", ",")}% dos votos válidos)` : ""}</li>`).join("")}</ul>`;
    corpo += `<p>Local: ${esc(local)}.${e.resultado ? ` Resultado oficial: <b>${esc(rotuloResultado(e.resultado))}</b>.` : ""}</p>`;
    corpo += blocoDisputa(e, fontesLista) + blocoPartido(e, fontesLista) + blocoAlianca(e, fontesLista) + blocoOndeVotou(e, fontesLista) + blocoCampanha(e, fontesLista);
    if (cargoTse && !MAJORITARIOS.has(cargoTse)) corpo += `<p>Nas eleições proporcionais as vagas são distribuídas entre os partidos pelo quociente eleitoral; por isso o número de votos de cada candidato não diz sozinho quem foi eleito.</p>`;
    if (cargoTse) fontesLista.push([`Constituição Federal, art. ${ARTIGO_ELEICAO[cargoTse]}`, linkCF(ARTIGO_ELEICAO[cargoTse])]);
    if (cargoTse && !MAJORITARIOS.has(cargoTse)) fontesLista.push(["Código Eleitoral, art. 106", CODIGO_ELEITORAL_URL]);
    const d = divulgaUrl({ fonte: "tse", ano: e.ano, eleicao: e.eleicao, unidadeEleitoral: e.unidadeEleitoral, sequencial: e.sequencial });
    if (d) fontesLista.unshift(["Candidatura no DivulgaCandContas (TSE)", d]);
    fontesLista.unshift([`Votação por zona eleitoral ${e.ano} (TSE)`, `${TSE_CDN}/votacao_candidato_munzona/votacao_candidato_munzona_${e.ano}.zip`]);
  } else if (e) {
    corpo += `<p>Eleito em ${esc(e.ano)}. ${semFonte("votos ainda não coletados")}</p>`;
  } else if (!o.suplente) {
    corpo += `<p>${semFonte("não encontramos como foi eleito")}</p>`;
  }
  return `<section class="painel"><div class="painel-titulo"><h2>Quem o elegeu?</h2></div>${corpo}${fontes(fontesLista)}</section>`;
}

/* Monta a aba a partir da ficha de um político (TSE ou Senado). */
export function painelEleicaoDe(p, nome) {
  if (p.fonte === "senado") {
    const suplente = !!(p.participacao && p.participacao !== "Titular");
    return painelEleicao(nome, p.eleicao, { suplente, condicao: p.participacao, titular: p.titular, desde: p.exercicioDesde, cargoTse: "SENADOR",
      fontes: [["Dados Abertos do Senado", `${SENADO_API}/senador/${encodeURIComponent(p.id)}`]] });
  }
  return painelEleicao(nome, p, {});
}
