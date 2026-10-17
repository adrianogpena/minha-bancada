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
  const links = [["index.html", "Políticos", "inicio"], ["camara.html", "Câmara", "camara"], ["votacoes.html", "Votações", "votacoes"], ["sobre.html", "Sobre os dados", "sobre"]];
  const atual = { deputado: "camara", votacao: "votacoes", politico: "inicio" }[pagina] || pagina;
  document.body.insertAdjacentHTML("afterbegin", `
    <header class="topo"><div class="recipiente">
      <a class="marca" href="index.html"><span class="marca-icone" aria-hidden="true">${"<i></i>".repeat(9)}</span>Minha Bancada</a>
      <nav class="nav" aria-label="Principal">${links.map(([h, t, p]) => `<a href="${h}"${p === atual ? ' aria-current="page"' : ""}>${t}</a>`).join("")}</nav>
    </div></header>`);
  document.body.insertAdjacentHTML("beforeend", `
    <footer class="rodape"><div class="recipiente" id="rodape">
      Dados públicos do <a href="https://dadosabertos.tse.jus.br">TSE</a>, da <a href="https://dadosabertos.camara.leg.br">Câmara dos Deputados</a> e do <a href="https://www12.senado.leg.br/dados-abertos">Senado Federal</a>, atualizados automaticamente.
      Projeto independente, sem vínculo com órgãos públicos ou partidos. Encontrou um erro? Confira sempre a fonte oficial.
    </div></footer>`);
  carregar("dados/meta.json").then((m) => {
    if (m.atualizadoEm) $("#rodape").insertAdjacentHTML("beforeend", ` Última atualização: ${new Date(m.atualizadoEm).toLocaleString("pt-BR")}.`);
  }).catch(() => {});
}

function erro(alvo, e) {
  alvo.innerHTML = `<p class="aviso">${esc(e.message)}. Se o site acabou de ser criado, rode a coleta de dados uma vez (veja o README).</p>`;
  console.error(e);
}

/* ---------- Câmara: lista de deputados federais ---------- */
async function paginaCamara() {
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
const CAMARA_API = "https://dadosabertos.camara.leg.br/api/v2";
const resultado = (a) => (a === 1 ? ["Aprovada", "aprovada"] : a === 0 ? ["Rejeitada", "rejeitada"] : ["Sem resultado informado", "sem"]);

// projetos de verdade; o resto (requerimentos, emendas, pareceres) só aparece em "Outros documentos"
const TIPOS_PROJETO = { PL: "Projeto de lei", PLP: "Projeto de lei complementar", PEC: "Proposta de emenda à Constituição", PDL: "Projeto de decreto legislativo",
  PRC: "Projeto de resolução", PLC: "Projeto de lei da Câmara", PLS: "Projeto de lei do Senado", PRS: "Projeto de resolução do Senado", PDS: "Projeto de decreto legislativo do Senado", PLN: "Projeto de lei do Congresso", PFC: "Proposta de fiscalização e controle", PLV: "Projeto de lei de conversão", MPV: "Medida provisória" };

// resume a situação da Câmara em um destino compreensível
function desfecho(p) {
  const s = semAcento(p.sit || "");
  if (!p.sit) return ["Situação ainda não consultada", "sem"];
  if (/tramitacao encerrada/.test(s)) return ["Tramitação encerrada", "sem"];
  if (/^(aprovad|sancionad|promulgad)/.test(s)) return ["Aprovada", "aprovada"];
  if (/^rejeitad/.test(s)) return ["Rejeitada", "rejeitada"];
  if (/transformad[ao] em norma|transformad[ao] em lei|sancionad/.test(s)) return ["Virou lei", "aprovada"];
  if (/arquivad/.test(s)) return ["Arquivada", "rejeitada"];
  if (/retirad/.test(s)) return ["Retirada pelo autor", "rejeitada"];
  if (/vetad/.test(s)) return ["Vetada", "rejeitada"];
  if (/prejudicad/.test(s)) return ["Prejudicada", "rejeitada"];
  if (/remetid[ao] a camara/.test(s)) return ["Aprovada no Senado", "aprovada"];
  if (/aguardando sancao|remetid.*(sancao|senado)/.test(s)) return ["Aprovada na Câmara", "aprovada"];
  return ["Em tramitação", "tramitando"];
}

const linkTramitacao = (id) => `https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=${encodeURIComponent(id)}`;

function fontes(links) {
  if (!links.filter(Boolean).length) return "";
  return `<span class="fontes">Fonte: ${links.filter(Boolean).map(([t, h]) => `<a href="${esc(h)}" rel="noopener">${esc(t)}</a>`).join(" · ")}</span>`;
}

async function paginaDeputado() {
  const alvo = $("#conteudo");
  const id = param("id");
  let dep, votacoes;
  try {
    [dep, votacoes] = await Promise.all([carregar(`dados/deputado/${encodeURIComponent(id)}.json`), carregar("dados/votacoes.json")]);
  } catch (e) { return erro(alvo, e); }
  document.title = `${dep.nome} (${dep.partido}/${dep.uf}) | Minha Bancada`;

  const meus = new Map(dep.votos.map((v) => [v.id, v.voto]));
  const desp = dep.despesas;
  const maxTipo = desp.porTipo[0]?.[1] || 1;
  const painelPerfil = `
    <h2>Gastos da cota parlamentar em ${desp.ano}</h2>
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
    ${fontes([["Cota parlamentar (API da Câmara)", `${CAMARA_API}/deputados/${encodeURIComponent(dep.id)}/despesas?ano=${desp.ano}`], ["Portal da Câmara", `https://www.camara.leg.br/deputados/${encodeURIComponent(dep.id)}`]])}

    <h2>Ficha</h2>
    <dl class="ficha">
      ${dep.nomeCivil ? `<dt>Nome civil</dt><dd>${esc(dep.nomeCivil)}</dd>` : ""}
      ${dep.nascimento ? `<dt>Nascimento</dt><dd>${data(dep.nascimento, true)}${dep.naturalidade ? `, ${esc(dep.naturalidade)}` : ""}</dd>` : ""}
      ${dep.escolaridade ? `<dt>Escolaridade</dt><dd>${esc(dep.escolaridade)}</dd>` : ""}
      ${dep.email ? `<dt>E-mail</dt><dd><a href="mailto:${esc(dep.email)}">${esc(dep.email)}</a></dd>` : ""}
      <dt>Página oficial</dt><dd><a href="https://www.camara.leg.br/deputados/${encodeURIComponent(dep.id)}">camara.leg.br/deputados/${esc(dep.id)}</a></dd>
      ${(dep.redesSociais || []).map((r) => `<dt>Rede social</dt><dd><a href="${esc(r)}" rel="noopener">${esc(r.replace(/^https?:\/\/(www\.)?/, ""))}</a></dd>`).join("")}
    </dl>`;

  montarParlamentar(alvo, {
    nome: dep.nome, foto: dep,
    subtitulo: `<span class="selo">${esc(dep.partido)}/${esc(dep.uf)}</span> ${dep.situacao ? esc(dep.situacao) : ""}`,
    painelPerfil, rotuloPerfil: "Perfil e gastos",
    linhaDoTempo: votacoes.map((v) => ({ ...v, voto: meus.get(v.id) || "ausente" })), // mais recente primeiro
    proposicoes: dep.proposicoes, tipoProjeto: (p) => !!TIPOS_PROJETO[p.tipo],
    textoLegislatura: "como autor ou coautor nesta legislatura (desde fev. de 2023)",
    aviso: "A situação vem da ficha de tramitação da Câmara e é atualizada aos poucos todo dia.",
    fonteTramitacao: "Ficha de tramitação (Câmara)",
    linkTramitacao: (p) => linkTramitacao(p.id),
    linkApi: (p) => `${CAMARA_API}/proposicoes/${encodeURIComponent(p.id)}`,
    hrefVotacao: (v) => `votacao.html?id=${encodeURIComponent(v.id)}`,
    fontesVotacao: (v) => [["Votos de cada deputado (API da Câmara)", `${CAMARA_API}/votacoes/${encodeURIComponent(v.id)}/votos`], ["Detalhes da votação", `${CAMARA_API}/votacoes/${encodeURIComponent(v.id)}`], v.propId ? ["Tramitação do projeto", linkTramitacao(v.propId)] : null],
  });
}

/* Troca entre as abas de uma página de pessoa; a aba escolhida fica no #endereço. */
function ligarAbas(alvo) {
  function irParaAba(nome, atualizarUrl = true) {
    if (!$(`#painel-${nome}`)) nome = "perfil";
    alvo.querySelectorAll("[data-aba]").forEach((b) => b.setAttribute("aria-selected", b.dataset.aba === nome));
    alvo.querySelectorAll("[role=tabpanel]").forEach((p) => (p.hidden = p.id !== `painel-${nome}`));
    if (atualizarUrl) history.replaceState(null, "", nome === "perfil" ? location.pathname + location.search : `${location.pathname}${location.search}#${nome}`);
  }
  $(".abas-pagina", alvo).addEventListener("click", (e) => { const b = e.target.closest("[data-aba]"); if (b) irParaAba(b.dataset.aba); });
  irParaAba(location.hash.slice(1), false);
  window.addEventListener("hashchange", () => irParaAba(location.hash.slice(1), false));
}

