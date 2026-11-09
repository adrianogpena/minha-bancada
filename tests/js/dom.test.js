const test = require("node:test");
const assert = require("node:assert/strict");
const { Elemento, comPagina, comFetch, instalarDom, js } = require("./apoio_dom.js");

globalThis.window = {};
const comum = js("comum.js");
const { filtrosNaUrl, botaoVoltar, listaPaginada, abas, rotularTabelas, agruparFichas, moldura, ligarAbas } = comum;
const { montarEventos, abaEventos, painelEventos } = js("eventos.js");
const { blocoCampanha, blocoDisputa, blocoPartido, blocoAlianca, blocoOndeVotou, blocoPatrimonioFontes, linksRedes } = js("ficha.js");
const { casaLegislativa, itemGoverno, itemExecutivo } = js("executivo.js");
const { svgMapa, desenharEleitorado } = js("mapa.js");
const { painelGastos } = js("deputado.js");
const { painelAposentadoria } = js("senador.js");

const semEsperar = () => new Promise((r) => setTimeout(r, 0));

test("filtrosNaUrl lê os valores da URL, redesenha ao digitar e grava só os filtros preenchidos", async () => {
  const dom = instalarDom({ search: "?busca=ana&tipo=", pathname: "/votacoes.html" });
  try {
    let desenhos = 0;
    filtrosNaUrl(["busca", "tipo"], () => { desenhos++; });
    assert.equal(dom.el("#busca").value, "ana");
    assert.equal(dom.el("#tipo").value, "");
    assert.equal(desenhos, 1);
    dom.el("#busca").value = "zé";
    await dom.el("#busca").disparar("input");
    dom.el("#tipo").value = "PL";
    await dom.el("#tipo").disparar("input");
    dom.el("#busca").value = "";
    await dom.el("#busca").disparar("input");
    assert.equal(desenhos, 4);
    assert.deepEqual(dom.gravacoes.map((g) => g[1]), ["/votacoes.html?busca=z%C3%A9", "/votacoes.html?busca=z%C3%A9&tipo=PL", "/votacoes.html?tipo=PL"]);
  } finally { dom.restaurar(); }
});

test("filtrosNaUrl deixa o endereço sem query quando todos os filtros ficam vazios", async () => {
  const dom = instalarDom({ pathname: "/proposicoes.html" });
  try {
    filtrosNaUrl(["busca"], () => {});
    await dom.el("#busca").disparar("input");
    assert.deepEqual(dom.gravacoes, [["replaceState", "/proposicoes.html"]]);
  } finally { dom.restaurar(); }
});

test("botaoVoltar usa o rótulo da página de origem, escapa o destino e volta pelo histórico", async () => {
  const dom = instalarDom({ referrer: "https://site.exemplo/proposicoes.html?q=1", historico: 3 });
  try {
    const html = botaoVoltar("Lista", 'x.html?a="1"');
    assert.match(html, /href="x\.html\?a=&quot;1&quot;"/);
    assert.match(html, /← Voltar às proposições/);
    await semEsperar();
    const preventDefault = () => dom.gravacoes.push(["preventDefault"]);
    await dom.el(".voltar").disparar("click", { preventDefault });
    assert.deepEqual(dom.gravacoes, [["preventDefault"], ["back"]]);
  } finally { dom.restaurar(); }
});

test("botaoVoltar mostra o rótulo da lista sem referrer do site e não volta pelo histórico", async () => {
  for (const [referrer, esperado] of [["", "Lista"], ["https://outro.site/proposicoes.html", "Lista"], ["https://site.exemplo/votacoes.html", "Voltar às votações"], ["https://site.exemplo/index.html", "Voltar"]]) {
    const dom = instalarDom({ referrer, historico: 1 });
    try {
      assert.match(botaoVoltar("Lista", "l.html"), new RegExp(`← ${esperado}</a>`));
      await semEsperar();
      await dom.el(".voltar").disparar("click", { preventDefault: () => dom.gravacoes.push(["preventDefault"]) });
      assert.deepEqual(dom.gravacoes, []);
    } finally { dom.restaurar(); }
  }
});

test("listaPaginada mostra a mensagem vazia escapada quando não há itens", () => {
  const dom = instalarDom();
  try {
    const alvo = new Elemento();
    listaPaginada(alvo, [], () => "", 20, "Nada <aqui>");
    assert.equal(alvo.innerHTML, '<p class="vazio">Nada &lt;aqui&gt;</p>');
    listaPaginada(alvo, [], () => "");
    assert.match(alvo.innerHTML, /Nada por aqui ainda\./);
  } finally { dom.restaurar(); }
});

test("listaPaginada cresce de passo em passo, atualiza o contador e esconde o botão no fim", async () => {
  const dom = instalarDom();
  try {
    const alvo = new Elemento();
    listaPaginada(alvo, [1, 2, 3, 4, 5], (n) => `<li>${n}</li>`, 2);
    const ul = alvo.querySelector("ul");
    const botao = alvo.children[0];
    assert.equal(botao.className, "mais");
    assert.equal(ul.innerHTML, "<li>1</li><li>2</li>");
    assert.equal(botao.textContent, "Mostrar mais (3 restantes)");
    assert.equal(botao.hidden, false);
    await botao.disparar("click");
    assert.equal(ul.innerHTML, "<li>1</li><li>2</li><li>3</li><li>4</li>");
    assert.equal(botao.textContent, "Mostrar mais (1 restantes)");
    await botao.disparar("click");
    assert.equal(ul.innerHTML, "<li>1</li><li>2</li><li>3</li><li>4</li><li>5</li>");
    assert.equal(botao.hidden, true);
  } finally { dom.restaurar(); }
});

