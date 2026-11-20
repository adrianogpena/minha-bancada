/* Busca de proposições (projetos, PECs…) e ficha de uma: autores e votações, com os políticos ligados a elas. */
import { $, esc, data, semAcento, param, carregar, urlSegura } from "./util.js";
import { VOTOS, selo, listaPaginada, erro, semDadosLocais, filtrosNaUrl, botaoVoltar } from "./comum.js";
import { TIPOS_PROJETO, CAMARA_API, SENADO_API, fontes, linkTramitacao, linkMateriaSenado, linkParlamentar } from "./apis.js";
import { barraPlacar } from "./votacoes.js";

const DESTINOS = { aprovada: "Aprovada", rejeitada: "Rejeitada/arquivada", tramitando: "Em tramitação", sem: "Sem situação" };
const nomeCasa = (c) => (c === "s" ? "Senado" : "Câmara");
const rotulo = (p) => `${p.t} ${p.n}/${p.a}`;
const DOC_SENADO = "https://legis.senado.leg.br/sdleg-getter/dadosabertos/documento/";
const docSenado = (x) => (!x ? null : x.startsWith("http") ? x : DOC_SENADO + x);   // o coletor guarda só o código do documento
const TIPO_AUTOR = { DEPUTADO: "deputado(a)", COMISSAO: "comissão", PRESIDENTE_REPUBLICA: "Presidente da República", SENADOR: "senador(a) sem ficha no site" };

/* ---------- busca ---------- */
export async function paginaProposicoes() {
  const alvo = $("#resultado");
  let lista;
  try { lista = await carregar("dados/proposicoes.json"); } catch (e) { return erro(alvo, e); }
  const tipos = [...new Set(lista.map((p) => p.t))].sort();
  $("#tipo").innerHTML = `<option value="">Todos</option>${tipos.map((t) => `<option value="${esc(t)}">${esc(t)}${TIPOS_PROJETO[t] ? ` · ${esc(TIPOS_PROJETO[t])}` : ""}</option>`).join("")}`;
  $("#situacao").innerHTML = `<option value="">Todas</option>${Object.entries(DESTINOS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}`;
  const indexada = lista.map((p) => ({ p, texto: semAcento(`${rotulo(p)} ${p.t} ${p.n} ${p.a} ${p.e} ${p.l || ""}`) }));
  const render = (p) => `<li>
    <span class="quando">${nomeCasa(p.c)}, ${esc(p.s || "situação não consultada")}</span>
    <a class="texto" href="proposicao.html?k=${encodeURIComponent(p.k)}"><b>${esc(rotulo(p))}</b>${p.l ? ` (“${esc(p.l)}”)` : ""}${p.e ? `: ${esc(p.e)}` : ""}</a></li>`;
  const desenhar = () => {
    const termos = semAcento($("#busca").value.trim()).split(/\s+/).filter(Boolean);
    const tipo = $("#tipo").value, casa = $("#casa").value, sit = $("#situacao").value;
    const f = indexada.filter(({ p, texto }) => (!tipo || p.t === tipo) && (!casa || p.c === casa) && (!sit || p.d === sit) && termos.every((t) => texto.includes(t))).map((x) => x.p);
    $("#contagem").textContent = `${f.length} proposições`;
    listaPaginada(alvo, f, render, 30, "Nenhuma proposição encontrada com essa busca.");
  };
  filtrosNaUrl(["busca", "tipo", "casa", "situacao"], desenhar);
}

/* ---------- ficha ---------- */
const SEM_NOME = "sem-nome";
const linkPolitico = (a, casa) => (!a.id ? esc(a.nome) : a.id === SEM_NOME ? `<a href="sem-nome.html" title="Parlamentar que não está no nosso banco">${esc(a.nome)}</a>` : `<a href="${linkParlamentar(casa === "s" ? "senado" : "camara", a.id)}">${esc(a.nome)}</a>`);
const siglaUf = (a) => [a.partido || a.pt, a.uf].filter(Boolean).join("/");
const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