/* As três abas (perfil, votações, propostas) de um parlamentar. Serve a deputados e senadores. */
function montarParlamentar(alvo, c) {
  const nome = c.nome, linhaDoTempo = c.linhaDoTempo;
  const projetos = c.proposicoes.filter(c.tipoProjeto), outros = c.proposicoes.filter((p) => !c.tipoProjeto(p));
  const contagem = linhaDoTempo.reduce((m, v) => ((m[v.voto] = (m[v.voto] || 0) + 1), m), {});
  const votou = linhaDoTempo.length - (contagem.ausente || 0) - (contagem.obstrucao || 0);

  const painelVotacoes = `
    <section class="painel" aria-labelledby="t-painel">
      <div class="painel-titulo">
        <h2 id="t-painel">Votos no Plenário</h2>
        <p>${linhaDoTempo.length} votações nominais${linhaDoTempo.length ? `, de ${data(linhaDoTempo.at(-1).data)} a ${data(linhaDoTempo[0].data)}` : ""}. Da mais antiga para a mais recente.</p>
      </div>
      <div class="faixa" role="list">${[...linhaDoTempo].reverse().map((v) =>
        `<a role="listitem" class="v-${v.voto}" ${c.hrefVotacao ? `href="${esc(c.hrefVotacao(v))}"` : ""} title="${esc(data(v.data))}: ${esc(VOTOS[v.voto]?.rotulo)}. ${esc(v.proposicao || "")} ${esc((v.descricao || "").slice(0, 120))}" aria-label="${esc(data(v.data))}, ${esc(VOTOS[v.voto]?.rotulo)}"></a>`).join("")}</div>
      ${legenda(["sim", "nao", "abstencao", "obstrucao", "ausente"])}
      <div class="numeros">
        <div><b>${pct(votou, linhaDoTempo.length)}</b><span>votou (sim, não ou abstenção)</span></div>
        <div><b>${contagem.sim || 0}</b><span>votos sim</span></div>
        <div><b>${contagem.nao || 0}</b><span>votos não</span></div>
        <div><b>${contagem.abstencao || 0}</b><span>abstenções</span></div>
        <div><b>${(contagem.obstrucao || 0) + (contagem.art17 || 0) + (contagem.outro || 0)}</b><span>obstrução e outros</span></div>
        <div><b>${contagem.ausente || 0}</b><span>sem voto registrado</span></div>
      </div>
    </section>
    <h2 id="votos">Como votou</h2>
    <p>Cada linha mostra o voto de ${esc(nome)}, o resultado final da votação e o placar geral.</p>
    <div class="abas" id="abas-votos"></div>
    <div id="lista-votos"></div>`;

  const painelPropostas = `
    <section class="painel">
      <div class="painel-titulo"><h2>Propostas de ${esc(nome)}</h2>
        <p>${c.proposicoes.length} documentos apresentados ${esc(c.textoLegislatura)}.</p></div>
      <div class="numeros" id="numeros-prop"></div>
    </section>
    <h2 id="proposicoes">Projetos <small class="sub">(${projetos.length})</small></h2>
    <p>Projetos de lei, emendas à Constituição e similares. ${esc(c.aviso)}</p>
    <div class="abas" id="abas-proj"></div>
    <div id="lista-proj"></div>
    ${c.semOutros ? `<p class="aviso">${esc(c.semOutros)}</p>` : `
    <h2>Outros documentos <small class="sub">(${outros.length})</small></h2>
    <p>Requerimentos, indicações, emendas a outros projetos, pareceres e afins. Cada um tem a tramitação como fonte.</p>
    <div class="abas" id="abas-outros"></div>
    <div id="lista-outros"></div>`}`;

  alvo.innerHTML = `
    <section class="perfil">
      ${foto(c.foto, true)}
      <div>
        <h1>${esc(nome)}</h1>
        <p class="sub">${c.subtitulo}</p>
      </div>
    </section>
    ${c.antes || ""}
    <div class="abas-pagina" role="tablist" aria-label="Seções do perfil">
      <button type="button" role="tab" id="aba-perfil" aria-controls="painel-perfil" data-aba="perfil">${esc(c.rotuloPerfil)}</button>
      <button type="button" role="tab" id="aba-votacoes" aria-controls="painel-votacoes" data-aba="votacoes">Votações <small>${linhaDoTempo.length}</small></button>
      <button type="button" role="tab" id="aba-propostas" aria-controls="painel-propostas" data-aba="propostas">Propostas <small>${c.proposicoes.length}</small></button>
    </div>
    <div role="tabpanel" id="painel-perfil" aria-labelledby="aba-perfil">${c.painelPerfil}</div>
    <div role="tabpanel" id="painel-votacoes" aria-labelledby="aba-votacoes" hidden>${painelVotacoes}</div>
    <div role="tabpanel" id="painel-propostas" aria-labelledby="aba-propostas" hidden>${painelPropostas}</div>`;

  ligarAbas(alvo);

  /* --- aba Votações --- */
  const renderVoto = (v) => {
    const [res, classe] = resultado(v.aprovada);
    const pl = v.placar || {};
    return `<li class="cartao-item">
      <span class="quando">${data(v.data)}${v.proposicao ? `, <b>${esc(v.proposicao)}</b>` : ""}</span>
      <span>${selo(v.voto)} <span class="resultado r-${classe}">${esc(res)}</span></span>
      ${c.hrefVotacao ? `<a class="texto" href="${esc(c.hrefVotacao(v))}">${esc(v.descricao || "Votação sem descrição")}</a>` : `<span class="texto">${esc(v.descricao || "Votação sem descrição")}</span>`}
      ${v.ementa ? `<span class="texto ementa">${esc(v.ementa)}</span>` : ""}
      <span class="texto">${barraPlacar(pl)}<span class="quando">Placar: Sim ${pl.sim || 0} · Não ${pl.nao || 0} · Abstenção ${pl.abstencao || 0}${pl.obstrucao ? ` · Obstrução ${pl.obstrucao}` : ""}</span></span>
      <span class="texto">${fontes(c.fontesVotacao(v))}</span>
    </li>`;
  };
  const filtrosVoto = { todos: () => true, sim: (v) => v.voto === "sim", nao: (v) => v.voto === "nao", outros: (v) => ["abstencao", "obstrucao", "art17", "outro"].includes(v.voto), ausente: (v) => v.voto === "ausente" };
  const mostrarVotos = (f) => listaPaginada($("#lista-votos"), linhaDoTempo.filter(filtrosVoto[f]), renderVoto, 10, "Nenhuma votação nesse filtro.");
  abas($("#abas-votos"), [{ valor: "todos", rotulo: "Todas" }, { valor: "sim", rotulo: "Sim" }, { valor: "nao", rotulo: "Não" }, { valor: "outros", rotulo: "Abstenção e obstrução" }, { valor: "ausente", rotulo: "Sem voto" }], mostrarVotos);
  mostrarVotos("todos");

  /* --- aba Propostas --- */
  const destinos = projetos.map((p) => desfecho(p)[1]);
  const cont = destinos.reduce((m, d) => ((m[d] = (m[d] || 0) + 1), m), {});
  $("#numeros-prop").innerHTML = `
    <div><b>${projetos.length}</b><span>projetos</span></div>
    <div><b>${cont.tramitando || 0}</b><span>em tramitação</span></div>
    <div><b>${cont.aprovada || 0}</b><span>aprovados ou viraram lei</span></div>
    <div><b>${cont.rejeitada || 0}</b><span>arquivados ou retirados</span></div>
    <div><b>${cont.sem || 0}</b><span>${esc(c.rotuloSem || "situação a consultar")}</span></div>`;

  const renderProj = (p) => {
    const [texto, classe] = desfecho(p);
    return `<li class="cartao-item">
      <span class="quando"><b>${esc(p.tipo)} ${esc(p.numero)}/${esc(p.ano)}</b>${p.ap ? `, apresentado em ${data(p.ap)}` : ""}${p.principal ? ", autor principal" : ""}</span>
      <span class="resultado r-${classe}">${esc(texto)}</span>
      <span class="texto">${esc(p.ementa || "Sem ementa")}</span>
      ${p.sit ? `<span class="texto"><b>Situação:</b> ${esc(p.sit)}${p.org ? ` (${esc(p.org)})` : ""}${p.dt ? `, em ${data(p.dt)}` : ""}.${p.desp ? ` <span class="quando">Despacho: ${esc(p.desp.slice(0, 300))}</span>` : ""}</span>` : ""}
      ${p.kw ? `<span class="texto quando">Temas: ${esc(p.kw)}</span>` : ""}
      <span class="texto">${fontes([[c.fonteTramitacao, c.linkTramitacao(p)], p.pdf ? ["Texto integral", p.pdf] : null, ["Dados na API", c.linkApi(p)]])}</span>
    </li>`;
  };
  const tiposProj = [...new Set(projetos.map((p) => p.tipo))].sort();
  const filtroProj = (f) => projetos.filter((p) => f === "todos" ? true : ["tramitando", "aprovada", "rejeitada"].includes(f) ? desfecho(p)[1] === f : p.tipo === f);
  const mostrarProj = (f) => listaPaginada($("#lista-proj"), filtroProj(f), renderProj, 10, "Nenhum projeto nesse filtro.");
  abas($("#abas-proj"), [{ valor: "todos", rotulo: "Todos" }, { valor: "tramitando", rotulo: "Em tramitação" }, { valor: "aprovada", rotulo: "Aprovados" }, { valor: "rejeitada", rotulo: "Arquivados" }, ...tiposProj.map((t) => ({ valor: t, rotulo: t }))], mostrarProj);
  mostrarProj("todos");

  const renderOutro = (p) => `<li>
      <span class="quando"><b>${esc(p.tipo)} ${esc(p.numero)}/${esc(p.ano)}</b></span>
      <span class="texto">${esc(p.ementa || "Sem ementa")}</span>
      <span class="texto">${fontes([[c.fonteTramitacao, c.linkTramitacao(p)]])}</span></li>`;
  if (!c.semOutros) {
    const tiposOutros = [...new Set(outros.map((p) => p.tipo))].sort();
    const mostrarOutros = (t) => listaPaginada($("#lista-outros"), outros.filter((p) => t === "todos" || p.tipo === t), renderOutro, 10, "Nenhum documento apresentado no período.");
    abas($("#abas-outros"), [{ valor: "todos", rotulo: "Todos" }, ...tiposOutros.map((t) => ({ valor: t, rotulo: t }))], mostrarOutros);
    mostrarOutros("todos");
  }
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
      ${v.ementa ? `<p class="texto-longo"><b>Sobre o quê:</b> ${esc(v.ementa)}</p>` : ""}
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

/* ---------- todos os políticos ---------- */
const UFS = { AC: "Acre", AL: "Alagoas", AP: "Amapá", AM: "Amazonas", BA: "Bahia", CE: "Ceará", DF: "Distrito Federal",
  ES: "Espírito Santo", GO: "Goiás", MA: "Maranhão", MT: "Mato Grosso", MS: "Mato Grosso do Sul", MG: "Minas Gerais",
  PA: "Pará", PB: "Paraíba", PR: "Paraná", PE: "Pernambuco", PI: "Piauí", RJ: "Rio de Janeiro", RN: "Rio Grande do Norte",
  RS: "Rio Grande do Sul", RO: "Rondônia", RR: "Roraima", SC: "Santa Catarina", SP: "São Paulo", SE: "Sergipe", TO: "Tocantins" };

// grupos na ordem em que aparecem; k = ordem do cargo vinda do gerador
const GRUPOS = [
  { titulo: "Presidência da República", ks: [1, 2] },
  { titulo: "Senado Federal", ks: [3] },
  { titulo: "Câmara dos Deputados", ks: [4] },
  { titulo: "Governo do estado", ks: [5, 6] },
  { titulo: (uf) => (uf === "DF" ? "Câmara Legislativa" : "Assembleia Legislativa"), ks: [7] },
  { titulo: "Prefeitura", ks: [8, 9], municipal: true },
  { titulo: "Câmara Municipal", ks: [10], municipal: true },
];

const lembrar = (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch {} };
const lembrado = (k) => { try { return localStorage.getItem(k); } catch { return null; } };

function linkPolitico(x) {
  return x.h || `politico.html?f=${encodeURIComponent(x.f)}&i=${encodeURIComponent(x.i)}`;
}

function etiquetaEstado(e) {
  if (e === "eleito") return `<span class="etiqueta">Eleito em 2026</span>`;
  if (e === "2turno") return `<span class="etiqueta segundo">No 2º turno</span>`;
  return "";
}

function linhaPolitico(x) {
  return `<li><a class="linha-pol" href="${linkPolitico(x)}">
    ${foto({ nome: x.n || "?", foto: x.fo })}
    <span><span class="nome">${esc(x.n)}</span><br><span class="sigla">${esc(x.c)}${x.p ? `, ${esc(x.p)}` : ""}${x.m ? ` em ${esc(x.m)}` : ""}</span></span>
    ${etiquetaEstado(x.e)}
  </a></li>`;
}

async function paginaPoliticos() {
  const alvo = $("#resultado");
  const q = new URLSearchParams(location.search);
  const selUf = $("#uf"), selMun = $("#municipio"), busca = $("#busca");
  selUf.insertAdjacentHTML("beforeend", Object.entries(UFS).map(([k, v]) => `<option value="${k}">${v}</option>`).join(""));

  let br = [];
  try { br = await carregar("dados/indice/BR.json"); } catch (e) { return erro(alvo, e); }
  const cache = {};
  let lista = [];

  let periodo = q.get("periodo") === "2026" ? "2026" : "agora";
  abas($("#periodo"), [{ valor: "agora", rotulo: "No cargo agora" }, { valor: "2026", rotulo: "Eleitos em 2026" }], (v) => { periodo = v; desenhar(); });
  $("#periodo").querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.v === periodo));

  async function trocarUf() {
    const uf = selUf.value;
    lembrar("mb-uf", uf || null);
    selMun.innerHTML = `<option value="">Todos os municípios</option>`;
    selMun.disabled = !uf;
    if (!uf) { lista = []; return desenhar(); }
    alvo.innerHTML = `<p class="vazio">Carregando ${esc(UFS[uf])}…</p>`;
    try { cache[uf] ||= await carregar(`dados/indice/${uf}.json`); } catch (e) { return erro(alvo, e); }
    lista = cache[uf];
    const muns = new Map();
    lista.forEach((x) => x.g && muns.set(x.g, x.m));
    selMun.insertAdjacentHTML("beforeend", [...muns].sort((a, b) => a[1].localeCompare(b[1], "pt-BR"))
      .map(([g, m]) => `<option value="${esc(g)}">${esc(m)}</option>`).join(""));
    const mun = q.get("municipio") || lembrado(`mb-mun-${uf}`);
    if (mun && muns.has(mun)) selMun.value = mun;
    desenhar();
  }

  function desenhar() {
    const uf = selUf.value, mun = selMun.value, termo = semAcento(busca.value.trim());
    lembrar(`mb-mun-${uf}`, mun || null);
    const nova = new URLSearchParams();
    if (uf) nova.set("uf", uf);
    if (mun) nova.set("municipio", mun);
    if (periodo === "2026") nova.set("periodo", "2026");
    history.replaceState(null, "", nova.toString() ? "?" + nova : location.pathname);

    const doPeriodo = (x) => (periodo === "agora" ? x.e === "atual" : x.e !== "atual");
    const todos = [...br, ...lista].filter(doPeriodo).filter((x) => !termo || semAcento(`${x.n} ${x.p} ${x.m || ""}`).includes(termo));
    let html = "", total = 0;
    for (const g of GRUPOS) {
      let itens = todos.filter((x) => g.ks.includes(x.k));
      if (g.municipal) {
        if (!uf) continue;
        if (mun) itens = itens.filter((x) => x.g === mun);
        else if (!termo) {
          if (itens.length) html += `<section class="grupo"><h2>${g.titulo}</h2><p class="vazio">Escolha um município para ver ${g.ks.includes(10) ? "os vereadores" : "o prefeito e o vice"}, ou busque pelo nome.</p></section>`;
          continue;
        }
      } else if (g.ks[0] > 2 && !uf) continue;
      if (!itens.length) continue;
      total += itens.length;
      const titulo = typeof g.titulo === "function" ? g.titulo(uf) : g.titulo;
      html += `<section class="grupo"><h2>${titulo} <small class="sub">${itens.length}</small></h2><ul class="lista" data-grupo="${g.ks[0]}"></ul></section>`;
      g._itens = itens;
    }
    if (!uf) html += `<p class="aviso">Escolha um estado para ver senadores, deputados, governo, prefeitos e vereadores.</p>`;
    if (periodo === "2026" && !total && uf) html += `<p class="vazio">Nenhum eleito em 2026 encontrado com esses filtros.</p>`;
    alvo.innerHTML = html || `<p class="vazio">Nada encontrado. Tente outro nome ou limpe a busca.</p>`;
    for (const g of GRUPOS) {
      const ul = alvo.querySelector(`ul[data-grupo="${g.ks[0]}"]`);
      if (!ul) continue;
      // listas longas (vereadores de uma capital) crescem aos poucos
      const itens = g._itens; let n = 0;
      const mais = () => {
        ul.insertAdjacentHTML("beforeend", itens.slice(n, n + 60).map(linhaPolitico).join(""));
        n += 60;
        botao.hidden = n >= itens.length;
        botao.textContent = `Mostrar mais (${itens.length - n} restantes)`;
      };
      const botao = document.createElement("button");
      botao.className = "mais"; botao.addEventListener("click", mais);
      ul.after(botao); mais();
    }
    $("#contagem").textContent = uf ? `${total} políticos ${periodo === "agora" ? "no cargo" : "eleitos ou no 2º turno em 2026"}${mun ? ` em ${selMun.selectedOptions[0].text}` : ` em ${UFS[uf]}`}` : "";
  }

  selUf.addEventListener("input", () => { q.delete("municipio"); trocarUf(); });
  selMun.addEventListener("input", desenhar);
  busca.addEventListener("input", desenhar);
  const inicial = q.get("uf") || lembrado("mb-uf");
  if (inicial && UFS[inicial]) selUf.value = inicial;
  trocarUf();
}

