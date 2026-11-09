const test = require("node:test");
const assert = require("node:assert/strict");
const { Elemento, comPagina, js } = require("./apoio_dom.js");

globalThis.window = {};
const { paginaCoautoria } = js("coautoria.js");
const { paginaFonte } = js("fonte.js");
const { paginaTribunais } = js("tribunais.js");
const { paginaMinistro, paginaMinisterios, avisoLicenca } = js("ministros.js");
const { paginaFornecedores } = js("fornecedores.js");
const { paginaVotacoes, paginaVotacao } = js("votacoes.js");
const { paginaProposicoes, paginaProposicao } = js("proposicoes.js");
const { paginaPoliticos } = js("politicos.js");
const { montarEstadual } = js("estadual.js");

const esperar = async (n = 4) => { for (let i = 0; i < n; i++) await new Promise((r) => setTimeout(r, 0)); };
const ul = (el) => el.querySelector("ul").innerHTML;

test("paginaCoautoria mostra o erro quando o arquivo falta", async () => {
  await comPagina({}, {}, async (dom, chamadas, erros) => {
    await paginaCoautoria();
    assert.match(dom.el("#resultado").innerHTML, /Não foi possível carregar dados\/coautoria\.json \(404\)/);
    assert.equal(erros.length, 1);
  });
});

