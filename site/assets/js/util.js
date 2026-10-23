/* Utilidades puras: DOM, escape, URL segura, formatação e carga de JSON. */

/* Só devolve a URL se for http(s) (ou, com aceitaRelativa, um caminho do próprio site); senão "". Barra javascript:, data: etc. */
export function urlSegura(u, aceitaRelativa = false) {
  const s = String(u ?? "").trim();
  if (!s) return "";
  let x, absoluta = true;
  try { x = new URL(s); } catch {
    absoluta = false;
    try { x = new URL(s, "https://base.invalido/"); } catch { return ""; }
  }
  if (x.protocol !== "http:" && x.protocol !== "https:") return "";
  return absoluta || aceitaRelativa ? s : "";
}

export const $ = (sel, raiz = document) => raiz.querySelector(sel);
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const reais = (n) => (n ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
export const reaisCentavos = (n) => (n ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
export const pct = (a, b) => (b ? Math.round((a / b) * 100) + "%" : "—");
export const data = (iso, longo = false) => {
  if (!iso) return "";
  const d = new Date(iso.slice(0, 10) + "T12:00:00Z");
  return d.toLocaleDateString("pt-BR", longo ? { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" } : { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });
};
export const semAcento = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
export const param = (nome) => new URLSearchParams(location.search).get(nome);

export async function carregar(caminho) {
  const r = await fetch(caminho, { cache: "no-cache" });
  if (!r.ok) throw new Error(`Não foi possível carregar ${caminho} (${r.status})`);
  return r.json();
}

export const pctBr = (v) => `${v.toFixed(1).replace(".", ",")}%`;

export const numeroBr = (n) => n.toLocaleString("pt-BR");