test("listaPaginada esconde o botão de imediato quando tudo cabe na primeira página", () => {
  const dom = instalarDom();
  try {
    const alvo = new Elemento();
    listaPaginada(alvo, ["a"], (n) => `<li>${n}</li>`, 20);
    assert.equal(alvo.children[0].hidden, true);
    assert.equal(alvo.querySelector("ul").innerHTML, "<li>a</li>");
  } finally { dom.restaurar(); }
});

test("abas desenha um botão por opção com escape, marca a primeira e troca a marca ao clicar", async () => {
  const alvo = new Elemento();
  abas(alvo, [{ valor: "a", rotulo: "<A>" }, { valor: 'b"', rotulo: "B" }], () => {});
  assert.match(alvo.innerHTML, /<button type="button" data-v="a" aria-pressed="true">&lt;A&gt;<\/button>/);
  assert.match(alvo.innerHTML, /data-v="b&quot;" aria-pressed="false"/);
  const b1 = new Elemento("button"), b2 = new Elemento("button");
  b1.setAttribute = (k, v) => { b1.marca = v; };
  b2.setAttribute = (k, v) => { b2.marca = v; };
  alvo.definirTodos("button", [b1, b2]);
  const escolhidos = [];
  alvo._ouvintes.click = [];
  abas(alvo, [{ valor: "a", rotulo: "A" }, { valor: "b", rotulo: "B" }], (v) => escolhidos.push(v));
  b2.dataset.v = "b";
  await alvo.disparar("click", { target: { closest: () => b2 } });
  await alvo.disparar("click", { target: { closest: () => null } });
  assert.deepEqual(escolhidos, ["b"]);
  assert.equal(b1.marca, false);
  assert.equal(b2.marca, true);
});

test("rotularTabelas copia o cabeçalho para as células sem rótulo e ignora matriz e tabela-fonte", () => {
  const celula = (rotulo) => ({ dataset: rotulo ? { rotulo } : {} });
  const th = (t) => ({ textContent: ` ${t} ` });
  const tabela = (cab, linhas) => ({
    querySelectorAll: (s) => (s === "thead th" ? cab.map(th) : s === "tbody tr" ? linhas : []),
  });
  const c1 = celula(), c2 = celula(), c3 = celula("já tinha"), c4 = celula();
  const t = tabela(["Nome", "Valor"], [{ children: [c1, c2] }, { children: [c3, c4, celula()] }]);
  const raiz = { querySelectorAll: (s) => {
    assert.equal(s, "table.tabela:not(.matriz):not(.tabela-fonte)");
    return [t];
  } };
  rotularTabelas(raiz);
  assert.equal(c1.dataset.rotulo, "Nome");
  assert.equal(c2.dataset.rotulo, "Valor");
  assert.equal(c3.dataset.rotulo, "já tinha");
  assert.equal(c4.dataset.rotulo, "Valor");
});

function noFicha(tag, embaixo = false) {
  const n = { tagName: tag, className: embaixo ? "embaixo" : "", classList: { contains: (c) => n.className.split(" ").includes(c) }, filhos: [] };
  return n;
}

test("agruparFichas põe cada dt com o dd seguinte numa div e marca a lista como agrupada", () => {
  const dom = instalarDom();
  try {
    const dt1 = noFicha("DT"), dd1 = noFicha("DD"), dt2 = noFicha("DT", true), dd2 = noFicha("DD", true), dt3 = noFicha("DT");
    const dl = { dataset: {}, children: [dt1, dd1, dt2, dd2, dt3] };
    dl.insertBefore = (g, ref) => { dl.children.splice(dl.children.indexOf(ref), 0, g); };
    dom.doc.createElement = () => {
      const g = { className: "", filhos: [] };
      g.append = (n) => { dl.children.splice(dl.children.indexOf(n), 1); g.filhos.push(n); };
      return g;
    };
    agruparFichas({ querySelectorAll: (s) => (s === "dl.ficha:not([data-agrupada])" ? [dl] : []) });
    assert.equal(dl.dataset.agrupada, "1");
    assert.equal(dl.children.length, 3);
    assert.deepEqual(dl.children.map((g) => g.filhos.map((f) => f.tagName)), [["DT", "DD"], ["DT", "DD"], ["DT"]]);
    assert.deepEqual(dl.children.map((g) => g.className), ["", "embaixo", ""]);
  } finally { dom.restaurar(); }
});

test("agruparFichas não mexe numa ficha que tem filho fora de dt e dd", () => {
  const dl = { dataset: {}, children: [noFicha("DT"), noFicha("DIV")] };
  agruparFichas({ querySelectorAll: () => [dl] });
  assert.equal(dl.dataset.agrupada, undefined);
  assert.equal(dl.children.length, 2);
});

