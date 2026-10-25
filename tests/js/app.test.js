// Testa os módulos de site/assets/js sem navegador (Node 24 carrega módulos ES com require).
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

globalThis.window = {};
const js = (nome) => require(path.join(__dirname, "../../site/assets/js", nome));
const { esc, reais, reaisCentavos, pct, data, semAcento, urlSegura } = js("util.js");
const { urlLegivel, fontes, temResultado } = js("apis.js");
const { resumosEstadual } = js("estadual.js");
const { linksRedes } = js("ficha.js");
const { foto } = js("comum.js");
const { agruparPeriodos, chaveDe, juntarDias } = js("historico.js");

test("temResultado deixa de fora a votação sem aprovada nem rejeitada", () => {
  assert.equal(temResultado({ aprovada: 1 }), true);
  assert.equal(temResultado({ aprovada: 0 }), true);
  assert.equal(temResultado({ aprovada: null }), false);
  assert.equal(temResultado({}), false);
});

test("esc escapa HTML e trata nulos", () => {
  assert.equal(esc(`<a href="x">'&'</a>`), "&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;");
  assert.equal(esc(null), "");
  assert.equal(esc(undefined), "");
  assert.equal(esc(0), "0");
});

test("reais formata em BRL", () => {
  assert.match(reais(1234.4), /R\$\s?1\.234/);
  assert.match(reais(null), /R\$\s?0/);
  assert.match(reaisCentavos(1.5), /1,50/);
});

test("pct arredonda e evita divisão por zero", () => {
  assert.equal(pct(1, 3), "33%");
  assert.equal(pct(2, 3), "67%");
  assert.equal(pct(5, 0), "—");
});

test("data usa UTC e aceita ISO completo", () => {
  assert.equal(data(""), "");
  assert.equal(data(null), "");
  assert.match(data("2026-01-01T00:00:00"), /01.*2026/);
  assert.match(data("2026-03-05", true), /5 de março de 2026/);
});

test("semAcento normaliza para busca", () => {
  assert.equal(semAcento("São José"), "sao jose");
  assert.equal(semAcento(null), "");
});

test("urlSegura só aceita http e https", () => {
  assert.equal(urlSegura("https://exemplo.com/a?b=1"), "https://exemplo.com/a?b=1");
  assert.equal(urlSegura("http://exemplo.com"), "http://exemplo.com");
  assert.equal(urlSegura("  https://exemplo.com  "), "https://exemplo.com");
  assert.equal(urlSegura("javascript:alert(1)"), "");
  assert.equal(urlSegura("JavaScript:alert(1)"), "");
  assert.equal(urlSegura(" java\tscript:alert(1)"), "");
  assert.equal(urlSegura("data:text/html,<script>alert(1)</script>"), "");
  assert.equal(urlSegura("vbscript:x"), "");
  assert.equal(urlSegura("ftp://exemplo.com/x"), "");
  assert.equal(urlSegura(""), "");
  assert.equal(urlSegura(null), "");
  assert.equal(urlSegura(undefined), "");
});

test("urlSegura recusa caminho relativo, a não ser que seja pedido", () => {
  assert.equal(urlSegura("politico.html?f=x&i=1"), "");
  assert.equal(urlSegura("politico.html?f=x&i=1", true), "politico.html?f=x&i=1");
  assert.equal(urlSegura("fotos/1.jpg", true), "fotos/1.jpg");
  assert.equal(urlSegura("javascript:alert(1)", true), "");
  assert.equal(urlSegura("data:image/png;base64,AAAA", true), "");
});

test("links montados com dado externo não levam javascript: nem data:", () => {
  const ruim = "javascript:alert(1)";
  assert.equal(fontes([["Fonte", ruim], ["Outra", "data:text/html,x"]]), "");
  assert.match(fontes([["Fonte", "https://dadosabertos.camara.leg.br/api/v2/x"]]), /href="https:\/\/dadosabertos\.camara\.leg\.br\/api\/v2\/x"/);
  assert.doesNotMatch(foto({ nome: "Ana Souza", foto: ruim }), /<img|javascript:/);
  assert.match(foto({ nome: "Ana Souza", foto: "https://x.org/a.jpg" }), /<img[^>]*src="https:\/\/x\.org\/a\.jpg"/);
  assert.match(foto({ nome: "Ana Souza", foto: "fotos/1.jpg" }), /src="fotos\/1\.jpg"/);
  const redes = linksRedes([ruim, "https://instagram.com/anasouza"], { nome: "Ana Souza" });
  assert.doesNotMatch(redes, /javascript:/);
  assert.match(redes, /href="https:\/\/instagram\.com\/anasouza"/);
  assert.equal(linksRedes([ruim], { nome: "Ana Souza" }), null);
});

