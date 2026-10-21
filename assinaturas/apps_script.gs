/**
 * Cadastro do "Fique informado" do Minha Bancada.
 * Guarda os assinantes numa planilha do Google privada (aba "assinaturas") e atende:
 *   POST (texto JSON)          pedido de assinatura vindo do site; manda e-mail de confirmação
 *   GET ?acao=confirmar&t=...  link do e-mail de confirmação: ativa a assinatura
 *   GET ?acao=cancelar&t=...   link no rodapé de cada aviso: apaga a assinatura
 *   GET ?acao=lista&chave=...  usado só pelo GitHub Actions; devolve os assinantes confirmados
 * Passo a passo em assinaturas/LEIAME.md.
 */
const ABA = "assinaturas";
const SITE = "https://adrianogpena.github.io/minha-bancada/informado.html";
// colunas: email | token | confirmado | criado | config ativa (JSON) | config pendente (JSON)
const COLUNAS = 6;
const LOCAL = /^(BR|(UF|MUN):[A-Z]{2})$/;
const POLITICO = /^(pres|dep:\d+|gov:[A-Z]{2}|est:[A-Z]{2}:\d+|pref:[A-Z]{2})$/;

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

function limpar_(lista, regra, max) {
  return (Array.isArray(lista) ? lista : []).filter((x) => typeof x === "string" && regra.test(x)).slice(0, max);
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    const d = JSON.parse(e.postData.contents);
    const email = String(d.email || "").trim().toLowerCase();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || email.length > 120) return ContentService.createTextOutput("erro");
    const config = {
      locais: limpar_(d.locais, LOCAL, 30),
      politicos: limpar_(d.politicos, POLITICO, 60),
      rotulos: (Array.isArray(d.rotulos) ? d.rotulos : []).map((x) => String(x).slice(0, 120)).slice(0, 90),
    };
    if (!config.locais.length && !config.politicos.length) return ContentService.createTextOutput("erro");

    const cache = CacheService.getScriptCache();
    const chaveLimite = "lim:" + email;
    const tentativas = Number(cache.get(chaveLimite) || 0);
    if (tentativas >= 3) return ContentService.createTextOutput("limite");  // evita usar o site para encher a caixa de alguém
    cache.put(chaveLimite, String(tentativas + 1), 3600);

    lock.waitLock(20000);
    const folha = aba_();
    const dados = folha.getDataRange().getValues();
    let linha = dados.findIndex((l) => String(l[0]).toLowerCase() === email) + 1;
    let token;
    if (linha) {
      token = dados[linha - 1][1];
      folha.getRange(linha, 6).setValue(JSON.stringify(config));  // só vale depois que o dono do e-mail confirma
    } else {
      token = Utilities.getUuid();
      folha.appendRow([email, token, false, new Date(), "", JSON.stringify(config)]);
    }
    const link = ScriptApp.getService().getUrl() + "?acao=confirmar&t=" + token;
    MailApp.sendEmail({
      to: email,
      subject: "Confirme seu aviso do Minha Bancada",
      body: "Alguém (esperamos que você) pediu para receber por e-mail o que muda nos dados do Minha Bancada:\n\n- " +
        config.rotulos.join("\n- ") + "\n\nPara confirmar, abra: " + link +
        "\n\nSe não foi você, ignore esta mensagem: nada será enviado.",
    });
    return ContentService.createTextOutput("ok");
  } catch (err) {
    return ContentService.createTextOutput("erro");
  } finally {
    try { lock.releaseLock(); } catch (e2) {}
  }
}

function doGet(e) {
  const p = e.parameter || {};
  if (p.acao === "lista") {
    const chave = PropertiesService.getScriptProperties().getProperty("CHAVE");
    if (!chave || p.chave !== chave) return ContentService.createTextOutput("[]").setMimeType(ContentService.MimeType.JSON);
    const lista = aba_().getDataRange().getValues()
      .filter((l) => l[2] === true && l[4])
      .map((l) => Object.assign({ email: l[0], token: l[1] }, JSON.parse(l[4])));
    return ContentService.createTextOutput(JSON.stringify(lista)).setMimeType(ContentService.MimeType.JSON);
  }
  if (p.acao === "confirmar" || p.acao === "cancelar") {
    const lock = LockService.getScriptLock();
    lock.waitLock(20000);
    try {
      const folha = aba_();
      const linha = folha.getDataRange().getValues().findIndex((l) => l[1] && l[1] === p.t) + 1;
      if (!linha) return pagina_("Link inválido", "Este link não vale mais. Se você já cancelou, está tudo certo.");
      if (p.acao === "cancelar") {
        folha.deleteRow(linha);
        return pagina_("Aviso cancelado", "Você não vai mais receber e-mails do Minha Bancada.");
      }
      const pendente = folha.getRange(linha, 6).getValue();
      if (pendente) {
        folha.getRange(linha, 5).setValue(pendente);
        folha.getRange(linha, 6).setValue("");
      }
      folha.getRange(linha, 3).setValue(true);
      return pagina_("Tudo certo", "Você vai receber um e-mail por dia, só quando houver novidade no que você escolheu acompanhar.");
    } finally {
      lock.releaseLock();
    }
  }
  return pagina_("Minha Bancada", "Para receber os avisos, use a página Fique informado.");
}
