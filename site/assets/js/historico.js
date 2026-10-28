/* Histórico por dia, semana ou mês. */
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

/* ---------- Semana e mês ---------- */
/* Não há arquivo de semana nem de mês: o período é a junção, no navegador, dos arquivos diários que ele cobre. */
const PERIODOS = { dia: "Dia", semana: "Semana", mes: "Mês" };
const dataHora = (iso) => new Date(iso).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }).replace(",", "");
const somarDias = (iso, n) => { const d = new Date(iso + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const segunda = (iso) => somarDias(iso, -((new Date(iso + "T12:00:00Z").getUTCDay() + 6) % 7));

/* Chave do período que contém o dia: o próprio dia, a segunda-feira da semana ou AAAA-MM. */
export const chaveDe = (periodo, iso) => periodo === "semana" ? segunda(iso) : periodo === "mes" ? iso.slice(0, 7) : iso;

/* Agrupa o índice (do mais novo ao mais antigo) por período; `dias` guarda os dias do grupo na mesma ordem. */
export function agruparPeriodos(indice, periodo) {
  const grupos = new Map();
  for (const x of indice) {
    const chave = chaveDe(periodo, x.data);
    if (!grupos.has(chave)) grupos.set(chave, { chave, dias: [], total: 0 });
    const g = grupos.get(chave);
    g.dias.push(x.data);
    g.total += x.total;
  }
  return [...grupos.values()];
}

function rotuloPeriodo(g, periodo) {
  if (periodo === "semana") return `Semana de ${data(g.chave)} a ${data(somarDias(g.chave, 6))}`;
  if (periodo === "mes") return new Date(g.chave + "-15T12:00:00Z").toLocaleDateString("pt-BR", { month: "long", year: "numeric", timeZone: "UTC" });
  return data(g.chave);
}

const chaveLocal = (c) => `${c === "BR" ? 0 : 1}${c.startsWith("MUN") ? 1 : 0}${c}`;   // mesma ordem de historico.ordem_local

const statusDe = (x) => x.status || (x.mudou ? "irrelevante" : "parado");   // dias gravados antes dos status
const diasEntre = (a, b) => Math.round((Date.parse(b + "T12:00:00Z") - Date.parse(a + "T12:00:00Z")) / 864e5);

/* Junta os arquivos diários (do mais novo ao mais antigo) no formato de um dia. Cada evento ganha `_dia`; os de dias diferentes não são deduplicados. */
export function juntarDias(dias, chave) {
  const locais = {}, contagem = {}, cobertura = {};
  const eventos = [];
  for (const d of dias) {
    for (const [c, nome] of Object.entries(d.locais)) locais[c] ??= nome;
    for (const [c, porTipo] of Object.entries(d.contagem)) for (const [k, n] of Object.entries(porTipo)) {
      contagem[c] ??= {};
      contagem[c][k] = (contagem[c][k] || 0) + n;
    }
    for (const [c, x] of Object.entries(d.cobertura || {})) {   // só conta como "sem novidade" quem não teve item em nenhum dia
      const acc = cobertura[c];
      if (!acc) { cobertura[c] = { ...x, itens: x.itens || 0, foraDaJanela: x.foraDaJanela || 0, mudancas: [...(x.mudancas || [])] }; continue; }
      acc.itens += x.itens || 0;
      acc.foraDaJanela += x.foraDaJanela || 0;
      for (const m of x.mudancas || []) if (!acc.mudancas.includes(m)) acc.mudancas.push(m);
      acc.ultimaMudanca ??= x.ultimaMudanca;
      acc.ultimaColeta ??= x.ultimaColeta;
      if (statusDe(x) === "irrelevante" && ["parado", "falha"].includes(statusDe(acc))) { acc.status = "irrelevante"; acc.mudou = true; }   // mudança em qualquer dia vale para o período; falha só vale se for a do dia mais novo e nada mudou
    }
    for (const e of d.eventos) eventos.push({ ...e, _dia: d.data });
  }
  const ordem = Object.keys(locais).sort((a, b) => (chaveLocal(a) < chaveLocal(b) ? -1 : 1));
  eventos.sort((a, b) => (chaveLocal(a.local) < chaveLocal(b.local) ? -1 : chaveLocal(a.local) > chaveLocal(b.local) ? 1 : 0));
  return {
    data: chave, de: dias[dias.length - 1].data, ate: dias[0].data, eventos, cobertura,
    locais: Object.fromEntries(ordem.map((c) => [c, locais[c]])),
    contagem: Object.fromEntries(ordem.map((c) => [c, contagem[c] || {}])),
  };
}

/* Locais acompanhados no dia (ou no período) que não tiveram item: distingue "nada aconteceu" de "não foi acompanhado" e mostra coleta parada. */
function coberturaSemNovidade(dia, codigos, local, mostrar, unidade = "dia") {
  if (!dia.cobertura || !mostrar) return "";
  const lista = Object.entries(dia.cobertura).filter(([c, x]) => !x.itens && (local && local !== "__avisos" ? c === local : noEscopo({ local: c, uf: c.startsWith("UF:") ? c.slice(3) : null, politicos: [] }, codigos)));
  if (!lista.length) return "";
  const status = statusDe;
  const referencia = dia.ate || dia.data;
  const fora = (x) => x.foraDaJanela ? `; ${x.foraDaJanela} ${x.foraDaJanela === 1 ? "item" : "itens"} com data do ato anterior à janela de 3 dias ficaram só no site` : "";
  const haDias = (x) => { const n = diasEntre(x.ultimaColeta, referencia); return n > 0 ? ` (há ${n} ${n === 1 ? "dia" : "dias"})` : ""; };
  const grupos = [
    ["irrelevante", "Dados mudaram, mas nada relevante para o histórico", (x) => (x.mudancas && x.mudancas.length ? `atualizou ${x.mudancas.join(", ")}` : "os arquivos foram atualizados, sem item para o histórico (detalhe não registrado neste dia)") + fora(x)],
    ["parado", "Sem dados novos", (x) => (x.ultimaMudanca ? `sem alteração desde ${data(x.ultimaMudanca)}` : "sem alteração nos dados") + fora(x)],
    ["falha", `Coleta falhou ou não rodou neste ${unidade}`, (x) => (x.ultimaColeta ? `última coleta gravada em ${data(x.ultimaColeta)}${haDias(x)}` : `nenhum dado gravado neste ${unidade}`) + fora(x), (a, b) => (a.ultimaColeta || "") < (b.ultimaColeta || "") ? -1 : 1],   // a parada mais antiga primeiro
  ];
  const bloco = ([chave, titulo, motivo, ordem]) => {
    const itens = lista.filter(([, x]) => status(x) === chave);
    if (ordem) itens.sort(([, a], [, b]) => ordem(a, b));
    return itens.length ? `<h3>${titulo} <small>${itens.length}</small></h3><ul>${itens.map(([, x]) => `<li><b>${esc(x.nome)}</b>: ${esc(motivo(x))}</li>`).join("")}</ul>` : "";
  };
  const acompanhados = lista.filter(([, x]) => status(x) !== "sem_cobertura");
  const sem = lista.filter(([, x]) => status(x) === "sem_cobertura");
  return (acompanhados.length ? `<section class="painel hist-sem"><h2>Acompanhados, sem novidade <small>${acompanhados.length}</small></h2>${grupos.map(bloco).join("")}</section>` : "")
    + (sem.length ? `<section class="painel hist-sem"><h2>Sem cobertura <small>${sem.length}</small></h2><p class="texto">Ainda não coletamos estes locais (sem fonte conectada): ${sem.map(([, x]) => `<b>${esc(x.nome)}</b>`).join(", ")}.</p></section>` : "");
}

function itemHistorico(e) {
  const mudanca = e.mudanca ? `<p class="hist-mudanca"><span>${esc(e.mudanca[0])}</span> → <b>${esc(e.mudanca[1])}</b></p>` : "";
  return `<li class="hist-item r-${e.relevancia || 2}">
    <div class="hist-cab"><span class="hist-tag k-${esc(e.categoria)}">${esc(CATEGORIAS_HIST[e.categoria] || e.categoria)}</span> <b>${esc(e.titulo)}</b>${e.dataDoAto ? (e.dataDoAtoAproximada ? ` <span class="quando" title="A fonte não informa a data desta mudança; vale o dia em que o site a encontrou">apresentado em ${esc(data(e.dataDoAto))}, data da mudança desconhecida</span>` : ` <span class="quando">${esc(data(e.dataDoAto))}</span>`) : ""}${e._dia ? ` <span class="quando">registrado em ${esc(data(e._dia))}</span>` : ""}</div>
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
  let periodo = PERIODOS[q.get("periodo")] ? q.get("periodo") : "dia";
  let grupos = agruparPeriodos(indice, periodo);
  const diaPedido = /^\d{4}-\d{2}-\d{2}/.test(q.get("dia") || "") ? chaveDe(periodo, q.get("dia").slice(0, 10)) : /^\d{4}-\d{2}$/.test(q.get("dia") || "") ? q.get("dia") : "";
  const diaInicial = grupos.some((g) => g.chave === diaPedido) ? diaPedido : grupos[0].chave;
  const listarPeriodos = (escolhido) => {
    grupos = agruparPeriodos(indice, periodo);
    $("#h-dia").innerHTML = grupos.map((g) => `<option value="${esc(g.chave)}">${esc(rotuloPeriodo(g, periodo))} (${g.total})</option>`).join("");
    $("#h-dia").value = escolhido;
  };

  alvo.innerHTML = `
    <div class="filtros hist-filtros">
      <label class="campo">Ver por<select id="h-periodo">${Object.entries(PERIODOS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></label>
      <label class="campo">Quando<select id="h-dia"></select></label>
      <label class="campo">Local<select id="h-local"></select></label>
      <label class="campo">Tipo<select id="h-tipo"><option value="">Todos</option>${Object.entries(CATEGORIAS_HIST).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></label>
      <label class="campo">Importância<select id="h-imp">${Object.entries(IMPORTANCIA_HIST).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></label>
      <label class="campo">Buscar<input id="h-busca" type="search" placeholder="Político, projeto ou assunto" autocomplete="off" value="${esc(q.get("busca") || "")}"></label>
    </div>
    <p class="contagem" id="h-contagem" aria-live="polite"></p>
    <div id="h-lista"></div>`;
  $("#h-periodo").value = periodo;
  listarPeriodos(diaInicial);
  $("#h-tipo").value = q.get("tipo") || "";
  $("#h-imp").value = q.has("imp") ? q.get("imp") : periodo === "dia" ? "" : "2";   // semana e mês começam em "Projetos e marcos"

  let dia = null;
  async function abrirDia() {
    $("#h-lista").innerHTML = `<p class="vazio">Carregando…</p>`;
    const g = grupos.find((x) => x.chave === $("#h-dia").value);
    try {
      dia = periodo === "dia" ? await carregar(`dados/historico/${g.chave}.json`)
        : juntarDias(await Promise.all(g.dias.map((d) => carregar(`dados/historico/${d}.json`))), g.chave);
    } catch (e) { return erro($("#h-lista"), e); }
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
    if (periodo !== "dia") novo.set("periodo", periodo);
    if (codigos.length) novo.set("locais", codigos.join(","));
    if (tipo) novo.set("tipo", tipo);
    if (imp || periodo !== "dia") novo.set("imp", $("#h-imp").value);
    if (busca) novo.set("busca", $("#h-busca").value.trim());
    history.replaceState(null, "", "?" + novo);

    const locais = [...new Set(filtrados.map((e) => e.local))];
    const quando = periodo === "dia" ? `em ${data(dia.data, true)}${dia.coletaEm ? ` (novidades ${dia.coletaAnterior ? `entre ${dataHora(dia.coletaAnterior)} e` : "até"} ${dataHora(dia.coletaEm)})` : ""}` : `de ${data(dia.de, true)} a ${data(dia.ate, true)}`;
    const unidade = periodo === "dia" ? "dia" : "período";
    $("#h-contagem").textContent = `${somar(filtrados)} de ${somar(dia.eventos)} mudanças ${quando}, em ${locais.length} ${locais.length === 1 ? "local" : "locais"}.`;
    const semNovidade = coberturaSemNovidade(dia, codigos, $("#h-local").value, tipo || busca || imp ? 0 : 1, unidade);
    if (!filtrados.length) { $("#h-lista").innerHTML = `<p class="vazio">Nada com esses filtros neste ${unidade}. Tente outro ${unidade} ou limpe os filtros.</p>${semNovidade}`; return; }
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

  $("#h-periodo").addEventListener("change", () => {
    const recente = grupos.find((g) => g.chave === $("#h-dia").value).dias[0];
    periodo = $("#h-periodo").value;
    $("#h-imp").value = periodo === "dia" ? "" : "2";
    listarPeriodos(chaveDe(periodo, recente));
    abrirDia();
  });
  $("#h-dia").addEventListener("change", abrirDia);
  $("#h-local").addEventListener("change", () => { codigos = $("#h-local").value === "__avisos" ? codigos : $("#h-local").value ? [$("#h-local").value] : []; desenhar(); });
  $("#h-tipo").addEventListener("change", desenhar);
  $("#h-imp").addEventListener("change", desenhar);
  $("#h-busca").addEventListener("input", desenhar);
  abrirDia();
}
