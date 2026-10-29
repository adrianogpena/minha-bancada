/* Ministros de Estado e ministérios (dados/ministerios.json, dados/ministerio/<pasta>.json, dados/ministro/<pessoa>.json; scripts/gerar_ministros.py). */
import { $, esc, data, param, carregar, numeroBr, pct, urlSegura } from "./util.js";
import { erro, listaPaginada, abas, ligarAbas, foto, itemFicha } from "./comum.js";
import { fontes, CAMARA_API, SENADO_API, linkTramitacao } from "./apis.js";
import { linkCF, semFonte } from "./ficha.js";

const PLANALTO = "https://www.gov.br/planalto/pt-br/conheca-a-presidencia/ministros-e-ministras";
const NATUREZAS = { informacao: "Requerimento de informação", convocacao: "Convocação", convite: "Convite" };
const idValido = (s) => typeof s === "string" && /^[\w-]+$/.test(s);
const hojeIso = () => new Date().toISOString().slice(0, 10);

/* Situação de um pedido de informação da Câmara a partir de remessa, prazo e resposta; null para o que não tem esse ciclo. */
export function situacaoPedido(r, hoje = hojeIso()) {
  if (r.natureza !== "informacao" || r.fonte !== "camara") return null;
  if (r.resposta) {
    if (!r.prazoFim) return ["Respondido", "aprovada", "respondido"];
    return r.resposta <= r.prazoFim ? ["Respondido no prazo", "aprovada", "no-prazo"] : ["Respondido fora do prazo", "rejeitada", "fora-do-prazo"];
  }
  if (r.prazoFim) return hoje > r.prazoFim ? ["Prazo vencido sem resposta", "rejeitada", "vencido"] : [`Aguardando resposta, prazo até ${data(r.prazoFim)}`, "tramitando", "aguardando"];
  if (r.remessa) return ["Enviado ao ministério, prazo ainda não registrado", "tramitando", "aguardando"];
  return ["Ainda não enviado ao ministério", "sem", "sem-envio"];
}

function autoresDe(r, ctx) {
  if (r.fonte === "camara") {
    return r.autores.map((id) => {
      const nome = ctx.deputados.get(id) || ctx.fora[id] || `deputado ${id}`;
      return ctx.deputados.has(id) ? `<a href="deputado.html?id=${encodeURIComponent(id)}">${esc(nome)}</a>`
        : `<a href="https://www.camara.leg.br/deputados/${encodeURIComponent(id)}" rel="noopener">${esc(nome)}</a>`;
    }).join(", ");
  }
  const sen = r.autores.map((id) => ctx.senadores.has(id) ? `<a href="politico.html?f=senado&i=${encodeURIComponent(id)}">${esc(ctx.senadores.get(id))}</a>` : null).filter(Boolean);
  return [...sen, r.autoria && !sen.length ? esc(r.autoria) : null].filter(Boolean).join(", ");
}

function renderPedido(r, ctx) {
  const sit = situacaoPedido(r);
  const link = r.fonte === "camara" ? ["Ficha de tramitação (Câmara)", linkTramitacao(r.idFonte)] : r.documento ? ["Documento (Senado)", r.documento] : null;
  const datas = [r.data && `apresentado em ${data(r.data)}`, r.remessa && `enviado ao ministério em ${data(r.remessa)}`, r.prazoFim && `prazo até ${data(r.prazoFim)}`,
    r.resposta && `resposta em ${data(r.resposta)}`].filter(Boolean).join(" · ");
  const autores = autoresDe(r, ctx);
  const outras = (r.pastas || []).map((p) => ctx.nomes[p]).filter(Boolean);
  return `<li class="cartao-item">
    <span class="quando"><b>${esc(r.tipo)} ${esc(r.numero ?? "")}/${esc(r.ano ?? "")}</b> · ${esc(NATUREZAS[r.natureza] || r.natureza)}${datas ? ` · ${esc(datas)}` : ""}</span>
    ${sit ? `<span class="resultado r-${sit[1]}">${esc(sit[0])}</span>` : ""}
    <span class="texto">${esc(r.ementa || "Sem ementa")}</span>
    ${autores ? `<span class="texto quando">Autoria: ${autores}</span>` : ""}
    ${outras.length ? `<span class="texto quando">Cita também: ${esc(outras.join(", "))}</span>` : ""}
    ${r.fonte === "senado" ? `<span class="texto quando">${r.deliberacao ? `Deliberação: ${esc(r.deliberacao)}${r.dataDeliberacao ? `, em ${data(r.dataDeliberacao)}` : ""}. ` : r.tramitando === false ? "Fora de tramitação. " : "Em tramitação. "}${r.natureza === "informacao" ? semFonte("resposta do ministério ao Senado") : ""}</span>` : ""}
    ${r.situacao && r.fonte === "camara" ? `<span class="texto quando">Situação na Câmara: ${esc(r.situacao)}.</span>` : ""}
    <span class="texto">${fontes([link])}</span>
  </li>`;
}