/* Quem assinou: total, partidos diferentes e, para quem não tem ficha no site, o tipo de autor que a fonte informa. */
function blocoAutores(autores, casa) {
  if (!autores.length) return `<h2>Autores</h2><p class="vazio">Autoria ainda não coletada.</p>`;
  const partidos = new Set(autores.map((a) => a.partido || a.pt).filter(Boolean));
  const resumo = autores.length > 1 ? `<p class="quando">${plural(autores.length, "autor", "autores")}${partidos.size ? `, de ${plural(partidos.size, "partido", "partidos")}` : ""}.</p>` : "";
  return `<h2>Autores (${autores.length})</h2>${resumo}
    <ul class="itens">${autores.map((a) => `<li>${linkPolitico(a, casa)}${a.principal ? ` <span class="quando">autor principal</span>` : ""}<span class="quando texto">${esc(siglaUf(a) || "")}${a.id && a.id !== SEM_NOME ? "" : `${siglaUf(a) ? " · " : ""}${esc(TIPO_AUTOR[a.tp] || (a.tp ? a.tp.toLowerCase() : "sem ficha no site"))}`}</span></li>`).join("")}</ul>`;
}

/* A mesma matéria na outra Casa: link para a ficha dela no site, quando ela está no índice; senão, para a página oficial. */
function outraCasa(f, senado) {
  if (senado && f.cn) {
    const href = f.cd ? `proposicao.html?k=c-${encodeURIComponent(f.cd)}` : f.cdx ? linkTramitacao(f.cdx) : null;
    return `<p class="texto-longo"><b>Na Câmara dos Deputados:</b> ${href ? `<a href="${esc(href)}"${f.cd ? "" : ` rel="noopener"`}>${esc(f.cn)}</a>` : esc(f.cn)}</p>`;
  }
  if (!senado && f.sf) return `<p class="texto-longo"><b>Veio do Senado:</b> <a href="proposicao.html?k=s-${encodeURIComponent(f.sf)}">ver a matéria no Senado</a></p>`;
  return "";
}