test("moldura monta cabeçalho, menu com a página atual marcada, barra do celular e rodapé com a data da coleta", async () => {
  await comPagina({}, { "dados/meta.json": { atualizadoEm: "2026-03-10T12:30:00-03:00" } }, async (dom) => {
    moldura("deputado");
    const topo = dom.corpo.innerHTML;
    assert.match(topo, /<header class="topo">/);
    assert.match(topo, /<a href="camara\.html" aria-current="page">Câmara<\/a>/);
    assert.equal((topo.match(/aria-current="page"/g) || []).length, 3);
    assert.match(topo, /<button type="button" aria-current="page">Políticos<\/button>/);
    assert.match(topo, /<button type="button" class="mb-item" id="mb-mais" aria-expanded="false"[^>]*>Mais<\/button>/);
    assert.doesNotMatch(topo, /<button type="button" class="mb-item" id="mb-mais"[^>]*aria-current/);
    assert.match(topo, /<footer class="rodape">/);
    await semEsperar();
    assert.match(dom.el("#rodape").innerHTML, /Última atualização: \d{2}\/\d{2}\/\d{2}/);
  });
});

test("moldura de uma página do menu Mais marca o botão Mais e usa o nome da página quando não há apelido", async () => {
  await comPagina({}, {}, async (dom) => {
    moldura("sobre");
    const topo = dom.corpo.innerHTML;
    assert.match(topo, /<a href="sobre\.html" aria-current="page">Sobre os dados<\/a>/);
    assert.match(topo, /id="mb-mais"[^>]*aria-current="page">Mais/);
    assert.match(topo, /<button type="button" aria-current="page">Dados<\/button>/);
    await semEsperar();
    assert.doesNotMatch(dom.el("#rodape").innerHTML, /Última atualização/);
  });
});

test("moldura liga o botão Mais à folha: abre, fecha ao tocar num link e fecha com Escape", async () => {
  await comPagina({}, {}, async (dom) => {
    moldura("camara");
    await semEsperar();
    const botao = dom.el("#mb-mais"), folha = dom.el("#mb-folha");
    folha.hidden = true;
    await botao.disparar("click");
    assert.equal(folha.hidden, false);
    assert.equal(botao.getAttribute("aria-expanded"), "true");
    await folha.disparar("click", { target: { closest: () => ({}) } });
    assert.equal(folha.hidden, true);
    assert.equal(botao.getAttribute("aria-expanded"), "false");
    await botao.disparar("click");
    for (const fn of dom.doc._ouvintes.keydown) await fn({ key: "Escape" });
    assert.equal(folha.hidden, true);
    await botao.disparar("click");
    for (const fn of dom.doc._ouvintes.keydown) await fn({ key: "Enter" });
    assert.equal(folha.hidden, false);
  });
});

test("ligarAbas escolhe a aba do endereço e atualiza o hash ao clicar", async () => {
  const dom = instalarDom({ hash: "#eleicao", pathname: "/politico.html", search: "?f=x" });
  try {
    const alvo = new Elemento();
    const botoes = ["perfil", "eleicao"].map((a) => { const b = new Elemento("button"); b.dataset.aba = a; return b; });
    const paineis = ["perfil", "eleicao"].map((a) => { const p = new Elemento(); p.id = `painel-${a}`; return p; });
    alvo.definirTodos("[data-aba]", botoes);
    alvo.definirTodos("[role=tabpanel]", paineis);
    const faixa = alvo.querySelector(".abas-pagina");
    alvo.querySelector("[role=tabpanel]:not([hidden])").getBoundingClientRect = () => ({ top: -50 });
    faixa.getBoundingClientRect = () => ({ bottom: 0 });
    ligarAbas(alvo);
    assert.deepEqual(botoes.map((b) => b.getAttribute("aria-selected")), ["false", "true"]);
    assert.deepEqual(paineis.map((p) => p.hidden), [true, false]);
    assert.deepEqual(dom.gravacoes, []);
    await faixa.disparar("click", { target: { closest: () => botoes[0] } });
    assert.deepEqual(botoes.map((b) => b.getAttribute("aria-selected")), ["true", "false"]);
    assert.deepEqual(paineis.map((p) => p.hidden), [false, true]);
    assert.deepEqual(dom.gravacoes[0], ["replaceState", "/politico.html?f=x"]);
    assert.deepEqual(dom.gravacoes[1], ["scrollBy", { top: -50, behavior: "smooth" }]);
    await faixa.disparar("click", { target: { closest: () => botoes[1] } });
    assert.deepEqual(dom.gravacoes[2], ["replaceState", "/politico.html?f=x#eleicao"]);
  } finally { dom.restaurar(); }
});

test("montarEventos só carrega a lista com o painel aberto e escapa o link dos políticos", async () => {
  const observadores = [];
  globalThis.MutationObserver = class { constructor(fn) { this.fn = fn; observadores.push(this); } observe() {} };
  const respostas = {
    "dados/historico/indice.json": [{ data: "2026-03-03" }],
    "dados/historico/2026-03-03.json": { data: "2026-03-03", eventos: [{ id: "e1", titulo: "<b>Evento</b>", politicos: [{ codigo: "pes_1" }] }] },
  };
  try {
    await comPagina({}, respostas, async (dom, chamadas) => {
      const alvo = new Elemento();
      alvo.querySelector("#painel-eventos").hidden = true;
      montarEventos(alvo, ["pes_1", "min:x y"]);
      await semEsperar();
      assert.deepEqual(chamadas, []);
      alvo.querySelector("#painel-eventos").hidden = false;
      await observadores[0].fn();
      await semEsperar();
      const html = alvo.querySelector("#eventos-politico").innerHTML;
      assert.match(html, /único evento registrado/);
      assert.match(html, /&lt;b&gt;Evento&lt;\/b&gt;/);
      assert.match(html, /politico=pes_1%2Cmin%3Ax%20y/);
      assert.equal(chamadas.length, 2);
      await observadores[0].fn();
      assert.equal(chamadas.length, 2);
    });
  } finally { delete globalThis.MutationObserver; }
});

