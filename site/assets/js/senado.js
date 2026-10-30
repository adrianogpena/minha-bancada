/* Página do Senado: lista de senadores em exercício. */
import { $, esc, reais, pct, semAcento, carregar } from "./util.js";
import { foto, erro } from "./comum.js";

export async function paginaSenado() {
  const alvo = $("#resultado");
  let sens;
  try { sens = await carregar("dados/senado.json"); } catch (e) { return erro(alvo, e); }

  const ufs = [...new Set(sens.map((s) => s.uf))].sort();
  const partidos = [...new Set(sens.map((s) => s.partido))].sort();
  $("#uf").insertAdjacentHTML("beforeend", ufs.map((u) => `<option>${esc(u)}</option>`).join(""));
  $("#partido").insertAdjacentHTML("beforeend", partidos.map((p) => `<option>${esc(p)}</option>`).join(""));

  const q = new URLSearchParams(location.search);
  for (const k of ["busca", "uf", "partido", "ordem"]) if (q.get(k)) $("#" + k).value = q.get(k);

  const ordenadores = {
    nome: (a, b) => a.nome.localeCompare(b.nome, "pt-BR"),
    presenca: (a, b) => b.compareceu / (b.votacoes || 1) - a.compareceu / (a.votacoes || 1),
    proposicoes: (a, b) => b.proposicoes - a.proposicoes,
    proprias: (a, b) => b.proprias - a.proprias,
    gasto: (a, b) => (b.gasto || 0) - (a.gasto || 0),
  };

  function desenhar() {
    const busca = semAcento($("#busca").value.trim());
    const uf = $("#uf").value, partido = $("#partido").value, ordem = $("#ordem").value;
    const filtrados = sens
      .filter((s) => (!uf || s.uf === uf) && (!partido || s.partido === partido) && (!busca || semAcento(s.nome).includes(busca)))
      .sort(ordenadores[ordem]);
    const novo = new URLSearchParams();
    if (busca) novo.set("busca", $("#busca").value.trim());
    if (uf) novo.set("uf", uf);
    if (partido) novo.set("partido", partido);
    if (ordem !== "nome") novo.set("ordem", ordem);
    history.replaceState(null, "", novo.toString() ? "?" + novo : location.pathname);

    $("#contagem").textContent = `${filtrados.length} de ${sens.length} senadores em exercício`;
    if (!filtrados.length) { alvo.innerHTML = `<p class="vazio">Nenhum senador com esses filtros. Tente limpar a busca ou escolher outro estado.</p>`; return; }
    alvo.innerHTML = `
      <div class="cabecalho-lista cabecalho-sen" aria-hidden="true"><span></span><span>Senador</span><span>Presença</span><span class="so-largo">Proposições</span><span class="so-largo">Iniciativas próprias</span><span class="so-largo">Mandato até</span><span class="so-largo">Gastos no ano</span></div>
      <ul class="lista">${filtrados.map((s) => `
        <li><a class="linha-dep linha-sen" href="politico.html?f=senado&i=${encodeURIComponent(s.id)}">
          ${foto(s)}
          <span><span class="nome">${esc(s.nome)}</span><br><span class="sigla">${esc(s.partido || "")}/${esc(s.uf)}${s.participacao && s.participacao !== "Titular" ? `, ${esc(s.participacao.toLowerCase())}` : ""}</span></span>
          <span class="metrica"><b>${s.votacoes ? pct(s.compareceu, s.votacoes) : "—"}</b><span>das votações</span></span>
          <span class="metrica so-largo"><b>${s.proposicoes}</b><span>apresentadas</span></span>
          <span class="metrica so-largo" title="Projetos em que ${esc(s.nome)} é o primeiro a assinar"><b>${s.proprias}</b><span>como autor principal</span></span>
          <span class="metrica so-largo"><b>${s.fimMandato ? esc(s.fimMandato.slice(0, 4)) : "—"}</b><span>fim do mandato</span></span>
          <span class="metrica so-largo"><b>${s.gasto == null ? "—" : reais(s.gasto)}</b><span>cota parlamentar</span></span>
        </a></li>`).join("")}</ul>`;
  }
  ["busca", "uf", "partido", "ordem"].forEach((id) => $("#" + id).addEventListener("input", desenhar));
  desenhar();
}