/* O cabeçalho vem do índice; autores e votações, do arquivo do ano; nome, partido e UF, das listas de políticos; placar, das listas de votações. */
export async function paginaProposicao() {
  const alvo = $("#conteudo");
  const k = param("k") || "";
  let p, f, politicos, lista, indice;
  const casa = k[0] === "s" ? "s" : "c", id = k.slice(2), senado = casa === "s";
  try {
    indice = await carregar("dados/proposicoes.json");
    p = indice.find((x) => x.k === k);
    if (!p) throw new Error(`proposição ${k} não encontrada`);
    [f, politicos, lista] = await Promise.all([carregar(`dados/proposicao/${casa}-${p.a}.json`), carregar(senado ? "dados/senadores.json" : "dados/deputados.json"), carregar(senado ? "dados/votacoes_senado.json" : "dados/votacoes.json")]);
  } catch (e) { return semDadosLocais(alvo, e, null); }
  f = f[id] || {};
  let leis = {};
  if (f.ls) { try { leis = await carregar("dados/leis.json"); } catch { /* sem o resumo das leis, a ficha segue sem a seção */ } }
  const quem = new Map(politicos.map((x) => [String(x.id), x]));
  const relator = f.rl ? quem.get(String(f.rl)) : null;   // relator sem ficha no site: o nome continua em "Vida do projeto"
  const nominais = new Map(lista.map((x) => [String(x.id), x]));
  const autores = (f.au || []).map((a) => ({ ...a, ...(a.id ? quem.get(a.id) : {}), principal: !!a.p }));
  const votacoes = (f.v || []).map((v) => ({ ...v, ...(nominais.get(v.id) || {}), nominal: nominais.has(v.id) }));
  const outra = senado ? null : f.sf;   // projeto da Câmara que veio do Senado
  document.title = `${rotulo(p)} | Minha Bancada`;
  alvo.innerHTML = `
    ${botaoVoltar("Proposições", "proposicoes.html")}
    <section class="abertura">
      <p>${nomeCasa(casa)}${f.ap ? `, apresentada em ${data(f.ap)}` : ""}</p>
      <h1 style="max-width:none;font-size:clamp(28px,4.5vw,44px)">${esc(rotulo(p))}</h1>
      ${f.apl ? `<p><b>Apelido:</b> “${esc(f.apl)}”</p>` : ""}
      ${TIPOS_PROJETO[p.t] ? `<p>${esc(TIPOS_PROJETO[p.t])}</p>` : ""}
      <p class="texto-longo">${esc(f.em || p.e)}</p>
      ${f.ed ? `<details class="texto"><summary>Ementa detalhada</summary>${esc(f.ed)}</details>` : ""}
      <p class="texto-longo"><b>Situação:</b> ${esc(p.s || "ainda não consultada")}${f.o ? ` (${esc(f.o)})` : ""}${f.ds ? `, desde ${data(f.ds)}` : `<span class="quando"> · data da situação não informada pela fonte</span>`}</p>
      ${f.dl ? `<p class="texto-longo"><b>Deliberação:</b> ${esc(f.dl.t || "")}${f.dl.d ? ` em ${data(f.dl.d)}` : ""}${f.dl.p ? `; ${esc(f.dl.p.replace(/^À /, "remetida à "))}` : ""}</p>` : ""}
      ${f.ng ? `<p class="texto-longo"><b>Virou norma:</b> ${f.ng.u ? `<a href="${esc(f.ng.u)}" rel="noopener">${esc(f.ng.d || "norma")}</a>` : esc(f.ng.d || "")}${f.ng.dt ? `, assinada em ${data(f.ng.dt)}` : ""}</p>` : ""}
      ${outraCasa(f, senado)}
      ${f.tr ? `<p class="texto-longo"><b>Última tramitação:</b> ${esc(f.tr)}${f.rg ? ` · regime: ${esc(f.rg)}` : ""}</p>` : f.rg ? `<p class="texto-longo"><b>Regime:</b> ${esc(f.rg)}</p>` : ""}
      ${relator ? `<p class="texto-longo"><b>Relator:</b> ${linkPolitico(relator, casa)}${siglaUf(relator) ? ` (${esc(siglaUf(relator))})` : ""}</p>` : ""}
      ${f.tm ? `<p class="texto-longo"><b>Temas:</b> ${esc(f.tm.join(", "))}</p>` : ""}
      ${f.pc ? (f.pc.length > 240 ? `<details class="texto"><summary>Palavras-chave (${f.pc.split(",").length})</summary>${esc(f.pc)}</details>` : `<p class="texto-longo"><b>Palavras-chave:</b> ${esc(f.pc)}</p>`) : ""}
      ${f.pr ? `<p class="texto-longo"><b>Apensada ao projeto principal:</b> <a href="proposicao.html?k=c-${encodeURIComponent(f.pr)}">ver o projeto principal</a></p>` : ""}
    </section>
    ${leisCitadas(f.ls, leis)}
    ${blocoAutores(autores, casa)}
    <h2>Votações (${votacoes.length})</h2>
    ${votacoes.length ? `<ul class="itens">${votacoes.map((v, i) => `<li>
      <span class="quando">${data(v.data)}${v.orgao ? ` · ${esc(v.orgao)}` : ""}${v.aprovada === 1 ? ", aprovada" : v.aprovada === 0 ? ", rejeitada" : ""}</span>
      <span class="texto">${esc(v.descricao || "Votação")}${v.nominal ? barraPlacar(v.placar) : `<span class="quando">Votação simbólica ou em comissão: sem voto individual.</span>`}
        ${v.orientacoes ? `<br><span class="quando">Orientação das lideranças: ${Object.entries(v.orientacoes).map(([b, o]) => `${esc(b)} ${esc(o)}`).join(" · ")}.</span>` : ""}</span>
      ${v.nominal ? `<button type="button" class="mais" data-i="${i}">Ver quem votou</button><div id="votos-${i}"></div>` : ""}</li>`).join("")}</ul>` : `<p class="vazio">Nenhuma votação registrada no Plenário.</p>`}
    <div id="vida"></div>
    ${fontes([["Tramitação oficial", senado ? linkMateriaSenado(id) : linkTramitacao(id)], ["Inteiro teor", f.tx],
      senado ? ["Dados abertos do Senado (autoria e situação)", `${SENADO_API}/processo?codigoMateria=${encodeURIComponent(id)}`] : null,
      outra ? ["Matéria no Senado", linkMateriaSenado(outra)] : null])}`;

  if (senado) vidaNoSenado($("#vida"), id, !!relator);
  else vidaDoProjeto($("#vida"), id, !!relator);

  alvo.addEventListener("click", async (e) => {
    const b = e.target.closest("button[data-i]");
    if (!b) return;
    const v = votacoes[b.dataset.i], saida = $(`#votos-${b.dataset.i}`);
    b.hidden = true;
    saida.textContent = "Carregando…";
    let det;
    try { det = await carregar(`dados/${senado ? "votacao_senado" : "votacao"}/${encodeURIComponent(v.id)}.json`); } catch (err) { return erro(saida, err); }
    const render = (d) => `<li>${d.anterior || (senado && !d.id) ? esc(d.nome) : linkPolitico(d, casa)}${selo(d.voto)}<span class="quando texto">${esc(d.partido)}${d.uf ? `/${esc(d.uf)}` : ""}</span></li>`;
    saida.innerHTML = `<div class="filtros" style="grid-template-columns:2fr 1fr"><label class="campo">Buscar<input type="search" class="b" placeholder="Nome, partido ou estado"></label>
      <label class="campo">Voto<select class="f"><option value="">Todos</option>${["sim", "nao", "abstencao", "obstrucao"].map((x) => `<option value="${x}">${VOTOS[x].rotulo}</option>`).join("")}</select></label></div><div class="l"></div>`;
    const desenhar = () => {
      const t = semAcento($(".b", saida).value.trim()), f = $(".f", saida).value;
      listaPaginada($(".l", saida), det.votos.filter((d) => (!f || d.voto === f) && (!t || semAcento(`${d.nome} ${d.partido} ${d.uf}`).includes(t))), render, 50, "Ninguém com esse filtro.");
    };
    $(".b", saida).addEventListener("input", desenhar);
    $(".f", saida).addEventListener("input", desenhar);
    desenhar();
  });
}