test("urlLegivel reaproveita páginas do site e usa fonte.html nas demais APIs", () => {
  const f = urlLegivel, api = "https://dadosabertos.camara.leg.br/api/v2";
  assert.equal(f(`${api}/votacoes/2270800-69/votos`), "votacao.html?id=2270800-69");
  assert.equal(f(`${api}/votacoes/2270800-69`), "votacao.html?id=2270800-69");
  assert.equal(f(`${api}/deputados/204379`), "deputado.html?id=204379");
  assert.equal(f(`${api}/proposicoes/1`), `fonte.html?u=${encodeURIComponent(`${api}/proposicoes/1`)}`);
  assert.match(f("https://legis.senado.leg.br/dadosabertos/processo/1"), /^fonte\.html\?u=/);
  assert.equal(f("https://cdn.tse.jus.br/estatistica/sead/odsele/x.zip"), null);
  assert.equal(f("https://www.camara.leg.br/deputados/1"), null);
  assert.equal(f("http://dadosabertos.camara.leg.br/api/v2/x"), null);
  assert.equal(f("https://exemplo.com/api/x"), null);
  assert.equal(f("lixo"), null);
});

test("resumosEstadual mostra cada seção com fonte e avisa quando falta", () => {
  assert.equal(resumosEstadual({}), "");
  const html = resumosEstadual({
    verba: { fonte: "https://v.org/dados", anos: [{ ano: 2024, total: 30, meses: [{ mes: 1, total: 30 }], categorias: [{ id: "imovel", categoria: "Imóvel e escritório de apoio", total: 30, originais: [["Aluguel", 30]] }], fornecedores: [{ fornecedor: "F", cnpj: "1", total: 30 }] }] },
    remuneracao: { fonte: "https://r.org/dados", ano: 2024, mes: 3, bruto: 100, liquido: 80 },
    diarias: { anos: [{ ano: 2024, total: 5, quantidade: 1 }] },
  });
  assert.match(html, /Verba\/cota/);
  assert.match(html, /jan/);
  assert.match(html, /href="https:\/\/v\.org\/dados"/);
  assert.match(html, /title="Aluguel: [^"]*">Imóvel e escritório de apoio/);
  assert.match(html, /Remuneração/);
  assert.match(html, /mar\/2024/);
  assert.match(html, /Diárias[\s\S]*sem-fonte/);
  assert.doesNotMatch(html, /Presença|Emendas/);
});

test("resumosEstadual mostra lançamentos da verba e pagamentos das emendas com data e fonte", () => {
  const html = resumosEstadual({
    verba: { fonte: "https://v.org/dados", anos: [{ ano: 2026, total: 30, meses: [{ mes: 2, total: 30 }], categorias: [], fornecedores: [],
      lancamentos: [{ mes: 2, fornecedor: "F", valor: 30.5, documento: "NF-1", emissao: "2026-02-03", fonte: "https://c.org/nf.pdf" }, { mes: 3, empenho: "2026NE1", descricao: "Combustível", valor: 1, fonte: "javascript:x" }] }] },
    emendas: { fonte: "https://e.org", anos: [{ ano: 2025, empenhado: 10, pago: 5 }],
      pagamentos: [{ data: "2026-02-23", credor: "Credor <b>", objeto: "Obra", valor: 20, efetivado: true }, { data: "2026-01-20", credor: "B", valor: 1, efetivado: false }] },
  });
  assert.match(html, /Lançamentos de 2026/);
  assert.match(html, /03\/02\/2026[\s\S]*NF-1[\s\S]*href="https:\/\/c\.org\/nf\.pdf"/);
  assert.match(html, /2026NE1[\s\S]*Combustível/);
  assert.doesNotMatch(html, /javascript:/);
  assert.match(html, /Pagamentos das emendas/);
  assert.match(html, /23\/02\/2026<\/td><td>Credor &lt;b&gt;/);
  assert.match(html, /não efetivado/);
});