test("montarEventos avisa quando o político não tem eventos e mostra o erro quando a leitura falha", async () => {
  globalThis.MutationObserver = class { observe() {} };
  try {
    await comPagina({}, { "dados/historico/indice.json": [{ data: "2026-03-03" }], "dados/historico/2026-03-03.json": { data: "2026-03-03", eventos: [] } }, async () => {
      const alvo = new Elemento();
      montarEventos(alvo, ["pes_9"]);
      await semEsperar();
      const html = alvo.querySelector("#eventos-politico").innerHTML;
      assert.match(html, /Nenhum evento registrado no histórico do site\./);
      assert.doesNotMatch(html, /hist-itens/);
    });
    await comPagina({}, { "dados/historico/indice.json": [{ data: "2026-03-03" }] }, async (dom, chamadas, erros) => {
      const alvo = new Elemento();
      montarEventos(alvo, ["pes_9"]);
      await semEsperar();
      assert.match(alvo.querySelector("#eventos-politico").innerHTML, /class="aviso">Não foi possível carregar dados\/historico\/2026-03-03\.json \(404\)/);
      assert.equal(erros.length, 1);
    });
  } finally { delete globalThis.MutationObserver; }
  assert.match(abaEventos, /data-aba="eventos"/);
  assert.match(painelEventos, /id="eventos-politico"/);
});

const contas = (extra = {}) => ({
  receitas: 1000, despesasContratadas: 900, despesasPagas: 700,
  origensReceita: [["Recursos de partido político", 600], ["Pessoa física", 400]],
  principaisDoadores: [["Ana <Doadora>", "Pessoa física", 250]],
  doadoresOriginarios: [["Empresa X", 100]],
  gastosPorCategoria: [["Publicidade", 500]],
  custoVoto: { valor: 12.5, cargo: { mediana: 10, n: 300 }, partido: { mediana: 8, n: 12 } },
  ...extra,
});

test("blocoCampanha com contas mostra arrecadação, pendências, origens, doadores, gastos e custo do voto", () => {
  const fontesLista = [["Outra", "http://x"]];
  const html = blocoCampanha({ ano: 2022, partido: "ABC", votos: [1, 2], contas: contas() }, fontesLista);
  assert.match(html, /<h3>Campanha de 2022: quem pagou<\/h3>/);
  assert.match(html, /Arrecadou <b>R\$\s1\.000,00<\/b> e contratou <b>R\$\s900,00<\/b>/);
  assert.match(html, /Pagou <b>R\$\s700,00<\/b>[^.]*<b>R\$\s200,00<\/b> ficaram contratados e sem pagamento/);
  assert.match(html, /Recursos de partido político<\/span> <b>R\$\s600,00<\/b> \(60%\)/);
  assert.match(html, /<b>Ana &lt;Doadora&gt;<\/b>/);
  assert.match(html, /Quem está por trás dos repasses/);
  assert.match(html, /Em que gastou/);
  assert.match(html, /Custo do voto: <b>R\$\s12,50<\/b>[^.]*, somando os turnos/);
  assert.match(html, /mediana do ABC nesse cargo: R\$\s8,00 \(12 eleitos\)/);
  assert.match(html, /Dependência do partido: <b>60,0%<\/b>/);
  assert.equal(fontesLista[0][0], "Prestação de contas de campanha 2022 (TSE)");
  assert.match(fontesLista[0][1], /prestacao_de_contas_eleitorais_candidatos_2022\.zip$/);
  assert.equal(fontesLista.length, 2);
});

test("blocoCampanha omite as seções vazias e o aviso de despesas sem pagamento quando está tudo pago", () => {
  const html = blocoCampanha({ ano: 2024, contas: { receitas: 0, despesasContratadas: 100, despesasPagas: 100, origensReceita: [], principaisDoadores: [], gastosPorCategoria: [] } }, []);
  assert.doesNotMatch(html, /sem pagamento registrado/);
  assert.doesNotMatch(html, /De onde veio o dinheiro|Maiores doadores|Em que gastou|Custo do voto|Dependência do partido|por trás dos repasses/);
});