/* ---------- ficha de um político (TSE ou Senado) ---------- */
const EXECUTIVOS = new Set(["PRESIDENTE", "VICE-PRESIDENTE", "GOVERNADOR", "VICE-GOVERNADOR", "PREFEITO", "VICE-PREFEITO"]);
const ASSEMBLEIAS = { AC: "aleac.gov.br", AL: "al.al.leg.br", AP: "al.ap.leg.br", AM: "aleam.gov.br", BA: "al.ba.gov.br", CE: "al.ce.gov.br", DF: "cl.df.gov.br",
  ES: "al.es.gov.br", GO: "al.go.leg.br", MA: "al.ma.leg.br", MT: "al.mt.gov.br", MS: "al.ms.gov.br", MG: "almg.gov.br", PA: "alepa.pa.gov.br", PB: "al.pb.leg.br",
  PR: "assembleia.pr.leg.br", PE: "alepe.pe.gov.br", PI: "alepi.pi.leg.br", RJ: "alerj.rj.gov.br", RN: "al.rn.leg.br", RS: "al.rs.gov.br", RO: "al.ro.leg.br",
  RR: "al.rr.leg.br", SC: "alesc.sc.gov.br", SP: "al.sp.gov.br", SE: "al.se.leg.br", TO: "al.to.leg.br" };

