// Teste de fumaça no navegador: abre cada página do site sobre dados mínimos e falha se houver
// erro de JavaScript, erro de console, requisição local quebrada ou página sem o conteúdo esperado.
// Uso: node --test tests/e2e/fumaca.test.js   (precisa do pacote "playwright" e do Chromium)
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");

const RAIZ = path.resolve(__dirname, "../..");
const TIPOS = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml" };
// arquivos opcionais: a página trata a ausência (try/catch), mas o navegador registra o 404
const OPCIONAIS = ["/dados/executivo.json", "/dados/historico/indice.json", "/dados/indice/BR.json", "/dados/municipios_ibge.json", "/dados/status_apis.json", "/geo/br.json", "/dados/tramitacao/900.json", "/chave_publica.json", "/favicon.ico"];

let pasta, servidor, base, navegador;

function carregarPlaywright() {
  try { return require("playwright"); } catch { /* instalado globalmente: tenta pela raiz dos módulos globais */ }
  const global = execFileSync("npm", ["root", "-g"], { encoding: "utf8" }).trim();
  return require(path.join(global, "playwright"));
}

before(async () => {
  pasta = fs.mkdtempSync(path.join(os.tmpdir(), "bancada-e2e-"));
  execFileSync(process.env.PYTHON || "python", [path.join(RAIZ, "tests/e2e/preparar_site.py"), pasta], { stdio: "inherit" });
  servidor = http.createServer((req, res) => {
    const alvo = path.join(pasta, decodeURIComponent(new URL(req.url, "http://x").pathname));
    if (!alvo.startsWith(pasta) || !fs.existsSync(alvo) || fs.statSync(alvo).isDirectory()) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { "Content-Type": TIPOS[path.extname(alvo)] || "application/octet-stream" });
    fs.createReadStream(alvo).pipe(res);
  });
  await new Promise((ok) => servidor.listen(0, "127.0.0.1", ok));
  base = `http://127.0.0.1:${servidor.address().port}`;
  const { chromium } = carregarPlaywright();
  navegador = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
});

after(async () => {
  await navegador?.close();
  servidor?.close();
  if (pasta) fs.rmSync(pasta, { recursive: true, force: true });
});

// [página, texto que precisa aparecer quando os dados carregam, estado do elemento (padrão: visible)]
const PAGINAS = [
  ["index.html", "Minha Bancada"],
  ["camara.html", "Ana Souza"],
  ["deputado.html?id=101", "Ana Souza"],
  ["proposicoes.html", "PL 1/2026"],
  ["proposicao.html?k=c-900", "Ana Souza"],
  ["votacoes.html", "PL 1/2026"],
  ["votacao.html?id=1-1", "PL 1/2026"],
  ["fornecedores.html", "Cia Aérea"],
  // blocos montados a partir de `_disputas` (ficam numa aba fechada: basta estarem na página)
  ["politico.html?f=t/2024/71072&i=500", "Comparecimento e vagas", "attached"],
  ["politico.html?f=t/2024/71072&i=500", "Quociente eleitoral", "attached"],
  ["politico.html?f=t/2024/71072&i=501", "concorreu sozinho", "attached"],
  ["sobre.html", "Como ler os números"],
  ["mapa-dados.html", "Como uma ligação é feita"],
  ["informado.html", "Minha Bancada"],
  ["historico.html", "Minha Bancada"],
];

for (const [pagina, texto, estado = "visible"] of PAGINAS) {
  test(`${pagina} abre sem erros e mostra "${texto}"`, async () => {
    const contexto = await navegador.newContext();
    const aba = await contexto.newPage();
    const problemas = [];
    aba.on("pageerror", (e) => problemas.push(`erro de JS: ${e.message}`));
    aba.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) problemas.push(`console: ${m.text()}`); });
    aba.on("response", (r) => {
      const u = new URL(r.url());
      if (r.url().startsWith(base) && r.status() >= 400 && !OPCIONAIS.includes(u.pathname)) problemas.push(`${r.status()} ${u.pathname}`);
    });
    // nada de internet no teste: fontes, imagens e APIs externas são cortadas
    await aba.route((u) => !u.href.startsWith(base), (rota) => rota.abort());
    await aba.goto(`${base}/${pagina}`, { waitUntil: "networkidle" });
    await aba.getByText(texto, { exact: false }).first().waitFor({ timeout: 10000, state: estado });
    await contexto.close();
    assert.deepEqual(problemas, []);
  });
}
