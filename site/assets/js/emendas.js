/* Emendas parlamentares federais de um político (coletar_emendas.py; ligadas à pessoa em identidades.py: ligar_emendas; gerar_emendas.py). */
import { esc, reaisCentavos, carregar, carregarMalha, semAcento } from "./util.js";
import { fontes, UFS, COD_UF, MALHAS } from "./apis.js";
import { svgMapa } from "./mapa.js";

export const PORTAL_EMENDAS = "https://portaldatransparencia.gov.br/emendas/consulta";
const ITENS_EXIBIDOS = 50;
const MUNICIPIOS_EXIBIDOS = 15;

/* Emenda Pix: emenda individual de "Transferências Especiais" (a verba vai direto ao caixa do município). */
export const ehPix = (tipo) => semAcento(tipo || "").toLowerCase().includes("transferencias especiais");

export async function carregarEmendas(pessoa) {
  if (!pessoa || !/^[\w-]+$/.test(pessoa)) return null;
  try { return await carregar(`dados/emendas/${pessoa}.json`); } catch { return null; }
}

export function painelEmendas(e) {
  if (!e?.anos?.length) return "";
  const itens = e.itens || [];
  const pix = itens.filter((i) => ehPix(i.tipo));
  const soma = (lista, campo) => lista.reduce((t, i) => t + (i[campo] || 0), 0);
  const comMapa = (e.municipios || []).some((m) => m.ibge);
  return `<h2>Emendas parlamentares</h2>
    <p class="aviso">Emendas ao orçamento federal em que o Portal da Transparência registra este nome como autor. A ligação é só pelo nome (média): confira o número da emenda no portal. <b>Empenhado</b> é o valor reservado; só o <b>pago</b> chegou a quem executa a obra ou o serviço.</p>
    <div class="rolagem"><table class="tabela"><thead><tr><th>Ano</th><th>Emendas</th><th>Empenhado</th><th>Liquidado</th><th>Pago</th></tr></thead><tbody>
      ${e.anos.map((a) => `<tr><td>${esc(a.ano)}</td><td>${a.n}</td><td>${reaisCentavos(a.empenhado)}</td><td>${reaisCentavos(a.liquidado)}</td><td>${reaisCentavos(a.pago)}</td></tr>`).join("")}
    </tbody></table></div>
    ${pix.length ? `<p><b>Emendas Pix</b> (transferências especiais, enviadas direto ao município sem convênio): <b>${pix.length}</b>, com ${reaisCentavos(soma(pix, "empenhado"))} empenhados e ${reaisCentavos(soma(pix, "pago"))} pagos.</p>` : ""}
    ${comMapa ? `<h3>Mapa dos destinos</h3><div class="mapa-emendas" data-municipios="${esc(JSON.stringify(e.municipios.filter((m) => m.ibge)))}" data-pix="${pix.length ? 1 : 0}"><p class="aviso">Carregando o mapa...</p></div>` : ""}
    ${e.municipios?.length ? `<h3>Municípios que mais receberam</h3>
      <div class="rolagem"><table class="tabela"><thead><tr><th>Município</th><th>Emendas</th><th>Empenhado</th><th>Pago</th>${pix.length ? "<th>Pix (empenhado)</th>" : ""}</tr></thead><tbody>
        ${e.municipios.slice(0, MUNICIPIOS_EXIBIDOS).map((m) => `<tr><td>${esc(m.nome)} (${esc(m.uf)})</td><td>${m.n}</td><td>${reaisCentavos(m.empenhado)}</td><td>${reaisCentavos(m.pago)}</td>${pix.length ? `<td>${m.pixN ? reaisCentavos(m.pixEmpenhado) : ""}</td>` : ""}</tr>`).join("")}
      </tbody></table></div>` : ""}
    <details><summary>Emendas ${itens.length > ITENS_EXIBIDOS ? `(as ${ITENS_EXIBIDOS} maiores de ${itens.length})` : `(${itens.length})`}</summary>
      <div class="rolagem"><table class="tabela"><thead><tr><th>Ano</th><th>Número</th><th>Tipo</th><th>Local</th><th>Área</th><th>Empenhado</th><th>Pago</th></tr></thead><tbody>
        ${itens.slice(0, ITENS_EXIBIDOS).map((i) => `<tr><td>${esc(i.ano)}</td><td>${esc(i.numero || i.codigo)}</td><td>${esc(i.tipo || "")}</td><td>${esc(i.local || "")}</td><td>${esc([i.funcao, i.subfuncao].filter(Boolean).join(" / "))}</td><td>${reaisCentavos(i.empenhado)}</td><td>${reaisCentavos(i.pago)}</td></tr>`).join("")}
      </tbody></table></div>
    </details>
    ${fontes(e.anos.map((a) => [`Emendas de ${a.ano} (Portal da Transparência)`, `${PORTAL_EMENDAS}?ano=${encodeURIComponent(a.ano)}`]))}`;
}

