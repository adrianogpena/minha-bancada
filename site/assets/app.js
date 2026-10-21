/* Minha Bancada — um arquivo para todas as páginas.
   Cada página declara <body data-pagina="..."> e este script monta o resto. */

const VOTOS = {
  sim: { rotulo: "Sim", cor: "var(--sim)" },
  nao: { rotulo: "Não", cor: "var(--nao)" },
  abstencao: { rotulo: "Abstenção", cor: "var(--abstencao)" },
  obstrucao: { rotulo: "Obstrução", cor: "var(--obstrucao)" },
  art17: { rotulo: "Art. 17 (presidência)", cor: "var(--tinta-suave)" },
  secreto: { rotulo: "Voto secreto", cor: "var(--secreto)" },
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

const TSE_CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele";
const arquivoTse = (conjunto, p) => `${TSE_CDN}/${conjunto}/${conjunto}_${p.ano}.zip`;
const arquivoRedesTse = (p) => `${TSE_CDN}/consulta_cand/rede_social_candidato_${p.ano}${p.ano === 2022 ? `_${p.uf === "BR" ? "BR" : p.uf}` : ""}.zip`;

const SOBRENOMES_COMUNS = new Set(["silva", "santos", "souza", "oliveira", "pereira", "costa", "filho", "junior", "neto", "sobrinho"]);

function perfilDoPolitico(url, p) {
  const nomes = `${p.urna || ""} ${p.nome || ""}`;
  const partes = semAcento(nomes).split(/[^a-z0-9]+/).filter((t) => t.length >= 4 && !SOBRENOMES_COMUNS.has(t));
  let alvo;
  try { const u = new URL(url); alvo = `${u.hostname}${u.pathname}`; } catch { alvo = url; }
  alvo = semAcento(decodeURIComponent(alvo.replace(/%(?![0-9a-f]{2})/gi, ""))).replace(/[^a-z0-9]/g, "");
  return partes.some((t) => alvo.includes(t));
}

function linksRedes(redes, p) {
  const todas = [...new Set((redes || []).filter((r) => !/\s/.test(r)))];
  const item = (r) => `<a class="link-rede" href="${esc(r)}" rel="noopener">${esc(r.replace(/^https?:\/\/(www\.)?/, "").replace(/[?#].*$/, "").replace(/\/$/, ""))}</a>`;
  const lista = (itens) => {
    const aberto = itens.slice(0, 6).join("");
    const resto = itens.slice(6);
    return resto.length ? `${aberto}<details><summary>mais ${resto.length}</summary>${resto.join("")}</details>` : aberto;
  };
  const proprios = todas.filter((r) => perfilDoPolitico(r, p));
  const outros = todas.filter((r) => !perfilDoPolitico(r, p));
  if (!todas.length) return null;
  const fonte = p.fonteRedes || "";
  let html = proprios.length ? lista(proprios.map((r) => `<span class="link-bloco">${item(r)}${fonte}</span>`)) : "";
  if (outros.length) {
    html += `${html ? "<br><br>" : ""}<b>Outros perfis e sites citados na candidatura</b> (sem o nome do político no endereço)<br>`
      + lista(outros.map((r) => `<span class="link-bloco">${item(r)}${fonte}</span>`));
  }
  return html;
}

/* linha da ficha: [rótulo, valor, valor é html, valor fica embaixo do rótulo] */
const itemFicha = ([k, v, html, embaixo]) => {
  const classe = embaixo ? ' class="embaixo"' : "";
  return `<dt${classe}>${k}</dt><dd${classe}>${html ? v : esc(v)}</dd>`;
};

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
  const links = [["index.html", "Políticos", "inicio"], ["camara.html", "Câmara", "camara"], ["votacoes.html", "Votações", "votacoes"], ["informado.html", "Fique informado", "informado"], ["sobre.html", "Sobre os dados", "sobre"]];
  const atual = { deputado: "camara", votacao: "votacoes", politico: "inicio" }[pagina] || pagina;
  document.body.insertAdjacentHTML("afterbegin", `
    <header class="topo"><div class="recipiente">
      <a class="marca" href="index.html"><span class="marca-icone" aria-hidden="true">${"<i></i>".repeat(9)}</span>Minha Bancada</a>
      <a class="repo" href="https://github.com/adrianogpena/minha-bancada" rel="noopener" aria-label="Código-fonte no GitHub" title="Código-fonte no GitHub"><svg viewBox="0 0 16 16" width="22" height="22" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg></a>
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
  return `<span class="fontes"><span class="rotulo-fonte">Fonte</span><span class="fontes-lista">${links.filter(Boolean).map(([t, h]) => `<a href="${esc(h)}" rel="noopener">${esc(t)}</a>`).join("")}</span></span>`;
}

/* gastos da cota (deputado: CEAP; senador: CEAPS); desp vem de gerar.py */
function painelGastos(desp, explicacao) {
  const maxTipo = desp.porTipo[0]?.[1] || 1;
  return `
    <h2>Gastos da cota parlamentar em ${desp.ano}</h2>
    <p>Total no ano: <b>${reaisCentavos(desp.total)}</b>. ${esc(explicacao)}</p>
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
  `;
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
  const painelPerfil = `
    ${painelGastos(desp, "A cota paga despesas do mandato, como passagens, aluguel de escritório e divulgação.")}
    ${fontes([["Cota parlamentar (API da Câmara)", `${CAMARA_API}/deputados/${encodeURIComponent(dep.id)}/despesas?ano=${desp.ano}`], ["Portal da Câmara", `https://www.camara.leg.br/deputados/${encodeURIComponent(dep.id)}`]])}

    <h2>Ficha</h2>
    <dl class="ficha">
      ${dep.nomeCivil ? `<dt>Nome civil</dt><dd>${esc(dep.nomeCivil)}</dd>` : ""}
      ${dep.nascimento ? `<dt>Nascimento</dt><dd>${data(dep.nascimento, true)}${dep.naturalidade ? `, ${esc(dep.naturalidade)}` : ""}</dd>` : ""}
      ${dep.escolaridade ? `<dt>Escolaridade</dt><dd>${esc(dep.escolaridade)}</dd>` : ""}
      <dt>No cargo até</dt><dd>${linhaNoCargoAte({ fimMandato: "2027-01-31", estado: "atual" }, "DEPUTADO FEDERAL")[1]}</dd>
      ${dep.email ? `<dt>E-mail</dt><dd><a href="mailto:${esc(dep.email)}">${esc(dep.email)}</a></dd>` : ""}
      ${dep.gabinete ? `<dt>Gabinete</dt><dd>${esc([dep.gabinete.predio && `Prédio ${dep.gabinete.predio}`, dep.gabinete.andar && `${dep.gabinete.andar}º andar`, dep.gabinete.sala && `sala ${dep.gabinete.sala}`].filter(Boolean).join(", "))}${dep.gabinete.telefone ? `, tel. ${esc(dep.gabinete.telefone)}` : ""}${dep.gabinete.email && dep.gabinete.email !== dep.email ? `, <a href="mailto:${esc(dep.gabinete.email)}">${esc(dep.gabinete.email)}</a>` : ""} <span class="fonte-link"><span class="rotulo-fonte">Fonte</span> <a href="${CAMARA_API}/deputados/${encodeURIComponent(dep.id)}" rel="noopener">cadastro na API da Câmara</a></span></dd>` : ""}
      <dt>Página oficial</dt><dd><a href="https://www.camara.leg.br/deputados/${encodeURIComponent(dep.id)}">camara.leg.br/deputados/${esc(dep.id)}</a></dd>
      ${(dep.redesSociais || []).map((r) => `<dt>Rede social</dt><dd><span class="link-bloco"><a class="link-rede" href="${esc(r)}" rel="noopener">${esc(r.replace(/^https?:\/\/(www\.)?/, ""))}</a> <span class="fonte-link"><span class="rotulo-fonte">Fonte</span> <a href="${CAMARA_API}/deputados/${encodeURIComponent(dep.id)}" rel="noopener">cadastro na API da Câmara</a></span></span></dd>`).join("")}
    </dl>
    ${fontes([["Cadastro do deputado (API da Câmara)", `${CAMARA_API}/deputados/${encodeURIComponent(dep.id)}`], ["Portal da Câmara", `https://www.camara.leg.br/deputados/${encodeURIComponent(dep.id)}`]])}`;

  montarParlamentar(alvo, {
    nome: dep.nome, foto: dep,
    painelEleicao: painelEleicao(dep.nome, dep.eleicao, { suplente: /suplente/i.test(dep.condicao || ""), condicao: dep.condicao, cargoTse: "DEPUTADO FEDERAL",
      fontes: [["Cadastro do deputado (API da Câmara)", `${CAMARA_API}/deputados/${encodeURIComponent(dep.id)}`]] }),
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

const TIPOS_SESSAO = { DOR: "Sessão deliberativa ordinária", DEX: "Sessão deliberativa extraordinária", NOR: "Sessão não deliberativa", ESP: "Sessão especial" };

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
      ${legenda(["sim", "nao", "abstencao", "obstrucao", ...(contagem.secreto ? ["secreto"] : []), "ausente"])}
      <div class="numeros">
        <div><b>${pct(votou, linhaDoTempo.length)}</b><span>votou (sim, não ou abstenção)</span></div>
        <div><b>${contagem.sim || 0}</b><span>votos sim</span></div>
        <div><b>${contagem.nao || 0}</b><span>votos não</span></div>
        <div><b>${contagem.abstencao || 0}</b><span>abstenções</span></div>
        <div><b>${(contagem.obstrucao || 0) + (contagem.art17 || 0) + (contagem.outro || 0)}</b><span>obstrução e outros</span></div>
        ${contagem.secreto ? `<div><b>${contagem.secreto}</b><span>votos secretos</span></div>` : ""}
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
      <button type="button" role="tab" id="aba-eleicao" aria-controls="painel-eleicao" data-aba="eleicao">Quem o elegeu?</button>
      <button type="button" role="tab" id="aba-votacoes" aria-controls="painel-votacoes" data-aba="votacoes">Votações <small>${linhaDoTempo.length}</small></button>
      <button type="button" role="tab" id="aba-propostas" aria-controls="painel-propostas" data-aba="propostas">Propostas <small>${c.proposicoes.length}</small></button>
    </div>
    <div role="tabpanel" id="painel-perfil" aria-labelledby="aba-perfil">${c.painelPerfil}</div>
    <div role="tabpanel" id="painel-eleicao" aria-labelledby="aba-eleicao" hidden>${c.painelEleicao}</div>
    <div role="tabpanel" id="painel-votacoes" aria-labelledby="aba-votacoes" hidden>${painelVotacoes}</div>
    <div role="tabpanel" id="painel-propostas" aria-labelledby="aba-propostas" hidden>${painelPropostas}</div>`;

  ligarAbas(alvo);

  /* --- aba Votações --- */
  const textoPlacar = (v) => {
    const pl = v.placar || {};
    const partes = [`Sim ${pl.sim || 0}`, `Não ${pl.nao || 0}`, `Abstenção ${pl.abstencao || 0}`];
    if (pl.obstrucao) partes.push(`Obstrução ${pl.obstrucao}`);
    if (pl.secreto) partes.push(`Voto secreto ${pl.secreto}`);
    if (pl.art17) partes.push(`Presidente (art. 51) ${pl.art17}`);
    if (pl.outro) partes.push(`Outros ${pl.outro}`);
    if (v.ausentes) partes.push(`Sem voto registrado ${v.ausentes}`);
    return partes.join(" · ");
  };
  const renderVoto = (v) => {
    const [res, classe] = resultado(v.aprovada);
    const pl = v.placar || {};
    const sessao = v.sessao ? [v.sessao.tipo && (TIPOS_SESSAO[v.sessao.tipo] || `Sessão ${v.sessao.tipo}`), v.sessao.numero && `nº ${v.sessao.numero}`, v.sessao.votacao && `votação ${v.sessao.votacao} do dia`].filter(Boolean).join(", ") : "";
    return `<li class="cartao-item">
      <span class="quando">${data(v.data)}${v.hora ? `, ${esc(v.hora)}` : ""}${v.proposicao ? `, <b>${esc(v.proposicao)}</b>` : ""}</span>
      <span>${selo(v.voto)} <span class="resultado r-${classe}">${esc(res)}</span></span>
      ${c.hrefVotacao ? `<a class="texto" href="${esc(c.hrefVotacao(v))}">${esc(v.descricao || "Votação sem descrição")}</a>` : `<span class="texto">${esc(v.descricao || "Votação sem descrição")}</span>`}
      ${v.secreta ? `<span class="texto aviso-ementa"><b>Votação secreta:</b> o Senado informa que cada senador votou, mas não como. O voto individual não é público.</span>` : ""}
      ${v.ementa ? `<span class="texto ementa">${esc(v.ementa)}</span>` : `<span class="texto ementa sem-ementa">Ementa não informada${c.fonteEmenta ? ` pelo ${esc(c.fonteEmenta)}` : ""}.</span>`}
      <span class="texto">${barraPlacar(pl)}<span class="quando">Placar${v.placarOficial === undefined ? "" : v.placarOficial ? " oficial" : " (contado dos votos individuais)"}: ${esc(textoPlacar(v))}</span></span>
      ${sessao ? `<span class="texto quando">${esc(sessao)}${v.resultadoTexto ? ` · Resultado informado: ${esc(v.resultadoTexto)}` : ""}</span>` : ""}
      <span class="texto">${fontes(c.fontesVotacao(v))}</span>
    </li>`;
  };
  const filtrosVoto = { todos: () => true, sim: (v) => v.voto === "sim", nao: (v) => v.voto === "nao", outros: (v) => ["abstencao", "obstrucao", "art17", "outro"].includes(v.voto), secreto: (v) => v.voto === "secreto", ausente: (v) => v.voto === "ausente" };
  const mostrarVotos = (f) => listaPaginada($("#lista-votos"), linhaDoTempo.filter(filtrosVoto[f]), renderVoto, 10, "Nenhuma votação nesse filtro.");
  abas($("#abas-votos"), [{ valor: "todos", rotulo: "Todas" }, { valor: "sim", rotulo: "Sim" }, { valor: "nao", rotulo: "Não" }, { valor: "outros", rotulo: "Abstenção e obstrução" }, ...(contagem.secreto ? [{ valor: "secreto", rotulo: "Voto secreto" }] : []), { valor: "ausente", rotulo: "Sem voto" }], mostrarVotos);
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
      ${p.td || p.tram || p.reg || p.co ? `<span class="texto quando">${[p.td && `Tipo: ${esc(p.td)}`, p.reg && `Regime: ${esc(p.reg)}`, p.tram && `Tramitação: ${esc(p.tram)}`, p.co && `Coautores: ${esc(p.co.join(", "))}`].filter(Boolean).join(" · ")}</span>` : ""}
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
    ${["sim", "nao", "abstencao", "obstrucao", "secreto", "art17", "outro"].filter((k) => placar[k]).map((k) => `<i style="width:${(placar[k] / total) * 100}%;background:${VOTOS[k].cor}"></i>`).join("")}</div>`;
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
  const senado = param("casa") === "senado";
  let v;
  try { v = await carregar(`dados/${senado ? "votacao_senado" : "votacao"}/${encodeURIComponent(param("id"))}.json`); } catch (e) { return erro(alvo, e); }
  const quem = senado ? "senador" : "deputado";
  const linkQuem = (d) => senado ? (d.anterior ? "" : `politico.html?f=senado&i=${encodeURIComponent(d.id)}`) : `deputado.html?id=${d.id}`;
  document.title = `${v.proposicao || "Votação"} em ${data(v.data)} | Minha Bancada`;
  v.votos.sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
  const partidos = Object.entries(v.porPartido).sort((a, b) => Object.values(b[1]).reduce((x, y) => x + y, 0) - Object.values(a[1]).reduce((x, y) => x + y, 0));

  alvo.innerHTML = `
    <section class="abertura">
      <p>${data(v.data, true)}${v.hora ? `, às ${esc(v.hora)}` : ""}, no Plenário${senado ? " do Senado" : ""}</p>
      <h1 style="max-width:none;font-size:clamp(28px,4.5vw,44px)">${esc(v.proposicao || "Votação no Plenário")}</h1>
      ${v.ementa ? `<p class="texto-longo"><b>Sobre o quê:</b> ${esc(v.ementa)}</p>` : ""}
      <p class="texto-longo">${esc(v.descricao)}</p>
    </section>
    <section class="painel">
      <div class="painel-titulo"><h2>Placar</h2><p>${v.aprovada === 1 ? "Aprovada" : v.aprovada === 0 ? "Rejeitada" : ""}</p></div>
      ${v.secreta ? `<p class="aviso">Votação secreta: o Senado informa que cada senador votou, mas não como. O voto individual não é público.</p>` : ""}
      ${barraPlacar(v.placar)}
      <div class="numeros">
        <div><b>${v.placar.sim || 0}</b><span>Sim</span></div>
        <div><b>${v.placar.nao || 0}</b><span>Não</span></div>
        <div><b>${v.placar.abstencao || 0}</b><span>Abstenção</span></div>
        <div><b>${v.placar.obstrucao || 0}</b><span>Obstrução</span></div>
        ${senado ? `<div><b>${v.ausentes || 0}</b><span>Sem voto registrado</span></div>` : ""}
      </div>
    </section>
    <h2>Por partido</h2>
    <div class="rolagem"><table class="tabela"><thead><tr><th>Partido</th><th>Sim</th><th>Não</th><th>Abst.</th><th>Obstr.</th></tr></thead><tbody>
      ${partidos.map(([p, c]) => `<tr><td><b>${esc(p)}</b></td><td>${c.sim || 0}</td><td>${c.nao || 0}</td><td>${c.abstencao || 0}</td><td>${c.obstrucao || 0}</td></tr>`).join("")}
    </tbody></table></div>
    <h2>Voto de cada ${quem}</h2>
    <div class="filtros" style="grid-template-columns:2fr 1fr"><label class="campo">Buscar ${quem}<input id="busca-dep" type="search" placeholder="Nome, partido ou estado"></label>
      <label class="campo">Voto<select id="filtro-voto"><option value="">Todos</option>${["sim", "nao", "abstencao", "obstrucao", ...(senado ? ["art17", "secreto", "ausente"] : [])].map((k) => `<option value="${k}">${VOTOS[k].rotulo}</option>`).join("")}</select></label></div>
    <div id="lista-dep"></div>
    ${senado ? fontes([["Votos de cada senador (API do Senado)", `${SENADO_API}/votacao?dataInicio=${v.data.replaceAll("-", "")}&dataFim=${v.data.replaceAll("-", "")}`], v.propId ? ["Tramitação da matéria", linkMateriaSenado(v.propId)] : null]) : ""}`;

  const render = (d) => `<li>${linkQuem(d) ? `<a href="${esc(linkQuem(d))}">${esc(d.nome)}</a>` : esc(d.nome)}${selo(d.voto)}<span class="quando texto">${esc(d.partido)}${d.uf ? `/${esc(d.uf)}` : ""}${d.motivo ? ` · ${esc(d.motivo)}` : ""}</span></li>`;
  const desenhar = () => {
    const b = semAcento($("#busca-dep").value.trim()), f = $("#filtro-voto").value;
    listaPaginada($("#lista-dep"), v.votos.filter((d) => (!f || d.voto === f) && (!b || semAcento(`${d.nome} ${d.partido} ${d.uf}`).includes(b))), render, 50, `Nenhum ${quem} com esse filtro.`);
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

const UF_COD = { 11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO", 21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
  28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR", 42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF" };
const COD_UF = Object.fromEntries(Object.entries(UF_COD).map(([c, u]) => [u, c]));
const MALHAS = "https://servicodados.ibge.gov.br/api/v3/malhas";

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
    <span><span class="nome">${esc(x.n)}</span><br><span class="sigla">${esc(x.c)}${x.p ? `, ${esc(x.p)}` : ""}${x.m ? ` em ${esc(x.m)}` : x.u ? `, ${esc(x.u)}` : ""}</span></span>
    ${etiquetaEstado(x.e)}
  </a></li>`;
}

/* Desenha um GeoJSON do IBGE como SVG (projeção simples, corrigida pela latitude média). */
function svgMapa(fc, idDe) {
  const poligonos = (g) => (g.type === "Polygon" ? [g.coordinates] : g.coordinates);
  let x0 = 180, x1 = -180, y0 = 90, y1 = -90;
  for (const f of fc.features) for (const poli of poligonos(f.geometry)) for (const anel of poli) for (const [x, y] of anel) {
    if (x < x0) x0 = x;
    if (x > x1) x1 = x;
    if (y < y0) y0 = y;
    if (y > y1) y1 = y;
  }
  const k = Math.cos((((y0 + y1) / 2) * Math.PI) / 180), escala = 1000 / ((x1 - x0) * k);
  const px = (x) => Math.round((x - x0) * k * escala * 10) / 10, py = (y) => Math.round((y1 - y) * escala * 10) / 10;
  const caminhos = fc.features.map((f) => {
    const d = poligonos(f.geometry).map((poli) => poli.map((anel) => "M" + anel.map(([x, y]) => `${px(x)} ${py(y)}`).join("L") + "Z").join("")).join("");
    return `<path d="${d}" data-id="${esc(idDe(f))}" tabindex="0" role="link"></path>`;
  });
  return `<svg viewBox="0 0 ${px(x1)} ${py(y0)}" xmlns="http://www.w3.org/2000/svg">${caminhos.join("")}</svg>`;
}

/* Perfil do eleitorado (TSE) do estado ou município escolhido: total e divisão por gênero, faixa etária e escolaridade. */
const FAIXAS = ["16 e 17 anos", "18 a 24", "25 a 34", "35 a 44", "45 a 54", "55 a 64", "65 a 74", "75 ou mais"];
const ESCOLARIDADE = ["Analfabeto", "Lê e escreve", "Fundamental incompleto", "Fundamental completo", "Médio incompleto", "Médio completo", "Superior incompleto", "Superior completo"];
const eleitoradoUf = {};
async function desenharEleitorado(el, uf, mun, nomeLocal) {
  if (!uf) { el.hidden = true; return; }
  try { eleitoradoUf[uf] ||= await carregar(`dados/eleitorado/${uf}.json`); } catch (e) { el.hidden = true; return; }
  const { ano, d } = eleitoradoUf[uf];
  const r = d[mun || "_uf"];
  if (!r || !r.t) { el.hidden = true; return; }
  const porcento = (v, base) => (base ? `${((100 * v) / base).toFixed(1).replace(".", ",")}%` : "");
  const barras = (rotulos, valores, base) => `<div class="barras">${rotulos.map((r, i) => `<div><div class="barra-rotulo"><span>${esc(r)}</span>
    <b>${numeroBr(valores[i])} · ${porcento(valores[i], base)}</b></div><div class="barra"><i style="width:${base ? (100 * valores[i]) / base : 0}%"></i></div></div>`).join("")}</div>`;
  const faixas = r.f.reduce((a, b) => a + b, 0), escolas = r.e.reduce((a, b) => a + b, 0), genero = r.g[0] + r.g[1];
  el.innerHTML = `<summary>Eleitorado de ${esc(nomeLocal)}: <b>${numeroBr(r.t)}</b> eleitores (${esc(ano)})</summary>
    <h3>Gênero</h3>${barras(["Mulheres", "Homens"], [r.g[1], r.g[0]], genero)}
    <h3>Faixa etária</h3>${barras(FAIXAS, r.f, faixas)}
    <h3>Escolaridade</h3>${barras(ESCOLARIDADE, r.e, escolas)}
    <p class="fonte-link"><span class="rotulo-fonte">Fonte</span> <a href="${TSE_CDN}/perfil_eleitorado/perfil_eleitorado_${ano}.zip" rel="noopener">Perfil do eleitorado ${esc(ano)} (TSE)</a>.
    Os percentuais de cada grupo são sobre quem tem a informação registrada.</p>`;
  el.hidden = false;
}

async function paginaPoliticos() {
  const alvo = $("#resultado"), mapa = $("#mapa"), dica = $("#dica"), trilha = $("#trilha");
  const q = new URLSearchParams(location.search);
  const selUf = $("#uf"), selMun = $("#municipio"), busca = $("#busca");
  selUf.insertAdjacentHTML("beforeend", Object.entries(UFS).map(([k, v]) => `<option value="${k}">${v}</option>`).join(""));

  let br = [];
  try { br = await carregar("dados/indice/BR.json"); } catch (e) { return erro(alvo, e); }
  const cache = {}, geos = {};
  let lista = [], uf = null, mun = "", tseDeIbge = {}, nomes = new Map(), versao = 0;
  carregar("dados/municipios_ibge.json").then((m) => {
    tseDeIbge = Object.fromEntries(Object.entries(m).map(([t, i]) => [i, t]));
    if (uf) desenharMapa();
  }).catch(() => {});

  let periodo = q.get("periodo") === "2026" ? "2026" : "agora";
  abas($("#periodo"), [{ valor: "agora", rotulo: "No cargo agora" }, { valor: "2026", rotulo: "Eleitos em 2026" }], (v) => { periodo = v; desenhar(); });
  $("#periodo").querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.v === periodo));

  const geo = async (url) => (geos[url] ||= await carregar(url));

  function desenharTrilha() {
    const partes = [uf ? `<button type="button" data-ir="br">Brasil</button>` : `<b>Brasil</b>`];
    if (uf) partes.push(mun ? `<button type="button" data-ir="uf">${esc(UFS[uf])}</button>` : `<b>${esc(UFS[uf])}</b>`);
    if (mun) partes.push(`<b>${esc(nomes.get(mun) || "")}</b>`);
    trilha.innerHTML = partes.join(`<span aria-hidden="true">›</span>`);
  }

  async function desenharMapa() {
    const minha = ++versao;
    try {
      // o DF não tem municípios (nem eleição municipal): desenha as regiões administrativas, só para olhar
      const semMunicipios = uf === "DF";
      const fc = semMunicipios ? await geo("geo/df_ras.json") : uf
        ? await geo(`${MALHAS}/estados/${COD_UF[uf]}?formato=application/vnd.geo+json&intrarregiao=municipio&qualidade=minima`)
        : await geo(`${MALHAS}/paises/BR?formato=application/vnd.geo+json&intrarregiao=UF&qualidade=minima`);
      if (minha !== versao) return;
      mapa.innerHTML = svgMapa(fc, semMunicipios ? (f) => f.properties.codigo : uf ? (f) => tseDeIbge[f.properties.codarea] || "" : (f) => UF_COD[f.properties.codarea] || "");
      mapa.querySelectorAll("path").forEach((p) => {
        const nome = uf ? nomes.get(p.dataset.id) : UFS[p.dataset.id];
        if (semMunicipios) {
          const ra = fc.features.find((f) => f.properties.codigo === p.dataset.id).properties.nome;
          p.classList.add("unico"); p.removeAttribute("tabindex"); p.removeAttribute("role"); p.setAttribute("aria-label", ra);
          p.insertAdjacentHTML("afterbegin", `<title>${esc(ra)}</title>`);
          return;
        }
        if (!nome) { p.classList.add("fundo"); p.removeAttribute("tabindex"); p.removeAttribute("role"); return; }
        p.setAttribute("aria-label", nome);
        p.insertAdjacentHTML("afterbegin", `<title>${esc(nome)}</title>`);
        if (uf && p.dataset.id === mun) p.classList.add("escolhido");
      });
      dica.textContent = semMunicipios ? "O Distrito Federal não tem municípios nem prefeitos: o governo e a Câmara Legislativa cuidam de tudo. As divisões são as regiões administrativas." : uf ? "Clique em um município para ver os políticos dele." : "Clique em um estado para ver os políticos dele.";
    } catch (e) {
      if (minha === versao) mapa.innerHTML = `<p class="vazio">Não foi possível carregar o mapa. Use os campos ao lado.</p>`;
    }
  }

  async function irPara(novoUf, novoMun = "") {
    if (novoUf !== uf || (novoUf && !lista.length)) {
      uf = novoUf; mun = "";
      selUf.value = uf;
      selMun.innerHTML = `<option value="">Todos os municípios</option>`;
      selMun.disabled = !uf;
      nomes = new Map();
      lista = [];
      if (uf) {
        alvo.innerHTML = `<p class="vazio">Carregando ${esc(UFS[uf])}…</p>`;
        try { cache[uf] ||= await carregar(`dados/indice/${uf}.json`); } catch (e) { return erro(alvo, e); }
        lista = cache[uf];
        lista.forEach((x) => x.g && nomes.set(x.g, x.m));
        selMun.disabled = !nomes.size;
        selMun.insertAdjacentHTML("beforeend", [...nomes].sort((a, b) => a[1].localeCompare(b[1], "pt-BR"))
          .map(([g, m]) => `<option value="${esc(g)}">${esc(m)}</option>`).join(""));
      }
      mapa.innerHTML = `<p class="vazio">Carregando mapa…</p>`;
      desenharMapa();
    }
    mun = nomes.has(novoMun) ? novoMun : "";
    selMun.value = mun;
    mapa.querySelectorAll("path").forEach((p) => p.classList.toggle("escolhido", !!mun && p.dataset.id === mun));
    desenharTrilha();
    desenhar();
  }

  function desenhar() {
    const termo = semAcento(busca.value.trim());
    const nova = new URLSearchParams();
    if (uf) nova.set("uf", uf);
    if (mun) nova.set("municipio", mun);
    if (periodo === "2026") nova.set("periodo", "2026");
    history.replaceState(null, "", nova.toString() ? "?" + nova : location.pathname);

    const doPeriodo = (x) => (periodo === "agora" ? x.e === "atual" : x.e !== "atual");
    // no Brasil, o BR.json traz a presidência e os cargos federais; no estado, os cargos vêm do arquivo do estado
    const base = uf ? lista : br;
    const todos = base.filter(doPeriodo).filter((x) => !termo || semAcento(`${x.n} ${x.p} ${x.m || ""} ${x.u || ""}`).includes(termo));
    const grupos = uf && mun ? [...GRUPOS].sort((a, b) => !!b.municipal - !!a.municipal) : GRUPOS;
    let html = "", total = 0;
    for (const g of GRUPOS) g._itens = null;
    for (const g of grupos) {
      let itens = todos.filter((x) => g.ks.includes(x.k));
      if (g.municipal) {
        if (!uf) continue;
        if (mun) itens = itens.filter((x) => x.g === mun);
        else if (!termo) {
          if (itens.length) html += `<section class="grupo"><h2>${g.titulo}</h2><p class="vazio">Clique em um município no mapa para ver ${g.ks.includes(10) ? "os vereadores" : "o prefeito e o vice"}, ou busque pelo nome.</p></section>`;
          continue;
        }
      }
      if (!itens.length) continue;
      total += itens.length;
      const titulo = typeof g.titulo === "function" ? g.titulo(uf) : g.titulo;
      html += `<section class="grupo"><h2>${titulo} <small class="sub">${itens.length}</small></h2><ul class="lista" data-grupo="${g.ks[0]}"></ul></section>`;
      g._itens = itens;
    }
    if (periodo === "2026" && !total) html += `<p class="vazio">Nenhum eleito em 2026 encontrado com esses filtros.</p>`;
    alvo.innerHTML = html || `<p class="vazio">Nada encontrado. Tente outro nome ou limpe a busca.</p>`;
    for (const g of GRUPOS) {
      const ul = g._itens && alvo.querySelector(`ul[data-grupo="${g.ks[0]}"]`);
      if (!ul) continue;
      // listas longas (Câmara, vereadores de uma capital) crescem aos poucos
      const itens = g._itens; let n = 0;
      const mais = () => {
        ul.insertAdjacentHTML("beforeend", itens.slice(n, n + 30).map(linhaPolitico).join(""));
        n += 30;
        botao.hidden = n >= itens.length;
        botao.textContent = `Mostrar mais (${itens.length - n} restantes)`;
      };
      const botao = document.createElement("button");
      botao.className = "mais"; botao.addEventListener("click", mais);
      ul.after(botao); mais();
    }
    const onde = mun ? `${nomes.get(mun)}, ${UFS[uf]}` : uf ? UFS[uf] : "Brasil";
    desenharEleitorado($("#eleitorado"), uf, mun, mun ? `${nomes.get(mun)}, ${uf}` : uf ? UFS[uf] : "");
    $("#contagem").textContent = `${total} políticos ${periodo === "agora" ? "no cargo" : "eleitos ou no 2º turno em 2026"}: ${onde}`;
  }

  const clicar = (p) => { if (p && !p.classList.contains("fundo") && !p.classList.contains("unico")) irPara(uf || p.dataset.id, uf ? p.dataset.id : ""); };
  mapa.addEventListener("click", (e) => clicar(e.target.closest("path")));
  mapa.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); clicar(e.target.closest("path")); } });
  const nomeSob = (e) => {
    const p = e.target.closest?.("path");
    if (!p || p.classList.contains("fundo")) return;
    dica.textContent = p.classList.contains("unico") ? p.getAttribute("aria-label") : uf ? nomes.get(p.dataset.id) : UFS[p.dataset.id];
  };
  mapa.addEventListener("mouseover", nomeSob);
  mapa.addEventListener("focusin", nomeSob);
  trilha.addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) irPara(b.dataset.ir === "br" ? "" : uf); });
  selUf.addEventListener("input", () => irPara(selUf.value));
  selMun.addEventListener("input", () => irPara(uf, selMun.value));
  busca.addEventListener("input", desenhar);
  const inicial = q.get("uf");
  irPara(inicial && UFS[inicial] ? inicial : "", q.get("municipio") || "");
}

