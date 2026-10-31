// Abre o site numa janela de celular (toque ligado, janela 412x800 por padrão, a área visível do Galaxy M55 no Chrome) servindo site/ com os dados já gerados.
// Com --desktop abre a janela com o layout de navegador de computador (1280x800 por padrão, sem toque).
// Uso: npm run dev:mobile [-- <página>] [--largura=360] [--altura=740]  |  npm run dev:window [-- <página>] [--largura=1280] [--altura=800]
// Fechar a janela encerra o servidor. Mudou CSS em site/: as folhas são trocadas sem recarregar. Mudou outra coisa: a janela recarrega mantendo rolagem, <details> e campos.
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");

const SITE = path.resolve(__dirname, "../site");
const TIPOS = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg" };

const args = process.argv.slice(2);
const opcao = (nome, padrao) => Number(args.find((a) => a.startsWith(`--${nome}=`))?.split("=")[1] ?? padrao);
const desktop = args.includes("--desktop");
const largura = opcao("largura", desktop ? 1280 : 412), altura = opcao("altura", 800);
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
  // Janela sem barra de endereço e sem viewport emulado: a área da página é a própria janela, do tamanho pedido.
  const perfil = fs.mkdtempSync(path.join(os.tmpdir(), "bancada-mobile-dev-"));
  const contexto = await chromium.launchPersistentContext(perfil, {
    // --test-type some com o aviso de flag não suportada; as variáveis GOOGLE_* somem com o de chaves de API ausentes
    env: { ...process.env, GOOGLE_API_KEY: "no", GOOGLE_DEFAULT_CLIENT_ID: "no", GOOGLE_DEFAULT_CLIENT_SECRET: "no" },
    headless: false, viewport: null, colorScheme: "dark", ignoreDefaultArgs: ["--enable-automation"],
    ...(desktop ? {} : {
      hasTouch: true,
      userAgent: "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Mobile Safari/537.36",
    }),
    args: [`--app=${base}/${pagina}`, `--window-size=${largura},${altura}`, "--test-type", "--disable-features=Translate,TranslateUI", "--lang=pt-BR", ...(desktop ? [] : ["--hide-scrollbars", "--touch-events=enabled"])],
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
  console.log(`Modo ${desktop ? "desktop" : "celular"} ${w}x${h} (pedido ${largura}x${altura}) em ${base}/${pagina}. Feche a janela para encerrar.`);

  // Mudou só CSS: troca as folhas sem recarregar (todo o estado da página fica). Mudou outra coisa: recarrega
  // guardando rolagem, <details> abertos e campos, e devolve tudo quando a página termina de montar.
  const trocarCss = () => aba.evaluate(() => {
    for (const velha of document.querySelectorAll("link[rel=stylesheet]")) {
      const url = new URL(velha.href);
      if (url.origin !== location.origin) continue;
      url.searchParams.set("_", Date.now());
      const nova = velha.cloneNode();
      nova.href = url;
      nova.onload = () => velha.remove();
      velha.after(nova);
    }
  });
  const capturar = () => aba.evaluate(() => ({
    y: scrollY,
    abertos: [...document.querySelectorAll("details")].map((d) => d.open),
    campos: [...document.querySelectorAll("input, select, textarea")].map((c) => (c.type === "checkbox" || c.type === "radio" ? c.checked : c.value)),
  }));
  const restaurar = (estado) => aba.evaluate(async (e) => {
    let abertos = false, campos = false;
    for (let i = 0; i < 40; i++) {
      const ds = [...document.querySelectorAll("details")], cs = [...document.querySelectorAll("input, select, textarea")];
      if (!abertos && ds.length === e.abertos.length) { ds.forEach((d, k) => { d.open = e.abertos[k]; }); abertos = ds.length > 0; }
      if (!campos && cs.length === e.campos.length) {
        cs.forEach((c, k) => {
          const caixa = c.type === "checkbox" || c.type === "radio", v = e.campos[k];
          if ((caixa ? c.checked : c.value) === v) return;
          if (caixa) c.checked = v; else c.value = v;
          c.dispatchEvent(new Event(caixa || c.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
        });
        campos = cs.length > 0;
      }
      scrollTo(0, e.y);
      if (Math.abs(scrollY - e.y) < 2 && document.readyState === "complete" && i > 4) break;
      await new Promise((ok) => setTimeout(ok, 150));
    }
  }, estado);
  const recarregar = async () => {
    const estado = await capturar().catch(() => null);
    await aba.reload();
    if (estado) await restaurar(estado).catch(() => {});
  };

  let pendente, alterados = new Set();
  const observador = fs.watch(SITE, { recursive: true }, (_, arquivo) => {
    alterados.add(arquivo ? path.extname(arquivo) : "");
    clearTimeout(pendente);
    pendente = setTimeout(() => {
      const soCss = alterados.size === 1 && alterados.has(".css");
      alterados = new Set();
      (soCss ? trocarCss() : recarregar()).catch(() => {});
    }, 200);
  });

  const encerrar = () => { observador.close(); servidor.close(); process.exit(0); };
  contexto.on("close", encerrar);
  process.on("SIGINT", () => contexto.close().finally(encerrar));
})();
