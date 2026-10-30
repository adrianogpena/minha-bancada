/* Emendas parlamentares federais de um político (coletar_emendas.py; ligadas à pessoa em identidades.py: ligar_emendas; gerar_emendas.py). */
import { esc, reaisCentavos, carregar } from "./util.js";
import { fontes } from "./apis.js";

export const PORTAL_EMENDAS = "https://portaldatransparencia.gov.br/emendas/consulta";
const ITENS_EXIBIDOS = 50;

export async function carregarEmendas(pessoa) {
  if (!pessoa || !/^[\w-]+$/.test(pessoa)) return null;
  try { return await carregar(`dados/emendas/${pessoa}.json`); } catch { return null; }
}

export function painelEmendas(e) {
  if (!e?.anos?.length) return "";
  const itens = e.itens || [];
  return `<h2>Emendas parlamentares</h2>
    <p class="aviso">Emendas ao orçamento federal em que o Portal da Transparência registra este nome como autor. A ligação é só pelo nome (média): confira o número da emenda no portal. <b>Empenhado</b> é o valor reservado; só o <b>pago</b> chegou a quem executa a obra ou o serviço.</p>
    <div class="rolagem"><table class="tabela"><thead><tr><th>Ano</th><th>Emendas</th><th>Empenhado</th><th>Liquidado</th><th>Pago</th></tr></thead><tbody>
      ${e.anos.map((a) => `<tr><td>${esc(a.ano)}</td><td>${a.n}</td><td>${reaisCentavos(a.empenhado)}</td><td>${reaisCentavos(a.liquidado)}</td><td>${reaisCentavos(a.pago)}</td></tr>`).join("")}
    </tbody></table></div>
    ${e.municipios?.length ? `<h3>Municípios que mais receberam</h3>
      <div class="rolagem"><table class="tabela"><thead><tr><th>Município</th><th>Emendas</th><th>Empenhado</th><th>Pago</th></tr></thead><tbody>
        ${e.municipios.map((m) => `<tr><td>${esc(m.nome)} (${esc(m.uf)})</td><td>${m.n}</td><td>${reaisCentavos(m.empenhado)}</td><td>${reaisCentavos(m.pago)}</td></tr>`).join("")}
      </tbody></table></div>` : ""}
    <details><summary>Emendas ${itens.length > ITENS_EXIBIDOS ? `(as ${ITENS_EXIBIDOS} maiores de ${itens.length})` : `(${itens.length})`}</summary>
      <div class="rolagem"><table class="tabela"><thead><tr><th>Ano</th><th>Número</th><th>Tipo</th><th>Local</th><th>Área</th><th>Empenhado</th><th>Pago</th></tr></thead><tbody>
        ${itens.slice(0, ITENS_EXIBIDOS).map((i) => `<tr><td>${esc(i.ano)}</td><td>${esc(i.numero || i.codigo)}</td><td>${esc(i.tipo || "")}</td><td>${esc(i.local || "")}</td><td>${esc([i.funcao, i.subfuncao].filter(Boolean).join(" / "))}</td><td>${reaisCentavos(i.empenhado)}</td><td>${reaisCentavos(i.pago)}</td></tr>`).join("")}
      </tbody></table></div>
    </details>
    ${fontes(e.anos.map((a) => [`Emendas de ${a.ano} (Portal da Transparência)`, `${PORTAL_EMENDAS}?ano=${encodeURIComponent(a.ano)}`]))}`;
}
