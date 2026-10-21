// Testa as utilidades puras do site/assets/app.js sem navegador: carrega só o trecho de utilidades.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const fonte = fs.readFileSync(path.join(__dirname, "../../site/assets/app.js"), "utf8");
const inicio = fonte.indexOf("const esc =");
const fim = fonte.indexOf("const param =");
assert.ok(inicio > 0 && fim > inicio, "trecho de utilidades não encontrado em app.js");

const ctx = vm.createContext({});
vm.runInContext(fonte.slice(inicio, fim) + "\nthis.f = { esc, reais, reaisCentavos, pct, data, semAcento };", ctx);
const { esc, reais, reaisCentavos, pct, data, semAcento } = ctx.f;

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
