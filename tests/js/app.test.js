// Testa os módulos de site/assets/js sem navegador (Node 24 carrega módulos ES com require).
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

globalThis.window = {};
const js = (nome) => require(path.join(__dirname, "../../site/assets/js", nome));
const { esc, reais, reaisCentavos, pct, data, semAcento, urlSegura } = js("util.js");
const { urlLegivel, fontes } = js("apis.js");
const { resumosEstadual } = js("estadual.js");
const { linksRedes } = js("ficha.js");
const { foto } = js("comum.js");

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
    verba: { fonte: "https://v.org/dados", anos: [{ ano: 2024, total: 30, meses: [{ mes: 1, total: 30 }], categorias: [{ categoria: "Aluguel", total: 30 }], fornecedores: [{ fornecedor: "F", cnpj: "1", total: 30 }] }] },
    remuneracao: { fonte: "https://r.org/dados", ano: 2024, mes: 3, bruto: 100, liquido: 80 },
    diarias: { anos: [{ ano: 2024, total: 5, quantidade: 1 }] },
  });
  assert.match(html, /Verba\/cota/);
  assert.match(html, /jan/);
  assert.match(html, /href="https:\/\/v\.org\/dados"/);
  assert.match(html, /Remuneração/);
  assert.match(html, /mar\/2024/);
  assert.match(html, /Diárias[\s\S]*sem-fonte/);
  assert.doesNotMatch(html, /Presença|Emendas/);
});
