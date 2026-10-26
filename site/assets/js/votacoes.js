/* Lista de votações e detalhe de uma votação. */
import { $, esc, data, dataHora, semAcento, param, carregar } from "./util.js";
import { VOTOS, selo, listaPaginada, erro, semDadosLocais, filtrosNaUrl, botaoVoltar } from "./comum.js";
import { CAMARA_API, fontes, SENADO_API, linkMateriaSenado } from "./apis.js";

/* ---------- lista de votações ---------- */
export function barraPlacar(placar) {
  const total = Object.values(placar).reduce((a, b) => a + b, 0) || 1;
  return `<div class="placar" role="img" aria-label="${Object.entries(placar).map(([k, n]) => `${VOTOS[k]?.rotulo || k}: ${n}`).join(", ")}">
    ${["sim", "nao", "abstencao", "obstrucao", "secreto", "art17", "outro"].filter((k) => placar[k]).map((k) => `<i style="width:${(placar[k] / total) * 100}%;background:${VOTOS[k].cor}"></i>`).join("")}</div>`;
}

export async function paginaVotacoes() {
  const alvo = $("#resultado");
  let lista;
  try { lista = await carregar("dados/votacoes.json"); } catch (e) { return erro(alvo, e); }
  const render = (v) => `<li>
    <span class="quando">${data(v.data)}${v.proposicao ? `, <b>${esc(v.proposicao)}</b>` : ""}</span>
    <span class="quando">${v.aprovada === 1 ? "Aprovada" : v.aprovada === 0 ? "Rejeitada" : ""}</span>
    <a class="texto" href="votacao.html?id=${encodeURIComponent(v.id)}">${esc(v.descricao || "Votação sem descrição")}</a>
    <span class="texto">${barraPlacar(v.placar)}<span class="quando">Sim ${v.placar.sim || 0}, Não ${v.placar.nao || 0}</span></span></li>`;
  const desenhar = () => {
    const b = semAcento($("#busca").value.trim());
    const f = lista.filter((v) => !b || semAcento(`${v.descricao} ${v.proposicao}`).includes(b));
    $("#contagem").textContent = `${f.length} votações nominais no Plenário`;
    listaPaginada(alvo, f, render, 20, "Nenhuma votação encontrada com essa busca.");
  };
  filtrosNaUrl(["busca"], desenhar);
}