/* Números, filtros e lista de pedidos de uma pasta ou de um ministro. `ctx`: nomes de deputados e senadores, autores que já saíram, nome das pastas. */
function montarPedidos(alvo, lista, ctx, aviso = "") {
  const infos = lista.filter((r) => r.natureza === "informacao" && r.fonte === "camara");
  const cont = (c) => infos.filter((r) => situacaoPedido(r)?.[2] === c).length;
  const respondidos = cont("respondido") + cont("no-prazo") + cont("fora-do-prazo");
  const convs = lista.filter((r) => r.natureza !== "informacao");
  alvo.innerHTML = `
    <div class="numeros">
      <div><b>${numeroBr(lista.length)}</b><span>pedidos no total</span></div>
      <div><b>${numeroBr(infos.length)}</b><span>requerimentos de informação na Câmara</span></div>
      <div><b>${pct(respondidos, infos.length)}</b><span>deles já respondidos (${numeroBr(respondidos)})</span></div>
      <div><b>${numeroBr(cont("no-prazo"))}</b><span>respondidos no prazo</span></div>
      <div><b>${numeroBr(cont("vencido"))}</b><span>com prazo vencido sem resposta</span></div>
      <div><b>${numeroBr(convs.length)}</b><span>convocações e convites</span></div>
    </div>
    ${aviso}
    <div class="abas" id="abas-pedidos"></div>
    <div id="lista-pedidos"></div>`;
  const filtros = {
    todos: () => true, informacao: (r) => r.natureza === "informacao", convocacao: (r) => r.natureza !== "informacao",
    "no-prazo": (r) => situacaoPedido(r)?.[2] === "no-prazo", "fora-do-prazo": (r) => situacaoPedido(r)?.[2] === "fora-do-prazo",
    vencido: (r) => situacaoPedido(r)?.[2] === "vencido", aguardando: (r) => situacaoPedido(r)?.[2] === "aguardando",
  };
  const mostrar = (f) => listaPaginada($("#lista-pedidos", alvo), lista.filter(filtros[f]), (r) => renderPedido(r, ctx), 10, "Nenhum pedido nesse filtro.");
  abas($("#abas-pedidos", alvo), [["todos", "Todos"], ["informacao", "Informações"], ["convocacao", "Convocações e convites"], ["no-prazo", "Respondidos no prazo"],
    ["fora-do-prazo", "Respondidos fora do prazo"], ["vencido", "Prazo vencido sem resposta"], ["aguardando", "Aguardando resposta"]].map(([valor, rotulo]) => ({ valor, rotulo })), mostrar);
  mostrar("todos");
}

async function contexto() {
  const [deps, sens, fora, resumo] = await Promise.all([carregar("dados/deputados.json").catch(() => []), carregar("dados/senadores.json").catch(() => []),
    carregar("dados/ministros_autores.json").catch(() => ({})), carregar("dados/ministerios.json").catch(() => [])]);
  return { deputados: new Map(deps.map((d) => [String(d.id), d.nome])), senadores: new Map(sens.map((s) => [String(s.id), s.nome])), fora,
    nomes: Object.fromEntries(resumo.map((m) => [m.pasta, m.nome])) };
}

const nomeCargo = (c) => c.cargo.replace(/^Ministr[oa] de Estado\s*/i, "Ministro de Estado ").trim();
const semPrazo = `Sem prazo: pode ser exonerado a qualquer momento <span class="fonte-link"><span class="rotulo-fonte">Fonte</span> <a href="${linkCF(84)}" rel="noopener">Constituição Federal, art. 84, I</a></span>`;

