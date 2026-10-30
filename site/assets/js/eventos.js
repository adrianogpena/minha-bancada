/* Aba "Eventos" da ficha: os 10 últimos eventos do histórico diário que citam o político, de qualquer data. */
import { $, carregar } from "./util.js";
import { erro } from "./comum.js";
import { doPolitico, itemHistorico } from "./historico.js";

const LIMITE = 10;
const LOTE = 4;   // arquivos diários lidos por vez, do mais novo ao mais antigo, até juntar o limite

/* `fichas`: códigos do "Fique informado" e/ou páginas do site que identificam o político nos eventos. */
export const abaEventos = `<button type="button" role="tab" id="aba-eventos" aria-controls="painel-eventos" data-aba="eventos">Eventos</button>`;
export const painelEventos = `<div role="tabpanel" id="painel-eventos" aria-labelledby="aba-eventos" hidden><div id="eventos-politico"><p class="vazio">Carregando…</p></div></div>`;

export async function ultimosEventos(fichas, limite = LIMITE) {
  let indice;
  try { indice = await carregar("dados/historico/indice.json"); } catch { return []; }
  const achados = [];
  for (let i = 0; i < indice.length && achados.length < limite; i += LOTE) {
    const dias = await Promise.all(indice.slice(i, i + LOTE).map((x) => carregar(`dados/historico/${x.data}.json`)));
    for (const d of dias) for (const e of d.eventos) if (doPolitico(e, fichas)) achados.push({ ...e, _dia: d.data });
  }
  return achados.slice(0, limite);
}

/* Lê os arquivos só quando a aba é aberta pela primeira vez. */
export function montarEventos(alvo, fichas) {
  const painel = $("#painel-eventos", alvo), lista = $("#eventos-politico", alvo);
  const link = `historico.html?periodo=30dias&imp=&politico=${encodeURIComponent(fichas.join(","))}`;
  let iniciado = false;
  async function carregarLista() {
    if (iniciado || painel.hidden) return;
    iniciado = true;
    let eventos;
    try { eventos = await ultimosEventos(fichas); } catch (e) { return erro(lista, e); }
    lista.innerHTML = `<section class="painel"><div class="painel-titulo"><h2>Últimos eventos</h2>
        <p>${eventos.length ? `Os ${eventos.length === 1 ? "único evento registrado" : `${eventos.length} eventos mais recentes`} no histórico do site, de qualquer data.` : "Nenhum evento registrado no histórico do site."}</p></div>
      ${eventos.length ? `<ul class="hist-itens">${eventos.map(itemHistorico).join("")}</ul>` : ""}
      <p><a href="${link}">Ver mais eventos deste político (últimos 30 dias)</a></p></section>`;
  }
  new MutationObserver(carregarLista).observe(painel, { attributes: true, attributeFilter: ["hidden"] });
  carregarLista();
}