/* Leis que a ementa menciona: cada lei com os próprios links, rotulados com o nome dela (o LexML reúne as versões oficiais;
   Senado e Câmara mostram o texto da norma). A ementa oficial da lei é o resumo. */
function leisCitadas(ids, leis) {
  const itens = (ids || []).map((i) => leis[i]).filter(Boolean);
  if (!itens.length) return "";
  const links = (l) => [[l.u, "LexML"], [l.s, "Senado"], [l.c, "Câmara"]].filter(([u]) => urlSegura(u))
    .map(([u, onde]) => `<a href="${esc(u)}" rel="noopener" aria-label="${esc(l.r)} no ${onde}">${onde}</a>`).join(" · ");
  return `<h2>Leis citadas (${itens.length})</h2><ul class="itens">${itens.map((l) => `<li>
    <span class="texto"><b>${esc(l.r)}</b>${l.e ? `: ${esc(l.e)}` : `<span class="quando"> Resumo ainda não coletado.</span>`}<br>
      <span class="quando">Texto da ${esc(l.r)}:</span> ${links(l)}</span></li>`).join("")}</ul>
    <p class="quando">O resumo é a ementa oficial da lei, não uma interpretação do que o projeto muda nela.</p>`;
}

/* Linha do tempo, relator, comissões e projetos relacionados (coletar.py: coletar_tramitacoes_proposicoes). */
async function vidaDoProjeto(alvo, id, comRelator) {
  let t;
  try { t = await carregar(`dados/tramitacao/${encodeURIComponent(id)}.json`); } catch { return; }
  const eventos = t.eventos || [], orgaos = [...new Set(eventos.map((e) => e[1]).filter(Boolean))];
  const relacionadas = t.relacionadas || [];
  const [tempo, ligar] = linhaDoTempo(eventos.map(([dia, orgao, tipo, situacao, despacho]) => [dia, orgao, situacao, tipo || "Movimentação", despacho]));
  alvo.innerHTML = `<h2>Vida do projeto (${eventos.length} movimentações)</h2>
    ${t.relator && !comRelator ? `<p class="texto-longo"><b>Último relator designado:</b> ${esc(t.relator)}</p>` : ""}
    ${orgaos.length ? `<p class="texto-longo"><b>Por onde passou:</b> ${esc(orgaos.join(", "))}</p>` : ""}
    ${tempo}
    ${relacionadas.length ? `<p class="texto-longo"><b>Proposições relacionadas (${relacionadas.length}):</b> ${relacionadas.map(([rid, rot]) => `<a href="${esc(linkTramitacao(rid))}" rel="noopener">${esc(rot)}</a>`).join(", ")}</p>` : ""}
    ${fontes([["Tramitações (API da Câmara)", `${CAMARA_API}/proposicoes/${encodeURIComponent(id)}/tramitacoes`]])}`;
  ligar();
}