const fonteWikipedia = (c) => `<span class="fonte-link"><span class="rotulo-fonte">Fonte</span> ${urlSegura(c.inicioUrl) ? `<a href="${esc(c.inicioUrl)}" rel="noopener">Wikipédia</a>` : "Wikipédia"}</span>`;

/* Início do cargo: a posse (Wikipédia), quando consta; senão o da licença do parlamentar ou o dia em que a coleta viu o nome na lista do Planalto. */
function textoInicio(c, parlamentar) {
  if (c.inicioFonte === "wikipedia") return `${esc(data(c.inicio, true))} (data da posse) ${fonteWikipedia(c)}`;
  if (c.inicioFonte === "licenca") {
    const api = parlamentar?.casa === "senado" ? `${SENADO_API}/senador/lista/afastados.json` : `${CAMARA_API}/deputados/${encodeURIComponent(parlamentar?.id || "")}/historico`;
    return `${esc(data(c.inicio, true))} (aproximada: dia em que se licenciou do mandato) <span class="fonte-link"><span class="rotulo-fonte">Fonte</span> <a href="${esc(api)}" rel="noopener">${parlamentar?.casa === "senado" ? "afastamentos no Senado" : "histórico na Câmara"}</a></span>`;
  }
  return `${esc(data(c.inicio, true))} (aproximada: dia em que o nome apareceu na lista do Planalto; o Planalto não publica a data da posse) <span class="fonte-link"><span class="rotulo-fonte">Fonte</span> <a href="${PLANALTO}" rel="noopener">Ministros e Ministras (Planalto)</a></span>`;
}

