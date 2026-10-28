/* Rede de coautoria entre os partidos da Câmara (dados/coautoria.json, gerado por scripts/gerar_coautoria.py). */
import { $, esc, pct, carregar } from "./util.js";
import { erro } from "./comum.js";
import { CAMARA_API, fontes } from "./apis.js";

export async function paginaCoautoria() {
  const alvo = $("#resultado");
  let j;
  try { j = await carregar("dados/coautoria.json"); } catch (e) { return erro(alvo, e); }
  const partidos = j.partidos.filter((p) => p.projetos >= 5).sort((a, b) => b.projetos - a.projetos);
  const pares = new Map();
  for (const [chave, n] of Object.entries(j.pares)) {
    const [a, b] = chave.split("|");
    pares.set(`${a}|${b}`, n); pares.set(`${b}|${a}`, n);
  }
  const maximo = Math.max(1, ...pares.values());
  $("#contagem").textContent = `${j.projetos} projetos assinados por mais de um deputado, ${partidos.length} partidos com ao menos 5 deles`;
  const celula = (a, b) => {
    if (a === b) return `<td class="vazio">·</td>`;
    const n = pares.get(`${a.sigla}|${b.sigla}`) || 0;
    return `<td title="${esc(a.sigla)} e ${esc(b.sigla)}: ${n} projetos" style="background:rgba(36,86,201,${(n / maximo).toFixed(2)})">${n || ""}</td>`;
  };
  alvo.innerHTML = `
    <h2>Partidos que assinam fora de casa</h2>
    <div class="rolagem"><table class="tabela"><thead><tr><th>Partido</th><th>Projetos com coautoria</th><th>Com outro partido</th></tr></thead><tbody>
      ${[...partidos].sort((a, b) => b.comOutros / b.projetos - a.comOutros / a.projetos).map((p) =>
        `<tr><td>${esc(p.sigla)}</td><td>${p.projetos}</td><td>${p.comOutros} (${pct(p.comOutros, p.projetos)})</td></tr>`).join("")}
    </tbody></table></div>
    <h2>Projetos assinados por cada par de partidos</h2>
    <div class="rolagem"><table class="tabela matriz"><thead><tr><th></th>${partidos.map((p) => `<th>${esc(p.sigla)}</th>`).join("")}</tr></thead><tbody>
      ${partidos.map((a) => `<tr><th>${esc(a.sigla)}</th>${partidos.map((b) => celula(a, b)).join("")}</tr>`).join("")}
    </tbody></table></div>`;
  $("#notas").innerHTML = `Um projeto com deputados de três partidos conta uma vez para cada par. Ficam de fora autores que não são deputados (Executivo, Senado, comissões) e ${j.ignorados} ${j.ignorados === 1 ? "projeto" : "projetos"} com mais de ${j.maxAutores} deputados, que ligariam todos os partidos entre si. A autoria de proposições antigas é coletada aos poucos, então os números crescem nos primeiros dias.
    ${fontes([["Autores de cada proposição (API da Câmara)", `${CAMARA_API}/proposicoes`]])}`;
}
