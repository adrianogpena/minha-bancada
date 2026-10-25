/* Sobre os dados: lista das APIs e fontes que o site consulta, com o resultado do último checkup (dados/status_apis.json). */
import { $, esc, carregar, urlSegura } from "./util.js";

const quando = (iso) => (!iso ? "—" : iso.length === 10 ? new Date(iso + "T12:00:00Z").toLocaleDateString("pt-BR", { dateStyle: "short", timeZone: "UTC" }) : new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }));
const host = (u) => { try { return new URL(u).hostname; } catch { return u; } };

function linha([nome, a]) {
  const link = urlSegura(a.url) ? `<a href="${esc(a.url)}" rel="noopener">${esc(host(a.url))}</a>` : esc(host(a.url));
  const estado = a.ok ? `<span class="estado-api ok">Funcionando</span>` : `<span class="estado-api erro">${a.ultimoOk ? "Fora do ar" : "Nunca funcionou"}</span>`;
  return `<tr><td>${esc(nome)}<br><span class="quando">${esc(a.grupo)}<br>${link}</span></td><td>${estado}${a.ok ? "" : `<br><span class="quando">${esc(a.detalhe)}</span>`}</td><td>${quando(a.verificadoEm)}</td><td>${a.ultimoOk ? quando(a.ultimoOk) : "nunca"}</td></tr>`;
}

export async function paginaSobre() {
  const alvo = $("#status-apis");
  let status;
  try { status = await carregar("dados/status_apis.json"); } catch { alvo.innerHTML = `<p class="quando">O status das APIs ainda não foi gerado.</p>`; return; }
  const ordem = (a) => (a.ok ? 2 : a.ultimoOk ? 1 : 0);
  const todas = Object.entries(status).sort((x, y) => (ordem(x[1]) - ordem(y[1])) || x[0].localeCompare(y[0], "pt-BR"));
  const fora = todas.filter(([, a]) => !a.ok);
  const tabela = (itens) => `<div class="rolagem"><table class="tabela tabela-fonte"><thead><tr><th>API ou fonte</th><th>Status</th><th>Último checkup</th><th>Último funcionamento</th></tr></thead><tbody>${itens.map(linha).join("")}</tbody></table></div>`;
  alvo.innerHTML = `<p>${todas.length - fora.length} de ${todas.length} funcionando no último checkup (${quando(todas.map(([, a]) => a.verificadoEm).sort().pop())}).</p>
    <h3>Todas as APIs e fontes</h3>${tabela(todas)}`;
}
