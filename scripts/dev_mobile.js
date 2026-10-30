// Abre o site numa janela de celular (toque ligado, janela 412x800 por padrão, a área visível do Galaxy M55 no Chrome) servindo site/ com os dados já gerados.
// Uso: npm run dev:mobile [-- <página>] [--largura=360] [--altura=740]
// Fechar a janela encerra o servidor. Recarregue (F5) para ver mudanças no CSS/JS.
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");

const SITE = path.resolve(__dirname, "../site");
const TIPOS = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg" };

const args = process.argv.slice(2);
const opcao = (nome, padrao) => Number(args.find((a) => a.startsWith(`--${nome}=`))?.split("=")[1] ?? padrao);
const largura = opcao("largura", 412), altura = opcao("altura", 800);
const pagina = args.find((a) => !a.startsWith("--")) || "index.html";

function carregarPlaywright() {
  try { return require("playwright"); } catch { /* instalado globalmente: tenta pela raiz dos módulos globais */ }
  const global = execFileSync("npm", ["root", "-g"], { encoding: "utf8", shell: true }).trim();
  return require(path.join(global, "playwright"));
}

(async () => {
  if (!fs.existsSync(path.join(SITE, "dados"))) console.warn("Aviso: site/dados não existe; rode `python scripts/gerar.py` para ver dados reais.");
  const servidor = http.createServer((req, res) => {
    const alvo = path.join(SITE, decodeURIComponent(new URL(req.url, "http://x").pathname));
    if (!alvo.startsWith(SITE) || !fs.existsSync(alvo) || fs.statSync(alvo).isDirectory()) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { "Content-Type": TIPOS[path.extname(alvo)] || "application/octet-stream", "Cache-Control": "no-store" });
    fs.createReadStream(alvo).pipe(res);
  });
  await new Promise((ok) => servidor.listen(0, "127.0.0.1", ok));
  const base = `http://127.0.0.1:${servidor.address().port}`;

  const { chromium } = carregarPlaywright();
  // Janela sem barra de endereço e sem viewport emulado: a área da página é a própria janela, do tamanho do celular.
  const perfil = fs.mkdtempSync(path.join(os.tmpdir(), "bancada-mobile-dev-"));
  const contexto = await chromium.launchPersistentContext(perfil, {
    headless: false, viewport: null, hasTouch: true, colorScheme: "dark", ignoreDefaultArgs: ["--enable-automation"],
    userAgent: "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Mobile Safari/537.36",
    args: [`--app=${base}/${pagina}`, `--window-size=${largura},${altura}`, "--hide-scrollbars", "--touch-events=enabled"],
  });
  const aba = contexto.pages()[0] ?? (await contexto.waitForEvent("page"));
  await aba.waitForLoadState();
  // a moldura da janela (borda, barra de título) come parte do tamanho pedido: ajusta até a área da página medir largura x altura
  const cdp = await contexto.newCDPSession(aba);
  const { windowId } = await cdp.send("Browser.getWindowForTarget");
  for (let i = 0; i < 6; i++) {
    const { bounds } = await cdp.send("Browser.getWindowForTarget");
    const [dentro, alto] = await aba.evaluate(() => [innerWidth, innerHeight]);
    if (dentro === largura && alto === altura) break;
    await cdp.send("Browser.setWindowBounds", { windowId, bounds: { windowState: "normal", width: bounds.width + (largura - dentro), height: bounds.height + (altura - alto) } });
    await aba.waitForTimeout(250);
  }
  const [w, h] = await aba.evaluate(() => [innerWidth, innerHeight]);
  console.log(`Modo celular ${w}x${h} (pedido ${largura}x${altura}) em ${base}/${pagina}. Feche a janela para encerrar.`);

  const encerrar = () => { servidor.close(); process.exit(0); };
  contexto.on("close", encerrar);
  process.on("SIGINT", () => contexto.close().finally(encerrar));
})();
