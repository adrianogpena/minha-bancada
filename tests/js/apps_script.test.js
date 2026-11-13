const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const CODIGO = fs.readFileSync(path.join(__dirname, "../../assinaturas/apps_script.gs"), "utf-8");
const sha = (t) => crypto.createHash("sha256").update(t).digest("hex");
const B64 = "QUJD";
const H = sha("token-a");

function criarFolha(linhas) {
  const folha = {
    linhas,
    apagadas: [],
    getLastRow: () => folha.linhas.length,
    getRange(l, c, n = 1) {
      return {
        getValues: () => folha.linhas.slice(l - 1, l - 1 + n).map((x) => [x[c - 1]]),
        setValue: (v) => { folha.linhas[l - 1][c - 1] = v; },
      };
    },
    getDataRange: () => ({ getValues: () => folha.linhas.map((x) => [...x]) }),
    appendRow: (x) => { folha.linhas.push(x); },
    deleteRow: (l) => { folha.apagadas.push(l); folha.linhas.splice(l - 1, 1); },
  };
  return folha;
}

function ambiente({ linhas = [], chave = "segredo", semAba = false } = {}) {
  const folha = criarFolha(linhas);
  const estado = { folha, locks: { espera: 0, solto: 0 }, abaCriada: false, lockFalha: false };
  const planilha = {
    getSheetByName: () => (semAba ? null : folha),
    insertSheet: () => { estado.abaCriada = true; return folha; },
  };
  const contexto = {
    SpreadsheetApp: { getActive: () => planilha },
    LockService: {
      getScriptLock: () => ({
        waitLock: () => { estado.locks.espera++; if (estado.lockFalha) throw new Error("sem lock"); },
        releaseLock: () => { estado.locks.solto++; },
      }),
    },
    PropertiesService: { getScriptProperties: () => ({ getProperty: () => chave }) },
    ContentService: { createTextOutput: (t) => ({ texto: t, setMimeType(m) { this.mime = m; return this; } }), MimeType: { JSON: "json" } },
    HtmlService: { createHtmlOutput: (h) => ({ html: h, setTitle(t) { this.titulo = t; return this; } }) },
    Utilities: {
      DigestAlgorithm: { SHA_256: "sha256" },
      Charset: { UTF_8: "utf8" },
      computeDigest: (alg, t) => Array.from(crypto.createHash("sha256").update(t).digest()).map((b) => (b > 127 ? b - 256 : b)),
    },
  };
  vm.createContext(contexto);
  vm.runInContext(CODIGO, contexto);
  return { ctx: contexto, estado };
}

const pedido = (extra = {}) => ({ postData: { contents: JSON.stringify({ v: 1, h: H, k: B64, iv: B64, c: B64, ...extra }) } });
const linha = (h, criado, confirmado = false, enviada = false) => [h, criado, confirmado, enviada, "k", "iv", "c"];
const lista = (out) => JSON.parse(out.texto);

test("doPost guarda a linha nova com os campos cifrados e libera o lock", () => {
  const { ctx, estado } = ambiente();
  const out = ctx.doPost(pedido());
  assert.equal(out.texto, "ok");
  assert.equal(estado.folha.linhas.length, 1);
  const [h, , confirmado, enviada, k, iv, c] = estado.folha.linhas[0];
  assert.deepEqual([h, confirmado, enviada, k, iv, c], [H, false, false, B64, B64, B64]);
  assert.equal(estado.locks.solto, 1);
});

test("doPost cria a aba quando ela não existe", () => {
  const { ctx, estado } = ambiente({ semAba: true });
  ctx.doPost(pedido());
  assert.equal(estado.abaCriada, true);
});

test("doPost repetido com o mesmo hash responde ok sem duplicar a linha", () => {
  const { ctx, estado } = ambiente({ linhas: [linha(H, "2026-01-01")] });
  assert.equal(ctx.doPost(pedido()).texto, "ok");
  assert.equal(estado.folha.linhas.length, 1);
});

