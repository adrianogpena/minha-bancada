// Teste do modo mobile: abre cada página em telas de celular (com toque) sobre dados mínimos e falha se
// houver rolagem horizontal, elemento que sai da tela, alvo de toque pequeno ou texto ilegível.
// Também passa por cada aba da ficha do político.
// Uso: node --test tests/e2e/mobile.test.js   (precisa do pacote "playwright" e do Chromium)
// Capturas de tela: MOBILE_FOTOS=<pasta> node --test tests/e2e/mobile.test.js
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");

const RAIZ = path.resolve(__dirname, "../..");
const TIPOS = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml" };
const TELAS = [
  { nome: "320", viewport: { width: 320, height: 640 } },
  { nome: "360", viewport: { width: 360, height: 740 } },
  { nome: "412", viewport: { width: 412, height: 915 } }, // Galaxy M55 5G: 1080x2400, densidade 2,625
];
const PAGINAS = [
  ["index.html", "Minha Bancada"],
  ["camara.html", "Ana Souza"],
  ["deputado.html?id=101", "Ana Souza"],
  ["proposicoes.html", "PL 1/2026"],
  ["proposicao.html?k=c-900", "Ana Souza"],
  ["votacoes.html", "PL 1/2026"],
  ["votacao.html?id=1-1", "PL 1/2026"],
  ["fornecedores.html", "Cia Aérea"],
  ["politico.html?f=t/2024/71072&i=500", "Comparecimento e vagas", "attached"],
  ["sobre.html", "Como ler os números"],
  ["mapa-dados.html", "Como uma ligação é feita"],
  ["informado.html", "Minha Bancada"],
  ["historico.html", "Minha Bancada"],
];
const ALVO_MIN = 44; // px, lado mínimo de botão, campo e item de menu
const FONTE_MIN = 13; // px

let pasta, servidor, base, navegador;

function carregarPlaywright() {
  try { return require("playwright"); } catch { /* instalado globalmente: tenta pela raiz dos módulos globais */ }
  const global = execFileSync("npm", ["root", "-g"], { encoding: "utf8", shell: true }).trim();
  return require(path.join(global, "playwright"));
}

before(async () => {
  pasta = fs.mkdtempSync(path.join(os.tmpdir(), "bancada-mobile-"));
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

// Roda dentro da página: devolve a lista de problemas de layout do estado atual.
function medir({ alvoMin, fonteMin }) {
  const larg = document.documentElement.clientWidth;
  const problemas = [];
  const rotulo = (el) => `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}${typeof el.className === "string" && el.className ? "." + el.className.trim().split(/\s+/).join(".") : ""}`;
  const visivel = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
  };
  // dentro de um contêiner com rolagem própria (ou cortado) o excesso é intencional
  const rolavel = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox === "auto" || ox === "scroll" || ox === "hidden" || ox === "clip") return true;
    }
    return false;
  };

  if (document.documentElement.scrollWidth > larg) problemas.push(`rolagem horizontal: página tem ${document.documentElement.scrollWidth}px em tela de ${larg}px`);

  const vistos = new Set();
  for (const el of document.body.querySelectorAll("*")) {
    if (!visivel(el) || rolavel(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.right > larg + 1 || r.left < -1) {
      const chave = rotulo(el);
      if (!vistos.has(chave)) { vistos.add(chave); problemas.push(`sai da tela: ${chave} (${Math.round(r.left)}..${Math.round(r.right)}px)`); }
    }
  }

  const seletorToque = "button, select, input, textarea, summary, [role=tab], .nav a, nav a, .abas a, .abas button, .mais, .voltar";
  const pequenos = new Set();
  for (const el of document.querySelectorAll(seletorToque)) {
    if (!visivel(el) || el.disabled || ["hidden", "checkbox", "radio"].includes(el.type)) continue;
    const r = el.getBoundingClientRect();
    if (r.height < alvoMin || r.width < alvoMin) {
      const chave = `${rotulo(el)} ${Math.round(r.width)}x${Math.round(r.height)}px`;
      if (!pequenos.has(chave)) { pequenos.add(chave); problemas.push(`alvo de toque pequeno: ${chave} "${(el.textContent || el.value || el.getAttribute("aria-label") || "").trim().slice(0, 30)}"`); }
    }
  }

  const miudos = new Set();
  for (const el of document.body.querySelectorAll("*")) {
    if (!visivel(el)) continue;
    const temTexto = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!temTexto) continue;
    const tamanho = parseFloat(getComputedStyle(el).fontSize);
    if (tamanho < fonteMin) {
      const chave = `${rotulo(el)} ${tamanho}px`;
      if (!miudos.has(chave)) { miudos.add(chave); problemas.push(`texto pequeno: ${chave}`); }
    }
  }

  const semZoom = document.querySelector('meta[name="viewport"]')?.content ?? "";
  if (/user-scalable\s*=\s*no|maximum-scale\s*=\s*1(\.0)?\b/.test(semZoom)) problemas.push("viewport bloqueia o zoom");
  return problemas;
}

async function verificar(aba, etapa, tela) {
  const problemas = await aba.evaluate(medir, { alvoMin: ALVO_MIN, fonteMin: FONTE_MIN });
  const fotos = process.env.MOBILE_FOTOS;
  if (fotos) {
    fs.mkdirSync(fotos, { recursive: true });
    await aba.screenshot({ path: path.join(fotos, `${tela.nome}-${etapa.replace(/[^\w-]+/g, "_")}.png`), fullPage: true });
  }
  return problemas.map((p) => `[${etapa}] ${p}`);
}

for (const tela of TELAS) {
  for (const [pagina, texto, estado = "visible"] of PAGINAS) {
    test(`${tela.nome}px: ${pagina} cabe na tela e é tocável`, async () => {
      const contexto = await navegador.newContext({ viewport: tela.viewport, isMobile: true, hasTouch: true, deviceScaleFactor: 2.625 });
      const aba = await contexto.newPage();
      await aba.route((u) => !u.href.startsWith(base), (rota) => rota.abort());
      await aba.goto(`${base}/${pagina}`, { waitUntil: "networkidle" });
      await aba.getByText(texto, { exact: false }).first().waitFor({ timeout: 10000, state: estado });

      const problemas = await verificar(aba, "inicial", tela);

      // cada aba da ficha é uma tela própria no celular
      const abas = aba.locator('.abas-pagina button, [role="tablist"] [role="tab"]');
      const n = await abas.count();
      for (let i = 0; i < n; i++) {
        const botao = abas.nth(i);
        if (!(await botao.isVisible())) continue;
        const nome = ((await botao.textContent()) || `aba${i}`).trim().replace(/\s+/g, " ");
        await botao.tap();
        await aba.waitForTimeout(150);
        problemas.push(...(await verificar(aba, `aba ${nome}`, tela)));
      }
      await contexto.close();
      assert.deepEqual([...new Set(problemas)], []);
    });
  }
}
