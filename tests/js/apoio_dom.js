const path = require("node:path");

class Elemento {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this._html = "";
    this._filhos = new Map();
    this._todos = new Map();
    this._ouvintes = {};
    this._atributos = {};
    this.textContent = "";
    this.value = "";
    this.hidden = false;
    this.dataset = {};
    this.className = "";
    this.children = [];
    this.estilo = {};
    this.style = {};
    this.classList = {
      contains: (c) => this.className.split(/\s+/).includes(c),
      add: (c) => { this.className = `${this.className} ${c}`.trim(); },
      toggle: (c, on) => { const tem = this.classList.contains(c); if (on && !tem) this.classList.add(c); if (!on && tem) this.className = this.className.split(/\s+/).filter((x) => x !== c).join(" "); },
    };
  }

  get innerHTML() { return this._html; }

  set innerHTML(v) { this._html = String(v); this._filhos = new Map(); }

  querySelector(sel) {
    if (!this._filhos.has(sel)) this._filhos.set(sel, new Elemento());
    return this._filhos.get(sel);
  }

  querySelectorAll(sel) { return this._todos.get(sel) || []; }

  definirTodos(sel, lista) { this._todos.set(sel, lista); }

  insertAdjacentHTML(pos, h) { this._html = pos === "afterbegin" ? h + this._html : this._html + h; }

  append(...nos) { nos.forEach((n) => this.children.push(n)); }

  addEventListener(tipo, fn) { (this._ouvintes[tipo] ||= []).push(fn); }

  async disparar(tipo, ev = {}) {
    for (const fn of this._ouvintes[tipo] || []) await fn(ev);
  }

  ouvintes(tipo) { return (this._ouvintes[tipo] || []).length; }

  setAttribute(k, v) { this._atributos[k] = String(v); }

  getAttribute(k) { return this._atributos[k]; }

  after() {}

  removeAttribute() {}

  scrollTo() {}

  getBoundingClientRect() { return { top: 0, bottom: 0 }; }
}

function instalarDom({ search = "", hash = "", pathname = "/pagina.html", origin = "https://site.exemplo", referrer = "", historico = 1 } = {}) {
  const gravacoes = [];
  const raiz = new Elemento("html");
  const corpo = new Elemento("body");
  const doc = {
    body: corpo,
    title: "",
    referrer,
    _ouvintes: {},
    querySelector: (s) => raiz.querySelector(s),
    querySelectorAll: (s) => raiz.querySelectorAll(s),
    getElementById: (id) => raiz.querySelector(`#${id}`),
    createElement: (t) => new Elemento(t),
    addEventListener(t, fn) { (this._ouvintes[t] ||= []).push(fn); },
  };
  const original = {};
  const definir = (nome, valor) => { original[nome] = Object.getOwnPropertyDescriptor(globalThis, nome); Object.defineProperty(globalThis, nome, { value: valor, configurable: true, writable: true }); };
  const loc = { search, hash, pathname, origin, replace: (u) => gravacoes.push(["replace", u]) };
  const hist = { length: historico, replaceState: (a, b, url) => gravacoes.push(["replaceState", url]), back: () => gravacoes.push(["back"]) };
  const janela = { scrollBy: (o) => gravacoes.push(["scrollBy", o]), addEventListener: () => {} };
  definir("document", doc);
  definir("location", loc);
  definir("history", hist);
  definir("window", janela);
  definir("matchMedia", () => ({ matches: false }));
  definir("getComputedStyle", () => ({ position: "static" }));
  return {
    doc, loc, hist, janela, gravacoes, raiz, corpo,
    el: (sel) => raiz.querySelector(sel),
    restaurar() {
      for (const [nome, d] of Object.entries(original)) {
        if (d) Object.defineProperty(globalThis, nome, d); else delete globalThis[nome];
      }
    },
  };
}

function comFetch(respostas, corpo) {
  const original = globalThis.fetch;
  const chamadas = [];
  globalThis.fetch = async (url) => {
    const chave = String(url);
    chamadas.push(chave);
    const r = respostas[chave];
    if (r === undefined) return { ok: false, status: 404, json: async () => ({}) };
    if (r instanceof Error) throw r;
    return { ok: true, status: 200, json: async () => r };
  };
  return Promise.resolve(corpo(chamadas)).finally(() => { globalThis.fetch = original; });
}

async function comPagina(opcoes, respostas, corpo) {
  const dom = instalarDom(opcoes);
  const erros = [];
  const consoleErro = console.error;
  console.error = (e) => erros.push(e);
  try {
    return await comFetch(respostas, (chamadas) => corpo(dom, chamadas, erros));
  } finally {
    console.error = consoleErro;
    dom.restaurar();
  }
}

const js = (nome) => require(path.join(__dirname, "../../site/assets/js", nome));

module.exports = { Elemento, instalarDom, comFetch, comPagina, js };