/* A casa legislativa ligada ao cargo: quem vota, onde, e o link oficial quando conhecemos. */
function casaLegislativa(p) {
  const c = p.cargoTse || "";
  if (p.fonte === "senado") return { quem: "o Senado", em: "no Senado", link: ["Senado Federal", "https://www25.senado.leg.br"] };
  if (c === "PRESIDENTE" || c === "VICE-PRESIDENTE") return { quem: "o Congresso Nacional", em: "no Congresso", link: ["Câmara dos Deputados", "https://www.camara.leg.br"] };
  if (c === "GOVERNADOR" || c === "VICE-GOVERNADOR") return { quem: `a Assembleia Legislativa${p.uf ? ` (${UFS[p.uf] || p.uf})` : ""}`, em: "na Assembleia", link: ASSEMBLEIAS[p.uf] ? ["Site da Assembleia Legislativa", `https://www.${ASSEMBLEIAS[p.uf]}`] : null };
  if (c === "PREFEITO" || c === "VICE-PREFEITO") return { quem: `a Câmara Municipal${p.municipio ? ` de ${p.municipio}` : ""}`, em: "na Câmara Municipal", link: null };
  if (c === "VEREADOR") return { quem: "", em: `na Câmara Municipal${p.municipio ? ` de ${p.municipio}` : ""}`, link: null };
  return { quem: "", em: `na Assembleia Legislativa${p.uf ? ` (${UFS[p.uf] || p.uf})` : ""}`, link: ASSEMBLEIAS[p.uf] ? ["Site da Assembleia Legislativa", `https://www.${ASSEMBLEIAS[p.uf]}`] : null };
}