test("blocoDisputa sem dados avisa só antes de 2026 e com dados lista os turnos e as vagas", () => {
  assert.match(blocoDisputa({ ano: 2022 }, []), /dado sem fonte: comparecimento desta eleição ainda não coletado/);
  assert.equal(blocoDisputa({ ano: 2026 }, []), "");
  const lista = [];
  const html = blocoDisputa({ ano: 2022, disputa: { vagas: 70, turnos: { 2: { aptos: 1000, comparecimento: 800, abstencoes: 200, brancos: 10, nulos: 20, validos: 770 }, 1: { aptos: 1000, comparecimento: 0, abstencoes: 0, brancos: 0, nulos: 0, validos: 0 } } } }, lista);
  assert.match(html, /Vagas em disputa neste cargo e local: <b>70<\/b>/);
  assert.ok(html.indexOf("1º turno") < html.indexOf("2º turno"));
  assert.match(html, /compareceram <b>800<\/b> \(80,0%\) · abstenção 200 \(20,0%\)/);
  assert.match(html, /compareceram <b>0<\/b> \(0,0%\)/);
  assert.deepEqual(lista.map((f) => f[0]), ["Detalhe da votação 2022 (TSE)", "Vagas 2022 (TSE)"]);
  const semVagas = [];
  assert.doesNotMatch(blocoDisputa({ ano: 2022, disputa: { vagas: null, turnos: {} } }, semVagas), /Vagas em disputa/);
  assert.equal(semVagas.length, 1);
});

test("blocoPartido calcula o quociente eleitoral e inclui a federação quando existe", () => {
  assert.match(blocoPartido({ ano: 2022, cargoTse: "DEPUTADO FEDERAL" }, []), /dado sem fonte: votos do partido nesta eleição/);
  assert.equal(blocoPartido({ ano: 2022, cargoTse: "GOVERNADOR" }, []), "");
  assert.equal(blocoPartido({ ano: 2026, cargoTse: "DEPUTADO FEDERAL" }, []), "");
  const lista = [];
  const e = { ano: 2022, partido: "A<B", disputa: { vagas: 10 }, partidoVotos: { votosLegenda: 100, votosNominais: 900, totalVotosPartidos: 10000 } };
  const html = blocoPartido(e, lista);
  assert.match(html, /O A&lt;B teve <b>1\.000<\/b> votos válidos \(10,0%\): <b>900<\/b> em candidatos e <b>100<\/b> só na legenda/);
  assert.match(html, /10\.000 votos válidos ÷ 10 vagas = <b>1\.000<\/b> votos por vaga\. O partido teve 1,0 quocientes\./);
  assert.doesNotMatch(html, /federação/);
  assert.equal(lista.length, 1);
  const fed = blocoPartido({ ...e, partidoVotos: { ...e.partidoVotos, federacao: "PT/PCdoB", votosLegendaFederacao: 300, votosNominaisFederacao: 1700 } }, []);
  assert.match(fed, /federação PT \/ PCdoB[^<]*<b>2\.000<\/b> votos \(20,0%\), sendo 300 de legenda/);
  assert.match(fed, /A federação teve 2,0 quocientes/);
});

test("blocoPartido sem vagas não mostra o quociente", () => {
  const html = blocoPartido({ ano: 2022, partido: "X", partidoVotos: { votosLegenda: 1, votosNominais: 1, totalVotosPartidos: 0 } }, []);
  assert.doesNotMatch(html, /Quociente eleitoral/);
  assert.match(html, /<b>2<\/b> votos válidos/);
});

test("blocoAlianca descreve coligação, federação e candidatura isolada e avisa legenda não deferida", () => {
  assert.match(blocoAlianca({ ano: 2020 }, []), /dado sem fonte: coligação ou federação desta eleição/);
  assert.equal(blocoAlianca({ ano: 2026 }, []), "");
  const lista = [];
  const col = blocoAlianca({ ano: 2022, partido: "A", alianca: { tipo: "C", nome: "Juntos <X>", composicao: "A (10-A) / 11-B", situacao: "Deferido" } }, lista);
  assert.match(col, /O A concorreu em coligação <b>Juntos &lt;X&gt;<\/b>, com os partidos: A \(A\) \/ B\./);
  assert.doesNotMatch(col, /Situação da legenda/);
  assert.equal(lista.length, 1);
  assert.match(blocoAlianca({ ano: 2022, partido: "A", alianca: { tipo: "F", composicao: "A / B" } }, []), /concorreu em federação, que vale como um partido só: A \/ B\./);
  const sozinho = blocoAlianca({ ano: 2022, partido: "A", alianca: { tipo: "I", composicao: "A", situacao: "Indeferido <1>" } }, []);
  assert.match(sozinho, /concorreu sozinho, sem coligação nem federação\./);
  assert.match(sozinho, /Situação da legenda no TSE: <b>Indeferido &lt;1&gt;<\/b>/);
});

