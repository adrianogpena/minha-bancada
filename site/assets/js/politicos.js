/* Página inicial: todos os políticos. */
import { $, esc, semAcento, carregar, carregarMalha } from "./util.js";
import { abas, erro } from "./comum.js";
import { UFS, UF_COD, COD_UF, MALHAS } from "./apis.js";
import { GRUPOS, linhaPolitico, svgMapa, desenharEleitorado, desenharPerfilCasas } from "./mapa.js";

export async function paginaPoliticos() {
  const alvo = $("#resultado"), mapa = $("#mapa"), dica = $("#dica"), trilha = $("#trilha");
  const q = new URLSearchParams(location.search);
  const selUf = $("#uf"), selMun = $("#municipio"), busca = $("#busca");
  selUf.insertAdjacentHTML("beforeend", Object.entries(UFS).map(([k, v]) => `<option value="${k}">${v}</option>`).join(""));

  let br = [];
  try { br = await carregar("dados/indice/BR.json"); } catch (e) { return erro(alvo, e); }
  const cache = {}, geos = {};
  let lista = [], uf = null, mun = "", tseDeIbge = {}, nomes = new Map(), versao = 0;
  carregar("dados/municipios_ibge.json").then((m) => {
    tseDeIbge = Object.fromEntries(Object.entries(m).map(([t, i]) => [i, t]));
    if (uf) desenharMapa();
  }).catch(() => {});

  let periodo = q.get("periodo") === "2026" ? "2026" : "agora";
  abas($("#periodo"), [{ valor: "agora", rotulo: "No cargo agora" }, { valor: "2026", rotulo: "Eleitos em 2026" }], (v) => { periodo = v; desenhar(); });
  $("#periodo").querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.v === periodo));

  const geo = async (local, remoto) => (geos[local] ||= await carregarMalha(local, remoto));

  function desenharTrilha() {
    const partes = [uf ? `<button type="button" data-ir="br">Brasil</button>` : `<b>Brasil</b>`];
    if (uf) partes.push(mun ? `<button type="button" data-ir="uf">${esc(UFS[uf])}</button>` : `<b>${esc(UFS[uf])}</b>`);
    if (mun) partes.push(`<b>${esc(nomes.get(mun) || "")}</b>`);
    trilha.innerHTML = partes.join(`<span aria-hidden="true">›</span>`);
  }

  async function desenharMapa() {
    const minha = ++versao;
    try {
      // o DF não tem municípios (nem eleição municipal): desenha as regiões administrativas, só para olhar
      const semMunicipios = uf === "DF";
      const fc = semMunicipios ? await geo("geo/df_ras.json", "geo/df_ras.json") : uf
        ? await geo(`geo/uf_${COD_UF[uf]}.json`, `${MALHAS}/estados/${COD_UF[uf]}?formato=application/vnd.geo+json&intrarregiao=municipio&qualidade=minima`)
        : await geo("geo/br.json", `${MALHAS}/paises/BR?formato=application/vnd.geo+json&intrarregiao=UF&qualidade=minima`);
      if (minha !== versao) return;
      mapa.innerHTML = svgMapa(fc, semMunicipios ? (f) => f.properties.codigo : uf ? (f) => tseDeIbge[f.properties.codarea] || "" : (f) => UF_COD[f.properties.codarea] || "");
      mapa.querySelectorAll("path").forEach((p) => {
        const nome = uf ? nomes.get(p.dataset.id) : UFS[p.dataset.id];
        if (semMunicipios) {
          const ra = fc.features.find((f) => f.properties.codigo === p.dataset.id).properties.nome;
          p.classList.add("unico"); p.removeAttribute("tabindex"); p.removeAttribute("role"); p.setAttribute("aria-label", ra);
          p.insertAdjacentHTML("afterbegin", `<title>${esc(ra)}</title>`);
          return;
        }
        if (!nome) { p.classList.add("fundo"); p.removeAttribute("tabindex"); p.removeAttribute("role"); return; }
        p.setAttribute("aria-label", nome);
        p.insertAdjacentHTML("afterbegin", `<title>${esc(nome)}</title>`);
        if (uf && p.dataset.id === mun) p.classList.add("escolhido");
      });
      dica.textContent = semMunicipios ? "O Distrito Federal não tem municípios nem prefeitos: o governo e a Câmara Legislativa cuidam de tudo. As divisões são as regiões administrativas." : uf ? "Clique em um município para ver os políticos dele." : "Clique em um estado para ver os políticos dele.";
    } catch (e) {
      if (minha === versao) mapa.innerHTML = `<p class="vazio">Não foi possível carregar o mapa. Use os campos ao lado.</p>`;
    }
  }

  async function irPara(novoUf, novoMun = "") {
    if (novoUf !== uf || (novoUf && !lista.length)) {
      uf = novoUf; mun = "";
      selUf.value = uf;
      selMun.innerHTML = `<option value="">Todos os municípios</option>`;
      selMun.disabled = !uf;
      nomes = new Map();
      lista = [];
      if (uf) {
        alvo.innerHTML = `<p class="vazio">Carregando ${esc(UFS[uf])}…</p>`;
        try { cache[uf] ||= await carregar(`dados/indice/${uf}.json`); } catch (e) { return erro(alvo, e); }
        lista = cache[uf];
        lista.forEach((x) => x.codigoMunicipio && nomes.set(x.codigoMunicipio, x.municipio));
        selMun.disabled = !nomes.size;
        selMun.insertAdjacentHTML("beforeend", [...nomes].sort((a, b) => a[1].localeCompare(b[1], "pt-BR"))
          .map(([g, m]) => `<option value="${esc(g)}">${esc(m)}</option>`).join(""));
      }
      mapa.innerHTML = `<p class="vazio">Carregando mapa…</p>`;
      desenharMapa();
    }
    mun = nomes.has(novoMun) ? novoMun : "";
    selMun.value = mun;
    mapa.querySelectorAll("path").forEach((p) => p.classList.toggle("escolhido", !!mun && p.dataset.id === mun));
    desenharTrilha();
    desenhar();
  }

  function desenhar() {
    const termo = semAcento(busca.value.trim());
    const nova = new URLSearchParams();
    if (uf) nova.set("uf", uf);
    if (mun) nova.set("municipio", mun);
    if (periodo === "2026") nova.set("periodo", "2026");
    history.replaceState(null, "", nova.toString() ? "?" + nova : location.pathname);

    const doPeriodo = (x) => (periodo === "agora" ? x.estado === "atual" : x.estado !== "atual");
    // no Brasil, o BR.json traz a presidência e os cargos federais; no estado, os cargos vêm do arquivo do estado
    const base = uf ? lista : br;
    const todos = base.filter(doPeriodo).filter((x) => !termo || semAcento(`${x.nome} ${x.partido} ${x.municipio || ""} ${x.uf || ""}`).includes(termo));
    const grupos = uf && mun ? [...GRUPOS].sort((a, b) => !!b.municipal - !!a.municipal) : GRUPOS;
    let html = "", total = 0;
    for (const g of GRUPOS) g._itens = null;
    for (const g of grupos) {
      let itens = todos.filter((x) => g.ordens.includes(x.ordemCargo));
      if (g.municipal) {
        if (!uf) continue;
        if (mun) itens = itens.filter((x) => x.codigoMunicipio === mun);
        else if (!termo) {
          if (itens.length) html += `<section class="grupo"><h2>${g.titulo}</h2><p class="vazio">Clique em um município no mapa para ver ${g.ordens.includes(10) ? "os vereadores" : "o prefeito e o vice"}, ou busque pelo nome.</p></section>`;
          continue;
        }
      }
      if (!itens.length) continue;
      total += itens.length;
      const titulo = typeof g.titulo === "function" ? g.titulo(uf) : g.titulo;
      html += `<section class="grupo"><h2>${titulo} <small class="sub">${itens.length}</small></h2><ul class="lista" data-grupo="${g.ordens[0]}"></ul></section>`;
      g._itens = itens;
    }
    if (periodo === "2026" && !total) html += `<p class="vazio">Nenhum eleito em 2026 encontrado com esses filtros.</p>`;
    alvo.innerHTML = html || `<p class="vazio">Nada encontrado. Tente outro nome ou limpe a busca.</p>`;
    for (const g of GRUPOS) {
      const ul = g._itens && alvo.querySelector(`ul[data-grupo="${g.ordens[0]}"]`);
      if (!ul) continue;
      // listas longas (Câmara, vereadores de uma capital) crescem aos poucos
      const itens = g._itens; let n = 0;
      const mais = () => {
        ul.insertAdjacentHTML("beforeend", itens.slice(n, n + 30).map(linhaPolitico).join(""));
        n += 30;
        botao.hidden = n >= itens.length;
        botao.textContent = `Mostrar mais (${itens.length - n} restantes)`;
      };
      const botao = document.createElement("button");
      botao.className = "mais"; botao.addEventListener("click", mais);
      ul.after(botao); mais();
    }
    const onde = mun ? `${nomes.get(mun)}, ${UFS[uf]}` : uf ? UFS[uf] : "Brasil";
    desenharEleitorado($("#eleitorado"), uf, mun, mun ? `${nomes.get(mun)}, ${uf}` : uf ? UFS[uf] : "");
    desenharPerfilCasas($("#casas"), uf, mun, mun ? `${nomes.get(mun)}, ${uf}` : uf ? UFS[uf] : "");
    $("#contagem").textContent = `${total} políticos ${periodo === "agora" ? "no cargo" : "eleitos ou no 2º turno em 2026"}: ${onde}`;
  }

  const clicar = (p) => { if (p && !p.classList.contains("fundo") && !p.classList.contains("unico")) irPara(uf || p.dataset.id, uf ? p.dataset.id : ""); };
  mapa.addEventListener("click", (e) => clicar(e.target.closest("path")));
  mapa.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); clicar(e.target.closest("path")); } });
  const nomeSob = (e) => {
    const p = e.target.closest?.("path");
    if (!p || p.classList.contains("fundo")) return;
    dica.textContent = p.classList.contains("unico") ? p.getAttribute("aria-label") : uf ? nomes.get(p.dataset.id) : UFS[p.dataset.id];
  };
  mapa.addEventListener("mouseover", nomeSob);
  mapa.addEventListener("focusin", nomeSob);
  trilha.addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) irPara(b.dataset.ir === "br" ? "" : uf); });
  selUf.addEventListener("input", () => irPara(selUf.value));
  selMun.addEventListener("input", () => irPara(uf, selMun.value));
  busca.addEventListener("input", desenhar);
  const inicial = q.get("uf");
  irPara(inicial && UFS[inicial] ? inicial : "", q.get("municipio") || "");
}