export async function paginaMinistro() {
  const alvo = $("#conteudo");
  const id = param("id");
  let m, ctx, pastas;
  try {
    if (!idValido(id)) throw new Error("Endereço incompleto");
    m = await carregar(`dados/ministro/${id}.json`);
    [ctx, pastas] = await Promise.all([contexto(), Promise.all(m.cargos.map((c) => carregar(`dados/ministerio/${encodeURIComponent(c.pasta)}.json`)))]);
  } catch (e) { return erro(alvo, e); }

  const atual = m.cargos.find((c) => c.atual) || m.cargos[0];
  document.title = `${m.nome}, ${nomeCargo(atual)} | Minha Bancada`;
  const parl = m.parlamentar;
  const casaParl = parl?.casa === "senado" ? "senador" : "deputado federal";
  const paginaParl = parl ? (parl.casa === "senado" ? `politico.html?f=senado&i=${encodeURIComponent(parl.id)}` : `deputado.html?id=${encodeURIComponent(parl.id)}`) : null;
  const pedidosDe = (c, i) => {
    const todos = new Map(pastas[i].requerimentos.map((r) => [r.id, r]));
    return c.requerimentos.map((rid) => todos.get(rid)).filter(Boolean);
  };

  const cargos = m.cargos.map((c) => `
    <dt>${c.atual ? "Cargo" : "Cargo anterior"}</dt><dd>${esc(nomeCargo(c))} <span class="fonte-link"><span class="rotulo-fonte">Fonte</span> <a href="${PLANALTO}" rel="noopener">Ministros e Ministras (Planalto)</a></span><br>
      <a href="ministerios.html?pasta=${encodeURIComponent(c.pasta)}">Ver o ministério e os pedidos feitos à pasta</a></dd>
    ${itemFicha(["No cargo desde", textoInicio(c, parl), true])}
    ${c.nomeadoPor ? itemFicha(["Nomeado por", `${esc(c.nomeadoPor)}, presidente na data da posse ${fonteWikipedia(c)}`, true]) : ""}
    ${itemFicha(["No cargo até", c.atual ? semPrazo : `${esc(data(c.fim, true))} (último dia em que o nome constava na lista do Planalto) <span class="fonte-link"><span class="rotulo-fonte">Fonte</span> <a href="${PLANALTO}" rel="noopener">Ministros e Ministras (Planalto)</a></span>`, true])}`).join("");

  const painelPerfil = `<h2>Ficha</h2>
    <dl class="ficha">${cargos}
      ${parl ? `<dt>Mandato</dt><dd>Licenciado do mandato de ${casaParl}: <a href="${paginaParl}">ver a página parlamentar</a></dd>` : ""}
    </dl>
    ${fontes([["Ministros e Ministras (Planalto)", PLANALTO]])}`;

  const painelEleicao = `<section class="painel"><div class="painel-titulo"><h2>Quem o elegeu?</h2></div>
    <p>${esc(m.nome)} não foi eleito para este cargo. Ministro de Estado é <b>indicado e nomeado pelo Presidente da República</b>, que também pode exonerá-lo.</p>
    ${m.cargos.map((c) => `<p>${esc(nomeCargo(c))}: ${c.inicioFonte === "wikipedia" ? `tomou posse em ${esc(data(c.inicio, true))}, nomeado por ${esc(c.nomeadoPor)}` : c.inicioFonte === "licenca" ? `licenciou-se do mandato em ${esc(data(c.inicio, true))}` : `consta na lista do Planalto desde ${esc(data(c.inicio, true))}`}. ${semFonte("data oficial da nomeação, publicada no Diário Oficial da União")}</p>`).join("")}
    ${fontes([["Constituição Federal, art. 84, I", linkCF(84)], ["Ministros e Ministras (Planalto)", PLANALTO], ...(m.cargos.some((c) => c.inicioFonte === "wikipedia") ? [["Wikipédia (posse e nomeação)", "https://pt.wikipedia.org/wiki/Gabinete_do_Brasil"]] : [])])}</section>`;

  const painelContas = `<section class="painel"><div class="painel-titulo"><h2>Prestação de contas</h2></div>
    <p>Pedidos de informação, convocações e convites do Congresso ligados a ${esc(m.nome)}. Só entram aqui os pedidos que citam o nome ou foram feitos depois ${m.cargos.length === 1 ? "do início no cargo" : "do início de cada cargo"}; como o Planalto não publica a data da posse, os pedidos anteriores à pasta ficam na página do ministério.</p>
    <div id="pedidos"></div></section>`;

  alvo.innerHTML = `
    <section class="perfil">
      ${foto({ nome: m.nome }, true)}
      <div><h1>${esc(m.nome)}</h1><p class="sub">${esc(nomeCargo(atual))}</p></div>
    </section>
    <div class="abas-pagina" role="tablist" aria-label="Seções do perfil">
      <button type="button" role="tab" id="aba-perfil" aria-controls="painel-perfil" data-aba="perfil">Perfil</button>
      <button type="button" role="tab" id="aba-eleicao" aria-controls="painel-eleicao" data-aba="eleicao">Quem o elegeu?</button>
      <button type="button" role="tab" id="aba-contas" aria-controls="painel-contas" data-aba="contas">Prestação de contas <small>${numeroBr(m.cargos.reduce((n, c) => n + c.requerimentos.length, 0))}</small></button>
    </div>
    <div role="tabpanel" id="painel-perfil" aria-labelledby="aba-perfil">${painelPerfil}</div>
    <div role="tabpanel" id="painel-eleicao" aria-labelledby="aba-eleicao" hidden>${painelEleicao}</div>
    <div role="tabpanel" id="painel-contas" aria-labelledby="aba-contas" hidden>${painelContas}</div>`;
  ligarAbas(alvo);
  const lista = m.cargos.flatMap((c, i) => pedidosDe(c, i)).sort((a, b) => (b.data || "").localeCompare(a.data || ""));
  montarPedidos($("#pedidos"), lista, ctx);
}