/* Mapa dos destinos: município colorido pelo valor empenhado, de um estado por vez; filtro de só Emendas Pix. DF não tem malha municipal. */
const COR = (v, maximo) => `color-mix(in srgb, var(--marca) ${Math.round(12 + 88 * Math.sqrt(v / maximo))}%, var(--superficie))`;
async function desenharMapaEmendas(el) {
  try {
    const municipios = JSON.parse(el.dataset.municipios).filter((m) => COD_UF[m.uf]);
    const ufs = [...new Set(municipios.map((m) => m.uf))];
    if (!ufs.length) { el.textContent = "Os destinos deste político não têm mapa municipal (só estado ou Distrito Federal)."; return; }
    const total = (uf) => municipios.filter((m) => m.uf === uf).reduce((t, m) => t + m.empenhado, 0);
    ufs.sort((a, b) => total(b) - total(a));
    el.innerHTML = `<p class="legenda-mapa"><label>Estado <select class="uf">${ufs.map((u) => `<option value="${u}">${esc(UFS[u] || u)}</option>`).join("")}</select></label>
      ${el.dataset.pix === "1" ? `<label><input type="checkbox" class="so-pix"> Só Emendas Pix</label>` : ""}</p>
      <div class="mapa-mun"></div><p class="legenda-mapa"><span>menos</span><i></i><span>mais empenhado</span></p>`;
    const [selUf, soPix, area] = [el.querySelector(".uf"), el.querySelector(".so-pix"), el.querySelector(".mapa-mun")];
    const malhas = {};
    const desenhar = async () => {
      const uf = selUf.value, cod = COD_UF[uf];
      malhas[uf] ||= await carregarMalha(`geo/uf_${cod}.json`, `${MALHAS}/estados/${cod}?formato=application/vnd.geo+json&intrarregiao=municipio&qualidade=minima`);
      const valor = (m) => (soPix?.checked ? m.pixEmpenhado || 0 : m.empenhado);
      const por_ibge = new Map(municipios.filter((m) => m.uf === uf).map((m) => [m.ibge, m]));
      const maximo = Math.max(1, ...[...por_ibge.values()].map(valor));
      area.innerHTML = svgMapa(malhas[uf], (f) => f.properties.codarea);
      area.querySelectorAll("path").forEach((p) => {
        const m = por_ibge.get(p.dataset.id), v = m ? valor(m) : 0;
        p.removeAttribute("tabindex"); p.removeAttribute("role");
        p.style.fill = v ? COR(v, maximo) : "var(--ausente)";
        if (m && v) p.insertAdjacentHTML("afterbegin", `<title>${esc(m.nome)}: ${reaisCentavos(v)} empenhados${soPix?.checked ? " (Pix)" : ""}; ${reaisCentavos(m.pago)} pagos no total</title>`);
      });
    };
    selUf.addEventListener("change", desenhar);
    soPix?.addEventListener("change", desenhar);
    await desenhar();
  } catch { el.textContent = "Não foi possível carregar o mapa."; }
}
if (typeof document !== "undefined" && window.IntersectionObserver) {
  const visto = new IntersectionObserver((itens) => itens.forEach((i) => {
    if (!i.isIntersecting) return;
    visto.unobserve(i.target);
    desenharMapaEmendas(i.target);
  }));
  new MutationObserver(() => document.querySelectorAll(".mapa-emendas:not([data-visto])").forEach((el) => { el.dataset.visto = "1"; visto.observe(el); }))
    .observe(document.body, { childList: true, subtree: true });
}