/* ---------- ficha de um político (TSE ou Senado) ---------- */
const EXECUTIVOS = new Set(["PRESIDENTE", "VICE-PRESIDENTE", "GOVERNADOR", "VICE-GOVERNADOR", "PREFEITO", "VICE-PREFEITO"]);
const ASSEMBLEIAS = { AC: "aleac.gov.br", AL: "al.al.leg.br", AP: "al.ap.leg.br", AM: "aleam.gov.br", BA: "al.ba.gov.br", CE: "al.ce.gov.br", DF: "cl.df.gov.br",
  ES: "al.es.gov.br", GO: "al.go.leg.br", MA: "al.ma.leg.br", MT: "al.mt.gov.br", MS: "al.ms.gov.br", MG: "almg.gov.br", PA: "alepa.pa.gov.br", PB: "al.pb.leg.br",
  PR: "assembleia.pr.leg.br", PE: "alepe.pe.gov.br", PI: "alepi.pi.leg.br", RJ: "alerj.rj.gov.br", RN: "al.rn.leg.br", RS: "al.rs.gov.br", RO: "al.ro.leg.br",
  RR: "al.rr.leg.br", SC: "alesc.sc.gov.br", SP: "al.sp.gov.br", SE: "al.se.leg.br", TO: "al.to.leg.br" };