test("completarEleicao monta disputa, votos do partido e aliança a partir do que o local tem em comum", () => {
  const { completarEleicao } = js("ficha.js");
  const comuns = {
    disputa: { "VEREADOR|71072": { vagas: 55, turnos: { 1: { aptos: 10 } } }, "GOVERNADOR|SP": { vagas: 1, turnos: {} } },
    partidos: { "VEREADOR|71072": { totalVotos: 770, partidos: { PT: [100, 300, "PT/PC do B/PV"], "PC do B": [10, 20, "PT/PC do B/PV"], PL: [50, 290, ""] } } },
    coligacoes: { "VEREADOR|71072": { coligacoes: [["F", "", "Federação X", "Deferido"], ["I", "", "PL", "Deferido"]], coligacaoDoPartido: { PT: 0, "PC do B": 0, PL: 1 } } },
  };
  const pt = completarEleicao({ cargoTse: "VEREADOR", unidadeEleitoral: "71072", partido: "PT" }, comuns);
  assert.deepEqual(pt.disputa, comuns.disputa["VEREADOR|71072"]);
  assert.deepEqual(pt.partidoVotos, { votosLegenda: 100, votosNominais: 300, totalVotosPartidos: 770, federacao: "PT/PC do B/PV", votosLegendaFederacao: 110, votosNominaisFederacao: 320 });
  assert.deepEqual(pt.alianca, { tipo: "F", nome: "", composicao: "Federação X", situacao: "Deferido" });
  const pl = completarEleicao({ cargoTse: "VEREADOR", unidadeEleitoral: "71072", partido: "PL" }, comuns);
  assert.deepEqual(pl.partidoVotos, { votosLegenda: 50, votosNominais: 290, totalVotosPartidos: 770 });   // sem federação: só os do partido
  assert.equal(pl.alianca.tipo, "I");
  // o vice disputa com o titular; votos por partido e coligações usam o cargo do próprio vice
  const vice = completarEleicao({ cargoTse: "VICE-GOVERNADOR", unidadeEleitoral: "SP", partido: "PT" }, comuns);
  assert.equal(vice.disputa.vagas, 1);
  assert.equal(vice.partidoVotos, undefined);
  assert.equal(vice.alianca, undefined);
  // partido sem votos no local, ficha sem `_disputas` e ficha que já traz os campos ficam como estão
  assert.equal(completarEleicao({ cargoTse: "VEREADOR", unidadeEleitoral: "71072", partido: "NOVO" }, comuns).partidoVotos, undefined);
  const solta = { cargoTse: "SENADOR", unidadeEleitoral: "SP" };
  assert.equal(completarEleicao(solta, undefined), solta);
  const pronta = { cargoTse: "VEREADOR", unidadeEleitoral: "71072", partido: "PT", disputa: { vagas: 1 } };
  assert.deepEqual(completarEleicao(pronta, comuns).disputa, { vagas: 1 });
  assert.equal(pronta.partidoVotos, undefined);
});

test("agruparPeriodos junta dias em semanas (segunda a domingo) e meses", () => {
  const indice = [{ data: "2026-10-26", total: 1 }, { data: "2026-10-25", total: 2 }, { data: "2026-10-19", total: 3 }, { data: "2026-09-30", total: 4 }];
  assert.deepEqual(agruparPeriodos(indice, "semana").map((g) => [g.chave, g.total]), [["2026-10-26", 1], ["2026-10-19", 5], ["2026-09-28", 4]]);
  assert.deepEqual(agruparPeriodos(indice, "mes").map((g) => [g.chave, g.dias.length]), [["2026-10", 3], ["2026-09", 1]]);
  assert.equal(chaveDe("semana", "2026-10-25"), "2026-10-19");
});

test("juntarDias soma contagens, marca o dia de cada evento e só dá cobertura vazia a quem não teve item no período", () => {
  const dia = (d, locais, eventos, cobertura) => ({ data: d, locais, contagem: Object.fromEntries(Object.keys(locais).map((c) => [c, { nova: eventos.filter((e) => e.local === c).length }])), cobertura, eventos });
  const novo = dia("2026-10-20", { BR: "Brasil", "UF:SP": "São Paulo" }, [{ local: "UF:SP", titulo: "b" }], { BR: { itens: 0, status: "parado" }, "UF:SP": { itens: 1 } });
  const velho = dia("2026-10-19", { BR: "Brasil" }, [{ local: "BR", titulo: "a" }], { BR: { itens: 1 } });
  const j = juntarDias([novo, velho], "2026-10-19");
  assert.deepEqual(Object.keys(j.locais), ["BR", "UF:SP"]);
  assert.deepEqual(j.eventos.map((e) => [e.titulo, e._dia]), [["a", "2026-10-19"], ["b", "2026-10-20"]]);
  assert.equal(j.contagem.BR.nova, 1);
  assert.equal(j.cobertura.BR.itens, 1);
  assert.deepEqual([j.de, j.ate], ["2026-10-19", "2026-10-20"]);
});
