/**
 * Caixa de correio cega do "Fique informado" do Minha Bancada.
 * Guarda numa planilha privada (aba "assinaturas") só texto CRIPTOGRAFADO no navegador de quem assina
 * (e-mail e escolhas); aqui ninguém consegue ler. A chave privada fica só no GitHub Actions.
 *   POST (texto JSON)                 pedido de assinatura vindo do site (cifrado)
 *   GET ?acao=confirmar&t=TOKEN       link do e-mail de confirmação
 *   GET ?acao=cancelar&t=TOKEN        link no rodapé de cada aviso
 *   GET ?acao=lista&chave=CHAVE       (Actions) devolve as linhas cifradas
 *   GET ?acao=marcar&chave=&h=        (Actions) confirmação já enviada
 *   GET ?acao=apagar&chave=&h=A,B     (Actions) apaga linhas substituídas
 * A linha é achada pelo SHA-256 do token (coluna h); o token só existe no e-mail de quem assina.
 * Passo a passo em assinaturas/LEIAME.md.
 */
const ABA = "assinaturas";
const SITE = "https://adrianogpena.github.io/minha-bancada/informado.html";
const MAX_LINHAS = 5000;                    // trava contra quem tente encher a planilha
const PENDENTE_DIAS = 7;                    // cadastro não confirmado some depois disso
// colunas: h | criado | confirmado | confirmacao_enviada | k | iv | c
const B64 = /^[A-Za-z0-9+\/]+={0,2}$/;

function aba_() {
  const planilha = SpreadsheetApp.getActive();
  return planilha.getSheetByName(ABA) || planilha.insertSheet(ABA);
}

function pagina_(titulo, texto) {
  const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  return HtmlService.createHtmlOutput(
    `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
     <body style="font:18px/1.5 system-ui,sans-serif;max-width:520px;margin:15vh auto;padding:0 20px">
     <h1 style="font-size:24px">${esc(titulo)}</h1><p>${esc(texto)}</p><p><a href="${SITE}">Voltar ao Minha Bancada</a></p></body>`
  ).setTitle(titulo);
}

function hash_(token) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, token, Utilities.Charset.UTF_8)
    .map((b) => ("0" + (b & 0xff).toString(16)).slice(-2)).join("");
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    const d = JSON.parse(e.postData.contents);
    if (d.v !== 1 || !/^[0-9a-f]{64}$/.test(d.h) || ![d.k, d.iv, d.c].every((x) => typeof x === "string" && B64.test(x))
        || d.k.length > 1400 || d.iv.length > 24 || d.c.length > 12000) return ContentService.createTextOutput("erro");
    lock.waitLock(20000);
    const folha = aba_();
    if (folha.getLastRow() >= MAX_LINHAS) return ContentService.createTextOutput("cheio");
    if (folha.getLastRow() && folha.getRange(1, 1, folha.getLastRow(), 1).getValues().some((l) => l[0] === d.h)) return ContentService.createTextOutput("ok");
    folha.appendRow([d.h, new Date(), false, false, d.k, d.iv, d.c]);
    return ContentService.createTextOutput("ok");
  } catch (err) {
    return ContentService.createTextOutput("erro");
  } finally {
    try { lock.releaseLock(); } catch (e2) {}
  }
}

function linhaDe_(folha, h) {
  const n = folha.getLastRow();
  return n ? folha.getRange(1, 1, n, 1).getValues().findIndex((l) => l[0] === h) + 1 : 0;
}

function doGet(e) {
  const p = e.parameter || {};
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const folha = aba_();
    if (p.acao === "confirmar" || p.acao === "cancelar") {
      const linha = p.t ? linhaDe_(folha, hash_(String(p.t))) : 0;
      if (!linha) return pagina_("Link inválido", "Este link não vale mais. Se você já cancelou, está tudo certo.");
      if (p.acao === "cancelar") {
        folha.deleteRow(linha);
        return pagina_("Aviso cancelado", "Você não vai mais receber e-mails do Minha Bancada.");
      }
      folha.getRange(linha, 3).setValue(true);
      return pagina_("Tudo certo", "Você vai receber um e-mail por dia, só quando houver novidade no que você escolheu acompanhar.");
    }
    const chave = PropertiesService.getScriptProperties().getProperty("CHAVE");
    if (["lista", "marcar", "apagar"].includes(p.acao)) {
      if (!chave || p.chave !== chave) return json_([]);
      if (p.acao === "marcar") {
        const linha = linhaDe_(folha, String(p.h));
        if (linha) folha.getRange(linha, 4).setValue(true);
        return json_({ ok: true });
      }
      if (p.acao === "apagar") {
        String(p.h || "").split(",").map((h) => linhaDe_(folha, h)).filter(Boolean).sort((a, b) => b - a).forEach((l) => folha.deleteRow(l));
        return json_({ ok: true });
      }
      const limite = Date.now() - PENDENTE_DIAS * 86400000;
      const todas = folha.getDataRange().getValues();
      const vencida = (l) => l[2] !== true && new Date(l[1]).getTime() < limite;
      todas.map((l, i) => (l[0] && vencida(l) ? i + 1 : 0)).filter(Boolean).sort((a, b) => b - a).forEach((n) => folha.deleteRow(n));
      return json_(todas.filter((l) => l[0] && !vencida(l))
        .map((l) => ({ h: l[0], criado: new Date(l[1]).toISOString(), confirmado: l[2] === true, enviada: l[3] === true, k: l[4], iv: l[5], c: l[6] })));
    }
    return pagina_("Minha Bancada", "Para receber os avisos, use a página Fique informado.");
  } finally {
    lock.releaseLock();
  }
}