/* Presidente em exercício: projetos e medidas provisórias que enviou ao Congresso e o que aconteceu com cada um. */
const TIPOS_EXECUTIVO = { PL: "Projeto de lei", PLP: "Projeto de lei complementar", PEC: "Proposta de emenda à Constituição", MPV: "Medida provisória" };
function desfechoExecutivo(x) {
  const s = (x.sit || "").toLowerCase();
  if (x.veto === "total" || s.startsWith("vetad")) return { rotulo: "Vetado", classe: "v-nao" };
  if (s.startsWith("transformad")) return x.veto === "parcial" ? { rotulo: "Sancionado, com vetos", classe: "v-sim" } : { rotulo: "Virou lei", classe: "v-sim" };
  if (s.includes("aguardando sanção")) return { rotulo: "Aguardando sanção", classe: "v-outro" };
  if (!x.sit && x.tipo === "MPV") return { rotulo: "Em vigor, no prazo do Congresso", classe: "v-outro" };
  if (s.startsWith("perdeu a efic")) return { rotulo: "Perdeu a eficácia", classe: "v-nao" };
  return { rotulo: x.sit || "Em tramitação", classe: "v-outro" };
}
const itemGoverno = (x) => `<li><span class="quando">${esc(x.td)} ${esc(x.numero)}/${esc(x.ano)}${x.ap ? ` · enviado em ${esc(data(x.ap))}` : ""}</span>
  <span class="voto v-outro">${esc(x.sit)}</span>
  <span class="texto">${esc(x.ementa)} ${x.pdf ? `<a href="${esc(x.pdf)}" rel="noopener">Texto</a>` : ""}</span></li>`;
const itemExecutivo = (x) => {
  const d = desfechoExecutivo(x);
  return `<li><span class="quando">${esc(TIPOS_EXECUTIVO[x.tipo] || x.tipo)} ${esc(x.numero)}/${esc(x.ano)} · enviado em ${esc(data(x.apres))}</span>
    <span class="voto ${d.classe}">${esc(d.rotulo)}</span>
    <span class="texto">${esc(x.ementa)}${x.norma ? ` <b>${esc(x.norma)}</b>${x.dataNorma ? `, ${esc(data(x.dataNorma))}` : ""}.` : ""}
      <a href="${esc(linkTramitacao(x.id))}" rel="noopener">Tramitação</a></span></li>`;
};