test("blocoOndeVotou lista locais e municípios, escapa os dados do mapa e cita as fontes", () => {
  assert.match(blocoOndeVotou({ ano: 2022 }, []), /dado sem fonte: votos por seção desta eleição ainda não coletados/);
  assert.equal(blocoOndeVotou({ ano: 2026 }, []), "");
  const lista = [];
  const e = { ano: 2022, uf: "SP", secoes: {
    turno: 1, totalVotos: 1000,
    locaisDeVotacao: [["Escola <A>", -23.5, -46.6, 250], ["Escola B", null, null, 100]],
    votosPorMunicipio: [["3550308", 500]],
    municipios: [["São Paulo", 500]],
  } };
  const html = blocoOndeVotou(e, lista);
  assert.match(html, /Locais de votação com mais votos no 1º turno de 2022, de um total de 1\.000 votos\./);
  assert.match(html, /class="mapa-votos"[^>]*data-pontos="\[\[&quot;Escola &lt;A&gt;&quot;,-23\.5,-46\.6,250\]\]"/);
  assert.match(html, /<li>Escola &lt;A&gt;: <b>250 votos<\/b> \(25,0%\)<\/li>/);
  assert.match(html, /<li>Escola B: <b>100 votos<\/b> \(10,0%\)<\/li>/);
  assert.match(html, /data-uf="SP" data-votos-por-municipio="\[\[&quot;3550308&quot;,500\]\]"/);
  assert.match(html, /<li>São Paulo: <b>500 votos<\/b> \(50,0%\)<\/li>/);
  assert.deepEqual(lista.map((f) => f[0]), ["Votação por seção 2022 (TSE)", "Locais de votação 2022 (TSE)", "Malhas municipais (IBGE)"]);
});

test("blocoOndeVotou sem locais fala em municípios e sem total não calcula percentual", () => {
  const html = blocoOndeVotou({ ano: 2022, uf: "SP", secoes: { turno: 1, totalVotos: 0, municipios: [["Santos", 5]] } }, []);
  assert.match(html, /Municípios com mais votos no 1º turno/);
  assert.match(html, /<li>Santos: <b>5 votos<\/b><\/li>/);
  assert.doesNotMatch(html, /mapa-votos|Votos por município/);
});

test("blocoPatrimonioFontes mostra a evolução com variação e junta as fontes de cada eleição", () => {
  const p = { ano: 2022, patrimonio: [[2018, "SENADOR", 100000], [2022, "SENADOR", 150000], [2024, "PREFEITO", 0]] };
  const html = blocoPatrimonioFontes(p, [["Base", "https://base.exemplo"]], [["Extra", "https://extra.exemplo"]]);
  assert.match(html, /Evolução do patrimônio declarado/);
  assert.match(html, /2018, Senador<\/span> <b>R\$\s100\.000,00<\/b>/);
  assert.match(html, /\(\+50,0% em relação a 2018\)/);
  assert.match(html, /\(−100,0% em relação a 2022\)/);
  assert.match(html, /Base/);
  assert.match(html, /Extra/);
  assert.match(html, /Bens de candidatos 2018 \(TSE\)/);
  const curto = blocoPatrimonioFontes({ ano: 2022, patrimonio: [[2022, "SENADOR", 1]] }, [], []);
  assert.doesNotMatch(curto, /Evolução do patrimônio/);
  assert.match(curto, /Portal de Dados Abertos do TSE/);
});

test("linksRedes separa perfis do político de outros, limita a seis e escapa", () => {
  assert.equal(linksRedes([], { nome: "Ana" }), null);
  assert.equal(linksRedes(["javascript:alert(1)", "https://x.com/ana silva"], { nome: "Ana" }), null);
  const redes = ["https://www.instagram.com/anamaria?x=1#y", "https://outro.com/foto<1>"];
  const html = linksRedes(redes, { nome: "Ana Maria", urna: "", fonteRedes: "<F>" });
  assert.match(html, /<span class="link-bloco"><a class="link-rede" href="https:\/\/www\.instagram\.com\/anamaria\?x=1#y" rel="noopener">instagram\.com\/anamaria<\/a><F><\/span>/);
  assert.match(html, /<b>Outros perfis e sites citados na candidatura<\/b>/);
  assert.match(html, /outro\.com\/foto&lt;1&gt;/);
  const muitas = Array.from({ length: 8 }, (_, i) => `https://rede.com/ana${i}`);
  assert.match(linksRedes(muitas, { nome: "Ana" }), /<details><summary>mais 2<\/summary>/);
});

test("casaLegislativa identifica a casa pelo cargo e só dá link quando conhece o site", () => {
  assert.deepEqual(casaLegislativa({ fonte: "senado" }).link, ["Senado Federal", "https://www25.senado.leg.br"]);
  assert.equal(casaLegislativa({ cargoTse: "PRESIDENTE" }).quem, "o Congresso Nacional");
  const gov = casaLegislativa({ cargoTse: "GOVERNADOR", uf: "SP" });
  assert.equal(gov.quem, "a Assembleia Legislativa (São Paulo)");
  assert.deepEqual(gov.link, ["Site da Assembleia Legislativa", "https://www.al.sp.gov.br"]);
  assert.equal(casaLegislativa({ cargoTse: "VICE-GOVERNADOR" }).link, null);
  const pref = casaLegislativa({ cargoTse: "PREFEITO", municipio: "Recife", ue: "25313" });
  assert.equal(pref.quem, "a Câmara Municipal de Recife");
  assert.deepEqual(pref.link, ["Site da Câmara Municipal", "https://www.recife.pe.leg.br"]);
  assert.equal(casaLegislativa({ cargoTse: "PREFEITO", ue: "00000" }).link, null);
  assert.deepEqual(casaLegislativa({ cargoTse: "VEREADOR", municipio: "Santos" }), { quem: "", em: "na Câmara Municipal de Santos", link: null });
  assert.equal(casaLegislativa({ cargoTse: "DEPUTADO ESTADUAL", uf: "MG" }).em, "na Assembleia Legislativa (Minas Gerais)");
});

