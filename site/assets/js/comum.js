/* Peças de interface usadas por várias páginas. */
import { $, esc, carregar, urlSegura } from "./util.js";

export const VOTOS = {
  sim: { rotulo: "Sim", cor: "var(--sim)" },
  nao: { rotulo: "Não", cor: "var(--nao)" },
  abstencao: { rotulo: "Abstenção", cor: "var(--abstencao)" },
  obstrucao: { rotulo: "Obstrução", cor: "var(--obstrucao)" },
  art17: { rotulo: "Art. 17 (presidência)", cor: "var(--tinta-suave)" },
  secreto: { rotulo: "Voto secreto", cor: "var(--secreto)" },
  outro: { rotulo: "Outro", cor: "var(--tinta-suave)" },
  ausente: { rotulo: "Sem voto registrado", cor: "var(--ausente)" },
};


export const itemFicha = ([k, v, html, embaixo]) => {
  const classe = embaixo ? ' class="embaixo"' : "";
  return `<dt${classe}>${k}</dt><dd${classe}>${html ? v : esc(v)}</dd>`;
};

export function foto(dep, grande = false) {
  const classe = "foto" + (grande ? " grande" : "");
  const iniciais = esc(dep.nome.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join(""));
  const src = urlSegura(dep.foto, true);
  if (!src) return `<span class="${classe}" aria-hidden="true">${iniciais}</span>`;
  return `<img class="${classe}" src="${esc(src)}" alt="" loading="lazy" width="48" height="48"
    onerror="this.outerHTML='<span class=&quot;${classe}&quot; aria-hidden=&quot;true&quot;>${iniciais}</span>'">`;
}

export function selo(voto) {
  const v = VOTOS[voto] || VOTOS.outro;
  return `<span class="voto v-${esc(voto)}">${esc(v.rotulo)}</span>`;
}

export function legenda(chaves) {
  return `<div class="legenda">${chaves.map((k) => `<span style="--c:${VOTOS[k].cor}">${VOTOS[k].rotulo}</span>`).join("")}</div>`;
}

/* Filtros da lista na URL (replaceState): quem volta pelo histórico reencontra a busca como estava. */
export function filtrosNaUrl(ids, desenhar) {
  const q = new URLSearchParams(location.search);
  ids.forEach((id) => { if (q.has(id)) $(`#${id}`).value = q.get(id); });
  const gravar = () => {
    const nq = new URLSearchParams();
    ids.forEach((id) => { const v = $(`#${id}`).value; if (v) nq.set(id, v); });
    history.replaceState(null, "", `${location.pathname}${nq.size ? `?${nq}` : ""}`);
  };
  ids.forEach((id) => $(`#${id}`).addEventListener("input", () => { gravar(); desenhar(); }));
  desenhar();
}

/* Botão de voltar das páginas de detalhe: volta pelo histórico (mantendo filtros) se veio de uma página do site; senão vai à lista. */
export function botaoVoltar(rotuloLista, hrefLista) {
  let ref = "";
  try { const u = new URL(document.referrer); if (u.origin === location.origin) ref = u.pathname; } catch { /* sem referrer */ }
  const rotulo = ref.endsWith("/proposicoes.html") ? "Voltar às proposições" : ref.endsWith("/votacoes.html") ? "Voltar às votações" : ref ? "Voltar" : rotuloLista;
  setTimeout(() => $(".voltar")?.addEventListener("click", (e) => { if (ref && history.length > 1) { e.preventDefault(); history.back(); } }));
  return `<p><a class="voltar" href="${esc(hrefLista)}">← ${esc(rotulo)}</a></p>`;
}

/* lista que cresce de N em N com um botão */
export function listaPaginada(alvo, itens, render, passo = 20, vazio = "Nada por aqui ainda.") {
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

export function abas(alvo, opcoes, aoMudar) {
  alvo.innerHTML = opcoes.map((o, i) => `<button type="button" data-v="${esc(o.valor)}" aria-pressed="${i === 0}">${esc(o.rotulo)}</button>`).join("");
  alvo.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    alvo.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
    aoMudar(b.dataset.v);
  });
}