/* Linha do tempo de uma matéria do Senado (coletar.py: coletar_processos_senado): relatoria, situações, informes, documentos e emendas. */
async function vidaNoSenado(alvo, id, comRelator) {
  let t;
  try { t = await carregar(`dados/tramitacao_senado/${encodeURIComponent(id)}.json`); } catch { return; }
  const informes = t.informes || [], situacoes = t.situacoes || [], relatorias = t.relatorias || [];
  const emendas = t.emendas || [], documentos = t.documentos || [], despachos = t.despachos || [];
  const colegiados = [...new Set(situacoes.map((s) => s[4]).concat(informes.map((i) => i[1])).filter(Boolean))];
  const porAutor = Object.entries(emendas.reduce((c, e) => ((c[e[1] || "sem autoria"] = (c[e[1] || "sem autoria"] || 0) + 1), c), {})).sort((a, b) => b[1] - a[1]);
  const api = `${SENADO_API}/processo`;
  const [tempo, ligar] = linhaDoTempo(informes.map(([quando, col, desc]) => [quando ? quando.slice(0, 10) : null, col, null, desc]));
  alvo.innerHTML = `<h2>Vida do projeto (${informes.length} movimentações)</h2>
    ${relatorias.length ? `<p class="texto-longo"><b>${relatorias.length > 1 ? "Relatores" : comRelator ? "Relatoria" : "Relator"}:</b> ${relatorias.map(([cod, nome, pt, uf, sigla, colegiado, tipo, desde, ate, fim]) =>
      `${esc(nome)}${pt ? ` (${esc([pt, uf].filter(Boolean).join("/"))})` : ""}, ${esc((tipo || "relator").toLowerCase())} em ${esc(colegiado || sigla || "")}, de ${data(desde)}${ate ? ` a ${data(ate)}${fim ? ` (${esc(fim.toLowerCase())})` : ""}` : " até hoje"}`).join("; ")}</p>` : ""}
    ${despachos.length ? `<p class="texto-longo"><b>Despacho:</b> ${despachos.map(([dia, prov, destinos, terminativa]) => `${esc(prov || "")}${destinos.length ? ` (${esc(destinos.join(", "))})` : ""}${terminativa ? ", em caráter terminativo" : ""}${dia ? `, em ${data(dia)}` : ""}`).join("; ")}</p>` : ""}
    ${colegiados.length ? `<p class="texto-longo"><b>Por onde passou:</b> ${esc(colegiados.join(", "))}</p>` : ""}
    ${situacoes.length ? `<details class="texto"><summary>Situações (${situacoes.length})</summary><ol class="itens">${[...situacoes].reverse().map(([ini, fim, , desc, col]) =>
      `<li><span class="quando">${data(ini)}${fim ? ` a ${data(fim)}` : " até hoje"}${col ? ` · ${esc(col)}` : ""}</span><span class="texto">${esc(desc || "")}</span></li>`).join("")}</ol></details>` : ""}
    ${tempo}
    ${blocoDocumentos(documentos)}
    ${emendas.length ? `<h3>Emendas (${emendas.length})</h3>
      <p class="quando">Quem mais apresentou: ${porAutor.slice(0, 5).map(([a, n]) => `${esc(a)} (${n})`).join(", ")}.</p>
      <details class="texto"><summary>Ver as ${emendas.length} emendas</summary><ul class="itens">${emendas.map(([num, autoria, dia, tipo, desc, turno, doc, decisao]) =>
        `<li><span class="quando">Emenda ${esc(num)}${dia ? ` · ${data(dia)}` : ""}${turno && turno !== "NORMAL" ? ` · turno ${esc(turno.toLowerCase())}` : ""}</span><span class="texto">${esc(autoria || "")}${tipo ? ` <span class="quando">${esc(tipo.replace(/_/g, " ").toLowerCase())}</span>` : ""}${desc ? `<br>${esc(desc)}` : ""}${decisao ? `<br><b>Decisão:</b> ${esc(decisao)}` : ""}${doc ? `<br><a href="${esc(docSenado(doc))}" rel="noopener">Texto da emenda ${esc(num)}</a>` : ""}</span></li>`).join("")}</ul></details>` : ""}
    ${(t.relacionados || []).length ? `<p class="texto-longo"><b>Requerimentos e matérias relacionadas (${t.relacionados.length}):</b> ${esc(t.relacionados.map(([, s, n, a]) => `${s} ${n}/${a}`).join(", "))}</p>` : ""}
    ${fontes([["Matéria (API do Senado)", t.processo ? `${api}/${encodeURIComponent(t.processo)}` : null], ["Relatoria (API do Senado)", `${api}/relatoria?codigoMateria=${encodeURIComponent(id)}`],
      ["Emendas (API do Senado)", `${api}/emenda?codigoMateria=${encodeURIComponent(id)}`]])}`;
  ligar();
}

