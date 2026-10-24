/* Busca de proposições (projetos, PECs…) e ficha de uma: autores e votações, com os políticos ligados a elas. */
import { $, esc, data, semAcento, param, carregar } from "./util.js";
import { VOTOS, selo, listaPaginada, erro, semDadosLocais, filtrosNaUrl, botaoVoltar } from "./comum.js";
import { TIPOS_PROJETO, fontes, linkTramitacao, linkMateriaSenado } from "./apis.js";
import { barraPlacar } from "./votacoes.js";

const DESTINOS = { aprovada: "Aprovada", rejeitada: "Rejeitada/arquivada", tramitando: "Em tramitação", sem: "Sem situação" };
const nomeCasa = (c) => (c === "s" ? "Senado" : "Câmara");
const rotulo = (p) => `${p.t} ${p.n}/${p.a}`;

/* ---------- busca ---------- */
export async function paginaProposicoes() {
  const alvo = $("#resultado");
  let lista;
  try { lista = await carregar("dados/proposicoes.json"); } catch (e) { return erro(alvo, e); }
  const tipos = [...new Set(lista.map((p) => p.t))].sort();
  $("#tipo").innerHTML = `<option value="">Todos</option>${tipos.map((t) => `<option value="${esc(t)}">${esc(t)}${TIPOS_PROJETO[t] ? ` · ${esc(TIPOS_PROJETO[t])}` : ""}</option>`).join("")}`;
  $("#situacao").innerHTML = `<option value="">Todas</option>${Object.entries(DESTINOS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}`;
  const indexada = lista.map((p) => ({ p, texto: semAcento(`${rotulo(p)} ${p.t} ${p.n} ${p.a} ${p.e}`) }));
  const render = (p) => `<li>
    <span class="quando">${nomeCasa(p.c)}, ${esc(p.s || "situação não consultada")}</span>
    <a class="texto" href="proposicao.html?k=${encodeURIComponent(p.k)}"><b>${esc(rotulo(p))}</b>${p.e ? `: ${esc(p.e)}` : ""}</a></li>`;
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
const linkPolitico = (a, casa) => (!a.id ? esc(a.nome) : `<a href="${casa === "s" ? `politico.html?f=senado&i=${encodeURIComponent(a.id)}` : `deputado.html?id=${encodeURIComponent(a.id)}`}">${esc(a.nome)}</a>`);

/* O cabeçalho vem do índice; autores e votações, do arquivo do ano; nome, partido e UF, das listas de políticos; placar, das listas de votações. */
export async function paginaProposicao() {
  const alvo = $("#conteudo");
  const k = param("k") || "";
  let p, f, politicos, lista;
  const casa = k[0] === "s" ? "s" : "c", id = k.slice(2), senado = casa === "s";
  try {
    p = (await carregar("dados/proposicoes.json")).find((x) => x.k === k);
    if (!p) throw new Error(`proposição ${k} não encontrada`);
    [f, politicos, lista] = await Promise.all([carregar(`dados/proposicao/${casa}-${p.a}.json`), carregar(senado ? "dados/senadores.json" : "dados/deputados.json"), carregar(senado ? "dados/votacoes_senado.json" : "dados/votacoes.json")]);
  } catch (e) { return semDadosLocais(alvo, e, null); }
  f = f[id] || {};
  const quem = new Map(politicos.map((x) => [String(x.id), x]));
  const nominais = new Map(lista.map((x) => [String(x.id), x]));
  const autores = (f.au || []).map((a) => ({ ...a, ...(a.id ? quem.get(a.id) : {}), principal: !!a.p }));
  const votacoes = (f.v || []).map((v) => ({ ...v, ...(nominais.get(v.id) || {}), nominal: nominais.has(v.id) }));
  document.title = `${rotulo(p)} | Minha Bancada`;
  alvo.innerHTML = `
    ${botaoVoltar("Proposições", "proposicoes.html")}
    <section class="abertura">
      <p>${nomeCasa(casa)}${f.ap ? `, apresentada em ${data(f.ap)}` : ""}</p>
      <h1 style="max-width:none;font-size:clamp(28px,4.5vw,44px)">${esc(rotulo(p))}</h1>
      ${TIPOS_PROJETO[p.t] ? `<p>${esc(TIPOS_PROJETO[p.t])}</p>` : ""}
      <p class="texto-longo">${esc(p.e)}</p>
      <p class="texto-longo"><b>Situação:</b> ${esc(p.s || "ainda não consultada")}${f.o ? ` (${esc(f.o)})` : ""}</p>
    </section>
    <h2>Autores (${autores.length})</h2>
    ${autores.length ? `<ul class="itens">${autores.map((a) => `<li>${linkPolitico(a, casa)}${a.principal ? ` <span class="quando">autor principal</span>` : ""}<span class="quando texto">${esc([a.partido, a.uf].filter(Boolean).join("/") || (a.id ? "" : "sem ficha no site"))}</span></li>`).join("")}</ul>` : `<p class="vazio">Autoria ainda não coletada.</p>`}
    <h2>Votações (${votacoes.length})</h2>
    ${votacoes.length ? `<ul class="itens">${votacoes.map((v, i) => `<li>
      <span class="quando">${data(v.data)}${v.aprovada === 1 ? ", aprovada" : v.aprovada === 0 ? ", rejeitada" : ""}</span>
      <span class="texto">${esc(v.descricao || "Votação")}${v.nominal ? barraPlacar(v.placar) : `<span class="quando">Votação simbólica ou em comissão: sem voto individual.</span>`}</span>
      ${v.nominal ? `<button type="button" class="mais" data-i="${i}">Ver quem votou</button><div id="votos-${i}"></div>` : ""}</li>`).join("")}</ul>` : `<p class="vazio">Nenhuma votação registrada no Plenário.</p>`}
    ${fontes([["Tramitação oficial", senado ? linkMateriaSenado(id) : linkTramitacao(id)]])}`;

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