test("itemExecutivo traduz o desfecho do projeto do presidente, escapa a ementa e só liga texto seguro", () => {
  const base = { tipo: "PL", numero: 1, ano: 2025, id: 77, dataApresentacao: "2025-01-10", ementa: "<script>x</script>" };
  const vetado = itemExecutivo({ ...base, veto: "total", dataNorma: "2025-03-01", razoesVeto: "R <1>" });
  assert.match(vetado, /Projeto de lei 1\/2025/);
  assert.match(vetado, /<span class="voto v-nao">Vetou<\/span>/);
  assert.match(vetado, /&lt;script&gt;x&lt;\/script&gt;/);
  assert.doesNotMatch(vetado, /<script>/);
  assert.match(vetado, /Razões do veto: R &lt;1&gt;/);
  assert.match(vetado, /idProposicao=77/);
  assert.doesNotMatch(vetado, /Texto original/);
  const lei = itemExecutivo({ ...base, situacao: "Transformado em Norma Jurídica", veto: "parcial", norma: "Lei 1/2025", inteiroTeor: "https://t.exemplo/x.pdf" });
  assert.match(lei, /Virou lei, com vetos/);
  assert.match(lei, /<b>Lei 1\/2025<\/b>/);
  assert.match(lei, /href="https:\/\/t\.exemplo\/x\.pdf" rel="noopener">Texto original/);
  assert.doesNotMatch(itemExecutivo({ ...base, inteiroTeor: "javascript:1" }), /Texto original/);
  assert.match(itemExecutivo({ ...base, situacao: "Aguardando Sanção" }), /Decide se sanciona[\s\S]*15 dias úteis/);
  assert.match(itemExecutivo({ ...base, tipo: "MPV" }), /Medida provisória 1\/2025[\s\S]*MP em vigor/);
  assert.match(itemExecutivo({ ...base, tipo: "MPV", situacao: "Perdeu a eficácia", dataSituacao: "2025-06-01" }), /MP deixou de valer[\s\S]*perdeu a eficácia em/);
  assert.match(itemExecutivo({ ...base, situacao: "Arquivada" }), /Não virou lei[\s\S]*Não houve sanção nem veto/);
  assert.match(itemExecutivo({ ...base, situacao: "Em tramitação" }), /No Congresso[\s\S]*Ainda no Congresso/);
});