export async function paginaMinisterios() {
  const alvo = $("#conteudo");
  const pasta = param("pasta");
  if (pasta) return paginaMinisterio(alvo, pasta);
  let lista;
  try { lista = await carregar("dados/ministerios.json"); } catch (e) { return erro(alvo, e); }
  const total = lista.reduce((n, m) => n + m.total, 0);
  alvo.innerHTML = `
    <section class="abertura"><h1>Ministérios</h1>
      <p>Os ministros de Estado em exercício, segundo a lista do Planalto, e os pedidos do Congresso a cada pasta desde 2023: requerimentos de informação, convocações e convites, com o prazo e a resposta de cada um.</p></section>
    <p class="contagem">${lista.length} pastas, ${numeroBr(total)} pedidos</p>
    <div class="rolagem"><table class="tabela"><thead><tr><th>Ministério</th><th>Ministro</th><th>Pedidos</th><th>Informações respondidas</th><th>Convocações e convites</th></tr></thead><tbody>
      ${lista.map((m) => `<tr><td><a href="ministerios.html?pasta=${encodeURIComponent(m.pasta)}">${esc(m.nome)}</a></td>
        <td>${m.ministro ? `<a href="ministro.html?id=${encodeURIComponent(m.ministro.pessoa)}">${esc(m.ministro.nome)}</a>` : "—"}</td>
        <td>${numeroBr(m.total)}</td><td>${m.informacao ? `<b>${numeroBr(m.respondidos)}</b> de ${numeroBr(m.informacao)} (${pct(m.respondidos, m.informacao)})` : "—"}</td><td>${numeroBr(m.convocacao)}</td></tr>`).join("")}
    </tbody></table></div>
    <p class="nota-lista">Cada pedido conta na pasta que a ementa cita primeiro. A resposta de um requerimento de informação só é coletada para os da Câmara; os do Senado aparecem sem esse dado.
      ${fontes([["Ministros e Ministras (Planalto)", PLANALTO], ["Requerimentos (arquivos da Câmara)", "https://dadosabertos.camara.leg.br/arquivos"]])}</p>`;
}

async function paginaMinisterio(alvo, pasta) {
  let p, ctx;
  try {
    if (!idValido(pasta)) throw new Error("Endereço incompleto");
    [p, ctx] = await Promise.all([carregar(`dados/ministerio/${pasta}.json`), contexto()]);
  } catch (e) { return erro(alvo, e); }
  document.title = `Ministério: ${p.nome} | Minha Bancada`;
  alvo.innerHTML = `
    <section class="abertura"><h1>${esc(p.nome)}</h1><p><a href="ministerios.html">Todos os ministérios</a></p></section>
    <h2>Ministros</h2>
    ${p.ministros.length ? `<ul class="lista-simples">${p.ministros.map((m) => `<li><a href="ministro.html?id=${encodeURIComponent(m.pessoa)}">${esc(m.nome)}</a>
      <br><span class="quando">${m.atual ? "No cargo" : "Saiu da lista do Planalto"}${m.inicioFonte === "wikipedia" ? `, desde ${esc(data(m.inicio, true))} (posse; nomeado por ${esc(m.nomeadoPor)})` : m.inicioFonte === "licenca" ? `, desde ${esc(data(m.inicio, true))} (dia da licença do mandato)` : `, na lista do Planalto desde ${esc(data(m.inicio, true))} (o Planalto não publica a data da posse)`}${m.fim ? ` até ${esc(data(m.fim, true))}` : ""}</span></li>`).join("")}</ul>`
      : `<p class="vazio">Nenhum ministro desta pasta na lista atual do Planalto.</p>`}
    ${fontes([["Ministros e Ministras (Planalto)", PLANALTO]])}
    <h2>Pedidos do Congresso à pasta</h2>
    <p>Todos os pedidos que citam esta pasta, de quem era o ministro na época ou não. A pasta pode ter mudado de nome ou de titular.</p>
    <div id="pedidos"></div>`;
  montarPedidos($("#pedidos"), p.requerimentos, ctx);
}

/* Aviso na página do parlamentar licenciado para ser ministro (dep.ministro / sen.ministro = id da pessoa). */
export async function avisoLicenca(idPessoa, casa) {
  if (!idValido(idPessoa)) return "";
  try {
    const m = await carregar(`dados/ministro/${idPessoa}.json`);
    const c = m.cargos.find((x) => x.atual);
    if (!c) return "";
    return `<p class="aviso"><b>Licenciado: ${esc(nomeCargo(c))}.</b> ${esc(m.nome)} deixou o exercício do mandato de ${casa} para ocupar o ministério (desde ${esc(data(c.inicio, true))}, data aproximada).
      <a href="ministro.html?id=${encodeURIComponent(idPessoa)}">Ver a página do ministro</a>.</p>`;
  } catch { return ""; }
}
