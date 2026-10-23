/* Histórico diário. */
import { $, esc, data, semAcento, carregar, urlSegura } from "./util.js";
import { erro } from "./comum.js";
import { fontes } from "./apis.js";

/* ---------- Histórico diário ---------- */
/* Lê dados/historico/<dia>.json (scripts/historico.py): eventos do dia com local, políticos e fontes. */
const CATEGORIAS_HIST = { nova: "Novo", situacao: "Mudou de situação", votacao: "Votação", eleicao: "Eleitos (TSE)", lote: "Em lote" };
const IMPORTANCIA_HIST = { "": "Tudo", 2: "Projetos e marcos", 3: "Só marcos (votações, aprovações, vetos, eleitos)" };
const SEM_POLITICO = "Sem político específico (votações e matérias gerais)";

/* Mesma regra dos feeds e e-mails: um estado traz a Assembleia, o governo, a bancada federal e a capital; BR traz Câmara, Senado e Presidência. */
function noEscopo(e, codigos) {
  if (!codigos.length) return true;
  return codigos.some((c) => {
    if (c === "BR") return e.local === "BR";
    if (c.startsWith("UF:")) { const uf = c.slice(3); return e.local === c || e.local === `MUN:${uf}` || e.uf === uf; }
    if (c.startsWith("MUN:")) return e.local === c;
    return (e.politicos || []).some((p) => p.codigo === c);
  });
}

/* Cargo exibido ao lado do nome do político. */
function cargoHist(p) {
  const c = p.codigo || "";
  if (c.startsWith("dep:")) return "Deputado(a) federal";
  if (c.startsWith("est:")) return "Deputado(a) estadual";
  if ((p.pagina || "").includes("f=senado")) return "Senador(a)";
  if (c === "pres") return "Presidente da República";
  if (c.startsWith("gov:")) return "Governador(a)";
  if (c.startsWith("pref:")) return "Prefeito(a)";
  return "";
}

const somar = (eventos) => eventos.reduce((t, e) => t + (e.quantidade || 1), 0);   // um evento "lote" resume vários registros

/* Locais acompanhados no dia que não tiveram item: distingue "nada aconteceu" de "não foi acompanhado" e mostra coleta parada. */
function coberturaSemNovidade(dia, codigos, local, mostrar) {
  if (!dia.cobertura || !mostrar) return "";
  const lista = Object.entries(dia.cobertura).filter(([c, x]) => !x.itens && (local && local !== "__avisos" ? c === local : noEscopo({ local: c, uf: c.startsWith("UF:") ? c.slice(3) : null, politicos: [] }, codigos)));
  if (!lista.length) return "";
  const status = (x) => x.status || (x.mudou ? "irrelevante" : "parado");   // dias gravados antes dos status
  const grupos = [
    ["irrelevante", "Dados mudaram, mas nada relevante para o histórico", (x) => x.mudancas && x.mudancas.length ? `atualizou ${x.mudancas.join(", ")}` : "os arquivos foram atualizados, sem item para o histórico (detalhe não registrado neste dia)"],
    ["parado", "Sem dados novos", (x) => x.ultimaMudanca ? `sem alteração desde ${data(x.ultimaMudanca)}` : "sem alteração nos dados"],
    ["falha", "Coleta falhou ou não rodou neste dia", (x) => x.ultimaColeta ? `última coleta gravada em ${data(x.ultimaColeta)}` : "nenhum dado gravado neste dia"],
    ["sem_cobertura", "Sem cobertura (ainda não coletamos este local)", () => "sem fonte conectada"],
  ];
  const bloco = ([chave, titulo, motivo]) => {
    const itens = lista.filter(([, x]) => status(x) === chave);
    return itens.length ? `<h3>${titulo} <small>${itens.length}</small></h3><ul>${itens.map(([, x]) => `<li><b>${esc(x.nome)}</b>: ${esc(motivo(x))}</li>`).join("")}</ul>` : "";
  };
  return `<section class="painel hist-sem"><h2>Acompanhados, sem novidade <small>${lista.length}</small></h2>${grupos.map(bloco).join("")}</section>`;
}

function itemHistorico(e) {
  const mudanca = e.mudanca ? `<p class="hist-mudanca"><span>${esc(e.mudanca[0])}</span> → <b>${esc(e.mudanca[1])}</b></p>` : "";
  return `<li class="hist-item r-${e.relevancia || 2}">
    <div class="hist-cab"><span class="hist-tag k-${esc(e.categoria)}">${esc(CATEGORIAS_HIST[e.categoria] || e.categoria)}</span> <b>${esc(e.titulo)}</b>${e.dataDoAto ? ` <span class="quando">${esc(data(e.dataDoAto))}</span>` : ""}</div>
    ${e.texto ? `<p class="texto">${esc(e.texto)}</p>` : ""}${mudanca}${e.resumo ? `<p class="hist-resumo">${esc(e.resumo)}</p>` : ""}${e.titulos ? `<details class="hist-lista"><summary>Ver os ${e.titulos.length} títulos</summary><p>${e.titulos.map(esc).join(" · ")}</p></details>` : ""}
    ${fontes(e.fontes || [])}</li>`;
}