/* Site da Câmara Municipal de cada capital, pelo código TSE do município. */
const CAMARAS_CAPITAIS = { "01392": "riobranco.ac.leg.br", "27855": "maceio.al.leg.br", "06050": "macapa.ap.leg.br", "02550": "cmm.am.gov.br",
  "38490": "cms.ba.gov.br", "13897": "cmfor.ce.gov.br", "57053": "cmvv.es.gov.br", "93734": "goiania.go.leg.br", "90670": "camaracuiaba.mt.gov.br",
  "41238": "cmbh.mg.gov.br", "04278": "cmb.pa.gov.br", "20516": "joaopessoa.pb.leg.br", "75353": "cmc.pr.gov.br", "25313": "recife.pe.leg.br",
  "12190": "teresina.pi.leg.br", "60011": "camara.rio", "17612": "natal.rn.leg.br", "88013": "camarapoa.rs.gov.br", "00035": "portovelho.ro.leg.br",
  "03018": "boavista.rr.leg.br", "81051": "cmf.sc.gov.br", "71072": "saopaulo.sp.leg.br", "73440": "palmas.to.leg.br" };

/* A casa legislativa ligada ao cargo: quem vota, onde, e o link oficial quando conhecemos. */
function casaLegislativa(p) {
  const c = p.cargoTse || "";
  if (p.fonte === "senado") return { quem: "o Senado", em: "no Senado", link: ["Senado Federal", "https://www25.senado.leg.br"] };
  if (c === "PRESIDENTE" || c === "VICE-PRESIDENTE") return { quem: "o Congresso Nacional", em: "no Congresso", link: ["Câmara dos Deputados", "https://www.camara.leg.br"] };
  if (c === "GOVERNADOR" || c === "VICE-GOVERNADOR") return { quem: `a Assembleia Legislativa${p.uf ? ` (${UFS[p.uf] || p.uf})` : ""}`, em: "na Assembleia", link: ASSEMBLEIAS[p.uf] ? ["Site da Assembleia Legislativa", `https://www.${ASSEMBLEIAS[p.uf]}`] : null };
  if (c === "PREFEITO" || c === "VICE-PREFEITO") return { quem: `a Câmara Municipal${p.municipio ? ` de ${p.municipio}` : ""}`, em: "na Câmara Municipal", link: CAMARAS_CAPITAIS[p.ue] ? ["Site da Câmara Municipal", `https://www.${CAMARAS_CAPITAIS[p.ue]}`] : null };
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
  <span class="texto">${esc(x.ementa)} ${x.pdf ? `<a href="${esc(x.pdf)}" rel="noopener">${/\.pdf$/i.test(x.pdf) ? "Texto" : "Tramitação"}</a>` : ""}</span></li>`;
const itemExecutivo = (x) => {
  const d = desfechoExecutivo(x);
  return `<li><span class="quando">${esc(TIPOS_EXECUTIVO[x.tipo] || x.tipo)} ${esc(x.numero)}/${esc(x.ano)} · enviado em ${esc(data(x.apres))}</span>
    <span class="voto ${d.classe}">${esc(d.rotulo)}</span>
    <span class="texto">${esc(x.ementa)}${x.norma ? ` <b>${esc(x.norma)}</b>${x.dataNorma ? `, ${esc(data(x.dataNorma))}` : ""}.` : ""}
      <a href="${esc(linkTramitacao(x.id))}" rel="noopener">Tramitação</a></span></li>`;
};

const fonteRedesTse = (p) => {
  if (p.fonte !== "tse") return "";
  const d = divulgaUrl(p);
  return `<span class="fonte-link"><span class="rotulo-fonte">Fonte</span> ${d ? `<a href="${esc(d)}" rel="noopener">candidatura ${esc(p.ano)} no DivulgaCandContas</a> · ` : ""}<a href="${esc(arquivoRedesTse(p))}" rel="noopener">arquivo de redes do TSE</a></span>`;
};

const divulgaUrl = (p) => p.fonte === "tse" && p.eleicao && p.ue ? `https://divulgacandcontas.tse.jus.br/divulga/#/candidato/${encodeURIComponent(p.ano)}/${encodeURIComponent(p.eleicao)}/${encodeURIComponent(p.ue)}/${encodeURIComponent(p.sq)}` : null;

const CF_URL = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm";
const EC111_URL = "https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc111.htm";
const CODIGO_ELEITORAL_URL = "https://www.planalto.gov.br/ccivil_03/leis/l4737compilado.htm";
const ARTIGO_CARGO = { PRESIDENTE: 82, "VICE-PRESIDENTE": 79, GOVERNADOR: 28, "VICE-GOVERNADOR": 28, SENADOR: 46, "DEPUTADO FEDERAL": 44,
  "DEPUTADO ESTADUAL": 27, "DEPUTADO DISTRITAL": 32, PREFEITO: 29, "VICE-PREFEITO": 29, VEREADOR: 29 };
const ARTIGO_ELEICAO = { PRESIDENTE: 77, "VICE-PRESIDENTE": 77, GOVERNADOR: 28, "VICE-GOVERNADOR": 28, SENADOR: 46, "DEPUTADO FEDERAL": 45,
  "DEPUTADO ESTADUAL": 27, "DEPUTADO DISTRITAL": 32, PREFEITO: 29, "VICE-PREFEITO": 29, VEREADOR: 29 };
const MAJORITARIOS = new Set(["PRESIDENTE", "VICE-PRESIDENTE", "GOVERNADOR", "VICE-GOVERNADOR", "PREFEITO", "VICE-PREFEITO", "SENADOR"]);
const ALTERA_POSSE = new Set(["PRESIDENTE", "VICE-PRESIDENTE", "GOVERNADOR", "VICE-GOVERNADOR"]);
const linkCF = (art) => `${CF_URL}#art${art}`;

const semFonte = (porque) => `<span class="sem-fonte" title="Ainda não temos uma fonte pública para este dado">⚠ dado sem fonte${porque ? `: ${esc(porque)}` : ""}</span>`;

/* Linha "No cargo até" da ficha, com a fonte do prazo: Senado (senadores) ou Constituição (demais). */
function linhaNoCargoAte(p, cargoTse = p.cargoTse) {
  if (!p.fimMandato) return ["No cargo até", semFonte("fim do mandato"), true];
  let origem;
  if (p.fonte === "senado") origem = `<a href="${esc(`${SENADO_API}/senador/${encodeURIComponent(p.id)}`)}" rel="noopener">Dados Abertos do Senado</a>`;
  else if (ARTIGO_CARGO[cargoTse]) {
    origem = `<a href="${linkCF(ARTIGO_CARGO[cargoTse])}" rel="noopener">Constituição Federal, art. ${ARTIGO_CARGO[cargoTse]}</a>`
      + (ALTERA_POSSE.has(cargoTse) ? ` e <a href="${EC111_URL}" rel="noopener">Emenda Constitucional 111/2021</a>` : "");
  }
  const antes = p.estado === "eleito" && p.inicioMandato ? `Toma posse em ${data(p.inicioMandato, true)}. Mandato até ` : p.estado === "2turno" ? "Se eleito, até " : "";
  return ["No cargo até", `${antes}${data(p.fimMandato, true)} ${origem ? `<span class="fonte-link"><span class="rotulo-fonte">Fonte</span> ${origem}</span>` : semFonte("prazo do mandato")}`, true];
}

const numeroBr = (n) => n.toLocaleString("pt-BR");
const rotuloResultado = (r) => /turno/i.test(r) ? "Vai ao 2º turno" : ({ "eleito por qp": "Eleito por quociente partidário", "eleito por média": "Eleito por média", "eleito por media": "Eleito por média" })[r.toLowerCase()] || r;

/* Dinheiro da campanha (prestação de contas ao TSE): quanto arrecadou, de onde veio, quem mais doou e em que gastou. */
function blocoCampanha(e, fontesLista) {
  const c = e.contas;
  if (!c) return e.ano < 2026 ? `<h3>Campanha de ${esc(e.ano)}</h3><p>${semFonte("prestação de contas desta eleição ainda não coletada")}</p>` : "";
  const linhas = (itens, rotuloDe) => `<ul class="lista-eleicao">${itens.map((x) => `<li>${rotuloDe(x)}</li>`).join("")}</ul>`;
  fontesLista.unshift([`Prestação de contas de campanha ${e.ano} (TSE)`, `${TSE_CDN}/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_${e.ano}.zip`]);
  return `<h3>Campanha de ${esc(e.ano)}: quem pagou</h3>
    <p>Arrecadou <b>${reaisCentavos(c.r)}</b> e contratou <b>${reaisCentavos(c.d)}</b> em despesas. ${c.p != null && c.d - c.p > 1 ? `Pagou <b>${reaisCentavos(c.p)}</b> até a prestação de contas; <b>${reaisCentavos(c.d - c.p)}</b> ficaram contratados e sem pagamento registrado.` : ""} Valores declarados pelo próprio candidato na prestação de contas ao TSE.</p>
    ${c.o.length ? `<h4>De onde veio o dinheiro</h4>${linhas(c.o, ([o, v]) => `<span class="quando">${esc(o)}</span> <b>${reaisCentavos(v)}</b>${c.r ? ` (${Math.round((100 * v) / c.r)}%)` : ""}`)}` : ""}
    ${c.dn.length ? `<h4>Maiores doadores</h4>${linhas(c.dn, ([n, o, v]) => `<b>${esc(n)}</b> <span class="quando">${esc(o)}</span> <b>${reaisCentavos(v)}</b>`)}
      <p>"Recursos de partido político" inclui o fundo eleitoral e o fundo partidário repassados pelo partido.</p>` : ""}
    ${c.do && c.do.length ? `<h4>Quem está por trás dos repasses</h4>${linhas(c.do, ([n, v]) => `<b>${esc(n)}</b> <b>${reaisCentavos(v)}</b>`)}
      <p>Pessoas e empresas que doaram ao partido (ou a outro candidato) e tiveram o dinheiro repassado a esta campanha, segundo o TSE. O repasse de fundo público não tem doador originário.</p>` : ""}
    ${c.g.length ? `<h4>Em que gastou</h4>${linhas(c.g, ([g, v]) => `<span class="quando">${esc(g)}</span> <b>${reaisCentavos(v)}</b>`)}` : ""}`;
}

/* Comparecimento e vagas da eleição (TSE: detalhe da votação e vagas). */
function blocoDisputa(e, fontesLista) {
  const d = e.disputa;
  if (!d) return e.ano < 2026 ? `<h3>Comparecimento e vagas</h3><p>${semFonte("comparecimento desta eleição ainda não coletado")}</p>` : "";
  fontesLista.push([`Detalhe da votação ${e.ano} (TSE)`, `${TSE_CDN}/detalhe_votacao_munzona/detalhe_votacao_munzona_${e.ano}.zip`]);
  if (d.v != null) fontesLista.push([`Vagas ${e.ano} (TSE)`, `${TSE_CDN}/consulta_vagas/consulta_vagas_${e.ano}.zip`]);
  const pct = (a, b) => (b ? `${((100 * a) / b).toFixed(1).replace(".", ",")}%` : "");
  const turnos = Object.entries(d.t).sort(([a], [b]) => a - b).map(([n, t]) => `<li><span class="quando">${esc(n)}º turno</span>
    ${numeroBr(t.aptos)} eleitores aptos · compareceram <b>${numeroBr(t.comparecimento)}</b> (${pct(t.comparecimento, t.aptos)}) · abstenção ${numeroBr(t.abstencoes)} (${pct(t.abstencoes, t.aptos)})
    · brancos ${numeroBr(t.brancos)} · nulos ${numeroBr(t.nulos)} · votos válidos ${numeroBr(t.validos)}</li>`).join("");
  return `<h3>Comparecimento e vagas</h3>${d.v != null ? `<p>Vagas em disputa neste cargo e local: <b>${numeroBr(d.v)}</b>.</p>` : ""}<ul class="lista-eleicao">${turnos}</ul>`;
}

/* Votos do partido (TSE: votação por partido): legenda, nominais e quociente eleitoral, nos cargos proporcionais. */
function blocoPartido(e, fontesLista) {
  const v = e.partidoVotos;
  if (!v) return e.ano < 2026 && !MAJORITARIOS.has(e.cargoTse) ? `<h3>Votos do partido</h3><p>${semFonte("votos do partido nesta eleição")}</p>` : "";
  fontesLista.push([`Votação por partido ${e.ano} (TSE)`, `${TSE_CDN}/votacao_partido_munzona/votacao_partido_munzona_${e.ano}.zip`]);
  const pct = (a, b) => (b ? ` (${((100 * a) / b).toFixed(1).replace(".", ",")}%)` : "");
  const total = v.l + v.n;
  const vagas = e.disputa && e.disputa.v;
  const qe = vagas ? v.t / vagas : 0;
  const nome = esc(e.partido);
  let html = `<h3>Votos do partido</h3><p>O ${nome} teve <b>${numeroBr(total)}</b> votos válidos${pct(total, v.t)}: <b>${numeroBr(v.n)}</b> em candidatos e <b>${numeroBr(v.l)}</b> só na legenda (o eleitor digitou o número do partido).</p>`;
  if (v.f) html += `<p>O ${nome} concorreu na federação ${esc(v.f.replace(/\//g, " / "))}, que conta como um partido só para dividir as vagas: <b>${numeroBr(v.fl + v.fn)}</b> votos${pct(v.fl + v.fn, v.t)}, sendo ${numeroBr(v.fl)} de legenda.</p>`;
  if (qe) html += `<p>Quociente eleitoral: ${numeroBr(v.t)} votos válidos ÷ ${numeroBr(vagas)} vagas = <b>${numeroBr(Math.round(qe))}</b> votos por vaga. ${v.f ? "A federação" : "O partido"} teve ${((v.f ? v.fl + v.fn : total) / qe).toFixed(1).replace(".", ",")} quocientes.</p>`;
  return html;
}

/* Com quem o partido se aliou na eleição (TSE: consulta de coligações): tipo, partidos e situação da legenda. */
function blocoAlianca(e, fontesLista) {
  const a = e.alianca;
  if (!a) return e.ano < 2026 ? `<h3>Alianças do partido</h3><p>${semFonte("coligação ou federação desta eleição")}</p>` : "";
  fontesLista.push([`Coligações e federações ${e.ano} (TSE)`, `${TSE_CDN}/consulta_coligacao/consulta_coligacao_${e.ano}.zip`]);
  const nome = esc(e.partido);
  const quais = esc(a.c.replace(/\(\d+-/g, "(").replace(/ \/ \d+-/g, " / "));
  const frase = { C: `O ${nome} concorreu em coligação${a.n ? ` <b>${esc(a.n)}</b>` : ""}, com os partidos: ${quais}.`,
    F: `O ${nome} concorreu em federação, que vale como um partido só: ${quais}.`,
    I: `O ${nome} concorreu sozinho, sem coligação nem federação.` }[a.t];
  const aviso = a.s && a.s !== "Deferido" ? ` Situação da legenda no TSE: <b>${esc(a.s)}</b>.` : "";
  return `<h3>Alianças do partido</h3><p>${frase}${aviso}</p>`;
}

/* Onde foi votado: mapa dos locais de votação com mais votos e, nos cargos estaduais e federais, os municípios. */
function blocoOndeVotou(e, fontesLista) {
  const s = e.secoes;
  if (!s) return e.ano < 2026 ? `<h3>Onde foi votado</h3><p>${semFonte("votos por seção desta eleição ainda não coletados")}</p>` : "";
  fontesLista.push([`Votação por seção ${e.ano} (TSE)`, `${TSE_CDN}/votacao_secao/votacao_secao_${e.ano}_${e.uf}.zip`],
    [`Locais de votação ${e.ano} (TSE)`, `${TSE_CDN}/eleitorado_locais_votacao/eleitorado_local_votacao_${e.ano}.zip`]);
  const pct = (v) => (s.t ? ` (${((100 * v) / s.t).toFixed(1).replace(".", ",")}%)` : "");
  const pontos = (s.l || []).filter(([, la, lo]) => la != null && lo != null);
  let html = `<h3>Onde foi votado</h3><p>${(s.l || []).length ? "Locais de votação" : "Municípios"} com mais votos no ${esc(s.n)}º turno de ${esc(e.ano)}, de um total de ${numeroBr(s.t)} votos.</p>`;
  if (pontos.length) html += `<div class="mapa-votos" role="img" aria-label="Mapa dos locais de votação com mais votos" data-pontos="${esc(JSON.stringify(pontos))}"></div>`;
  if (s.l && s.l.length) html += `<ol class="lista-eleicao">${s.l.map(([n, , , v]) => `<li>${esc(n)}: <b>${numeroBr(v)} votos</b>${pct(v)}</li>`).join("")}</ol>`;
  if (s.mp && s.mp.length) {
    fontesLista.push(["Malhas municipais (IBGE)", "https://servicodados.ibge.gov.br/api/v3/malhas"]);
    html += `<h4>Votos por município</h4><div class="mapa mapa-mun" role="img" aria-label="Mapa dos votos em cada município" data-uf="${esc(e.uf)}" data-mp="${esc(JSON.stringify(s.mp))}"></div>
      <p class="legenda-mapa"><span>menos votos</span><i></i><span>mais votos</span></p>`;
  }
  if (s.m && s.m.length) html += `<h4>Municípios com mais votos</h4><ol class="lista-eleicao">${s.m.map(([n, v]) => `<li>${esc(n)}: <b>${numeroBr(v)} votos</b>${pct(v)}</li>`).join("")}</ol>`;
  return html;
}

/* Mapas dos locais de votação (Leaflet, carregado só quando aparece um mapa na tela). */
const LEAFLET = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4";
let leafletPronto;
function carregarLeaflet() {
  leafletPronto ||= new Promise((ok, falha) => {
    const css = document.createElement("link");
    css.rel = "stylesheet"; css.href = `${LEAFLET}/leaflet.min.css`;
    const js = document.createElement("script");
    js.src = `${LEAFLET}/leaflet.min.js`; js.onload = () => ok(window.L); js.onerror = falha;
    document.head.append(css, js);
  });
  return leafletPronto;
}
function desenharMapaVotos(el) {
  carregarLeaflet().then((L) => {
    const pontos = JSON.parse(el.dataset.pontos);
    const mapa = L.map(el, { scrollWheelZoom: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(mapa);
    const maximo = Math.max(...pontos.map((p) => p[3]));
    const grupo = L.featureGroup(pontos.map(([nome, la, lo, v]) => L.circleMarker([la, lo], { radius: 6 + 14 * Math.sqrt(v / maximo), weight: 1, fillOpacity: 0.55 })
      .bindTooltip(`${nome}: ${numeroBr(v)} votos`))).addTo(mapa);
    mapa.fitBounds(grupo.getBounds().pad(0.2), { maxZoom: 15 });
  }).catch(() => { el.textContent = "Não foi possível carregar o mapa."; });
}
/* Mapa colorido por município (malha do IBGE; código TSE -> IBGE em dados/municipios_ibge.json). */
let ibgeDeTse;
async function desenharMapaMunicipios(el) {
  try {
    ibgeDeTse ||= await carregar("dados/municipios_ibge.json");
    const tseDeIbge = Object.fromEntries(Object.entries(ibgeDeTse).map(([t, i]) => [i, t]));
    const fc = await carregar(`${MALHAS}/estados/${COD_UF[el.dataset.uf]}?formato=application/vnd.geo+json&intrarregiao=municipio&qualidade=minima`);
    const votos = new Map(JSON.parse(el.dataset.mp).map(([c, v]) => [String(c).padStart(5, "0"), v]));
    const maximo = Math.max(...votos.values());
    el.innerHTML = svgMapa(fc, (f) => tseDeIbge[f.properties.codarea] || "");
    const nomes = new Map(fc.features.map((f) => [tseDeIbge[f.properties.codarea], f.properties.nome]));
    el.querySelectorAll("path").forEach((p) => {
      const v = votos.get(p.dataset.id) || 0;
      p.removeAttribute("tabindex"); p.removeAttribute("role");
      p.style.fill = v ? `color-mix(in srgb, var(--marca) ${Math.round(12 + 88 * Math.sqrt(v / maximo))}%, var(--superficie))` : "var(--ausente)";
      p.insertAdjacentHTML("afterbegin", `<title>${esc(nomes.get(p.dataset.id) || "")}: ${numeroBr(v)} votos</title>`);
    });
  } catch (err) { el.textContent = "Não foi possível carregar o mapa."; }
}
if (window.IntersectionObserver) {
  const visto = new IntersectionObserver((itens) => itens.forEach((i) => {
    if (!i.isIntersecting) return;
    visto.unobserve(i.target);
    (i.target.classList.contains("mapa-mun") ? desenharMapaMunicipios : desenharMapaVotos)(i.target);
  }));
  new MutationObserver(() => document.querySelectorAll(".mapa-votos:not([data-visto]), .mapa-mun:not([data-visto])").forEach((el) => { el.dataset.visto = "1"; visto.observe(el); }))
    .observe(document.body, { childList: true, subtree: true });
}

/* Aba "Quem o elegeu?": votação (ano, data, resultado) ou, para suplente, quem ele substituiu e desde quando. */
function painelEleicao(nome, e, o = {}) {
  const cargoTse = (e && e.cargoTse) || o.cargoTse;
  const ehVice = /^VICE-/.test(cargoTse || "");
  const fontesLista = [...(o.fontes || [])];
  let corpo = "";
  if (o.suplente) {
    corpo += `<p><b>${esc(nome)}</b> exerce o mandato como <b>${esc((o.condicao || "suplente").toLowerCase())}</b>${o.titular ? `, no lugar de <b>${esc(o.titular)}</b>` : ""}${o.desde ? `, desde ${esc(data(o.desde, true))}` : ""}.</p>`;
    if (!o.titular) corpo += `<p>${semFonte("não sabemos quem foi substituído")}</p>`;
    if (!o.desde) corpo += `<p>${semFonte("data em que assumiu")}</p>`;
    corpo += `<p>O suplente é eleito junto com o titular, na mesma chapa, e assume quando o titular se afasta${o.titular ? `. A eleição abaixo é a da chapa de ${esc(o.titular)}` : ""}.</p>`;
    fontesLista.push(["Constituição Federal, art. 56", linkCF(56)]);
  }
  if (e && e.votos && e.votos.length) {
    const local = e.municipio ? `${e.municipio} (${e.uf})` : e.uf === "BR" ? "todo o Brasil" : UFS[e.uf] || e.uf;
    corpo += `<h3>Eleição de ${esc(e.ano)}</h3>`;
    if (ehVice && e.titular) corpo += `<p>${esc(nome)} foi eleito na chapa de <b>${esc(e.titular)}</b>: o eleitor vota na chapa inteira, então os votos abaixo são os da chapa.</p>`;
    corpo += `<ul class="lista-eleicao">${e.votos.map((v) => `<li><span class="quando">${v.turno}º turno${v.data ? `, ${esc(data(v.data, true))}` : ""}</span>
      <b>${numeroBr(v.votos)} votos</b>${v.pct != null ? ` (${String(v.pct).replace(".", ",")}% dos votos válidos)` : ""}</li>`).join("")}</ul>`;
    corpo += `<p>Local: ${esc(local)}.${e.resultado ? ` Resultado oficial: <b>${esc(rotuloResultado(e.resultado))}</b>.` : ""}</p>`;
    corpo += blocoDisputa(e, fontesLista) + blocoPartido(e, fontesLista) + blocoAlianca(e, fontesLista) + blocoOndeVotou(e, fontesLista) + blocoCampanha(e, fontesLista);
    if (cargoTse && !MAJORITARIOS.has(cargoTse)) corpo += `<p>Nas eleições proporcionais as vagas são distribuídas entre os partidos pelo quociente eleitoral; por isso o número de votos de cada candidato não diz sozinho quem foi eleito.</p>`;
    if (cargoTse) fontesLista.push([`Constituição Federal, art. ${ARTIGO_ELEICAO[cargoTse]}`, linkCF(ARTIGO_ELEICAO[cargoTse])]);
    if (cargoTse && !MAJORITARIOS.has(cargoTse)) fontesLista.push(["Código Eleitoral, art. 106", CODIGO_ELEITORAL_URL]);
    const d = divulgaUrl({ fonte: "tse", ano: e.ano, eleicao: e.eleicao, ue: e.ue, sq: e.sq });
    if (d) fontesLista.unshift(["Candidatura no DivulgaCandContas (TSE)", d]);
    fontesLista.unshift([`Votação por zona eleitoral ${e.ano} (TSE)`, `${TSE_CDN}/votacao_candidato_munzona/votacao_candidato_munzona_${e.ano}.zip`]);
  } else if (e) {
    corpo += `<p>Eleito em ${esc(e.ano)}. ${semFonte("votos ainda não coletados")}</p>`;
  } else if (!o.suplente) {
    corpo += `<p>${semFonte("não encontramos como foi eleito")}</p>`;
  }
  return `<section class="painel"><div class="painel-titulo"><h2>Quem o elegeu?</h2></div>${corpo}${fontes(fontesLista)}</section>`;
}

/* Monta a aba a partir da ficha de um político (TSE ou Senado). */
function painelEleicaoDe(p, nome) {
  if (p.fonte === "senado") {
    const suplente = !!(p.participacao && p.participacao !== "Titular");
    return painelEleicao(nome, p.eleicao, { suplente, condicao: p.participacao, titular: p.titular, desde: p.exercicioDesde, cargoTse: "SENADOR",
      fontes: [["Dados Abertos do Senado", `${SENADO_API}/senador/${encodeURIComponent(p.id)}`]] });
  }
  return painelEleicao(nome, p, {});
}

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
    ["Nome social", p.nomeSocial],
    ["Número", p.numero],
    ["Partido", p.partido],
    ["Federação", p.federacao],
    ["Coligação", p.coligacao ? `${esc(p.coligacao)}${p.composicaoColigacao ? ` (${esc(p.composicaoColigacao)})` : ""}` : null, true],
    ["Nascimento", p.nascimento ? `${data(p.nascimento, true)}${idade ? ` (${idade} anos)` : ""}` : null],
    ["Estado civil", p.estadoCivil],
    ["Nasceu em (UF)", p.ufNascimento && UFS[p.ufNascimento] ? UFS[p.ufNascimento] : null],
    ["Gênero", p.genero ? p.genero[0] + p.genero.slice(1).toLowerCase() : null],
    ["Cor ou raça", p.corRaca],
    ["Escolaridade", p.instrucao],
    ["Ocupação declarada", p.ocupacao],
    ["E-mail", p.email ? `<a href="mailto:${esc(p.email)}">${esc(p.email)}</a>` : null, true],
    linhaNoCargoAte(p),
    ["Redes e sites declarados na candidatura", linksRedes(p.redes, { ...p, fonteRedes: fonteRedesTse(p) }), true, true],
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
  const divulga = divulgaUrl(p);
  const fonteTse = divulga ? [["Candidatura no DivulgaCandContas (TSE)", divulga]] : [];

  const painelPerfil = `
    <p class="situacao">${situacao}</p>
    ${p.paginaAtual ? `<p class="aviso">Já tem mandato hoje. <a href="${esc(p.paginaAtual)}">Ver votos, projetos e gastos do mandato atual</a>.</p>` : ""}
    ${p.fonte === "senado" ? `<p class="aviso">Os votos e projetos deste senador não puderam ser carregados agora. Veja no <a href="${esc(p.pagina)}" rel="noopener">perfil oficial no Senado</a>.</p>` : ""}

    <h2>Ficha</h2>
    <dl class="ficha">${ficha.map(itemFicha).join("")}
      <dt>Onde atua</dt><dd>${esc(local)}</dd>
    </dl>
    ${p.fonte === "tse" ? fontes([...fonteTse, ["Dados de candidatos (TSE)", arquivoTse("consulta_cand", p)]]) : ""}

    ${p.fonte === "tse" ? `
    <h2>Bens declarados em ${esc(p.ano)}</h2>
    <p>Total: <b>${reaisCentavos(p.totalBens)}</b>${bens.length ? `, em ${bens.length} ${bens.length === 1 ? "item" : "itens"}` : ""}. Valores informados pelo próprio candidato ao registrar a candidatura.</p>
    <div id="lista-bens"></div>
    ${fontes([...fonteTse, ["Bens de candidatos (TSE)", arquivoTse("bem_candidato", p)], ["Portal de Dados Abertos do TSE", "https://dadosabertos.tse.jus.br"]])}`
    : `<p class="fonte"><span class="rotulo-fonte">Fonte</span> <a href="https://legis.senado.leg.br/dadosabertos">Dados Abertos do Senado Federal</a>.${p.fimMandato ? ` Mandato até ${data(p.fimMandato, true)}.` : ""}</p>`}`;

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
  /* Prefeito de capital em exercício: o que enviou à Câmara Municipal, quando ela usa um sistema que já coletamos. */
  const prefeito = p.cargoTse === "PREFEITO";
  if (prefeito && p.estado === "atual" && p.ue) {
    try { governo = await carregar(`dados/prefeitura/${p.ue}.json`); } catch { /* sem dados: cai no texto padrão */ }
  }
  const orgao = prefeito ? "à Câmara Municipal" : "à Assembleia";
  const vetosGov = governo ? governo.materias.filter((x) => x.tipo === "VET") : [];
  const enviadosGov = governo ? governo.materias.filter((x) => x.tipo !== "VET") : [];
  const comGoverno = enviadosGov.length + vetosGov.length > 0;
  const aprovados = enviados.filter((x) => /^(transformad|vetad)/i.test(x.sit || "") || x.veto);
  const painelVotacoes = comGoverno
    ? `<section class="painel"><div class="painel-titulo"><h2>Vetos</h2></div>
        <p>${esc(p.cargo)} não vota em plenário. O que faz é propor leis, sancionar ou vetar o que ${prefeito ? "a Câmara" : "a Assembleia"} aprova, e editar decretos. Aqui estão os vetos enviados ${orgao} desde ${prefeito ? 2025 : 2023}: <b>${vetosGov.length}</b>. A situação é a que ${prefeito ? "a Câmara" : "a Assembleia"} registra no sistema dela, e nem sempre é atualizada.</p>
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
      ${comGoverno ? `<p>Projetos de lei, leis complementares, ${prefeito ? "emendas à Lei Orgânica" : "emendas à Constituição"}, medidas provisórias e mensagens enviados por ${esc(nome)} ${orgao} desde ${prefeito ? 2025 : 2023}: <b>${enviadosGov.length}</b>. As propostas de campanha ficam no plano de governo da candidatura no TSE.</p><div id="lista-enviados-gov"></div>` : ""}
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
      <button type="button" role="tab" id="aba-eleicao" aria-controls="painel-eleicao" data-aba="eleicao">Quem o elegeu?</button>
      <button type="button" role="tab" id="aba-votacoes" aria-controls="painel-votacoes" data-aba="votacoes">${comDados ? "Sanções e vetos" : comGoverno ? "Vetos" : "Votações"}</button>
      <button type="button" role="tab" id="aba-propostas" aria-controls="painel-propostas" data-aba="propostas">Propostas</button>
    </div>
    <div role="tabpanel" id="painel-perfil" aria-labelledby="aba-perfil">${painelPerfil}</div>
    <div role="tabpanel" id="painel-eleicao" aria-labelledby="aba-eleicao" hidden>${painelEleicaoDe(p, nome)}</div>
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
const SENADO_ADM_API = "https://adm.senado.gov.br/adm-dadosabertos/api/v1";
const linkMateriaSenado = (id) => `https://www25.senado.leg.br/web/atividade/materias/-/materia/${encodeURIComponent(id)}`;

async function montarSenador(alvo, p, nome, ficha) {
  let sen, lista;
  try { [sen, lista] = await Promise.all([carregar(`dados/senador/${encodeURIComponent(p.id)}.json`), carregar("dados/votacoes_senado.json")]); } catch { return false; }
  const meus = new Map(sen.votos.map((v) => [v.id, v.voto]));
  const linhaDoTempo = lista.filter((v) => meus.has(v.id)).map((v) => ({ ...v, voto: meus.get(v.id) }));
  const situacao = p.fimMandato ? `Mandato até ${data(p.fimMandato, true)}.` : "";
  const apiVotacao = (v) => `${SENADO_API}/votacao?dataInicio=${v.data.replaceAll("-", "")}&dataFim=${v.data.replaceAll("-", "")}`;
  montarParlamentar(alvo, {
    nome, foto: { nome, foto: p.foto }, painelEleicao: painelEleicaoDe(p, nome),
    subtitulo: `<span class="selo">${esc(p.partido || "")}/${esc(p.uf)}</span> ${esc(p.cargo)}${p.participacao && p.participacao !== "Titular" ? `, ${esc(p.participacao.toLowerCase())}` : ""}`,
    painelPerfil: `<p class="situacao">${esc(situacao)}</p>
      <h2>Ficha</h2>
      <dl class="ficha">${ficha.map(itemFicha).join("")}
        <dt>Onde atua</dt><dd>${esc(UFS[p.uf] || p.uf)}</dd>
        ${p.pagina ? `<dt>Página oficial</dt><dd><a href="${esc(p.pagina)}" rel="noopener">Perfil no Senado Federal</a></dd>` : ""}
      </dl>
      ${sen.despesas ? painelGastos(sen.despesas, "A cota (CEAPS) reembolsa despesas do mandato, como passagens, aluguel de escritório e divulgação. Os valores são os reembolsados pelo Senado.")
        : `<p class="aviso">Os gastos da cota (CEAPS) não puderam ser carregados agora. Veja no <a href="https://www12.senado.leg.br/transparencia/sen/${encodeURIComponent(p.id)}" rel="noopener">Portal da Transparência do Senado</a>.</p>`}
      ${fontes([["Dados Abertos do Senado", `${SENADO_API}/senador/${encodeURIComponent(p.id)}`], sen.despesas ? ["Cota parlamentar (CEAPS)", `${SENADO_ADM_API}/senadores/despesas_ceaps/${sen.despesas.ano}`] : null, ["Portal da Transparência do Senado", `https://www12.senado.leg.br/transparencia/sen/${encodeURIComponent(p.id)}`]])}`,
    rotuloPerfil: sen.despesas ? "Perfil e gastos" : "Perfil",
    linhaDoTempo, proposicoes: sen.proposicoes, tipoProjeto: (x) => !!TIPOS_PROJETO[x.tipo],
    textoLegislatura: "como autor ou coautor desde 2019",
    aviso: "A situação vem da tramitação no Senado e é atualizada aos poucos todo dia.",
    fonteTramitacao: "Tramitação (Senado)",
    fonteEmenta: "Senado",
    linkTramitacao: (x) => linkMateriaSenado(x.id),
    linkApi: (x) => `${SENADO_API}/processo/${encodeURIComponent(x.proc)}`,
    hrefVotacao: (v) => `votacao.html?casa=senado&id=${encodeURIComponent(v.id)}`,
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
  if (!p.email && dep.email) ficha.push(["E-mail", `<a href="mailto:${esc(dep.email)}">${esc(dep.email)}</a>`, true]);
  if (dep.titular === false) ficha.push(["Exercício", "Suplente em exercício"]);
  montarParlamentar(alvo, {
    nome, foto: { nome, foto: p.foto || dep.foto }, painelEleicao: painelEleicaoDe(p, nome),
    subtitulo: `<span class="selo">${esc(p.partido || "")}/${esc(p.uf)}</span> ${esc(p.cargo)}`,
    painelPerfil: `<p class="situacao">${situacao}</p>
      <h2>Ficha</h2>
      <dl class="ficha">${ficha.map(itemFicha).join("")}
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

/* ---------- Fique informado ---------- */
/* Feeds RSS estáticos (site/feeds/<código>.xml, gerados por scripts/feeds.py). Nada é enviado nem guardado: quem assina é o leitor de RSS da pessoa. */
const arquivoFeed = (codigo) => `feeds/${codigo.replace(/:/g, "-")}.xml`;
/* Endereço do Apps Script que guarda os cadastros cifrados (assinaturas/LEIAME.md). Vazio = aviso por e-mail desligado. */
const URL_ASSINATURAS = "";
const urlFeed = (codigo) => new URL(arquivoFeed(codigo), location.href).href;

async function paginaInformado() {
  const alvo = $("#informado");
  const cobertura = await carregar("dados/cobertura.json").catch(() => ({ estados: [], capitais: {} }));
  const escolhidos = new Map();   // código -> rótulo
  const nomeUf = (uf) => UFS[uf] || uf;
  alvo.innerHTML = `
    <div class="informado">
      <fieldset>
        <legend>1. O que você quer acompanhar?</legend>
        <p class="dica-form">Cada escolha vira um feed. Você pode misturar.</p>
        <div class="filtros dois">
          <label class="campo">Brasil
            <button type="button" class="mais" id="add-br">Câmara, Senado e Presidência</button></label>
          <label class="campo">Estado
            <select id="inf-uf"><option value="">Escolha…</option>${cobertura.estados.map((u) => `<option value="${u}">${esc(nomeUf(u))}</option>`).join("")}</select></label>
          <label class="campo">Capital
            <select id="inf-capital"><option value="">Escolha…</option>${Object.entries(cobertura.capitais).map(([u, m]) => `<option value="${u}">${esc(m)} (${u})</option>`).join("")}</select></label>
        </div>
        <p class="dica-form">Estado: Assembleia, governo, deputados federais do estado e a capital. Hoje só entram estados e capitais cujos dados já coletamos (${cobertura.estados.length} Assembleias, ${Object.keys(cobertura.capitais).length} capitais); outros locais entram conforme novas fontes forem conectadas.</p>
      </fieldset>
      <fieldset>
        <legend>2. Ou políticos específicos <small>(opcional)</small></legend>
        <div class="filtros dois">
          <label class="campo">Onde atua
            <select id="pol-uf"><option value="BR">Presidente e deputados federais (Brasil)</option>${Object.entries(UFS).map(([u, n]) => `<option value="${u}">${esc(n)}</option>`).join("")}</select></label>
          <label class="campo">Nome<input id="pol-busca" type="search" placeholder="Ex.: Presidente, Maria, PT" autocomplete="off"></label>
        </div>
        <ul class="itens" id="pol-achados" aria-live="polite"></ul>
        <p class="dica-form">Aparecem só políticos de quem já acompanhamos propostas: Presidente, governadores, deputados federais, deputados estaduais (Assembleias coletadas) e prefeitos de capitais com dados.</p>
      </fieldset>
      <fieldset>
        <legend>3. Seus feeds</legend>
        <ul class="escolhas" id="escolhas" aria-live="polite"></ul>
        <p id="opml-p" hidden><button type="button" class="botao" id="opml">Baixar todos (arquivo OPML)</button></p>
        <details>
          <summary>Como usar um feed RSS</summary>
          <p class="dica-form">Cole o endereço do feed (ou importe o arquivo OPML) num leitor de RSS, como Feedly, Inoreader, NetNewsWire, Thunderbird ou o leitor de notícias do seu celular. Quando houver novidade, ela aparece lá, no máximo uma vez por dia. Alguns leitores, como o Feedly e o Inoreader, também mandam o aviso por e-mail ou notificação.</p>
        </details>
        <p class="dica-form">No RSS não há cadastro: não pedimos nem guardamos e-mail ou qualquer dado seu. Seu leitor busca um arquivo público, igual a abrir uma página do site.</p>
      </fieldset>
      <fieldset id="sec-email" hidden>
        <legend>4. Prefere por e-mail? <small>(opcional)</small></legend>
        <p class="dica-form">Um e-mail por dia, só quando houver novidade no que você escolheu acima. Seu endereço é <b>criptografado no seu navegador</b> antes de sair: o site e a planilha onde fica o cadastro só guardam texto ilegível. Só o robô diário do GitHub, que tem a chave, consegue abri-lo para enviar o aviso. Quem administra o projeto controla esse robô e, tecnicamente, poderia mudá-lo para ler os endereços; se isso não é aceitável para você, use o RSS acima, que não pede nenhum dado.</p>
        <form id="form-email" novalidate>
          <label class="campo">E-mail<input id="inf-email" type="email" autocomplete="email" placeholder="voce@exemplo.com"></label>
          <p><button type="submit" class="botao" id="inf-enviar">Quero receber por e-mail</button></p>
          <p class="aviso-form" id="inf-msg" role="status" aria-live="polite"></p>
        </form>
        <p class="dica-form">Você recebe um e-mail para confirmar (a confirmação sai junto com o próximo envio diário, até 24 horas) e todo aviso traz o link para cancelar.</p>
      </fieldset>
    </div>`;

  const desenhar = () => {
    const todos = [...escolhidos];
    $("#escolhas").innerHTML = todos.length
      ? todos.map(([c, r], i) => `<li><span>${esc(r)}<br><small><a href="${esc(arquivoFeed(c))}">${esc(urlFeed(c))}</a></small></span>
          <span class="acoes"><button type="button" data-copiar="${i}">copiar</button><button type="button" data-tirar="${i}" aria-label="Remover ${esc(r)}">remover</button></span></li>`).join("")
      : `<li class="vazio">Nada escolhido ainda.</li>`;
    $("#opml-p").hidden = !todos.length;
    $("#escolhas").onclick = async (e) => {
      const b = e.target.closest("button"); if (!b) return;
      if (b.dataset.tirar != null) { escolhidos.delete(todos[b.dataset.tirar][0]); desenhar(); mostrarAchados(); return; }
      try { await navigator.clipboard.writeText(urlFeed(todos[b.dataset.copiar][0])); b.textContent = "copiado"; } catch { b.textContent = "selecione o endereço"; }
    };
  };
  const adicionar = (codigo, rotulo) => { if (codigo) { escolhidos.set(codigo, rotulo); desenhar(); mostrarAchados(); } };
  $("#add-br").onclick = () => adicionar("BR", "Brasil: Câmara, Senado e Presidência");
  $("#inf-uf").onchange = (e) => { const u = e.target.value; adicionar(u && `UF:${u}`, `Estado: ${nomeUf(u)}`); e.target.value = ""; };
  $("#inf-capital").onchange = (e) => { const u = e.target.value; adicionar(u && `MUN:${u}`, `Capital: ${cobertura.capitais[u]} (${u})`); e.target.value = ""; };
  $("#opml").onclick = () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?><opml version="2.0"><head><title>Minha Bancada</title></head><body>${
      [...escolhidos].map(([c, r]) => `<outline type="rss" text="${esc(r)}" title="${esc(r)}" xmlUrl="${esc(urlFeed(c))}"/>`).join("")}</body></opml>`;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([xml], { type: "text/x-opml" }));
    a.download = "minha-bancada.opml";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  /* políticos: índice do estado (ou do Brasil), só quem tem código "a" */
  let indice = [];
  const mostrarAchados = () => {
    const q = semAcento($("#pol-busca").value.trim());
    const achados = indice.filter((x) => x.a && (!q || semAcento(`${x.n} ${x.c} ${x.p || ""} ${x.m || ""}`).includes(q))).slice(0, 12);
    $("#pol-achados").innerHTML = achados.length
      ? achados.map((x, i) => `<li><span><b>${esc(x.n)}</b> <small>${esc(x.c)}${x.p ? ` · ${esc(x.p)}` : ""}${x.m ? ` · ${esc(x.m)}` : ""}</small></span>
          <button type="button" data-i="${i}"${escolhidos.has(x.a) ? " disabled" : ""}>${escolhidos.has(x.a) ? "adicionado" : "acompanhar"}</button></li>`).join("")
      : `<li class="vazio">Ninguém encontrado com dados acompanháveis.</li>`;
    $("#pol-achados").onclick = (e) => {
      const b = e.target.closest("button"); if (!b) return;
      const x = achados[b.dataset.i];
      adicionar(x.a, `${x.c}: ${x.n}`);
    };
  };
  $("#pol-uf").onchange = async () => { indice = await carregar(`dados/indice/${$("#pol-uf").value}.json`).catch(() => []); mostrarAchados(); };
  $("#pol-busca").oninput = mostrarAchados;
  desenhar();
  $("#pol-uf").onchange();

  /* aviso por e-mail: cifra no navegador (AES-256-GCM, chave de uso único embrulhada com RSA-OAEP) e manda só o texto cifrado */
  const chavePublica = URL_ASSINATURAS ? await carregar("chave_publica.json").catch(() => null) : null;
  if (chavePublica) {
    $("#sec-email").hidden = false;
    const b64 = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)));
    const hex = (buf) => [...new Uint8Array(buf)].map((x) => x.toString(16).padStart(2, "0")).join("");
    $("#form-email").addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = $("#inf-msg"), email = $("#inf-email").value.trim();
      const locais = [...escolhidos.keys()].filter((c) => /^(BR|UF:|MUN:)/.test(c));
      const politicos = [...escolhidos.keys()].filter((c) => !locais.includes(c));
      if (!escolhidos.size) { msg.textContent = "Escolha acima pelo menos um local ou político."; return; }
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { msg.textContent = "Digite um e-mail válido."; return; }
      $("#inf-enviar").disabled = true;
      msg.textContent = "Enviando…";
      try {
        const enc = new TextEncoder();
        const token = hex(crypto.getRandomValues(new Uint8Array(32)));   // só vai no e-mail de quem assina; a planilha guarda o SHA-256 dele
        const aes = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt"]);
        const iv = crypto.getRandomValues(new Uint8Array(12));
        const dados = enc.encode(JSON.stringify({ email, token, locais, politicos, rotulos: [...escolhidos.values()] }));
        const cifrado = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, aes, dados);
        const rsa = await crypto.subtle.importKey("jwk", chavePublica, { name: "RSA-OAEP", hash: "SHA-256" }, false, ["encrypt"]);
        const k = await crypto.subtle.encrypt({ name: "RSA-OAEP" }, rsa, await crypto.subtle.exportKey("raw", aes));
        const h = hex(await crypto.subtle.digest("SHA-256", enc.encode(token)));
        /* text/plain evita o pedido de verificação do navegador; o Apps Script não responde com CORS, então a resposta é opaca */
        await fetch(URL_ASSINATURAS, { method: "POST", mode: "no-cors", headers: { "Content-Type": "text/plain;charset=utf-8" },
          body: JSON.stringify({ v: 1, h, k: b64(k), iv: b64(iv), c: b64(cifrado) }) });
        msg.textContent = "Pedido enviado. Você receberá um e-mail de confirmação em até 24 horas; se não chegar, olhe o spam.";
      } catch {
        msg.textContent = "Não foi possível enviar agora. Tente de novo em instantes.";
      }
      $("#inf-enviar").disabled = false;
    });
  }
}

/* ---------- início ---------- */
const pagina = document.body.dataset.pagina;
moldura(pagina);
({ inicio: paginaPoliticos, politico: paginaPolitico, camara: paginaCamara, deputado: paginaDeputado, votacoes: paginaVotacoes, votacao: paginaVotacao, informado: paginaInformado }[pagina] || (() => {}))();
