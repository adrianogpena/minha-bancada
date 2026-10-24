/* Página Fique informado: feeds RSS e assinaturas. */
import { $, esc, semAcento, carregar } from "./util.js";
import { UFS } from "./apis.js";

/* ---------- Fique informado ---------- */
/* Feeds RSS estáticos (site/feeds/<código>.xml, gerados por scripts/feeds.py). Nada é enviado nem guardado: quem assina é o leitor de RSS da pessoa. */
const arquivoFeed = (codigo) => `feeds/${codigo.replace(/:/g, "-")}.xml`;
/* Endereço do Apps Script que guarda os cadastros cifrados (assinaturas/LEIAME.md). Vazio = aviso por e-mail desligado. */
const URL_ASSINATURAS = "https://script.google.com/macros/s/AKfycbw7wYVPqPthp0XkckChSa0lpbQJ6oHnNusYzgP9aGukc2zmEIeZkgOQOfPpcgYql31f/exec";
const urlFeed = (codigo) => new URL(arquivoFeed(codigo), location.href).href;

export async function paginaInformado() {
  const alvo = $("#informado");
  const cobertura = await carregar("dados/cobertura.json").catch(() => ({ estados: [], capitais: {} }));
  const escolhidos = new Map();   // código -> rótulo
  const nomeUf = (uf) => UFS[uf] || uf;
  alvo.innerHTML = `
    <div class="informado">
      <fieldset>
        <legend>1. O que você quer acompanhar?</legend>
        <p class="dica-form">Cada escolha vira um feed. Você pode misturar.</p>
        <div class="filtros dois">
          <label class="campo">Brasil
            <button type="button" class="mais" id="add-br">Câmara, Senado e Presidência</button></label>
          <label class="campo">Estado
            <select id="inf-uf"><option value="">Escolha…</option>${cobertura.estados.map((u) => `<option value="${u}">${esc(nomeUf(u))}</option>`).join("")}</select></label>
          <label class="campo">Capital
            <select id="inf-capital"><option value="">Escolha…</option>${Object.entries(cobertura.capitais).map(([u, m]) => `<option value="${u}">${esc(m)} (${u})</option>`).join("")}</select></label>
        </div>
        <div class="resumo-escolhas" id="resumo" role="status" aria-live="polite"></div>
        <p class="dica-form">Estado: Assembleia, governo, deputados federais do estado e a capital. Hoje só entram estados e capitais cujos dados já coletamos (${cobertura.estados.length} Assembleias, ${Object.keys(cobertura.capitais).length} capitais); outros locais entram conforme novas fontes forem conectadas.</p>
      </fieldset>
      <fieldset>
        <legend>2. Ou políticos <small>(opcional)</small></legend>
        <div class="filtros dois">
          <label class="campo">Onde atua
            <select id="pol-uf"><option value="BR">Presidente e deputados federais (Brasil)</option>${Object.entries(UFS).map(([u, n]) => `<option value="${u}">${esc(n)}</option>`).join("")}</select></label>
          <label class="campo">Nome<input id="pol-busca" type="search" placeholder="Ex.: Presidente, Maria, PT" autocomplete="off"></label>
        </div>
        <ul class="itens" id="pol-achados" aria-live="polite"></ul>
        <div class="resumo-escolhas" id="resumo-pol" role="status" aria-live="polite"></div>
        <p class="dica-form">Aparecem só políticos de quem já acompanhamos propostas: Presidente, governadores, deputados federais, deputados estaduais (Assembleias coletadas) e prefeitos de capitais com dados.</p>
      </fieldset>
      <fieldset id="sec-feeds">
        <legend>3. Seus feeds <small id="qtd-feeds"></small></legend>
        <ul class="escolhas" id="escolhas" aria-live="polite"></ul>
        <p id="opml-p" hidden><button type="button" class="botao" id="opml">Baixar todos (arquivo OPML)</button></p>
        <details>
          <summary>Como usar um feed RSS</summary>
          <p class="dica-form">Cole o endereço do feed (ou importe o arquivo OPML) num leitor de RSS, como Feedly, Inoreader, NetNewsWire, Thunderbird ou o leitor de notícias do seu celular. Quando houver novidade, ela aparece lá, no máximo uma vez por dia. Alguns leitores, como o Feedly e o Inoreader, também mandam o aviso por e-mail ou notificação.</p>
        </details>
        <p class="dica-form">No RSS não há cadastro: não pedimos nem guardamos e-mail ou qualquer dado seu. Seu leitor busca um arquivo público, igual a abrir uma página do site.</p>
      </fieldset>
      <fieldset id="sec-email" hidden>
        <legend>4. Prefere por e-mail? <small>(opcional)</small></legend>
        <p class="dica-form">Um e-mail por dia, por semana ou por mês (você escolhe), só quando houver novidade <b>nos itens de "Seus feeds"</b>, listados abaixo. O que você não escolheu não é enviado. Seu endereço é <b>criptografado no seu navegador</b> antes de sair: o site e a planilha onde fica o cadastro só guardam texto ilegível. Só o robô diário do GitHub, que tem a chave, consegue abri-lo para enviar o aviso. Quem administra o projeto controla esse robô e, tecnicamente, poderia mudá-lo para ler os endereços; se isso não é aceitável para você, use o RSS acima, que não pede nenhum dado.</p>
        <div class="resumo-escolhas" id="email-escolhas" role="status" aria-live="polite"></div>
        <form id="form-email" novalidate>
          <div class="linha-email">
            <label class="campo">E-mail<input id="inf-email" type="email" autocomplete="email" placeholder="voce@exemplo.com"></label>
            <label class="campo">Frequência
              <select id="inf-freq"><option value="diario" selected>Diário</option><option value="semanal">Semanal (segunda-feira)</option><option value="mensal">Mensal (dia 1)</option></select></label>
          </div>
          <p><button type="submit" class="botao" id="inf-enviar">Quero receber por e-mail</button></p>
          <p class="aviso-form" id="inf-msg" role="status" aria-live="polite"></p>
        </form>
        <p class="dica-form">Você recebe um e-mail para confirmar (a confirmação sai em até 15 minutos) e todo aviso traz o link para cancelar.</p>
      </fieldset>
    </div>`;

  const desenhar = () => {
    const todos = [...escolhidos];
    $("#escolhas").innerHTML = todos.length
      ? todos.map(([c, r], i) => `<li><span>${esc(r)}<br><small><a href="${esc(arquivoFeed(c))}">${esc(urlFeed(c))}</a></small></span>
          <span class="acoes"><button type="button" data-copiar="${i}">copiar</button><button type="button" data-tirar="${i}" aria-label="Remover ${esc(r)}">remover</button></span></li>`).join("")
      : `<li class="vazio">Nada escolhido ainda.</li>`;
    $("#opml-p").hidden = !todos.length;
    $("#email-escolhas").innerHTML = todos.length
      ? `<p class="dica-form"><b>O e-mail vai avisar sobre:</b></p><div class="chips">${todos.map(([, r], i) => `<span class="chip">${esc(r)}<button type="button" data-tirar="${i}" aria-label="Remover ${esc(r)}">×</button></span>`).join("")}</div>`
      : `<p class="dica-form"><b>Nada escolhido ainda.</b> Escolha locais ou políticos acima: só eles entram no e-mail.</p>`;
    $("#qtd-feeds").textContent = todos.length ? `(${todos.length})` : "";
    $("#email-escolhas").onclick = (e) => {
      const b = e.target.closest("button"); if (!b) return;
      escolhidos.delete(todos[b.dataset.tirar][0]); desenhar(); mostrarAchados();
    };
    const ehLocal = (c) => /^(BR|UF:|MUN:)/.test(c);
    for (const [id, local] of [["#resumo", true], ["#resumo-pol", false]]) {
      const lista = todos.map(([c, r], i) => [c, r, i]).filter(([c]) => ehLocal(c) === local);
      $(id).innerHTML = lista.length
        ? `<p class="dica-form"><b>Escolhido:</b></p><div class="chips">${lista.map(([, r, i]) => `<span class="chip">${esc(r)}<button type="button" data-tirar="${i}" aria-label="Remover ${esc(r)}">×</button></span>`).join("")}</div>
           <p class="dica-form"><a href="#sec-feeds">Ver endereços dos feeds ↓</a></p>`
        : "";
      $(id).onclick = (e) => {
        const b = e.target.closest("button"); if (!b) return;
        escolhidos.delete(todos[b.dataset.tirar][0]); desenhar(); mostrarAchados();
      };
    }
    $("#add-br").textContent = escolhidos.has("BR") ? "✓ Câmara, Senado e Presidência" : "Câmara, Senado e Presidência";
    $("#add-br").classList.toggle("marcado", escolhidos.has("BR"));
    for (const [id, pref] of [["#inf-uf", "UF:"], ["#inf-capital", "MUN:"]]) {
      const sel = $(id), v = sel.value;
      if (!v || !escolhidos.has(pref + v)) sel.value = [...escolhidos.keys()].map((c) => c.startsWith(pref) ? c.slice(pref.length) : null).filter(Boolean).pop() || "";
      sel.classList.toggle("marcado", !!sel.value);
    }
    $("#escolhas").onclick = async (e) => {
      const b = e.target.closest("button"); if (!b) return;
      if (b.dataset.tirar != null) { escolhidos.delete(todos[b.dataset.tirar][0]); desenhar(); mostrarAchados(); return; }
      try { await navigator.clipboard.writeText(urlFeed(todos[b.dataset.copiar][0])); b.textContent = "copiado"; } catch { b.textContent = "selecione o endereço"; }
    };
  };
  const adicionar = (codigo, rotulo) => { if (codigo) { escolhidos.set(codigo, rotulo); desenhar(); mostrarAchados(); } };
  $("#add-br").onclick = () => adicionar("BR", "Brasil: Câmara, Senado e Presidência");
  $("#inf-uf").onchange = (e) => { const u = e.target.value; adicionar(u && `UF:${u}`, `Estado: ${nomeUf(u)}`); };
  $("#inf-capital").onchange = (e) => { const u = e.target.value; adicionar(u && `MUN:${u}`, `Capital: ${cobertura.capitais[u]} (${u})`); };
  $("#opml").onclick = () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?><opml version="2.0"><head><title>Minha Bancada</title></head><body>${
      [...escolhidos].map(([c, r]) => `<outline type="rss" text="${esc(r)}" title="${esc(r)}" xmlUrl="${esc(urlFeed(c))}"/>`).join("")}</body></opml>`;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([xml], { type: "text/x-opml" }));
    a.download = "minha-bancada.opml";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  /* políticos: índice do estado (ou do Brasil), só quem tem código "codigoFeed" */
  let indice = [];
  const mostrarAchados = () => {
    const q = semAcento($("#pol-busca").value.trim());
    const achados = indice.filter((x) => x.codigoFeed && (!q || semAcento(`${x.nome} ${x.cargo} ${x.partido || ""} ${x.municipio || ""}`).includes(q))).slice(0, 12);
    $("#pol-achados").innerHTML = achados.length
      ? achados.map((x, i) => `<li><span><b>${esc(x.nome)}</b> <small>${esc(x.cargo)}${x.partido ? ` · ${esc(x.partido)}` : ""}${x.municipio ? ` · ${esc(x.municipio)}` : ""}</small></span>
          <button type="button" data-i="${i}"${escolhidos.has(x.codigoFeed) ? " disabled" : ""}>${escolhidos.has(x.codigoFeed) ? "adicionado" : "acompanhar"}</button></li>`).join("")
      : `<li class="vazio">Ninguém encontrado com dados acompanháveis.</li>`;
    $("#pol-achados").onclick = (e) => {
      const b = e.target.closest("button"); if (!b) return;
      const x = achados[b.dataset.i];
      adicionar(x.codigoFeed, `${x.cargo}: ${x.nome}`);
    };
  };
  $("#pol-uf").onchange = async () => { indice = await carregar(`dados/indice/${$("#pol-uf").value}.json`).catch(() => []); mostrarAchados(); };
  $("#pol-busca").oninput = mostrarAchados;
  desenhar();
  $("#pol-uf").onchange();

  /* aviso por e-mail: cifra no navegador (AES-256-GCM, chave de uso único embrulhada com RSA-OAEP) e manda só o texto cifrado */
  const chavePublica = URL_ASSINATURAS ? await carregar("chave_publica.json").catch(() => null) : null;
  if (chavePublica) {
    $("#sec-email").hidden = false;
    const b64 = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)));
    const hex = (buf) => [...new Uint8Array(buf)].map((x) => x.toString(16).padStart(2, "0")).join("");
    $("#form-email").addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = $("#inf-msg"), email = $("#inf-email").value.trim();
      const locais = [...escolhidos.keys()].filter((c) => /^(BR|UF:|MUN:)/.test(c));
      const politicos = [...escolhidos.keys()].filter((c) => !locais.includes(c));
      if (!escolhidos.size) { msg.textContent = "Escolha acima pelo menos um local ou político."; return; }
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { msg.textContent = "Digite um e-mail válido."; return; }
      $("#inf-enviar").disabled = true;
      msg.textContent = "Enviando…";
      try {
        const enc = new TextEncoder();
        const token = hex(crypto.getRandomValues(new Uint8Array(32)));   // só vai no e-mail de quem assina; a planilha guarda o SHA-256 dele
        const aes = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt"]);
        const iv = crypto.getRandomValues(new Uint8Array(12));
        const dados = enc.encode(JSON.stringify({ email, token, freq: $("#inf-freq").value, locais, politicos, rotulos: [...escolhidos.values()] }));
        const cifrado = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, aes, dados);
        const rsa = await crypto.subtle.importKey("jwk", chavePublica, { name: "RSA-OAEP", hash: "SHA-256" }, false, ["encrypt"]);
        const k = await crypto.subtle.encrypt({ name: "RSA-OAEP" }, rsa, await crypto.subtle.exportKey("raw", aes));
        const h = hex(await crypto.subtle.digest("SHA-256", enc.encode(token)));
        /* text/plain evita o pedido de verificação do navegador; o Apps Script não responde com CORS, então a resposta é opaca */
        await fetch(URL_ASSINATURAS, { method: "POST", mode: "no-cors", headers: { "Content-Type": "text/plain;charset=utf-8" },
          body: JSON.stringify({ v: 1, h, k: b64(k), iv: b64(iv), c: b64(cifrado) }) });
        msg.textContent = "Pedido enviado. Você receberá um e-mail de confirmação em até 15 minutos; se não chegar, olhe o spam.";
      } catch {
        msg.textContent = "Não foi possível enviar agora. Tente de novo em instantes.";
      }
      $("#inf-enviar").disabled = false;
    });
  }
}