/* ---------- detalhe de uma votação ---------- */
export async function paginaVotacao() {
  const alvo = $("#conteudo");
  const senado = param("casa") === "senado";
  let v;
  try { v = await carregar(`dados/${senado ? "votacao_senado" : "votacao"}/${encodeURIComponent(param("id"))}.json`); } catch (e) { return semDadosLocais(alvo, e, senado ? null : `${CAMARA_API}/votacoes/${encodeURIComponent(param("id"))}`); }
  const quem = senado ? "senador" : "deputado";
  const linkQuem = (d) => senado ? (d.anterior ? "" : `politico.html?f=senado&i=${encodeURIComponent(d.id)}`) : `deputado.html?id=${d.id}`;
  document.title = `${v.proposicao || "Votação"} em ${data(v.data)} | Minha Bancada`;
  v.votos.sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
  const partidos = Object.entries(v.porPartido).sort((a, b) => Object.values(b[1]).reduce((x, y) => x + y, 0) - Object.values(a[1]).reduce((x, y) => x + y, 0));

  alvo.innerHTML = `
    ${botaoVoltar("Votações", "votacoes.html")}
    <section class="abertura">
      <p>${v.dataHora ? esc(dataHora(v.dataHora, true)) : `${data(v.data, true)}${v.hora ? `, às ${esc(v.hora)}` : ""}`}, no Plenário${senado ? " do Senado" : ""}${v.orgao && v.orgao !== "PLEN" ? ` (órgão ${esc(v.orgao)})` : v.orgao ? " (PLEN)" : ""}</p>
      <h1 style="max-width:none;font-size:clamp(28px,4.5vw,44px)">${esc(v.proposicao || "Votação no Plenário")}</h1>
      ${v.propId ? `<p><a href="proposicao.html?k=${senado ? "s" : "c"}-${encodeURIComponent(v.propId)}">Ver autores e outras votações desta proposição</a></p>` : ""}
      ${v.ementa ? `<p class="texto-longo"><b>Sobre o quê:</b> ${esc(v.ementa)}</p>` : ""}
      <p class="texto-longo">${esc(v.descricao)}</p>
    </section>
    <section class="painel">
      <div class="painel-titulo"><h2>Placar</h2><p>${v.aprovada === 1 ? "Aprovada" : v.aprovada === 0 ? "Rejeitada" : ""}</p></div>
      ${v.secreta ? `<p class="aviso">Votação secreta: o Senado informa que cada senador votou, mas não como. O voto individual não é público.</p>` : ""}
      ${barraPlacar(v.placar)}
      <div class="numeros">
        <div><b>${v.placar.sim || 0}</b><span>Sim</span></div>
        <div><b>${v.placar.nao || 0}</b><span>Não</span></div>
        <div><b>${v.placar.abstencao || 0}</b><span>Abstenção</span></div>
        <div><b>${v.placar.obstrucao || 0}</b><span>Obstrução</span></div>
        ${senado ? `<div><b>${v.ausentes || 0}</b><span>Sem voto registrado</span></div>` : ""}
      </div>
    </section>
    <h2>Por partido</h2>
    <div class="rolagem"><table class="tabela"><thead><tr><th>Partido</th><th>Sim</th><th>Não</th><th>Abst.</th><th>Obstr.</th></tr></thead><tbody>
      ${partidos.map(([p, c]) => `<tr><td><b>${esc(p)}</b></td><td>${c.sim || 0}</td><td>${c.nao || 0}</td><td>${c.abstencao || 0}</td><td>${c.obstrucao || 0}</td></tr>`).join("")}
    </tbody></table></div>
    <h2>Voto de cada ${quem}</h2>
    <div class="filtros" style="grid-template-columns:2fr 1fr"><label class="campo">Buscar ${quem}<input id="busca-dep" type="search" placeholder="Nome, partido ou estado"></label>
      <label class="campo">Voto<select id="filtro-voto"><option value="">Todos</option>${["sim", "nao", "abstencao", "obstrucao", ...(senado ? ["art17", "secreto", "ausente"] : [])].map((k) => `<option value="${k}">${VOTOS[k].rotulo}</option>`).join("")}</select></label></div>
    <div id="lista-dep"></div>
    ${senado ? fontes([["Votos de cada senador (API do Senado)", `${SENADO_API}/votacao?dataInicio=${v.data.replaceAll("-", "")}&dataFim=${v.data.replaceAll("-", "")}`], v.propId ? ["Tramitação da matéria", linkMateriaSenado(v.propId)] : null]) : ""}`;

  const render = (d) => `<li>${linkQuem(d) ? `<a href="${esc(linkQuem(d))}">${esc(d.nome)}</a>` : esc(d.nome)}${selo(d.voto)}<span class="quando texto">${esc(d.partido)}${d.uf ? `/${esc(d.uf)}` : ""}${d.motivo ? ` · ${esc(d.motivo)}` : ""}</span></li>`;
  const desenhar = () => {
    const b = semAcento($("#busca-dep").value.trim()), f = $("#filtro-voto").value;
    listaPaginada($("#lista-dep"), v.votos.filter((d) => (!f || d.voto === f) && (!b || semAcento(`${d.nome} ${d.partido} ${d.uf}`).includes(b))), render, 50, `Nenhum ${quem} com esse filtro.`);
  };
  $("#busca-dep").addEventListener("input", desenhar);
  $("#filtro-voto").addEventListener("input", desenhar);
  desenhar();
}