test("doPost recusa pedido inválido e não grava nada", () => {
  const casos = {
    versao: { v: 2 },
    hashCurto: { h: "abc" },
    hashMaiusculo: { h: "A".repeat(64) },
    base64Invalido: { k: "!!!" },
    campoAusente: { iv: undefined },
    campoNumerico: { c: 5 },
    chaveGrande: { k: "A".repeat(1401) },
    ivGrande: { iv: "A".repeat(25) },
    cifradoGrande: { c: "A".repeat(12001) },
  };
  for (const [nome, extra] of Object.entries(casos)) {
    const { ctx, estado } = ambiente();
    assert.equal(ctx.doPost(pedido(extra)).texto, "erro", nome);
    assert.equal(estado.folha.linhas.length, 0, nome);
  }
});

test("doPost responde erro com corpo que não é JSON e quando o lock falha", () => {
  const a = ambiente();
  assert.equal(a.ctx.doPost({ postData: { contents: "nao é json" } }).texto, "erro");
  const b = ambiente();
  b.estado.lockFalha = true;
  assert.equal(b.ctx.doPost(pedido()).texto, "erro");
  assert.equal(b.estado.folha.linhas.length, 0);
});

test("doPost responde cheio com a planilha no limite", () => {
  const { ctx, estado } = ambiente({ linhas: Array.from({ length: 5000 }, (_, i) => linha(sha(`x${i}`), "2026-01-01")) });
  assert.equal(ctx.doPost(pedido()).texto, "cheio");
  assert.equal(estado.folha.linhas.length, 5000);
});

test("doGet confirmar marca a linha achada pelo hash do token", () => {
  const { ctx, estado } = ambiente({ linhas: [linha(sha("outro"), "2026-01-01"), linha(sha("token-a"), "2026-01-01")] });
  const out = ctx.doGet({ parameter: { acao: "confirmar", t: "token-a" } });
  assert.equal(out.titulo, "Tudo certo");
  assert.equal(estado.folha.linhas[1][2], true);
  assert.equal(estado.folha.linhas[0][2], false);
  assert.equal(estado.locks.solto, 1);
});

test("doGet cancelar apaga a linha", () => {
  const { ctx, estado } = ambiente({ linhas: [linha(sha("token-a"), "2026-01-01")] });
  const out = ctx.doGet({ parameter: { acao: "cancelar", t: "token-a" } });
  assert.equal(out.titulo, "Aviso cancelado");
  assert.equal(estado.folha.linhas.length, 0);
});

test("doGet confirmar e cancelar com token desconhecido ou ausente dão Link inválido", () => {
  for (const parametro of [{ acao: "confirmar", t: "nenhum" }, { acao: "cancelar" }, { acao: "confirmar", t: "" }]) {
    const { ctx, estado } = ambiente({ linhas: [linha(H, "2026-01-01")] });
    assert.equal(ctx.doGet({ parameter: parametro }).titulo, "Link inválido");
    assert.equal(estado.folha.linhas.length, 1);
    assert.equal(estado.folha.linhas[0][2], false);
  }
});

test("doGet confirmar em planilha vazia dá Link inválido", () => {
  const { ctx } = ambiente();
  assert.equal(ctx.doGet({ parameter: { acao: "confirmar", t: "x" } }).titulo, "Link inválido");
});

test("doGet lista devolve lista vazia com chave errada ou ausente", () => {
  for (const parametro of [{ acao: "lista", chave: "errada" }, { acao: "lista" }, { acao: "apagar", h: H }, { acao: "marcar", h: H }]) {
    const { ctx, estado } = ambiente({ linhas: [linha(H, new Date())] });
    assert.deepEqual(lista(ctx.doGet({ parameter: parametro })), []);
    assert.equal(estado.folha.linhas.length, 1);
    assert.equal(estado.folha.linhas[0][3], false);
  }
});