/* Documentos da matéria: os principais (texto, pareceres, relatórios) à vista, o resto (requerimentos, listagens, avulsos) num "ver todos". */
const DOC_PRINCIPAL = /^(Projeto|Parecer|Relatório Legislativo|Texto|Substitutivo|Autógrafo)/i;
function blocoDocumentos(documentos) {
  if (!documentos.length) return "";
  const item = ([dia, tipo, ident, autoria, doc]) => `<li><span class="quando">${dia ? data(dia) : "sem data"}${autoria ? ` · ${esc(autoria)}` : ""}</span><span class="texto"><a href="${esc(docSenado(doc))}" rel="noopener">${esc(tipo || "Documento")}</a>${ident && ident !== tipo ? `<br><span class="quando">${esc(ident)}</span>` : ""}</span></li>`;
  const todos = [...documentos].reverse(), principais = todos.filter((d) => DOC_PRINCIPAL.test(d[1] || ""));
  return `<h3>Documentos (${documentos.length})</h3>
    ${principais.length ? `<ul class="itens">${principais.map(item).join("")}</ul>` : ""}
    ${todos.length > principais.length ? `<details class="texto"><summary>${principais.length ? `Ver todos os ${todos.length} documentos` : `Ver os ${todos.length} documentos`} (requerimentos, listagens, ofícios…)</summary><ul class="itens">${todos.map(item).join("")}</ul></details>` : ""}`;
}

/* Movimentações, a mais recente primeiro: 15 à vista e o resto num botão. Cada evento: [dia, órgão, situação, descrição, detalhe].
   Devolve o HTML e a função que liga o botão (o resto entra na lista ao clicar). */
function linhaDoTempo(eventos) {
  const lista = [...eventos].reverse();
  const evento = ([dia, orgao, situacao, desc, detalhe]) => `<li><span class="quando">${dia ? data(dia) : "sem data"}${orgao ? ` · ${esc(orgao)}` : ""}${situacao ? ` · ${esc(situacao)}` : ""}</span>
    <span class="texto">${esc(desc || "Movimentação")}${detalhe ? `<br><span class="quando">${esc(detalhe)}</span>` : ""}</span></li>`;
  const html = `<ol class="itens" id="linha-tempo">${lista.slice(0, 15).map(evento).join("")}</ol>
    ${lista.length > 15 ? `<button type="button" class="mais" id="mais-tempo">Ver as ${lista.length - 15} movimentações mais antigas</button>` : ""}`;
  const ligar = () => {
    const mais = $("#mais-tempo");
    if (mais) mais.addEventListener("click", () => {
      $("#linha-tempo").insertAdjacentHTML("beforeend", lista.slice(15).map(evento).join(""));
      mais.hidden = true;
    });
  };
  return [html, ligar];
}