async function paginaPolitico() {
  const alvo = $("#conteudo");
  const f = param("f"), i = param("i");
  let p;
  try {
    if (!f || !/^[\w/-]+$/.test(f)) throw new Error("Endereço incompleto");
    p = (await carregar(`dados/p/${f}.json`))[i];
    if (!p) throw new Error("Político não encontrado. Ele pode ter deixado o cargo desde a última atualização");
  } catch (e) { return erro(alvo, e); }

  const nome = p.urna || p.nome;
  const local = p.municipio ? `${p.municipio} (${p.uf})` : p.uf === "BR" ? "Brasil" : UFS[p.uf] || p.uf;
  document.title = `${nome}, ${p.cargo} | Minha Bancada`;
  const idade = p.nascimento ? Math.floor((Date.now() - new Date(p.nascimento + "T12:00:00Z")) / 31557600000) : null;

  let situacao = "";
  if (p.estado === "atual") situacao = p.fimMandato ? `No cargo, com mandato até ${data(p.fimMandato, true)}.` : "No cargo.";
  if (p.estado === "eleito") situacao = `Eleito em 2026. Toma posse em 2027.`;
  if (p.estado === "2turno") situacao = `Disputa o 2º turno da eleição de 2026.`;
  if (p.fonte === "senado" && p.participacao && p.participacao !== "Titular") situacao += ` Em exercício como ${esc(p.participacao.toLowerCase())}.`;

  const ficha = [
    ["Nome completo", p.nomeCivil || p.nome],
    ["Número", p.numero],
    ["Partido", p.partido],
    ["Federação", p.federacao],
    ["Coligação", p.coligacao],
    ["Nascimento", p.nascimento ? `${data(p.nascimento, true)}${idade ? ` (${idade} anos)` : ""}` : null],
    ["Gênero", p.genero ? p.genero[0] + p.genero.slice(1).toLowerCase() : null],
    ["Cor ou raça", p.corRaca],
    ["Escolaridade", p.instrucao],
    ["Ocupação declarada", p.ocupacao],
    ["Buscava reeleição", p.fonte === "tse" ? (p.reeleicao ? "Sim" : "Não") : null],
    ["E-mail", p.email ? `<a href="mailto:${esc(p.email)}">${esc(p.email)}</a>` : null, true],
  ].filter(([, v]) => v);

  if (p.fonte === "senado") {
    const montado = await montarSenador(alvo, p, nome, ficha);
    if (montado) return;
  }
  if (p.estadual) {
    const montado = await montarEstadual(alvo, p, nome, ficha, situacao);
    if (montado) return;
  }

  const bens = p.bens || [];
  const executivo = EXECUTIVOS.has(p.cargoTse);
  const casa = casaLegislativa(p);
  const divulga = p.fonte === "tse" && p.eleicao && p.ue ? `https://divulgacandcontas.tse.jus.br/divulga/#/candidato/${encodeURIComponent(p.ano)}/${encodeURIComponent(p.eleicao)}/${encodeURIComponent(p.ue)}/${encodeURIComponent(p.sq)}` : null;
  const fonteTse = divulga ? [["Candidatura no DivulgaCandContas (TSE)", divulga]] : [];

  const painelPerfil = `
    <p class="situacao">${situacao}</p>
    ${p.paginaAtual ? `<p class="aviso">Já tem mandato hoje. <a href="${esc(p.paginaAtual)}">Ver votos, projetos e gastos do mandato atual</a>.</p>` : ""}
    ${p.fonte === "senado" ? `<p class="aviso">Votos e projetos de senadores ainda não estão no site. Veja no <a href="${esc(p.pagina)}" rel="noopener">perfil oficial no Senado</a>.</p>` : ""}

    <h2>Ficha</h2>
    <dl class="ficha">${ficha.map(([k, v, html]) => `<dt>${k}</dt><dd>${html ? v : esc(v)}</dd>`).join("")}
      <dt>Onde atua</dt><dd>${esc(local)}</dd>
    </dl>

    ${p.fonte === "tse" ? `
    <h2>Bens declarados em ${esc(p.ano)}</h2>
    <p>Total: <b>${reaisCentavos(p.totalBens)}</b>${bens.length ? `, em ${bens.length} ${bens.length === 1 ? "item" : "itens"}` : ""}. Valores informados pelo próprio candidato ao registrar a candidatura.</p>
    <div id="lista-bens"></div>
    <p class="fonte">Fonte: <a href="https://dadosabertos.tse.jus.br">Portal de Dados Abertos do TSE</a>, eleição de ${esc(p.ano)}.</p>`
    : `<p class="fonte">Fonte: <a href="https://legis.senado.leg.br/dadosabertos">Dados Abertos do Senado Federal</a>.${p.fimMandato ? ` Mandato até ${data(p.fimMandato, true)}.` : ""}</p>`}`;

  /* Para estes cargos ainda não temos votos nem projetos coletados; as abas dizem isso e levam à fonte oficial. */
  const presidente = p.cargoTse === "PRESIDENTE" && p.estado === "atual";
  let enviados = [];
  if (presidente) { try { enviados = await carregar("dados/executivo.json"); } catch { /* sem dados: cai no texto padrão */ } }
  const comDados = presidente && enviados.length > 0;
  /* Governador em exercício: o que enviou à Assembleia, quando ela usa um sistema que já coletamos. */
  let governo = null;
  if (p.cargoTse === "GOVERNADOR" && p.estado === "atual" && /^[A-Z]{2}$/.test(p.uf || "")) {
    try { governo = await carregar(`dados/governo/${p.uf}.json`); } catch { /* sem dados: cai no texto padrão */ }
  }
  /* Vice-governador: não propõe nem veta; quando a Assembleia está coletada, leva à página do governador. */
  let doVice = null;
  if (p.cargoTse === "VICE-GOVERNADOR" && p.estado === "atual" && /^[A-Z]{2}$/.test(p.uf || "")) {
    try {
      const [g, indice] = await Promise.all([carregar(`dados/governo/${p.uf}.json`), carregar(`dados/indice/${p.uf}.json`)]);
      const gov = indice.find((x) => x.k === 5 && x.e === "atual");
      if (gov && g.materias.length) doVice = { gov, host: g.host };
    } catch { /* sem dados: cai no texto padrão */ }
  }
  const vetosGov = governo ? governo.materias.filter((x) => x.tipo === "VET") : [];
  const enviadosGov = governo ? governo.materias.filter((x) => x.tipo !== "VET") : [];
  const comGoverno = enviadosGov.length + vetosGov.length > 0;
  const aprovados = enviados.filter((x) => /^(transformad|vetad)/i.test(x.sit || "") || x.veto);
  const painelVotacoes = comGoverno
    ? `<section class="painel"><div class="painel-titulo"><h2>Vetos</h2></div>
        <p>${esc(p.cargo)} não vota em plenário. O que faz é propor leis, sancionar ou vetar o que a Assembleia aprova, e editar decretos. Aqui estão os vetos enviados à Assembleia desde 2023: <b>${vetosGov.length}</b>. A situação é a que a Assembleia registra no sistema dela, e nem sempre é atualizada.</p>
        <div id="lista-vetos"></div>
        <p>Sanções e decretos ainda não estão no site. Quem vota é ${esc(casa.quem)}.</p>
        ${fontes([casa.link, ["Sistema de processo legislativo", `https://${governo.host}`]])}</section>`
    : doVice
    ? `<section class="painel"><div class="painel-titulo"><h2>Votações</h2></div>
        <p>${esc(p.cargo)} não vota projetos em plenário nem envia ou veta leis: quem faz isso é o governador. Substitui o governador quando ele se ausenta e assume se o cargo ficar vago.</p>
        <p>Veja o que <a href="${esc(linkPolitico(doVice.gov))}">${esc(doVice.gov.n)}</a> enviou e vetou na Assembleia.</p>
        ${fontes([casa.link, ["Sistema de processo legislativo", `https://${doVice.host}`]])}</section>`
    : comDados
    ? `<section class="painel"><div class="painel-titulo"><h2>Sanções e vetos</h2></div>
        <p>${esc(p.cargo)} não vota em plenário. O que faz é propor leis, sancionar ou vetar o que o Congresso aprova, e editar decretos. Aqui estão os projetos e medidas provisórias que enviou e que viraram lei ou foram vetados: <b>${aprovados.length}</b>, sendo <b>${aprovados.filter((x) => x.veto === "parcial").length}</b> com vetos parciais.</p>
        <div id="lista-sancoes"></div>
        <p>Decretos ainda não estão no site. Quem vota o que ${esc(p.cargo.toLowerCase())} envia é ${esc(casa.quem)}.</p>
        ${fontes([["Planalto: decretos e leis", "https://www.planalto.gov.br/ccivil_03/"], casa.link, ["Dados abertos da Câmara", "https://dadosabertos.camara.leg.br"]])}</section>`
    : executivo
    ? `<section class="painel"><div class="painel-titulo"><h2>Votações</h2></div>
        <p>${esc(p.cargo)} é cargo do Poder Executivo: não vota projetos em plenário. O que faz é propor leis, sancionar ou vetar o que o Legislativo aprova, e editar decretos.</p>
        <p>Quem vota é ${esc(casa.quem)}. Para saber como os legisladores votaram o que ${esc(p.cargo.toLowerCase())} enviou, veja a fonte oficial.</p>
        ${fontes([casa.link, ...fonteTse].filter(Boolean))}</section>`
    : `<section class="painel"><div class="painel-titulo"><h2>Votações</h2></div>
        <p>Ainda não temos os votos nominais de ${esc(p.cargo.toLowerCase())} ${esc(casa.em)}: cada casa legislativa publica seus dados de um jeito, e só a Câmara dos Deputados e o Senado estão no site por enquanto.</p>
        <p>As votações e a presença ficam no site oficial da casa.</p>
        ${fontes([casa.link].filter(Boolean))}</section>`;

  const painelPropostas = `<section class="painel"><div class="painel-titulo"><h2>Propostas</h2></div>
      ${comDados ? `<p>Projetos de lei, leis complementares, emendas à Constituição e medidas provisórias enviados por ${esc(nome)} ao Congresso desde 2023: <b>${enviados.length}</b>. As propostas de campanha ficam no plano de governo da candidatura no TSE.</p><div id="lista-enviados"></div>` : ""}
      ${comGoverno ? `<p>Projetos de lei, leis complementares, emendas à Constituição, medidas provisórias e mensagens enviados por ${esc(nome)} à Assembleia desde 2023: <b>${enviadosGov.length}</b>. As propostas de campanha ficam no plano de governo da candidatura no TSE.</p><div id="lista-enviados-gov"></div>` : ""}
      ${doVice ? `<p>${esc(p.cargo)} não apresenta projetos à Assembleia. Os projetos enviados pelo governo, e os vetos, estão na página de <a href="${esc(linkPolitico(doVice.gov))}">${esc(doVice.gov.n)}</a>.</p>` : ""}
      ${comDados || comGoverno || doVice ? "" : executivo
        ? `<p>As propostas de ${esc(nome)} estão no plano de governo registrado na candidatura, quando o candidato o apresentou ao TSE. Ele fica na página da candidatura, junto com as certidões e a prestação de contas.</p>`
        : `<p>Ainda não temos os projetos apresentados por ${esc(nome)} ${esc(casa.em)}. A lista de autoria e a tramitação ficam no site oficial da casa.</p>
           <p>As propostas de campanha, quando registradas, ficam na página da candidatura no TSE.</p>`}
      ${fontes([...(executivo ? [] : [casa.link]), ...fonteTse].filter(Boolean))}</section>`;

  alvo.innerHTML = `
    <section class="perfil">
      ${foto({ nome, foto: p.foto }, true)}
      <div>
        <h1>${esc(nome)}</h1>
        <p class="sub"><span class="selo">${esc(p.partido || "")}${p.uf && p.uf !== "BR" ? "/" + esc(p.uf) : ""}</span> ${esc(p.cargo)}${p.municipio ? ` em ${esc(p.municipio)}` : ""}</p>
      </div>
    </section>
    <div class="abas-pagina" role="tablist" aria-label="Seções do perfil">
      <button type="button" role="tab" id="aba-perfil" aria-controls="painel-perfil" data-aba="perfil">Perfil e bens</button>
      <button type="button" role="tab" id="aba-votacoes" aria-controls="painel-votacoes" data-aba="votacoes">${comDados ? "Sanções e vetos" : comGoverno ? "Vetos" : "Votações"}</button>
      <button type="button" role="tab" id="aba-propostas" aria-controls="painel-propostas" data-aba="propostas">Propostas</button>
    </div>
    <div role="tabpanel" id="painel-perfil" aria-labelledby="aba-perfil">${painelPerfil}</div>
    <div role="tabpanel" id="painel-votacoes" aria-labelledby="aba-votacoes" hidden>${painelVotacoes}</div>
    <div role="tabpanel" id="painel-propostas" aria-labelledby="aba-propostas" hidden>${painelPropostas}</div>`;
  ligarAbas(alvo);
  if (comGoverno) {
    listaPaginada($("#lista-vetos"), vetosGov, itemGoverno, 15, "Nenhum veto registrado.");
    listaPaginada($("#lista-enviados-gov"), enviadosGov, itemGoverno, 15);
  }
  if (comDados) {
    listaPaginada($("#lista-sancoes"), aprovados, itemExecutivo, 15, "Nenhum projeto virou lei ainda.");
    listaPaginada($("#lista-enviados"), enviados, itemExecutivo, 15);
  }

  if (p.fonte === "tse") {
    listaPaginada($("#lista-bens"), bens, ([tipo, desc, valor]) => `<li>
      <span class="quando"><b>${esc(tipo)}</b></span><b>${reais(valor)}</b>
      ${desc ? `<span class="texto">${esc(desc.charAt(0) + desc.slice(1).toLowerCase())}</span>` : ""}</li>`, 10, "Nenhum bem declarado.");
  }
}