test("itemGoverno distingue veto, lei, retirada, tramitação e encerramento para governador e prefeito", () => {
  const base = { tipoDescricao: "Projeto <de Lei>", numero: "9", ano: "2024", ementa: "Ementa & cia", dataApresentacao: "2024-02-02" };
  const gov = itemGoverno(false), pref = itemGoverno(true);
  const veto = gov({ ...base, tipo: "VET", tipoDescricao: "Veto Total", situacao: "Em tramitação" });
  assert.match(veto, /Veto Total 9\/2024/);
  assert.match(veto, /Vetou tudo/);
  assert.match(veto, /O governador vetou<\/b> o texto inteiro/);
  assert.match(veto, /A Assembleia ainda vai decidir/);
  assert.match(pref({ ...base, tipo: "VET", tipoDescricao: "Veto Parcial", situacao: "Arquivado" }), /Vetou em parte[\s\S]*A Câmara já concluiu/);
  const lei = gov({ ...base, situacao: "Sancionado (2024-05-05)", linkTexto: "https://x.exemplo/lei.pdf" });
  assert.match(lei, /Virou lei<\/span>/);
  assert.match(lei, /sancionou<\/b>\s*\(/);
  assert.match(lei, /\(05 de mai\. de 2024\)/);
  assert.match(lei, /href="https:\/\/x\.exemplo\/lei\.pdf" rel="noopener">Texto/);
  assert.match(gov({ ...base, linkTexto: "https://x.exemplo/p" }), />Tramitação<\/a>/);
  assert.doesNotMatch(gov({ ...base, linkTexto: "javascript:1" }), /<a href/);
  assert.match(pref({ ...base, situacao: "Retirado" }), /Retirou[\s\S]*O prefeito retirou/);
  assert.match(pref({ ...base, situacao: "Em tramitação", tipoDescricao: "Mensagem 3" }), /Na Câmara[\s\S]*enviou<\/b> uma mensagem à Câmara/);
  assert.match(gov({ ...base, situacao: "Arquivada" }), /Encerrado[\s\S]*não informa se virou lei/);
  const sem = gov({ ...base, situacao: "" });
  assert.match(sem, /Sem situação/);
  assert.match(sem, /não informada/);
  assert.match(gov({ ...base, tipoDescricao: "Medida Provisória" }), /editou<\/b> a medida provisória/);
});

test("svgMapa desenha um caminho por feição com o id escapado e ajusta a caixa aos extremos", () => {
  const fc = { features: [
    { id: "a\"b", geometry: { type: "Polygon", coordinates: [[[0, 0], [10, 0], [10, 10], [0, 10]]] } },
    { id: "c", geometry: { type: "MultiPolygon", coordinates: [[[[20, 0], [30, 0], [30, 10]]], [[[40, 0], [41, 0], [41, 1]]]] } },
  ] };
  const svg = svgMapa(fc, (f) => f.id);
  assert.equal((svg.match(/<path /g) || []).length, 2);
  assert.match(svg, /data-id="a&quot;b"/);
  assert.match(svg, /^<svg viewBox="0 0 1000 /);
  assert.equal((svg.match(/M/g) || []).length, 3);
  assert.equal((svg.match(/Z/g) || []).length, 3);
});

test("desenharEleitorado esconde o bloco sem UF, sem arquivo e sem total, e desenha os grupos quando há dados", async () => {
  const sem = new Elemento();
  await desenharEleitorado(sem, "", null, "x");
  assert.equal(sem.hidden, true);
  const dados = { ano: 2024, locais: { _uf: { total: 1000, porGenero: [450, 550], porFaixaEtaria: [10, 90, 100, 200, 200, 200, 100, 100], porEscolaridade: [1, 1, 1, 1, 1, 1, 1, 993] }, vazio: { total: 0 } } };
  await comFetch({ "dados/eleitorado/ZZ.json": dados }, async () => {
    const a = new Elemento();
    await desenharEleitorado(a, "XX", null, "x");
    assert.equal(a.hidden, true);
    const b = new Elemento();
    await desenharEleitorado(b, "ZZ", "vazio", "x");
    assert.equal(b.hidden, true);
    const c = new Elemento();
    await desenharEleitorado(c, "ZZ", null, "Estado <Z>");
    assert.equal(c.hidden, false);
    assert.match(c.innerHTML, /Eleitorado de Estado &lt;Z&gt;: <b>1\.000<\/b> eleitores \(2024\)/);
    assert.match(c.innerHTML, /Mulheres<\/span>\n?\s*<b>550 · 55,0%<\/b>/);
    assert.match(c.innerHTML, /Superior completo/);
    assert.match(c.innerHTML, /perfil_eleitorado_2024\.zip/);
  });
});

test("painelGastos mostra total, comparação com a cota e a média do estado, categorias, fornecedores e maiores notas", () => {
  const desp = {
    ano: 2025, total: 50000,
    limite: { mensal: 10000, meses: 10 }, mediaUF: { uf: "SP", deputados: 70, media: 40000 },
    porCategoria: [{ categoria: "Passagens <aéreas>", total: 30000, originais: [["Passagem", 30000]] }, { categoria: "Outros", total: 15000, originais: [] }],
    fornecedores: [["Empresa & Cia", 20000]],
    maiores: [{ data: "2025-02-01", fornecedor: "Forn <X>", tipo: "Voo", valor: 1234.5, documento: "https://nota.exemplo/1" }, { mes: 3, valor: 5, documento: "javascript:1" }],
  };
  const html = painelGastos(desp, "Explicação <b>");
  assert.match(html, /Gastos da cota parlamentar em 2025/);
  assert.match(html, /Total no ano: <b>R\$\s50\.000,00<\/b>\. Explicação &lt;b&gt;/);
  assert.match(html, /limite mensal da cota em SP é de R\$\s10\.000,00[^]*usou <b>50,0%<\/b>/);
  assert.match(html, /média dos 70 deputados em exercício de SP é de R\$\s40\.000,00; este deputado gastou <b>25,0% a mais<\/b>/);
  assert.match(html, /Passagens &lt;aéreas&gt;/);
  assert.match(html, /width:100%/);
  assert.match(html, /width:50%/);
  assert.match(html, /<td>Empresa &amp; Cia<\/td><td>R\$\s20\.000<\/td>/);
  assert.match(html, /Forn &lt;X&gt;/);
  assert.match(html, /href="https:\/\/nota\.exemplo\/1" rel="noopener">documento fiscal/);
  assert.match(html, /<td>mês 3<\/td><td>Não informado<\/td>/);
  assert.equal((html.match(/documento fiscal/g) || []).length, 1);
});

test("painelGastos sem despesas mostra os avisos de vazio e sem comparações nem maiores notas", () => {
  const html = painelGastos({ ano: 2025, total: 0, porCategoria: [], fornecedores: [], maiores: [] }, "x");
  assert.match(html, /Nenhuma despesa registrada neste ano\./);
  assert.match(html, /Sem fornecedores no período\./);
  assert.doesNotMatch(html, /Maiores notas do ano|limite mensal|A média dos/);
  const igual = painelGastos({ ano: 2025, total: 100, porCategoria: [], fornecedores: [], mediaUF: { uf: "AC", deputados: 8, media: 100 } }, "x");
  assert.match(igual, /gastou o mesmo/);
});

test("painelAposentadoria traduz o tipo, mostra início e valor e some sem registro", () => {
  assert.equal(painelAposentadoria(null), "");
  const ipc = painelAposentadoria({ tipo: "EX-SENADOR IPC", inicio: "2015-02-01", valor: 30000 });
  assert.match(ipc, /Instituto de Previdência dos Congressistas \(IPC\)/);
  assert.match(ipc, /desde 1 de fevereiro de 2015/);
  assert.match(ipc, /<b>R\$\s30\.000,00<\/b> por mês/);
  assert.match(painelAposentadoria({ tipo: "EX-SENADOR PSSC" }), /Plano de Seguridade Social dos Congressistas \(PSSC\)/);
  const outro = painelAposentadoria({ tipo: "<OUTRO>" });
  assert.match(outro, /&lt;OUTRO&gt;/);
  assert.doesNotMatch(outro, /desde|por mês/);
});