test("paginaCoautoria ignora partidos pequenos, escapa as siglas e monta a matriz simétrica", async () => {
  const j = {
    projetos: 40, ignorados: 1, maxAutores: 30,
    partidos: [{ sigla: "A<B", projetos: 20, comOutros: 10 }, { sigla: "CC", projetos: 10, comOutros: 9 }, { sigla: "PEQ", projetos: 4, comOutros: 4 }],
    pares: { "A<B|CC": 5, "A<B|PEQ": 3 },
  };
  await comPagina({}, { "dados/coautoria.json": j }, async (dom) => {
    await paginaCoautoria();
    const html = dom.el("#resultado").innerHTML;
    assert.match(dom.el("#contagem").textContent, /^40 projetos assinados por mais de um deputado, 2 partidos com ao menos 5 deles$/);
    assert.doesNotMatch(html, /PEQ/);
    assert.match(html, /<td>A&lt;B<\/td><td>20<\/td><td>10 \(50%\)<\/td>/);
    assert.ok(html.indexOf("<td>CC</td>") < html.indexOf("<td>A&lt;B</td>"));
    assert.equal((html.match(/title="A&lt;B e CC: 5 projetos"/g) || []).length, 1);
    assert.equal((html.match(/title="CC e A&lt;B: 5 projetos"/g) || []).length, 1);
    assert.equal((html.match(/<td class="vazio">·<\/td>/g) || []).length, 2);
    assert.match(html, /rgba\(36,86,201,1\.00\)">5</);
    assert.match(dom.el("#notas").innerHTML, /1 projeto com mais de 30 deputados/);
    assert.match(dom.el("#notas").innerHTML, /Autores de cada proposição \(API da Câmara\)/);
  });
});

test("paginaFonte recusa endereço inválido, host fora do governo e caminho que não é de API", async () => {
  for (const [u, texto] of [[null, /Endereço inválido\./], ["nao-e-url", /Endereço inválido\./], ["https://exemplo.com/api/x", /só mostra dados de APIs públicas/], ["http://x.leg.br/api/x", /só mostra dados de APIs públicas/], ["https://x.leg.br/pagina", /só mostra dados de APIs públicas/], ["https://x.leg.br/api/arquivo.zip", /só mostra dados de APIs públicas/]]) {
    await comPagina({ search: u === null ? "" : `?u=${encodeURIComponent(u)}` }, {}, async (dom, chamadas) => {
      await paginaFonte();
      assert.match(dom.el("#conteudo").innerHTML, texto);
      assert.deepEqual(chamadas, []);
    });
  }
});

test("paginaFonte mostra o JSON da API em forma legível com escape, tabela, ficha aninhada e links de navegação", async () => {
  const u = "https://dadosabertos.camara.leg.br/api/v2/proposicoes?pagina=1";
  const resposta = {
    dados: [
      { id: 1, nome: "<b>Ana</b>", aprovacao: true, valor: 1234.5, data: "2025-03-01T10:20:30Z", link: "https://dadosabertos.camara.leg.br/api/v2/deputados/9", foto: "https://x.exemplo/a.jpg", nada: null },
      { id: 2, nome: "Bia", aprovacao: false, valor: 3, data: "2025-03-02", link: "texto", foto: "", nada: "" },
    ],
    links: [{ rel: "next", href: "https://dadosabertos.camara.leg.br/api/v2/proposicoes?pagina=2" }, { rel: "previous", href: "https://exemplo.com/fora" }],
  };
  await comPagina({ search: `?u=${encodeURIComponent(u)}` }, { [u]: resposta }, async (dom) => {
    await paginaFonte();
    const html = dom.el("#conteudo").innerHTML;
    assert.equal(dom.doc.title, "Dados de dadosabertos.camara.leg.br | Minha Bancada");
    assert.match(html, /<h1[^>]*>proposicoes<\/h1>/);
    assert.match(html, /&lt;b&gt;Ana&lt;\/b&gt;/);
    assert.doesNotMatch(html, /<b>Ana<\/b>/);
    assert.match(html, /<table class="tabela tabela-fonte">/);
    assert.match(html, /<th>Aprovada<\/th>/);
    assert.match(html, /<td>Sim<\/td>/);
    assert.match(html, /<td>Não<\/td>/);
    assert.match(html, /<td>1\.234,5<\/td>/);
    assert.match(html, /<td>1<\/td>/);
    assert.match(html, /<a href="https:\/\/x\.exemplo\/a\.jpg" rel="noopener">imagem<\/a>/);
    assert.match(html, /class="ver-legivel" href="deputado\.html\?id=9">ver legível/);
    assert.match(html, /<span class="quando">—<\/span>/);
    assert.match(html, /class="mais" href="fonte\.html\?u=https%3A%2F%2Fdadosabertos\.camara\.leg\.br%2Fapi%2Fv2%2Fproposicoes%3Fpagina%3D2">Próxima página/);
    assert.doesNotMatch(html, /Página anterior/);
  });
});

test("paginaFonte mostra fichas empilhadas para objetos aninhados e o motivo da falha da fonte", async () => {
  const u = "https://www.senado.leg.br/dadosabertos/lista.json";
  await comPagina({ search: `?u=${encodeURIComponent(u)}` }, { [u]: [{ id: 1, filho: { a: 1 } }, { id: 2, filho: {} }] }, async (dom) => {
    await paginaFonte();
    const html = dom.el("#conteudo").innerHTML;
    assert.match(html, /<details><summary>Item 1: 1<\/summary><dl class="ficha">/);
    assert.match(html, /<span class="quando">—<\/span>/);
  });
  await comPagina({ search: `?u=${encodeURIComponent(u)}` }, {}, async (dom) => {
    await paginaFonte();
    const html = dom.el("#conteudo").innerHTML;
    assert.match(html, /Não foi possível ler www\.senado\.leg\.br: A fonte respondeu 404\./);
    assert.match(html, /href="https:\/\/www\.senado\.leg\.br\/dadosabertos\/lista\.json" rel="noopener">Abrir direto na fonte/);
  });
});

test("paginaTribunais mostra o erro sem o arquivo e, com ele, agrupa ministros, escapa os nomes e lista saídas e relatores", async () => {
  await comPagina({}, {}, async (dom) => {
    await paginaTribunais();
    assert.match(dom.el("#conteudo").innerHTML, /class="aviso"/);
  });
  const lista = [{
    sigla: "STJ", nome: "Superior <Tribunal>", fonte: "https://stj.jus.br", wikipedia: "https://pt.wikipedia.org/wiki/STJ",
    relatorias: { rotulo: "Acórdãos do STJ", url: "https://stj.exemplo/ac", ate: "2026-02-01" },
    ministros: [
      { nome: "Ana <A>", categoria: "Efetivos", posse: "2020-05-10", nomeadoPor: "Presidente X", vaga: "Vaga 1", wiki: "Ana A", relatorias: { 2025: 890, 2026: 1234 }, confirmado: true,
        parlamentar: { casa: "camara", id: 7 }, recentes: [{ tipo: "REsp", numero: 1, ano: 2025, data: "2025-06-01", url: "https://stj.exemplo/1", colegiado: "Turma <1>" }] },
      { nome: "Bia", categoria: "Substitutos", posseTexto: "<b>2019</b>", relatorias: {}, confirmado: false },
    ],
    saidas: [{ nome: "Cid", vistoAte: "2025-01-01" }],
    outrosRelatores: [{ nome: "Dedé <S>", relatorias: { 2025: 3 }, recentes: [] }],
  }, { sigla: "STF", nome: "Supremo", fonte: "https://stf.jus.br", wikipedia: "https://pt.wikipedia.org/wiki/STF", ministros: [{ nome: "Eva" }], saidas: [] }];
  await comPagina({}, { "dados/tribunais.json": lista }, async (dom) => {
    await paginaTribunais();
    const html = dom.el("#conteudo").innerHTML;
    assert.match(html, /<h2>STJ · Superior &lt;Tribunal&gt;<\/h2>/);
    assert.match(html, /2 ministros · relatorias até a sessão de 1 de fevereiro de 2026/);
    assert.match(html, /<h3>Efetivos<\/h3>/);
    assert.match(html, /<h3>Substitutos<\/h3>/);
    assert.match(html, /Ana &lt;A&gt;/);
    assert.doesNotMatch(html, /Ana <A>/);
    assert.match(html, /Wikipédia<\/a>/);
    assert.match(html, /href="deputado\.html\?id=7"[^>]*>ficha de parlamentar/);
    assert.match(html, /2026: <b>1\.234<\/b> · 2025: <b>890<\/b>/);
    assert.match(html, /Relatou no ano/);
    assert.match(html, /Sem relatoria recente/);
    assert.match(html, /REsp 1\/2025 \(Turma &lt;1&gt;\)/);
    assert.match(html, /&lt;b&gt;2019&lt;\/b&gt;/);
    assert.match(html, /Saíram da tabela desde que a coleta começou: Cid \(até 1 de janeiro de 2025\)/);
    assert.match(html, /Outros relatores/);
    assert.match(html, /Dedé &lt;S&gt;/);
    assert.match(html, /<section id="STF"><h2>STF · Supremo<\/h2>\s*<p class="contagem">1 ministros<\/p>/);
    assert.equal((html.match(/Outros relatores/g) || []).length, 1);
    assert.equal((html.match(/<th>Relatorias \(acórdãos\)<\/th>/g) || []).length, 2);
    assert.match(html, /Acórdãos do STJ/);
  });
});

test("paginaMinisterios lista as pastas com totais e links codificados, e mostra o erro sem o arquivo", async () => {
  await comPagina({}, {}, async (dom) => {
    await paginaMinisterios();
    assert.match(dom.el("#conteudo").innerHTML, /class="aviso"/);
  });
  const lista = [
    { pasta: "saude", nome: "Saúde <S>", total: 1500, informacao: 100, respondidos: 40, convocacao: 7, ministro: { pessoa: "pes_1", nome: "Min <1>" } },
    { pasta: "a b", nome: "Vazia", total: 0, informacao: 0, respondidos: 0, convocacao: 0, ministro: null },
  ];
  await comPagina({}, { "dados/ministerios.json": lista }, async (dom) => {
    await paginaMinisterios();
    const html = dom.el("#conteudo").innerHTML;
    assert.match(html, /2 pastas, 1\.500 pedidos/);
    assert.match(html, /href="ministerios\.html\?pasta=saude">Saúde &lt;S&gt;<\/a>/);
    assert.match(html, /href="ministro\.html\?id=pes_1">Min &lt;1&gt;<\/a>/);
    assert.match(html, /<b>40<\/b> de 100 \(40%\)/);
    assert.match(html, /pasta=a%20b">Vazia/);
    assert.match(html, /<td>—<\/td>\s*<td>0<\/td><td>—<\/td><td>0<\/td>/);
  });
});

test("paginaMinisterios com pasta mostra ministros, descrição e pedidos filtráveis; endereço inválido vira erro", async () => {
  const pasta = {
    nome: "Saúde <S>", descricao: { resumo: "Resumo <r>", areas: ["Área"], base: [], vinculados: [] },
    ministros: [{ pessoa: "pes_1", nome: "Ana", atual: true, inicio: "2023-01-01", inicioFonte: "wikipedia", nomeadoPor: "Lula" }, { pessoa: "pes_2", nome: "Bia", atual: false, inicio: "2022-01-01", fim: "2022-12-01" }],
    requerimentos: [
      { id: "r1", natureza: "informacao", fonte: "camara", tipo: "RIC", numero: 1, ano: 2024, ementa: "Ementa <x>", autores: ["5"], resposta: "2024-01-10", prazoFim: "2024-02-01", idFonte: 99 },
      { id: "r2", natureza: "convocacao", fonte: "senado", tipo: "REQ", numero: 2, ano: 2024, autores: [], autoria: "Sen <Fulano>", tramitando: false },
    ],
  };
  await comPagina({ search: "?pasta=saude" }, { "dados/ministerio/saude.json": pasta, "dados/deputados.json": [{ id: 5, nome: "Dep <Cinco>" }] }, async (dom) => {
    await paginaMinisterios();
    const html = dom.el("#conteudo").innerHTML;
    assert.equal(dom.doc.title, "Ministério: Saúde <S> | Minha Bancada");
    assert.match(html, /<h1>Saúde &lt;S&gt;<\/h1>/);
    assert.match(html, /Resumo &lt;r&gt;/);
    assert.match(html, /No cargo<\/span>|No cargo, desde/);
    assert.match(html, /desde 1 de janeiro de 2023 \(posse; nomeado por Lula\)/);
    assert.match(html, /Saiu da lista do Planalto/);
    assert.match(html, /até 1 de dezembro de 2022/);
    const pedidos = dom.el("#pedidos");
    assert.match(pedidos.querySelector("#lista-pedidos").innerHTML, /<ul class="itens">/);
    const itens = pedidos.querySelector("#lista-pedidos").querySelector("ul").innerHTML;
    assert.match(itens, /RIC 1\/2024/);
    assert.match(itens, /Respondido no prazo/);
    assert.match(itens, /Ementa &lt;x&gt;/);
    assert.match(itens, /Sem ementa/);
    assert.match(itens, /Fora de tramitação\./);
    assert.match(itens, /Autoria: Sen &lt;Fulano&gt;/);
    assert.match(pedidos.innerHTML, /<b>2<\/b><span>pedidos no total<\/span>/);
    assert.match(pedidos.innerHTML, /<b>100%<\/b><span>deles já respondidos \(1\)/);
  });
  await comPagina({ search: "?pasta=../x" }, {}, async (dom, chamadas) => {
    await paginaMinisterios();
    assert.match(dom.el("#conteudo").innerHTML, /Endereço incompleto/);
    assert.deepEqual(chamadas, []);
  });
});

test("paginaMinistro valida o id, monta a ficha com as fontes e a lista de pedidos e escapa os dados", async () => {
  await comPagina({ search: "?id=a/b" }, {}, async (dom, chamadas) => {
    await paginaMinistro();
    assert.match(dom.el("#conteudo").innerHTML, /Endereço incompleto/);
    assert.deepEqual(chamadas, []);
  });
  globalThis.MutationObserver = class { observe() {} };
  const m = {
    nome: "Ana <M>", parlamentar: { casa: "senado", id: 3 },
    cargos: [
      { pasta: "saude", cargo: "Ministra de Estado da Saúde", atual: true, inicio: "2023-01-02", inicioFonte: "licenca", requerimentos: ["r1"] },
      { pasta: "educ", cargo: "Ministro de Estado da Educação", atual: false, inicio: "2020-01-01", fim: "2021-01-01", inicioFonte: "wikipedia", nomeadoPor: "Pres <X>", inicioUrl: "javascript:1", requerimentos: [] },
    ],
  };
  const pastaSaude = { requerimentos: [{ id: "r1", natureza: "informacao", fonte: "camara", tipo: "RIC", numero: 1, ano: 2024, ementa: "E", autores: ["8"], remessa: "2024-01-01", idFonte: 5 }], descricao: { resumo: "Faz <coisas>" } };
  try {
    await comPagina({ search: "?id=pes_1" }, { "dados/ministro/pes_1.json": m, "dados/ministerio/saude.json": pastaSaude, "dados/ministerio/educ.json": { requerimentos: [] } }, async (dom) => {
      await paginaMinistro();
      const html = dom.el("#conteudo").innerHTML;
      assert.equal(dom.doc.title, "Ana <M>, Ministro de Estado da Saúde | Minha Bancada");
      assert.match(html, /<h1>Ana &lt;M&gt;<\/h1>/);
      assert.match(html, /Ministro de Estado da Saúde/);
      assert.match(html, /<dt>Cargo<\/dt>/);
      assert.match(html, /<dt>Cargo anterior<\/dt>/);
      assert.match(html, /Faz &lt;coisas&gt;/);
      assert.match(html, /aproximada: dia em que se licenciou do mandato/);
      assert.match(html, /afastamentos no Senado/);
      assert.match(html, /Sem prazo: pode ser exonerado a qualquer momento/);
      assert.match(html, /nomeado por Pres &lt;X&gt;/);
      assert.match(html, /Licenciado do mandato de senador: <a href="[^"]*">ver a página parlamentar/);
      assert.match(html, /não foi eleito para este cargo/);
      assert.match(html, /<small>1<\/small>/);
      assert.match(html, /id="painel-contas"/);
      assert.doesNotMatch(html, /href="javascript:/);
      const lista = dom.el("#pedidos");
      assert.match(lista.innerHTML, /<b>1<\/b><span>pedidos no total<\/span>/);
      assert.match(lista.querySelector("#lista-pedidos").querySelector("ul").innerHTML, /Enviado ao ministério, prazo ainda não registrado/);
      assert.match(lista.querySelector("#lista-pedidos").querySelector("ul").innerHTML, /deputado 8/);
    });
  } finally { delete globalThis.MutationObserver; }
});

test("avisoLicenca devolve o aviso escapado, vazio sem cargo atual, com id inválido ou sem arquivo", async () => {
  const m = { nome: "Ana <M>", cargos: [{ pasta: "x", cargo: "Ministro de Estado da Saúde", atual: true, inicio: "2023-01-02" }] };
  await comPagina({}, { "dados/ministro/pes_1.json": m, "dados/ministro/pes_2.json": { nome: "B", cargos: [{ cargo: "Ministro de Estado X", atual: false }] } }, async () => {
    const html = await avisoLicenca("pes_1", "deputado federal");
    assert.match(html, /<b>Licenciado: Ministro de Estado da Saúde.<\/b> Ana &lt;M&gt; deixou o exercício do mandato de deputado federal/);
    assert.match(html, /desde 2 de janeiro de 2023/);
    assert.match(html, /ministro\.html\?id=pes_1/);
    assert.equal(await avisoLicenca("pes_2", "senador"), "");
    assert.equal(await avisoLicenca("pes_3", "senador"), "");
    assert.equal(await avisoLicenca("../x", "senador"), "");
    assert.equal(await avisoLicenca(null, "senador"), "");
  });
});

const fornecedor = (extra = {}) => ({ id: "for_1", nome: "Empresa <A>", documento: "12345678000199", total: 5000, politicos: 2, notas: 1, porCasa: { camara: 3000, estadual: 2000 },
  maioresPoliticos: [{ nome: "Zé <Z>", partido: "", uf: "SP", valor: 100, pagina: "deputado.html?id=1" }, { nome: "Sem página", partido: "X", uf: "RJ", valor: 50 }], ...extra });

test("paginaFornecedores mostra o erro, lista fornecedores com escape e filtra por busca, CNPJ e casa", async () => {
  await comPagina({}, {}, async (dom) => {
    await paginaFornecedores();
    assert.match(dom.el("#resultado").innerHTML, /class="aviso"/);
  });
  const j = { ano: 2025, fornecedores: [fornecedor(), fornecedor({ id: "for_2", nome: "Gráfica Ñandú", documento: "", politicos: 1, notas: 3, porCasa: { senado: 10, x: 1 }, maioresPoliticos: [] })] };
  await comPagina({}, { "dados/fornecedores.json": j }, async (dom) => {
    await paginaFornecedores();
    const lista = () => dom.el("#resultado").querySelector("ul").innerHTML;
    assert.equal(dom.el("#contagem").textContent, "2 dos 2 fornecedores que mais receberam em 2025");
    assert.match(lista(), /<b>Empresa &lt;A&gt;<\/b>/);
    assert.match(lista(), /2 políticos, 1 nota/);
    assert.match(lista(), /Câmara R\$\s3\.000 · Assembleias R\$\s2\.000/);
    assert.match(lista(), /<a href="deputado\.html\?id=1">Zé &lt;Z&gt; \(s\/p-SP, R\$\s100\)<\/a>/);
    assert.match(lista(), /Sem página \(X-RJ, R\$\s50\)(?!<\/a>)/);
    assert.match(lista(), /sem CNPJ ou CPF na fonte/);
    assert.match(lista(), /Senado R\$\s10 · x R\$\s1/);
    dom.el("#busca").value = "grafica";
    await dom.el("#busca").disparar("input");
    assert.equal(dom.el("#contagem").textContent, "1 dos 2 fornecedores que mais receberam em 2025");
    dom.el("#busca").value = "12.345.678/0001-99";
    await dom.el("#busca").disparar("input");
    assert.match(lista(), /Empresa &lt;A&gt;/);
    assert.doesNotMatch(lista(), /Gráfica/);
    dom.el("#busca").value = "";
    dom.el("#casa").value = "senado";
    await dom.el("#casa").disparar("change");
    assert.equal(dom.el("#contagem").textContent, "1 dos 2 fornecedores que mais receberam em 2025");
    dom.el("#busca").value = "inexistente";
    await dom.el("#busca").disparar("input");
    assert.equal(dom.el("#resultado").innerHTML.includes("Nenhum fornecedor encontrado com essa busca."), true);
  });
});

test("paginaFornecedores acrescenta dados da Receita, empresa inidônea e o cruzamento com doadores de campanha", async () => {
  const respostas = {
    "dados/fornecedores.json": { ano: 2025, fornecedores: [fornecedor()] },
    "dados/inidoneos_tcu.json": { for_1: [{ cnpj: "12<3>", processo: "P-1", deliberacao: "Ac 1", uf: "SP", fim: "2030-01-01" }] },
    "dados/nucleo/empresas.json": {
      fonte: { nome: "Receita <F>", url: "https://receita.exemplo", competencia: "2025-10" }, recenteDias: 30,
      tabelas: { situacao: { "02": "Ativa" }, cnae: { 4711302: "Comércio" }, natureza: {}, porte: {}, municipio: {}, tipoSocio: {}, qualificacao: {} },
      empresas: { for_1: { abertura: "2025-01-01", situacao: "02", cnaePrincipal: "4711302", cnaesSecundarios: [1, 2], capitalSocial: 1000, uf: "SP", estabelecimentos: 3, primeiraNota: "2025-01-10", diasAteNota: 9, socios: [["Sócio <1>", null, null, null]] } },
    },
    "dados/doadores_fornecedores.json": {
      anoPagamentos: 2025, resumo: { comPagamentoAoMesmoPolitico: 1 }, fontes: { doacoes: { nome: "TSE <D>", url: "https://tse.exemplo" }, pagamentos: { camara: { nome: "Câmara", url: "javascript:1" } } },
      cruzamentos: [{ fornecedor: "for_1", doacoes: [{ pessoa: "pes_1", eleicao: 2022, uf: "SP", sequencial: "9 1", valor: 100, via: "doacao", origem: "Pessoa Jurídica", ligacao: ["cnpj", "alta"], pagoPeloMesmoPolitico: [{ casa: "camara", id: 5, valor: 50 }] },
        { pessoa: "pes_x", eleicao: 2022, uf: "SP", sequencial: "2", valor: 10, via: "repasse", ligacao: ["outro<", "baixa"] }] }],
    },
    "dados/nucleo/fornecedores.json": [{ id: "for_1", nome: "Empresa <A>", documento: "123" }],
    "dados/nucleo/pessoas.json": [{ id: "pes_1", nome: "Candidato <C>" }],
  };
  await comPagina({}, respostas, async (dom) => {
    await paginaFornecedores();
    await esperar();
    const principal = dom.el("#resultado").querySelector("ul").innerHTML;
    assert.match(principal, /Declarada inidônea pelo TCU<\/b> \(CNPJ 12&lt;3&gt;\)[^]*até 1 de jan\. de 2030|até 01 de jan\. de 2030/);
    assert.match(principal, /Processo P-1, Ac 1, SP\./);
    assert.match(principal, /Receita Federal: Aberta em 01 de jan\. de 2025 · situação: Ativa/);
    assert.match(principal, /atividade principal: 4711-3\/02 Comércio \(mais 2 secundárias\)/);
    assert.match(principal, /3 estabelecimentos/);
    assert.match(principal, /<b>A primeira nota do ano nesta base é de 10 de jan\. de 2025, 9 dias depois da abertura\.<\/b>|<b>A primeira nota do ano nesta base/);
    assert.match(principal, /1 sócio no cadastro/);
    assert.match(principal, /Sócio &lt;1&gt;/);
    assert.match(principal, /<a href="https:\/\/receita\.exemplo" rel="noopener">Receita &lt;F&gt;<\/a>, base de 2025-10/);
    assert.equal(dom.el("#doadores").hidden, false);
    assert.match(dom.el("#contagem-doadores").textContent, /^1 empresas; 1 receberam da cota do mesmo político/);
    const cruz = dom.el("#resultado-doadores").querySelector("ul").innerHTML;
    assert.match(cruz, /Campanha de <a href="politico\.html\?f=t\/2022\/SP&amp;i=9%201">Candidato &lt;C&gt;<\/a> em 2022: doação \(pessoa jurídica\), <b>R\$\s100<\/b>/);
    assert.match(cruz, /Ligação: mesmo CNPJ nas duas fontes \(confiança alta\)/);
    assert.match(cruz, /O mesmo político pagou a esta empresa em 2025:<\/b> <a href="[^"]*">Câmara R\$\s50<\/a>/);
    assert.match(cruz, /um eleito<\/a> em 2022: por trás de um repasse/);
    assert.match(cruz, /Ligação: outro&lt; \(confiança baixa\)/);
    assert.match(dom.el("#fontes-doadores").innerHTML, /doações, <a href="https:\/\/tse\.exemplo" rel="noopener">TSE &lt;D&gt;<\/a>; pagamentos da cota em 2025, Câmara: Câmara\./);
  });
});

test("paginaFornecedores esconde o cruzamento quando o arquivo falta ou não tem empresas", async () => {
  const base = { "dados/fornecedores.json": { ano: 2025, fornecedores: [fornecedor()] } };
  await comPagina({}, base, async (dom) => {
    await paginaFornecedores();
    await esperar();
    assert.equal(dom.el("#doadores").hidden, false === true);
    assert.equal(dom.el("#contagem-doadores").textContent, "");
  });
  await comPagina({}, { ...base, "dados/doadores_fornecedores.json": { cruzamentos: [] }, "dados/nucleo/fornecedores.json": [], "dados/nucleo/pessoas.json": [] }, async (dom) => {
    await paginaFornecedores();
    await esperar();
    assert.equal(dom.el("#contagem-doadores").textContent, "");
  });
});

const votacao = (extra = {}) => ({ id: "1", data: "2025-03-03", proposicao: "PL 1/2025", descricao: "Desc <x>", aprovada: 1, placar: { sim: 300, nao: 100 }, ...extra });

test("paginaVotacoes mostra o erro, lista votações com escape e filtra por busca sem acento", async () => {
  await comPagina({}, {}, async (dom) => {
    await paginaVotacoes();
    assert.match(dom.el("#resultado").innerHTML, /class="aviso"/);
  });
  const lista = [votacao(), votacao({ id: "2/x", descricao: "Reforma tributária", proposicao: "PEC 2/2025", aprovada: 0, placar: {} }), votacao({ id: "3", aprovada: null, proposicao: "" })];
  await comPagina({ search: "?busca=tributaria" }, { "dados/votacoes.json": lista }, async (dom) => {
    await paginaVotacoes();
    assert.equal(dom.el("#busca").value, "tributaria");
    assert.equal(dom.el("#contagem").textContent, "1 votações nominais no Plenário");
    const itens = ul(dom.el("#resultado"));
    assert.match(itens, /Rejeitada/);
    assert.match(itens, /href="votacao\.html\?id=2%2Fx">Reforma tributária<\/a>/);
    assert.match(itens, /Sim 0, Não 0/);
    dom.el("#busca").value = "";
    await dom.el("#busca").disparar("input");
    assert.equal(dom.el("#contagem").textContent, "3 votações nominais no Plenário");
    const todos = ul(dom.el("#resultado"));
    assert.match(todos, /Desc &lt;x&gt;/);
    assert.match(todos, /<b>PL 1\/2025<\/b>/);
    assert.match(todos, /Aprovada/);
    assert.match(todos, /Sim 300, Não 100/);
    dom.el("#busca").value = "zzz";
    await dom.el("#busca").disparar("input");
    assert.match(dom.el("#resultado").innerHTML, /Nenhuma votação encontrada com essa busca\./);
  });
});

test("paginaVotacao sem o arquivo local redireciona para a API da Câmara, e do Senado mostra o erro", async () => {
  await comPagina({ search: "?id=a b" }, {}, async (dom) => {
    await paginaVotacao();
    assert.deepEqual(dom.gravacoes[0], ["replace", `fonte.html?u=${encodeURIComponent("https://dadosabertos.camara.leg.br/api/v2/votacoes/a%20b")}`]);
  });
  await comPagina({ search: "?id=9&casa=senado" }, {}, async (dom, chamadas, erros) => {
    await paginaVotacao();
    assert.deepEqual(chamadas, ["dados/votacao_senado/9.json"]);
    assert.match(dom.el("#conteudo").innerHTML, /class="aviso"/);
    assert.equal(erros.length, 1);
  });
});

test("paginaVotacao da Câmara mostra o quórum, os deputados sem voto e filtra a lista de votos", async () => {
  const v = votacao({ id: "7", proposicao: "PEC 5/2025", dataHora: "2025-03-03T15:00:00-03:00", orgao: "PLEN", propId: "55", ementa: "Sobre <o quê>",
    placar: { sim: 2, nao: 1 }, porPartido: { X: { sim: 2 }, Y: { nao: 1, abstencao: 0 } },
    votos: [{ id: "2", nome: "Zé <Z>", partido: "X", uf: "SP", voto: "sim" }, { id: "1", nome: "Ana", partido: "X", uf: "RJ", voto: "sim" }, { id: "3", nome: "Bia", partido: "Y", uf: "MG", voto: "nao", motivo: "Motivo <m>" }] });
  const deputados = [{ id: "1", nome: "Ana", partido: "X", uf: "RJ" }, { id: "4", nome: "Caio <Ausente>", partido: "Z", uf: "BA" }];
  await comPagina({ referrer: "https://site.exemplo/votacoes.html" }, {}, async () => {});
  await comPagina({ search: "?id=7", referrer: "https://site.exemplo/votacoes.html" }, { "dados/votacao/7.json": v, "dados/deputados.json": deputados }, async (dom) => {
    await paginaVotacao();
    const html = dom.el("#conteudo").innerHTML;
    assert.match(dom.doc.title, /^PEC 5\/2025 em \d{2} de mar\. de 2025 \| Minha Bancada$/);
    assert.match(html, /← Voltar às votações/);
    assert.match(html, /<h1[^>]*>PEC 5\/2025<\/h1>/);
    assert.match(html, /proposicao\.html\?k=c-55/);
    assert.match(html, /Sobre o quê:<\/b> Sobre &lt;o quê&gt;/);
    assert.match(html, /\(PLEN\)/);
    assert.match(html, /três quintos dos 513 deputados/);
    assert.match(html, /Aqui o mínimo era <b>308 votos Sim<\/b>; foram <b>2<\/b>/);
    assert.match(html, /1 dos 4 deputados não aparecem na fonte desta votação/);
    assert.match(html, /<div><b>1<\/b><span>Sem voto registrado<\/span><\/div>/);
    assert.match(html, /<td><b>X<\/b><\/td><td>2<\/td>/);
    assert.ok(html.indexOf("<td><b>X</b></td>") < html.indexOf("<td><b>Y</b></td>"));
    assert.match(html, /<h2>Voto de cada deputado<\/h2>/);
    const lista = () => ul(dom.el("#lista-dep"));
    assert.ok(lista().indexOf("Ana") < lista().indexOf("Bia"));
    assert.match(lista(), /Caio &lt;Ausente&gt;/);
    assert.match(lista(), /Zé &lt;Z&gt;/);
    assert.match(lista(), /MG<\/span>|X\/RJ/);
    assert.match(lista(), /Motivo &lt;m&gt;/);
    dom.el("#filtro-voto").value = "nao";
    await dom.el("#filtro-voto").disparar("input");
    assert.match(lista(), /Bia/);
    assert.doesNotMatch(lista(), /Ana/);
    dom.el("#filtro-voto").value = "ausente";
    dom.el("#busca-dep").value = "zzz";
    await dom.el("#busca-dep").disparar("input");
    assert.match(dom.el("#lista-dep").innerHTML, /Nenhum deputado com esse filtro\./);
  });
});

test("paginaVotacao da Câmara sem a lista de deputados em exercício estima os sem voto pelas cadeiras", async () => {
  const v = votacao({ id: "8", placar: { sim: 1 }, porPartido: { X: { sim: 1 } }, votos: [{ id: "1", nome: "Ana", partido: "X", uf: "RJ", voto: "sim" }] });
  await comPagina({ search: "?id=8" }, { "dados/votacao/8.json": v }, async (dom) => {
    await paginaVotacao();
    assert.match(dom.el("#conteudo").innerHTML, /512 dos 513 deputados não aparecem/);
    assert.doesNotMatch(dom.el("#conteudo").innerHTML, /Por que o resultado não depende/);
  });
});

test("paginaVotacao do Senado trata votação secreta, anteriores sem link e fontes da API", async () => {
  const v = votacao({ id: "9", proposicao: "PEC 1/2025", propId: "77", secreta: true, ausentes: 4, placar: { sim: 1 }, porPartido: {}, orgao: "PLEN",
    votos: [{ id: "10", nome: "Sen <A>", partido: "X", uf: "SP", voto: "secreto" }, { id: "11", nome: "Sen B", partido: "X", uf: "SP", voto: "sim", anterior: true }] });
  await comPagina({ search: "?id=9&casa=senado" }, { "dados/votacao_senado/9.json": v }, async (dom, chamadas) => {
    await paginaVotacao();
    const html = dom.el("#conteudo").innerHTML;
    assert.deepEqual(chamadas, ["dados/votacao_senado/9.json"]);
    assert.match(html, /no Plenário do Senado/);
    assert.match(html, /proposicao\.html\?k=s-77/);
    assert.match(html, /Votação secreta: o Senado informa/);
    assert.doesNotMatch(html, /três quintos|Por que o resultado/);
    assert.match(html, /<div><b>4<\/b><span>Sem voto registrado<\/span><\/div>/);
    assert.match(html, /<h2>Voto de cada senador<\/h2>/);
    assert.match(html, /Votos de cada senador \(API do Senado\)/);
    assert.match(html, /Tramitação da matéria/);
    assert.match(html, /<option value="secreto">/);
    const lista = ul(dom.el("#lista-dep"));
    assert.match(lista, /<a href="[^"]*">Sen &lt;A&gt;<\/a>/);
    assert.match(lista, /<li>Sen B<span/);
  });
});

const proposicao = (extra = {}) => ({ k: "c-1", t: "PL", n: 1, a: 2025, e: "Ementa <x>", c: "c", s: "Em tramitação", d: "tramitando", ...extra });

test("paginaProposicoes mostra o erro, monta os filtros e filtra por tipo, casa, situação e texto", async () => {
  await comPagina({}, {}, async (dom) => {
    await paginaProposicoes();
    assert.match(dom.el("#resultado").innerHTML, /class="aviso"/);
  });
  const lista = [proposicao(), proposicao({ k: "s-2", t: "PEC", n: 2, c: "s", s: "", d: "aprovada", e: "Reforma tributária" }), proposicao({ k: "c-3", t: "XYZ", n: 3, e: "" })];
  await comPagina({ search: "?situacao=aprovada" }, { "dados/proposicoes.json": lista }, async (dom) => {
    await paginaProposicoes();
    assert.match(dom.el("#tipo").innerHTML, /<option value="PEC">PEC · Proposta de emenda à Constituição<\/option>/);
    assert.match(dom.el("#tipo").innerHTML, /<option value="XYZ">XYZ<\/option>/);
    assert.match(dom.el("#situacao").innerHTML, /<option value="aprovada">Aprovada<\/option>/);
    assert.equal(dom.el("#contagem").textContent, "1 proposições");
    const itens = () => ul(dom.el("#resultado"));
    assert.match(itens(), /Senado, situação não consultada/);
    assert.match(itens(), /href="proposicao\.html\?k=s-2"><b>PEC 2\/2025<\/b>: Reforma tributária/);
    dom.el("#situacao").value = "";
    dom.el("#busca").value = "tributaria";
    await dom.el("#busca").disparar("input");
    assert.equal(dom.el("#contagem").textContent, "1 proposições");
    dom.el("#busca").value = "";
    dom.el("#casa").value = "c";
    await dom.el("#casa").disparar("input");
    assert.equal(dom.el("#contagem").textContent, "2 proposições");
    assert.match(itens(), /Ementa &lt;x&gt;/);
    assert.doesNotMatch(itens(), /PEC 2/);
    dom.el("#tipo").value = "XYZ";
    await dom.el("#tipo").disparar("input");
    assert.doesNotMatch(itens(), /<b>PL 1/);
    assert.match(itens(), /<b>XYZ 3\/2025<\/b><\/a>/);
    dom.el("#busca").value = "naoexiste";
    await dom.el("#busca").disparar("input");
    assert.match(dom.el("#resultado").innerHTML, /Nenhuma proposição encontrada com essa busca\./);
  });
});

test("paginaProposicao sem a proposição no índice cai no erro com o código pedido", async () => {
  await comPagina({ search: "?k=c-99" }, { "dados/proposicoes.json": [proposicao()] }, async (dom, chamadas, erros) => {
    await paginaProposicao();
    assert.match(dom.el("#conteudo").innerHTML, /proposição c-99 não encontrada/);
    assert.equal(erros.length, 1);
  });
});

test("paginaProposicao da Câmara monta cabeçalho, autores, leis, votações e vida do projeto, e carrega quem votou ao clicar", async () => {
  const eventos = Array.from({ length: 17 }, (_, i) => [`2025-01-${String(i + 1).padStart(2, "0")}`, `Órgão ${i}`, "Tipo <t>", "Sit", i === 16 ? "Despacho <d>" : ""]);
  const f = {
    ap: "2025-01-02", em: "Ementa oficial", ed: "Detalhada <d>", o: "PLEN", tr: "Aprovado", ds: "2025-02-02", rg: "Urgência", rl: "7", tm: ["Saúde", "Tema <2>"], pc: "palavra <k>", pr: "88",
    ls: ["l1", "l2"], au: [{ id: "7", p: 1 }, { nome: "Autor <Externo>" }], tx: "https://inteiro.exemplo/x.pdf",
    v: [{ id: "v1", data: "2025-02-02", orgao: "PLEN", descricao: "Votação <1>", aprovada: 1 }, { id: "v2", data: "2025-02-03" }],
  };
  const respostas = {
    "dados/proposicoes.json": [proposicao({ e: "Ementa índice" })],
    "dados/proposicao/c-2025.json": { 1: f },
    "dados/deputados.json": [{ id: "7", nome: "Rel <A>", partido: "X", uf: "SP" }],
    "dados/votacoes.json": [{ id: "v1", placar: { sim: 1 } }],
    "dados/leis.json": { l1: { r: "Lei <1>", e: "Resumo", u: "https://lexml.exemplo", p: "https://planalto.exemplo" }, l2: { r: "Lei 2", u: "https://lexml.exemplo/2", p: "javascript:1" } },
    "dados/tramitacao/1.json": { eventos, relator: "Último <R>", relacionadas: [["2", "PL 2/2025"]] },
    "dados/votacao/v1.json": { votos: [{ id: "7", nome: "Rel <A>", partido: "X", uf: "SP", voto: "sim" }, { nome: "Ex", partido: "Y", uf: "", voto: "nao", anterior: true }] },
  };
  await comPagina({ search: "?k=c-1" }, respostas, async (dom) => {
    await paginaProposicao();
    await esperar();
    const html = dom.el("#conteudo").innerHTML;
    assert.equal(dom.doc.title, "PL 1/2025 | Minha Bancada");
    assert.match(html, /← Proposições/);
    assert.match(html, /Câmara, apresentada em 02 de jan\. de 2025/);
    assert.match(html, /<h1[^>]*>PL 1\/2025<\/h1>/);
    assert.match(html, /Projeto de lei<\/p>/);
    assert.match(html, /<p class="texto-longo">Ementa oficial<\/p>/);
    assert.match(html, /Detalhada &lt;d&gt;/);
    assert.match(html, /Situação:<\/b> Em tramitação \(PLEN\)/);
    assert.match(html, /Última tramitação:<\/b> Aprovado, em 02 de fev\. de 2025 · regime: Urgência/);
    assert.match(html, /Relator:<\/b> <a href="[^"]*">Rel &lt;A&gt;<\/a> \(X\/SP\)/);
    assert.match(html, /Temas:<\/b> Saúde, Tema &lt;2&gt;/);
    assert.match(html, /Palavras-chave:<\/b> palavra &lt;k&gt;/);
    assert.match(html, /proposicao\.html\?k=c-88/);
    assert.match(html, /Leis citadas \(2\)/);
    assert.match(html, /<b>Lei &lt;1&gt;<\/b>: Resumo/);
    assert.match(html, /Resumo ainda não coletado\./);
    assert.equal((html.match(/>Planalto<\/a>/g) || []).length, 1);
    assert.match(html, /Autores \(2\)/);
    assert.match(html, /autor principal/);
    assert.match(html, /Autor &lt;Externo&gt;<span class="quando texto">sem ficha no site/);
    assert.match(html, /Votações \(2\)/);
    assert.match(html, /Votação &lt;1&gt;/);
    assert.match(html, /, aprovada/);
    assert.match(html, /Votação simbólica ou em comissão: sem voto individual\./);
    assert.equal((html.match(/Ver quem votou/g) || []).length, 1);
    assert.match(html, /href="https:\/\/inteiro\.exemplo\/x\.pdf"|Inteiro teor/);
    const vida = dom.el("#vida").innerHTML;
    assert.match(vida, /Vida do projeto \(17 movimentações\)/);
    assert.doesNotMatch(vida, /Último relator designado/);
    assert.match(vida, /Por onde passou:<\/b> Órgão 0, Órgão 1/);
    assert.match(vida, /Ver as 2 movimentações mais antigas/);
    assert.match(vida, /Proposições relacionadas \(1\):<\/b> <a href="[^"]*idProposicao=2"[^>]*>PL 2\/2025/);
    const linha = dom.el("#linha-tempo");
    assert.equal((linha.innerHTML.match(/<li>/g) || []).length, 0);
    assert.match(vida, /Despacho &lt;d&gt;/);
    await dom.el("#mais-tempo").disparar("click");
    assert.equal(dom.el("#mais-tempo").hidden, true);
    assert.equal((linha.innerHTML.match(/<li>/g) || []).length, 2);
    const botao = { dataset: { i: "0" }, hidden: false };
    await dom.el("#conteudo").disparar("click", { target: { closest: () => botao } });
    await esperar();
    assert.equal(botao.hidden, true);
    const saida = dom.el("#votos-0");
    const votos = ul(saida.querySelector(".l"));
    assert.match(votos, /<a href="[^"]*">Rel &lt;A&gt;<\/a>/);
    assert.match(votos, /<li>Ex<span/);
    saida.querySelector(".f").value = "nao";
    await saida.querySelector(".f").disparar("input");
    assert.doesNotMatch(ul(saida.querySelector(".l")), /Rel/);
    saida.querySelector(".b").value = "zzz";
    await saida.querySelector(".b").disparar("input");
    assert.match(saida.querySelector(".l").innerHTML, /Ninguém com esse filtro\./);
    await dom.el("#conteudo").disparar("click", { target: { closest: () => null } });
  });
});

test("paginaProposicao mostra o relator da tramitação quando ele não tem ficha e avisa autoria e votações ausentes", async () => {
  const respostas = {
    "dados/proposicoes.json": [proposicao({ s: "" })],
    "dados/proposicao/c-2025.json": {},
    "dados/deputados.json": [],
    "dados/votacoes.json": [],
    "dados/tramitacao/1.json": { eventos: [], relator: "Último <R>" },
  };
  await comPagina({ search: "?k=c-1" }, respostas, async (dom) => {
    await paginaProposicao();
    await esperar();
    const html = dom.el("#conteudo").innerHTML;
    assert.match(html, /Situação:<\/b> ainda não consultada/);
    assert.match(html, /Autoria ainda não coletada\./);
    assert.match(html, /Nenhuma votação registrada no Plenário\./);
    assert.match(dom.el("#vida").innerHTML, /Último relator designado:<\/b> Último &lt;R&gt;/);
  });
});

test("paginaProposicao do Senado não busca a tramitação da Câmara e liga ao Senado", async () => {
  const respostas = {
    "dados/proposicoes.json": [proposicao({ k: "s-5", c: "s", a: 2024 })],
    "dados/proposicao/s-2024.json": { 5: { au: [{ id: "3" }] } },
    "dados/senadores.json": [{ id: "3", nome: "Sen <S>", partido: "X", uf: "SP" }],
    "dados/votacoes_senado.json": [],
  };
  await comPagina({ search: "?k=s-5" }, respostas, async (dom, chamadas) => {
    await paginaProposicao();
    await esperar();
    assert.ok(!chamadas.some((c) => c.includes("tramitacao")));
    const html = dom.el("#conteudo").innerHTML;
    assert.match(html, /<p>Senado<\/p>/);
    assert.match(html, /Sen &lt;S&gt;/);
    assert.match(html, /Tramitação oficial/);
  });
});

test("paginaPoliticos mostra o erro sem o índice e, com ele, agrupa por cargo, escapa e filtra pela busca", async () => {
  await comPagina({}, {}, async (dom) => {
    await paginaPoliticos();
    assert.match(dom.el("#resultado").innerHTML, /class="aviso"/);
  });
  const br = [
    { nome: "Zé <X>", cargo: "DEPUTADO FEDERAL", partido: "A&B", uf: "SP", estado: "atual", ordemCargo: 4, arquivoFicha: "f", id: "1" },
    { nome: "Ana Eleita", cargo: "SENADOR", partido: "C", uf: "RJ", estado: "eleito", ordemCargo: 3, arquivoFicha: "f", id: "2" },
    { nome: "Beto Senador", cargo: "SENADOR", partido: "D", uf: "MG", estado: "atual", ordemCargo: 3, arquivoFicha: "f", id: "3" },
  ];
  await comPagina({}, { "dados/indice/BR.json": br }, async (dom) => {
    await paginaPoliticos();
    await esperar();
    const html = dom.el("#resultado").innerHTML;
    assert.match(dom.el("#uf").innerHTML, /<option value="SP">São Paulo<\/option>/);
    assert.match(html, /<h2>Câmara dos Deputados <small class="sub">1<\/small><\/h2>/);
    assert.match(html, /<h2>Senado Federal <small class="sub">1<\/small><\/h2>/);
    assert.doesNotMatch(html, /Governo do estado/);
    const camara = dom.el("#resultado").querySelector('ul[data-grupo="4"]').innerHTML;
    assert.match(camara, /Zé &lt;X&gt;/);
    assert.match(camara, /DEPUTADO FEDERAL, A&amp;B, SP/);
    assert.doesNotMatch(dom.el("#resultado").querySelector('ul[data-grupo="3"]').innerHTML, /Ana Eleita/);
    assert.equal(dom.el("#contagem").textContent, "2 políticos no cargo: Brasil");
    assert.equal(dom.el("#mapa").innerHTML, '<p class="vazio">Não foi possível carregar o mapa. Use os campos ao lado.</p>');
    dom.el("#busca").value = "zzz";
    await dom.el("#busca").disparar("input");
    assert.match(dom.el("#resultado").innerHTML, /Nada encontrado\. Tente outro nome ou limpe a busca\./);
    assert.equal(dom.el("#contagem").textContent, "0 políticos no cargo: Brasil");
    assert.equal(dom.gravacoes.at(-1)[1], "/pagina.html");
  });
  await comPagina({ search: "?periodo=2026" }, { "dados/indice/BR.json": br }, async (dom) => {
    await paginaPoliticos();
    await esperar();
    assert.equal(dom.el("#contagem").textContent, "1 políticos eleitos ou no 2º turno em 2026: Brasil");
    assert.match(dom.el("#resultado").querySelector('ul[data-grupo="3"]').innerHTML, /Ana Eleita/);
    assert.match(dom.el("#resultado").querySelector('ul[data-grupo="3"]').innerHTML, /Eleito em 2026/);
    assert.equal(dom.gravacoes.at(-1)[1], "?periodo=2026");
  });
});

test("paginaPoliticos carrega o estado da URL, preenche os municípios com a capital primeiro e mostra a prefeitura do município", async () => {
  const indice = [
    { nome: "Gov", cargo: "GOVERNADOR", partido: "A", uf: "SP", estado: "atual", ordemCargo: 5, arquivoFicha: "f", id: "1" },
    { nome: "Prefeito Santos", cargo: "PREFEITO", partido: "B", uf: "SP", estado: "atual", ordemCargo: 8, codigoMunicipio: "71455", municipio: "Santos", arquivoFicha: "f", id: "2" },
    { nome: "Prefeito Capital", cargo: "PREFEITO", partido: "B", uf: "SP", estado: "atual", ordemCargo: 8, codigoMunicipio: "71072", municipio: "São Paulo", arquivoFicha: "f", id: "3" },
  ];
  await comPagina({ search: "?uf=SP&municipio=71455" }, { "dados/indice/BR.json": [], "dados/indice/SP.json": indice }, async (dom) => {
    await paginaPoliticos();
    await esperar(6);
    const opcoes = dom.el("#municipio").innerHTML;
    assert.ok(opcoes.indexOf("São Paulo") < opcoes.indexOf("Santos"));
    assert.equal(dom.el("#municipio").disabled, false);
    assert.equal(dom.el("#contagem").textContent, "2 políticos no cargo: Santos, São Paulo");
    const html = dom.el("#resultado").innerHTML;
    assert.ok(html.indexOf("Prefeitura") < html.indexOf("Governo do estado"));
    assert.match(dom.el("#resultado").querySelector('ul[data-grupo="8"]').innerHTML, /Prefeito Santos/);
    assert.doesNotMatch(dom.el("#resultado").querySelector('ul[data-grupo="8"]').innerHTML, /Prefeito Capital/);
    assert.match(dom.el("#trilha").innerHTML, /data-ir="br">Brasil<\/button>.*data-ir="uf">São Paulo<\/button>.*<b>Santos<\/b>/);
  });
});

test("montarEstadual devolve false quando faltam os arquivos do deputado ou das votações", async () => {
  await comPagina({}, {}, async () => {
    assert.equal(await montarEstadual(new Elemento(), { estadual: { uf: "SP", id: "1" } }, "Ana", [], ""), false);
  });
  await comPagina({}, { "dados/estadual/SP/1.json": { votos: [] } }, async () => {
    assert.equal(await montarEstadual(new Elemento(), { estadual: { uf: "SP", id: "1" } }, "Ana", [], ""), false);
  });
});