/* senador: mesmas abas do deputado. Devolve false se os dados de votos e projetos ainda não existem. */
const SENADO_API = "https://legis.senado.leg.br/dadosabertos";
const linkMateriaSenado = (id) => `https://www25.senado.leg.br/web/atividade/materias/-/materia/${encodeURIComponent(id)}`;

async function montarSenador(alvo, p, nome, ficha) {
  let sen, lista;
  try { [sen, lista] = await Promise.all([carregar(`dados/senador/${encodeURIComponent(p.id)}.json`), carregar("dados/votacoes_senado.json")]); } catch { return false; }
  const meus = new Map(sen.votos.map((v) => [v.id, v.voto]));
  const linhaDoTempo = lista.filter((v) => meus.has(v.id)).map((v) => ({ ...v, voto: meus.get(v.id) }));
  const situacao = p.fimMandato ? `Mandato até ${data(p.fimMandato, true)}.` : "";
  const apiVotacao = (v) => `${SENADO_API}/votacao?dataInicio=${v.data.replaceAll("-", "")}&dataFim=${v.data.replaceAll("-", "")}`;
  montarParlamentar(alvo, {
    nome, foto: { nome, foto: p.foto },
    subtitulo: `<span class="selo">${esc(p.partido || "")}/${esc(p.uf)}</span> ${esc(p.cargo)}${p.participacao && p.participacao !== "Titular" ? `, ${esc(p.participacao.toLowerCase())}` : ""}`,
    painelPerfil: `<p class="situacao">${esc(situacao)}</p>
      <h2>Ficha</h2>
      <dl class="ficha">${ficha.map(([k, v, html]) => `<dt>${k}</dt><dd>${html ? v : esc(v)}</dd>`).join("")}
        <dt>Onde atua</dt><dd>${esc(UFS[p.uf] || p.uf)}</dd>
        ${p.pagina ? `<dt>Página oficial</dt><dd><a href="${esc(p.pagina)}" rel="noopener">Perfil no Senado Federal</a></dd>` : ""}
      </dl>
      <p class="aviso">Gastos da cota (CEAPS) de senadores ainda não estão no site. Veja no <a href="https://www12.senado.leg.br/transparencia/sen/${encodeURIComponent(p.id)}" rel="noopener">Portal da Transparência do Senado</a>.</p>
      ${fontes([["Dados Abertos do Senado", `${SENADO_API}/senador/${encodeURIComponent(p.id)}`]])}`,
    rotuloPerfil: "Perfil",
    linhaDoTempo, proposicoes: sen.proposicoes, tipoProjeto: (x) => !!TIPOS_PROJETO[x.tipo],
    textoLegislatura: "como autor ou coautor desde 2019",
    aviso: "A situação vem da tramitação no Senado e é atualizada aos poucos todo dia.",
    fonteTramitacao: "Tramitação (Senado)",
    linkTramitacao: (x) => linkMateriaSenado(x.id),
    linkApi: (x) => `${SENADO_API}/materia/${encodeURIComponent(x.id)}`,
    hrefVotacao: null,
    fontesVotacao: (v) => [["Votos de cada senador (API do Senado)", apiVotacao(v)], v.propId ? ["Tramitação da matéria", linkMateriaSenado(v.propId)] : null],
  });
  return true;
}