/* ---------- moldura comum ---------- */
function menuItem(atual) {
  const link = ([h, t, p]) => `<a href="${h}"${p === atual ? ' aria-current="page"' : ""}>${t}</a>`;
  return (item) => {
    if (typeof item[1] === "string") return link(item);
    const [titulo, filhos] = item;
    return `<div class="nav-grupo"><button type="button"${filhos.some((f) => f[2] === atual) ? ' aria-current="page"' : ""}>${titulo}</button><div class="submenu">${filhos.map(link).join("")}</div></div>`;
  };
}

/* Navegação do modo celular (estilo em mobile.css; no computador fica escondida): barra inferior + folha "Mais". */
const BARRA_MOBILE = [["index.html", "Políticos", "inicio"], ["camara.html", "Câmara", "camara"], ["votacoes.html", "Votações", "votacoes"], ["historico.html", "Histórico", "historico"]];
const MAIS_MOBILE = [["proposicoes.html", "Proposições", "proposicoes"], ["ministerios.html", "Ministérios", "ministerios"], ["informado.html", "Fique informado", "informado"], ["sobre.html", "Sobre os dados", "sobre"], ["mapa-dados.html", "Mapa dos dados", "mapadados"]];

function barraMobile(atual) {
  const link = (classe) => ([h, t, p]) => `<a class="${classe}" href="${h}"${p === atual ? ' aria-current="page"' : ""}>${t}</a>`;
  const noMais = MAIS_MOBILE.some((i) => i[2] === atual);
  setTimeout(() => {
    const botao = document.getElementById("mb-mais"), folha = document.getElementById("mb-folha");
    if (!botao || !folha) return;
    const alternar = (aberta) => { folha.hidden = !aberta; botao.setAttribute("aria-expanded", String(aberta)); };
    botao.addEventListener("click", () => alternar(folha.hidden));
    folha.addEventListener("click", (e) => { if (e.target === folha || e.target.closest("a")) alternar(false); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") alternar(false); });
  });
  return `<nav class="mb-barra" aria-label="Navegação">${BARRA_MOBILE.map(link("mb-item")).join("")}<button type="button" class="mb-item" id="mb-mais" aria-expanded="false" aria-controls="mb-folha"${noMais ? ' aria-current="page"' : ""}>Mais</button></nav>
    <div class="mb-folha" id="mb-folha" hidden><div class="mb-folha-caixa">${MAIS_MOBILE.map(link("mb-link")).join("")}</div></div>`;
}

/* Copia o cabeçalho de cada coluna para o data-rotulo das células: o modo celular mostra cada linha como cartão "rótulo: valor". */
export function rotularTabelas(raiz = document) {
  for (const t of raiz.querySelectorAll("table.tabela:not(.matriz):not(.tabela-fonte)")) {
    const cab = [...t.querySelectorAll("thead th")].map((th) => th.textContent.trim());
    for (const tr of t.querySelectorAll("tbody tr")) {
      [...tr.children].forEach((td, i) => { if (cab[i] && !td.dataset.rotulo) td.dataset.rotulo = cab[i]; });
    }
  }
}

/* Agrupa cada <dt>+<dd> da ficha numa <div>: a grade em colunas do desktop nunca separa o rótulo do valor. */
export function agruparFichas(raiz = document) {
  for (const dl of raiz.querySelectorAll("dl.ficha:not([data-agrupada])")) {
    const filhos = [...dl.children];
    if (filhos.some((f) => f.tagName !== "DT" && f.tagName !== "DD")) continue;
    dl.dataset.agrupada = "1";
    for (let i = 0; i < filhos.length; i++) {
      const grupo = document.createElement("div");
      if (filhos[i].classList.contains("embaixo")) grupo.className = "embaixo";
      dl.insertBefore(grupo, filhos[i]);
      grupo.append(filhos[i]);
      if (filhos[i].tagName === "DT" && filhos[i + 1]?.tagName === "DD") grupo.append(filhos[++i]);
    }
  }
}

function rotularTabelasAoMontar() {
  if (typeof MutationObserver === "undefined") return;
  let agendado = false;
  new MutationObserver(() => {
    if (agendado) return;
    agendado = true;
    requestAnimationFrame(() => { agendado = false; rotularTabelas(); agruparFichas(); });
  }).observe(document.body, { childList: true, subtree: true });
}

export function moldura(pagina) {
  rotularTabelasAoMontar();
  const links = [
    ["Políticos", [["index.html", "Buscar políticos", "inicio"], ["camara.html", "Câmara", "camara"], ["ministerios.html", "Ministérios", "ministerios"]]],
    ["Atuação", [["proposicoes.html", "Proposições", "proposicoes"], ["votacoes.html", "Votações", "votacoes"]]],
    ["historico.html", "Histórico", "historico"], ["informado.html", "Fique informado", "informado"],
    ["Dados", [["sobre.html", "Sobre os dados", "sobre"], ["mapa-dados.html", "Mapa dos dados", "mapadados"]]]];
  const atual = { fornecedores: "camara", coautoria: "camara", deputado: "camara", votacao: "votacoes", proposicao: "proposicoes", politico: "inicio", ministro: "ministerios", fonte: "sobre" }[pagina] || pagina;
  document.body.insertAdjacentHTML("afterbegin", `
    <header class="topo"><div class="recipiente">
      <a class="marca" href="index.html"><span class="marca-icone" aria-hidden="true">${"<i></i>".repeat(9)}</span>Minha Bancada</a>
      <a class="repo" href="https://github.com/adrianogpena/minha-bancada" rel="noopener" aria-label="Código-fonte no GitHub" title="Código-fonte no GitHub"><svg viewBox="0 0 16 16" width="22" height="22" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg></a>
      <nav class="nav" aria-label="Principal">${links.map(menuItem(atual)).join("")}</nav>
    </div></header>`);
  document.body.insertAdjacentHTML("beforeend", barraMobile(atual));
  document.body.insertAdjacentHTML("beforeend", `
    <footer class="rodape"><div class="recipiente" id="rodape">
      Dados públicos do <a href="https://dadosabertos.tse.jus.br">TSE</a>, da <a href="https://dadosabertos.camara.leg.br">Câmara dos Deputados</a> e do <a href="https://www12.senado.leg.br/dados-abertos">Senado Federal</a>, atualizados automaticamente.
      Projeto independente, sem vínculo com órgãos públicos ou partidos. Encontrou um erro? Confira sempre a fonte oficial.
    </div></footer>`);
  carregar("dados/meta.json").then((m) => {
    if (m.atualizadoEm) $("#rodape").insertAdjacentHTML("beforeend", ` Última atualização: ${new Date(m.atualizadoEm).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit", timeZoneName: "short" })}.`);
  }).catch(() => {});
}

export function erro(alvo, e) {
  alvo.innerHTML = `<p class="aviso">${esc(e.message)}. Se o site acabou de ser criado, rode a coleta de dados uma vez (veja o README).</p>`;
  console.error(e);
}

/* Sem o JSON local (item que o site não coletou): mostra direto a versão legível da API oficial. */
export function semDadosLocais(alvo, e, api) {
  if (api) return location.replace(`fonte.html?u=${encodeURIComponent(api)}`); // direto, não por urlLegivel: ele voltaria a esta página
  erro(alvo, e);
}


/* Troca entre as abas de uma página de pessoa; a aba escolhida fica no #endereço. */
export function ligarAbas(alvo) {
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
