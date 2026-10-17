/* Minha Bancada — um arquivo para todas as páginas.
   Cada página declara <body data-pagina="..."> e este script monta o resto. */

const VOTOS = {
  sim: { rotulo: "Sim", cor: "var(--sim)" },
  nao: { rotulo: "Não", cor: "var(--nao)" },
  abstencao: { rotulo: "Abstenção", cor: "var(--abstencao)" },
  obstrucao: { rotulo: "Obstrução", cor: "var(--obstrucao)" },
  art17: { rotulo: "Art. 17 (presidência)", cor: "var(--tinta-suave)" },
  outro: { rotulo: "Outro", cor: "var(--tinta-suave)" },
  ausente: { rotulo: "Sem voto registrado", cor: "var(--ausente)" },
};

/* ---------- utilidades ---------- */
const $ = (sel, raiz = document) => raiz.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const reais = (n) => (n ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const reaisCentavos = (n) => (n ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const pct = (a, b) => (b ? Math.round((a / b) * 100) + "%" : "—");
const data = (iso, longo = false) => {
  if (!iso) return "";
  const d = new Date(iso.slice(0, 10) + "T12:00:00Z");
  return d.toLocaleDateString("pt-BR", longo ? { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" } : { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });
};
const semAcento = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const param = (nome) => new URLSearchParams(location.search).get(nome);

async function carregar(caminho) {
  const r = await fetch(caminho, { cache: "no-cache" });
  if (!r.ok) throw new Error(`Não foi possível carregar ${caminho} (${r.status})`);
  return r.json();
}

function foto(dep, grande = false) {
  const classe = "foto" + (grande ? " grande" : "");
  const iniciais = esc(dep.nome.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join(""));
  if (!dep.foto) return `<span class="${classe}" aria-hidden="true">${iniciais}</span>`;
  return `<img class="${classe}" src="${esc(dep.foto)}" alt="" loading="lazy" width="48" height="48"
    onerror="this.outerHTML='<span class=&quot;${classe}&quot; aria-hidden=&quot;true&quot;>${iniciais}</span>'">`;
}

function selo(voto) {
  const v = VOTOS[voto] || VOTOS.outro;
  return `<span class="voto v-${esc(voto)}">${esc(v.rotulo)}</span>`;
}

function legenda(chaves) {
  return `<div class="legenda">${chaves.map((k) => `<span style="--c:${VOTOS[k].cor}">${VOTOS[k].rotulo}</span>`).join("")}</div>`;
}

/* lista que cresce de N em N com um botão */
function listaPaginada(alvo, itens, render, passo = 20, vazio = "Nada por aqui ainda.") {
  let mostrados = 0;
  alvo.innerHTML = itens.length ? `<ul class="itens"></ul>` : `<p class="vazio">${esc(vazio)}</p>`;
  if (!itens.length) return;
  const ul = $("ul", alvo);
  const botao = document.createElement("button");
  botao.className = "mais";
  alvo.append(botao);
  const mais = () => {
    ul.insertAdjacentHTML("beforeend", itens.slice(mostrados, mostrados + passo).map(render).join(""));
    mostrados = Math.min(mostrados + passo, itens.length);
    botao.hidden = mostrados >= itens.length;
    botao.textContent = `Mostrar mais (${itens.length - mostrados} restantes)`;
  };
  botao.addEventListener("click", mais);
  mais();
}

function abas(alvo, opcoes, aoMudar) {
  alvo.innerHTML = opcoes.map((o, i) => `<button type="button" data-v="${esc(o.valor)}" aria-pressed="${i === 0}">${esc(o.rotulo)}</button>`).join("");
  alvo.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    alvo.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
    aoMudar(b.dataset.v);
  });
}

/* ---------- moldura comum ---------- */
function moldura(pagina) {
  const links = [["index.html", "Deputados", "inicio"], ["votacoes.html", "Votações", "votacoes"], ["sobre.html", "Sobre os dados", "sobre"]];
  document.body.insertAdjacentHTML("afterbegin", `
    <header class="topo"><div class="recipiente">
      <a class="marca" href="index.html"><span class="marca-icone" aria-hidden="true">${"<i></i>".repeat(9)}</span>Minha Bancada</a>
      <nav class="nav" aria-label="Principal">${links.map(([h, t, p]) => `<a href="${h}"${p === pagina || (p === "inicio" && pagina === "deputado") || (p === "votacoes" && pagina === "votacao") ? ' aria-current="page"' : ""}>${t}</a>`).join("")}</nav>
    </div></header>`);
  document.body.insertAdjacentHTML("beforeend", `
    <footer class="rodape"><div class="recipiente" id="rodape">
      Dados públicos da <a href="https://dadosabertos.camara.leg.br">API de Dados Abertos da Câmara dos Deputados</a>, atualizados automaticamente.
      Projeto independente, sem vínculo com a Câmara. Encontrou um erro? Confira sempre a fonte oficial.
    </div></footer>`);
  carregar("dados/meta.json").then((m) => {
    if (m.atualizadoEm) $("#rodape").insertAdjacentHTML("beforeend", ` Última atualização: ${new Date(m.atualizadoEm).toLocaleString("pt-BR")}.`);
  }).catch(() => {});
}

function erro(alvo, e) {
  alvo.innerHTML = `<p class="aviso">${esc(e.message)}. Se o site acabou de ser criado, rode a coleta de dados uma vez (veja o README).</p>`;
  console.error(e);
}

/* ---------- página inicial: lista de deputados ---------- */
async function paginaInicio() {
  const alvo = $("#resultado");
  let deps;
  try { deps = await carregar("dados/deputados.json"); } catch (e) { return erro(alvo, e); }

  const ufs = [...new Set(deps.map((d) => d.uf))].sort();
  const partidos = [...new Set(deps.map((d) => d.partido))].sort();
  $("#uf").insertAdjacentHTML("beforeend", ufs.map((u) => `<option>${esc(u)}</option>`).join(""));
  $("#partido").insertAdjacentHTML("beforeend", partidos.map((p) => `<option>${esc(p)}</option>`).join(""));

  // lembra os filtros na URL, para poder compartilhar o link
  const q = new URLSearchParams(location.search);
  for (const k of ["busca", "uf", "partido", "ordem"]) if (q.get(k)) $("#" + k).value = q.get(k);

  const ordenadores = {
    nome: (a, b) => a.nome.localeCompare(b.nome, "pt-BR"),
    participacao: (a, b) => b.votou / (b.votacoes || 1) - a.votou / (a.votacoes || 1),
    proposicoes: (a, b) => b.proposicoes - a.proposicoes,
    gasto: (a, b) => b.gasto - a.gasto,
  };

  function desenhar() {
    const busca = semAcento($("#busca").value.trim());
    const uf = $("#uf").value, partido = $("#partido").value, ordem = $("#ordem").value;
    const filtrados = deps
      .filter((d) => (!uf || d.uf === uf) && (!partido || d.partido === partido) && (!busca || semAcento(d.nome).includes(busca)))
      .sort(ordenadores[ordem]);
    const novo = new URLSearchParams();
    if (busca) novo.set("busca", $("#busca").value.trim());
    if (uf) novo.set("uf", uf);
    if (partido) novo.set("partido", partido);
    if (ordem !== "nome") novo.set("ordem", ordem);
    history.replaceState(null, "", novo.toString() ? "?" + novo : location.pathname);

    $("#contagem").textContent = `${filtrados.length} de ${deps.length} deputados em exercício`;
    if (!filtrados.length) { alvo.innerHTML = `<p class="vazio">Nenhum deputado com esses filtros. Tente limpar a busca ou escolher outro estado.</p>`; return; }
    alvo.innerHTML = `
      <div class="cabecalho-lista" aria-hidden="true"><span></span><span>Deputado</span><span>Votou</span><span class="so-largo">Proposições</span><span class="so-largo">Gastos no ano</span></div>
      <ul class="lista">${filtrados.map((d) => `
        <li><a class="linha-dep" href="deputado.html?id=${d.id}">
          ${foto(d)}
          <span><span class="nome">${esc(d.nome)}</span><br><span class="sigla">${esc(d.partido)}/${esc(d.uf)}</span></span>
          <span class="metrica"><b>${pct(d.votou, d.votacoes)}</b><span>das votações</span></span>
          <span class="metrica so-largo"><b>${d.proposicoes}</b><span>apresentadas</span></span>
          <span class="metrica so-largo"><b>${reais(d.gasto)}</b><span>cota parlamentar</span></span>
        </a></li>`).join("")}</ul>`;
  }
  ["busca", "uf", "partido", "ordem"].forEach((id) => $("#" + id).addEventListener("input", desenhar));
  desenhar();
}

/* ---------- perfil do deputado ---------- */
async function paginaDeputado() {
  const alvo = $("#conteudo");
  const id = param("id");
  let dep, votacoes;
  try {
    [dep, votacoes] = await Promise.all([carregar(`dados/deputado/${encodeURIComponent(id)}.json`), carregar("dados/votacoes.json")]);
  } catch (e) { return erro(alvo, e); }
  document.title = `${dep.nome} (${dep.partido}/${dep.uf}) | Minha Bancada`;

  const meus = new Map(dep.votos.map((v) => [v.id, v.voto]));
  const linhaDoTempo = votacoes.map((v) => ({ ...v, voto: meus.get(v.id) || "ausente" })); // mais recente primeiro
  const contagem = linhaDoTempo.reduce((c, v) => ((c[v.voto] = (c[v.voto] || 0) + 1), c), {});
  const votou = linhaDoTempo.length - (contagem.ausente || 0) - (contagem.obstrucao || 0);
  const desp = dep.despesas;
  const maxTipo = desp.porTipo[0]?.[1] || 1;

  alvo.innerHTML = `
    <section class="perfil">
      ${foto(dep, true)}
      <div>
        <h1>${esc(dep.nome)}</h1>
        <p class="sub"><span class="selo">${esc(dep.partido)}/${esc(dep.uf)}</span> ${dep.situacao ? esc(dep.situacao) : ""}</p>
      </div>
    </section>

    <section class="painel" aria-labelledby="t-painel">
      <div class="painel-titulo">
        <h2 id="t-painel">Votos no Plenário</h2>
        <p>${linhaDoTempo.length} votações nominais${votacoes.length ? `, de ${data(votacoes.at(-1).data)} a ${data(votacoes[0].data)}` : ""}. Da mais antiga para a mais recente.</p>
      </div>
      <div class="faixa" role="list">${[...linhaDoTempo].reverse().map((v) =>
        `<a role="listitem" class="v-${v.voto}" href="votacao.html?id=${encodeURIComponent(v.id)}" title="${esc(data(v.data))}: ${esc(VOTOS[v.voto]?.rotulo)}. ${esc(v.proposicao || "")} ${esc(v.descricao.slice(0, 120))}" aria-label="${esc(data(v.data))}, ${esc(VOTOS[v.voto]?.rotulo)}"></a>`).join("")}</div>
      ${legenda(["sim", "nao", "abstencao", "obstrucao", "ausente"])}
      <div class="numeros">
        <div><b>${pct(votou, linhaDoTempo.length)}</b><span>votou (sim, não ou abstenção)</span></div>
        <div><b>${contagem.sim || 0}</b><span>votos sim</span></div>
        <div><b>${contagem.nao || 0}</b><span>votos não</span></div>
        <div><b>${contagem.ausente || 0}</b><span>sem voto registrado</span></div>
      </div>
    </section>

    <h2 id="votos">Como votou</h2>
    <div class="abas" id="abas-votos"></div>
    <div id="lista-votos"></div>

    <h2 id="proposicoes">Proposições apresentadas <small class="sub">(${dep.proposicoes.length})</small></h2>
    <div class="abas" id="abas-prop"></div>
    <div id="lista-prop"></div>

    <h2 id="gastos">Gastos da cota parlamentar em ${desp.ano}</h2>
    <p>Total no ano: <b>${reaisCentavos(desp.total)}</b>. A cota paga despesas do mandato, como passagens, aluguel de escritório e divulgação.</p>
    <div class="duas-colunas">
      <div>
        <h3>Por tipo de despesa</h3>
        ${desp.porTipo.length ? `<div class="barras">${desp.porTipo.map(([t, v]) => `
          <div><div class="barra-rotulo"><span>${esc(t)}</span><b>${reais(v)}</b></div><div class="barra"><i style="width:${(v / maxTipo) * 100}%"></i></div></div>`).join("")}</div>`
          : `<p class="vazio">Nenhuma despesa registrada neste ano.</p>`}
      </div>
      <div>
        <h3>Maiores fornecedores</h3>
        ${desp.fornecedores.length ? `<div class="rolagem"><table class="tabela"><thead><tr><th>Fornecedor</th><th>Valor</th></tr></thead><tbody>
          ${desp.fornecedores.map(([f, v]) => `<tr><td>${esc(f)}</td><td>${reais(v)}</td></tr>`).join("")}</tbody></table></div>`
          : `<p class="vazio">Sem fornecedores no período.</p>`}
      </div>
    </div>

    <h2>Ficha</h2>
    <dl class="ficha">
      ${dep.nomeCivil ? `<dt>Nome civil</dt><dd>${esc(dep.nomeCivil)}</dd>` : ""}
      ${dep.nascimento ? `<dt>Nascimento</dt><dd>${data(dep.nascimento, true)}${dep.naturalidade ? `, ${esc(dep.naturalidade)}` : ""}</dd>` : ""}
      ${dep.escolaridade ? `<dt>Escolaridade</dt><dd>${esc(dep.escolaridade)}</dd>` : ""}
      ${dep.email ? `<dt>E-mail</dt><dd><a href="mailto:${esc(dep.email)}">${esc(dep.email)}</a></dd>` : ""}
      <dt>Página oficial</dt><dd><a href="https://www.camara.leg.br/deputados/${encodeURIComponent(dep.id)}">camara.leg.br/deputados/${esc(dep.id)}</a></dd>
      ${(dep.redesSociais || []).map((r) => `<dt>Rede social</dt><dd><a href="${esc(r)}" rel="noopener">${esc(r.replace(/^https?:\/\/(www\.)?/, ""))}</a></dd>`).join("")}
    </dl>`;

  const renderVoto = (v) => `<li>
      <span class="quando">${data(v.data)}${v.proposicao ? `, ${esc(v.proposicao)}` : ""}</span>${selo(v.voto)}
      <a class="texto" href="votacao.html?id=${encodeURIComponent(v.id)}">${esc(v.descricao || "Votação sem descrição")}</a></li>`;
  const filtrosVoto = { todos: () => true, sim: (v) => v.voto === "sim", nao: (v) => v.voto === "nao", outros: (v) => ["abstencao", "obstrucao", "art17", "outro"].includes(v.voto), ausente: (v) => v.voto === "ausente" };
  const mostrarVotos = (f) => listaPaginada($("#lista-votos"), linhaDoTempo.filter(filtrosVoto[f]), renderVoto, 15, "Nenhuma votação nesse filtro.");
  abas($("#abas-votos"), [{ valor: "todos", rotulo: "Todas" }, { valor: "sim", rotulo: "Sim" }, { valor: "nao", rotulo: "Não" }, { valor: "outros", rotulo: "Abstenção e obstrução" }, { valor: "ausente", rotulo: "Sem voto" }], mostrarVotos);
  mostrarVotos("todos");

  const tipos = [...new Set(dep.proposicoes.map((p) => p.tipo))].sort();
  const renderProp = (p) => `<li>
      <span class="quando"><b>${esc(p.tipo)} ${esc(p.numero)}/${esc(p.ano)}</b></span>
      <a href="https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=${encodeURIComponent(p.id)}" rel="noopener" style="font-size:14px">Tramitação</a>
      <span class="texto">${esc(p.ementa || "Sem ementa")}</span></li>`;
  const mostrarProp = (t) => listaPaginada($("#lista-prop"), dep.proposicoes.filter((p) => t === "todos" || p.tipo === t), renderProp, 10, "Nenhuma proposição apresentada nesta legislatura.");
  abas($("#abas-prop"), [{ valor: "todos", rotulo: "Todas" }, ...tipos.map((t) => ({ valor: t, rotulo: t }))], mostrarProp);
  mostrarProp("todos");
}

/* ---------- lista de votações ---------- */
function barraPlacar(placar) {
  const total = Object.values(placar).reduce((a, b) => a + b, 0) || 1;
  return `<div class="placar" role="img" aria-label="${Object.entries(placar).map(([k, n]) => `${VOTOS[k]?.rotulo || k}: ${n}`).join(", ")}">
    ${["sim", "nao", "abstencao", "obstrucao", "art17", "outro"].filter((k) => placar[k]).map((k) => `<i style="width:${(placar[k] / total) * 100}%;background:${VOTOS[k].cor}"></i>`).join("")}</div>`;
}

async function paginaVotacoes() {
  const alvo = $("#resultado");
  let lista;
  try { lista = await carregar("dados/votacoes.json"); } catch (e) { return erro(alvo, e); }
  const render = (v) => `<li>
    <span class="quando">${data(v.data)}${v.proposicao ? `, <b>${esc(v.proposicao)}</b>` : ""}</span>
    <span class="quando">${v.aprovada === 1 ? "Aprovada" : v.aprovada === 0 ? "Rejeitada" : ""}</span>
    <a class="texto" href="votacao.html?id=${encodeURIComponent(v.id)}">${esc(v.descricao || "Votação sem descrição")}</a>
    <span class="texto">${barraPlacar(v.placar)}<span class="quando">Sim ${v.placar.sim || 0}, Não ${v.placar.nao || 0}</span></span></li>`;
  const desenhar = () => {
    const b = semAcento($("#busca").value.trim());
    const f = lista.filter((v) => !b || semAcento(`${v.descricao} ${v.proposicao}`).includes(b));
    $("#contagem").textContent = `${f.length} votações nominais no Plenário`;
    listaPaginada(alvo, f, render, 20, "Nenhuma votação encontrada com essa busca.");
  };
  $("#busca").addEventListener("input", desenhar);
  desenhar();
}

/* ---------- detalhe de uma votação ---------- */
async function paginaVotacao() {
  const alvo = $("#conteudo");
  let v;
  try { v = await carregar(`dados/votacao/${encodeURIComponent(param("id"))}.json`); } catch (e) { return erro(alvo, e); }
  document.title = `${v.proposicao || "Votação"} em ${data(v.data)} | Minha Bancada`;
  v.votos.sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
  const partidos = Object.entries(v.porPartido).sort((a, b) => Object.values(b[1]).reduce((x, y) => x + y, 0) - Object.values(a[1]).reduce((x, y) => x + y, 0));

  alvo.innerHTML = `
    <section class="abertura">
      <p>${data(v.data, true)}${v.hora ? `, às ${esc(v.hora)}` : ""}, no Plenário</p>
      <h1 style="max-width:none;font-size:clamp(28px,4.5vw,44px)">${esc(v.proposicao || "Votação no Plenário")}</h1>
      <p class="texto-longo">${esc(v.descricao)}</p>
    </section>
    <section class="painel">
      <div class="painel-titulo"><h2>Placar</h2><p>${v.aprovada === 1 ? "Aprovada" : v.aprovada === 0 ? "Rejeitada" : ""}</p></div>
      ${barraPlacar(v.placar)}
      <div class="numeros">
        <div><b>${v.placar.sim || 0}</b><span>Sim</span></div>
        <div><b>${v.placar.nao || 0}</b><span>Não</span></div>
        <div><b>${v.placar.abstencao || 0}</b><span>Abstenção</span></div>
        <div><b>${v.placar.obstrucao || 0}</b><span>Obstrução</span></div>
      </div>
    </section>
    <h2>Por partido</h2>
    <div class="rolagem"><table class="tabela"><thead><tr><th>Partido</th><th>Sim</th><th>Não</th><th>Abst.</th><th>Obstr.</th></tr></thead><tbody>
      ${partidos.map(([p, c]) => `<tr><td><b>${esc(p)}</b></td><td>${c.sim || 0}</td><td>${c.nao || 0}</td><td>${c.abstencao || 0}</td><td>${c.obstrucao || 0}</td></tr>`).join("")}
    </tbody></table></div>
    <h2>Voto de cada deputado</h2>
    <div class="filtros" style="grid-template-columns:2fr 1fr"><label class="campo">Buscar deputado<input id="busca-dep" type="search" placeholder="Nome, partido ou estado"></label>
      <label class="campo">Voto<select id="filtro-voto"><option value="">Todos</option>${["sim", "nao", "abstencao", "obstrucao"].map((k) => `<option value="${k}">${VOTOS[k].rotulo}</option>`).join("")}</select></label></div>
    <div id="lista-dep"></div>`;

  const render = (d) => `<li><a href="deputado.html?id=${d.id}">${esc(d.nome)}</a>${selo(d.voto)}<span class="quando texto">${esc(d.partido)}/${esc(d.uf)}</span></li>`;
  const desenhar = () => {
    const b = semAcento($("#busca-dep").value.trim()), f = $("#filtro-voto").value;
    listaPaginada($("#lista-dep"), v.votos.filter((d) => (!f || d.voto === f) && (!b || semAcento(`${d.nome} ${d.partido} ${d.uf}`).includes(b))), render, 50, "Nenhum deputado com esse filtro.");
  };
  $("#busca-dep").addEventListener("input", desenhar);
  $("#filtro-voto").addEventListener("input", desenhar);
  desenhar();
}

/* ---------- início ---------- */
const pagina = document.body.dataset.pagina;
moldura(pagina);
({ inicio: paginaInicio, deputado: paginaDeputado, votacoes: paginaVotacoes, votacao: paginaVotacao }[pagina] || (() => {}))();