/* deputado estadual (Assembleias que usam o SAPL): mesmas abas do deputado federal. Devolve false se os dados ainda não existem. */
async function montarEstadual(alvo, p, nome, ficha, situacao) {
  const { uf, id } = p.estadual;
  let dep, lista;
  try { [dep, lista] = await Promise.all([carregar(`dados/estadual/${encodeURIComponent(uf)}/${encodeURIComponent(id)}.json`), carregar(`dados/votacoes_estadual_${encodeURIComponent(uf)}.json`)]); } catch { return false; }
  const meus = new Map(dep.votos.map((v) => [v.id, v.voto]));
  const linhaDoTempo = lista.filter((v) => meus.has(v.id)).map((v) => ({ ...v, voto: meus.get(v.id) }));
  const api = `https://${dep.host}/api`;
  const bens = p.bens || [];
  montarParlamentar(alvo, {
    nome, foto: { nome, foto: p.foto },
    subtitulo: `<span class="selo">${esc(p.partido || "")}/${esc(p.uf)}</span> ${esc(p.cargo)}`,
    painelPerfil: `<p class="situacao">${situacao}</p>
      <h2>Ficha</h2>
      <dl class="ficha">${ficha.map(([k, v, html]) => `<dt>${k}</dt><dd>${html ? v : esc(v)}</dd>`).join("")}
        <dt>Onde atua</dt><dd>${esc(UFS[p.uf] || p.uf)}</dd>
      </dl>
      <h2>Bens declarados em ${esc(p.ano)}</h2>
      <p>Total: <b>${reaisCentavos(p.totalBens)}</b>${bens.length ? `, em ${bens.length} ${bens.length === 1 ? "item" : "itens"}` : ""}. Valores informados pelo próprio candidato ao registrar a candidatura.</p>
      <div id="lista-bens"></div>
      ${fontes([["Portal de Dados Abertos do TSE", "https://dadosabertos.tse.jus.br"], ["Assembleia Legislativa (SAPL)", `https://${dep.host}`]])}`,
    rotuloPerfil: "Perfil e bens",
    linhaDoTempo, proposicoes: dep.proposicoes, tipoProjeto: () => true,
    textoLegislatura: "como autor ou coautor nesta legislatura",
    aviso: "Só entram projetos (de lei, resolução, decreto legislativo, emendas à Constituição e afins). A situação vem do sistema da Assembleia.",
    rotuloSem: "tramitação encerrada, sem resultado informado",
    semOutros: "Requerimentos, indicações e outros documentos da Assembleia não estão no site. Veja no sistema de tramitação da Assembleia.",
    fonteTramitacao: "Tramitação (Assembleia)",
    linkTramitacao: (x) => `https://${dep.host}/materia/${encodeURIComponent(x.id)}`,
    linkApi: (x) => `${api}/materia/materialegislativa/${encodeURIComponent(x.id)}/`,
    hrefVotacao: null,
    fontesVotacao: (v) => [["Dados da votação (API da Assembleia)", `${api}/sessao/registrovotacao/${encodeURIComponent(v.id)}/`]],
  });
  listaPaginada($("#lista-bens"), bens, ([tipo, desc, valor]) => `<li>
      <span class="quando"><b>${esc(tipo)}</b></span><b>${reais(valor)}</b>
      ${desc ? `<span class="texto">${esc(desc.charAt(0) + desc.slice(1).toLowerCase())}</span>` : ""}</li>`, 10, "Nenhum bem declarado.");
  return true;
}

/* ---------- início ---------- */
const pagina = document.body.dataset.pagina;
moldura(pagina);
({ inicio: paginaPoliticos, politico: paginaPolitico, camara: paginaCamara, deputado: paginaDeputado, votacoes: paginaVotacoes, votacao: paginaVotacao }[pagina] || (() => {}))();