test("doGet lista devolve as linhas com os campos e o tipo JSON", () => {
  const { ctx } = ambiente({ linhas: [linha("a".repeat(64), new Date(), true, true), linha("b".repeat(64), new Date())] });
  const out = ctx.doGet({ parameter: { acao: "lista", chave: "segredo" } });
  assert.equal(out.mime, "json");
  const itens = lista(out);
  assert.equal(itens.length, 2);
  assert.deepEqual(Object.keys(itens[0]), ["h", "criado", "confirmado", "enviada", "k", "iv", "c"]);
  assert.deepEqual([itens[0].confirmado, itens[0].enviada, itens[1].confirmado, itens[1].enviada], [true, true, false, false]);
  assert.equal(itens[0].k, "k");
});

test("doGet lista apaga os pendentes com mais de 7 dias e mantém confirmados antigos", () => {
  const velho = new Date(Date.now() - 8 * 86400000);
  const recente = new Date(Date.now() - 2 * 86400000);
  const { ctx, estado } = ambiente({
    linhas: [linha("a".repeat(64), velho), linha("b".repeat(64), velho, true), linha("c".repeat(64), recente), linha("d".repeat(64), velho)],
  });
  const itens = lista(ctx.doGet({ parameter: { acao: "lista", chave: "segredo" } }));
  assert.deepEqual(itens.map((i) => i.h[0]), ["b", "c"]);
  assert.deepEqual(estado.folha.apagadas, [4, 1]);
  assert.deepEqual(estado.folha.linhas.map((l) => l[0][0]), ["b", "c"]);
});

test("doGet marcar liga a coluna de confirmação enviada só da linha achada", () => {
  const { ctx, estado } = ambiente({ linhas: [linha("a".repeat(64), new Date()), linha(H, new Date())] });
  assert.deepEqual(lista(ctx.doGet({ parameter: { acao: "marcar", chave: "segredo", h: H } })), { ok: true });
  assert.equal(estado.folha.linhas[1][3], true);
  assert.equal(estado.folha.linhas[0][3], false);
});

test("doGet marcar com hash desconhecido responde ok sem alterar nada", () => {
  const { ctx, estado } = ambiente({ linhas: [linha(H, new Date())] });
  assert.deepEqual(lista(ctx.doGet({ parameter: { acao: "marcar", chave: "segredo", h: "zzz" } })), { ok: true });
  assert.equal(estado.folha.linhas[0][3], false);
});

test("doGet apagar remove as linhas de trás para frente e ignora hashes que não existem", () => {
  const a = "a".repeat(64), b = "b".repeat(64), c = "c".repeat(64);
  const { ctx, estado } = ambiente({ linhas: [linha(a, new Date()), linha(b, new Date()), linha(c, new Date())] });
  assert.deepEqual(lista(ctx.doGet({ parameter: { acao: "apagar", chave: "segredo", h: `${a},nada,${c}` } })), { ok: true });
  assert.deepEqual(estado.folha.apagadas, [3, 1]);
  assert.deepEqual(estado.folha.linhas.map((l) => l[0]), [b]);
});

test("doGet apagar sem h não apaga nada", () => {
  const { ctx, estado } = ambiente({ linhas: [linha(H, new Date())] });
  ctx.doGet({ parameter: { acao: "apagar", chave: "segredo" } });
  assert.equal(estado.folha.linhas.length, 1);
});

test("doGet sem ação, com ação desconhecida ou sem parameter mostra a página padrão e libera o lock", () => {
  for (const e of [{ parameter: {} }, {}, { parameter: { acao: "xyz" } }]) {
    const { ctx, estado } = ambiente({ linhas: [linha(H, new Date())] });
    assert.equal(ctx.doGet(e).titulo, "Minha Bancada");
    assert.equal(estado.folha.linhas.length, 1);
    assert.equal(estado.locks.solto, 1);
  }
});

test("a página escapa HTML do título e do texto", () => {
  const { ctx } = ambiente();
  const out = ctx.pagina_("<b>&", "<i>");
  assert.match(out.html, /&lt;b&gt;&amp;/);
  assert.match(out.html, /&lt;i&gt;/);
  assert.match(out.html, /https:\/\/adrianogpena\.github\.io\/minha-bancada\/informado\.html/);
});

test("hash_ devolve o SHA-256 em hexadecimal", () => {
  const { ctx } = ambiente();
  assert.equal(ctx.hash_("token-a"), sha("token-a"));
});