export async function paginaHistorico() {
  const alvo = $("#historico");
  let indice;
  try { indice = await carregar("dados/historico/indice.json"); } catch { indice = []; }
  if (!indice.length) { alvo.innerHTML = `<p class="vazio">O histórico começa no próximo dia com novidades nos dados.</p>`; return; }
  const q = new URLSearchParams(location.search);
  let codigos = (q.get("locais") || "").split(",").filter(Boolean);
  const dias = indice.map((x) => x.data);
  const diaInicial = dias.includes(q.get("dia")) ? q.get("dia") : dias[0];

  alvo.innerHTML = `
    <div class="filtros hist-filtros">
      <label class="campo">Dia<select id="h-dia">${indice.map((x) => `<option value="${esc(x.data)}">${esc(data(x.data))} (${x.total})</option>`).join("")}</select></label>
      <label class="campo">Local<select id="h-local"></select></label>
      <label class="campo">Tipo<select id="h-tipo"><option value="">Todos</option>${Object.entries(CATEGORIAS_HIST).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></label>
      <label class="campo">Importância<select id="h-imp">${Object.entries(IMPORTANCIA_HIST).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></label>
      <label class="campo">Buscar<input id="h-busca" type="search" placeholder="Político, projeto ou assunto" autocomplete="off" value="${esc(q.get("busca") || "")}"></label>
    </div>
    <p class="contagem" id="h-contagem" aria-live="polite"></p>
    <div id="h-lista"></div>`;
  $("#h-dia").value = diaInicial;
  $("#h-tipo").value = q.get("tipo") || "";
  $("#h-imp").value = q.get("imp") || "";

  let dia = null;
  async function abrirDia() {
    $("#h-lista").innerHTML = `<p class="vazio">Carregando…</p>`;
    try { dia = await carregar(`dados/historico/${$("#h-dia").value}.json`); } catch (e) { return erro($("#h-lista"), e); }
    const opcoes = [`<option value="">Todos os locais</option>`];
    const unico = codigos.length === 1 && dia.locais[codigos[0]];
    if (codigos.length && !unico) opcoes.push(`<option value="__avisos">Seus avisos (${codigos.length})</option>`);
    for (const [c, nome] of Object.entries(dia.locais)) opcoes.push(`<option value="${esc(c)}">${esc(nome)} (${Object.values(dia.contagem[c]).reduce((a, b) => a + b, 0)})</option>`);
    $("#h-local").innerHTML = opcoes.join("");
    $("#h-local").value = unico ? codigos[0] : codigos.length ? "__avisos" : "";
    desenhar();
  }

  function desenhar() {
    const tipo = $("#h-tipo").value, imp = Number($("#h-imp").value) || 0, busca = semAcento($("#h-busca").value.trim());
    const filtrados = dia.eventos.filter((e) => noEscopo(e, codigos) && (!tipo || e.categoria === tipo) && (e.relevancia || 2) >= imp
      && (!busca || semAcento([e.titulo, e.texto, e.resumo, ...(e.politicos || []).map((p) => p.nome)].join(" ")).includes(busca)));
    const novo = new URLSearchParams();
    novo.set("dia", dia.data);
    if (codigos.length) novo.set("locais", codigos.join(","));
    if (tipo) novo.set("tipo", tipo);
    if (imp) novo.set("imp", imp);
    if (busca) novo.set("busca", $("#h-busca").value.trim());
    history.replaceState(null, "", "?" + novo);

    const locais = [...new Set(filtrados.map((e) => e.local))];
    $("#h-contagem").textContent = `${somar(filtrados)} de ${somar(dia.eventos)} mudanças em ${data(dia.data, true)}, em ${locais.length} ${locais.length === 1 ? "local" : "locais"}.`;
    const semNovidade = coberturaSemNovidade(dia, codigos, $("#h-local").value, tipo || busca || imp ? 0 : 1);
    if (!filtrados.length) { $("#h-lista").innerHTML = `<p class="vazio">Nada com esses filtros neste dia. Tente outro dia ou limpe os filtros.</p>${semNovidade}`; return; }
    const abrir = filtrados.length <= 60;
    $("#h-lista").innerHTML = locais.map((l) => {
      const doLocal = filtrados.filter((e) => e.local === l);
      const grupos = new Map();   // nome do político -> {p, eventos}
      for (const e of doLocal) for (const p of (e.politicos?.length ? e.politicos : [{ nome: SEM_POLITICO }])) {
        if (!grupos.has(p.nome)) grupos.set(p.nome, { p, eventos: [] });
        grupos.get(p.nome).eventos.push(e);
      }
      const peso = (g) => Math.max(...g.eventos.map((e) => e.relevancia || 2));   // o político com o fato mais importante vem primeiro
      for (const g of grupos.values()) g.eventos.sort((a, b) => (b.relevancia || 2) - (a.relevancia || 2));
      const ordenados = [...grupos.values()].sort((a, b) => peso(b) - peso(a) || (a.p.codigo ? 0 : 1) - (b.p.codigo ? 0 : 1) || b.eventos.length - a.eventos.length || a.p.nome.localeCompare(b.p.nome, "pt-BR"));
      return `<section class="painel hist-local">
        <h2>${esc(dia.locais[l])} <small>${somar(doLocal)} ${somar(doLocal) === 1 ? "mudança" : "mudanças"}</small></h2>
        ${ordenados.map(({ p, eventos }) => `<details class="hist-pol"${abrir ? " open" : ""}>
          <summary>${urlSegura(p.pagina, true) ? `<a href="${esc(p.pagina)}">${esc(p.nome)}</a>` : esc(p.nome)}${cargoHist(p) ? ` <span class="quando">${esc(cargoHist(p))}</span>` : ""} <small>${eventos.length}</small></summary>
          <ul class="hist-itens">${eventos.map(itemHistorico).join("")}</ul></details>`).join("")}
      </section>`;
    }).join("") + semNovidade;
  }

  $("#h-dia").addEventListener("change", abrirDia);
  $("#h-local").addEventListener("change", () => { codigos = $("#h-local").value === "__avisos" ? codigos : $("#h-local").value ? [$("#h-local").value] : []; desenhar(); });
  $("#h-tipo").addEventListener("change", desenhar);
  $("#h-imp").addEventListener("change", desenhar);
  $("#h-busca").addEventListener("input", desenhar);
  abrirDia();
}
