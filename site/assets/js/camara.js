/* Página da Câmara: lista de deputados federais. */
import { $, esc, reais, pct, semAcento, carregar } from "./util.js";
import { foto, erro } from "./comum.js";

/* ---------- Câmara: lista de deputados federais ---------- */
export async function paginaCamara() {
  const alvo = $("#resultado");
  let deps;
  try { deps = await carregar("dados/deputados.json"); } catch (e) { return erro(alvo, e); }

  const ufs = [...new Set(deps.map((d) => d.uf))].sort();
  const partidos = [...new Set(deps.map((d) => d.partido))].sort();
  $("#uf").insertAdjacentHTML("beforeend", ufs.map((u) => `<option>${esc(u)}</option>`).join(""));
  $("#partido").insertAdjacentHTML("beforeend", partidos.map((p) => `<option>${esc(p)}</option>`).join(""));

  // lembra os filtros na URL, para poder compartilhar o link
  const q = new URLSearchParams(location.search);
  for (const k of ["busca", "uf", "partido", "ordem"]) if (q.get(k)) $("#" + k).value = q.get(k);

  const taxa = (x) => (x ? x.seguiu / x.total : -1);
  const ordenadores = {
    nome: (a, b) => a.nome.localeCompare(b.nome, "pt-BR"),
    participacao: (a, b) => b.votou / (b.votacoes || 1) - a.votou / (a.votacoes || 1),
    proposicoes: (a, b) => b.proposicoes - a.proposicoes,
    gasto: (a, b) => b.gasto - a.gasto,
    proprias: (a, b) => b.proprias - a.proprias || b.aprovadasProprias - a.aprovadasProprias,
    aprovadas: (a, b) => b.aprovadasProprias - a.aprovadasProprias || b.proprias - a.proprias,
    suprapartidarios: (a, b) => b.suprapartidarios - a.suprapartidarios,
    fidelidade: (a, b) => taxa(b.fidelidade) - taxa(a.fidelidade),
    governismo: (a, b) => taxa(b.governismo) - taxa(a.governismo),
  };

  function desenhar() {
    const busca = semAcento($("#busca").value.trim());
    const uf = $("#uf").value, partido = $("#partido").value, ordem = $("#ordem").value;
    const filtrados = deps
      .filter((d) => (!uf || d.uf === uf) && (!partido || d.partido === partido) && (!busca || semAcento(d.nome).includes(busca)))
      .sort(ordenadores[ordem]);
    const novo = new URLSearchParams();
    if (busca) novo.set("busca", $("#busca").value.trim());
    if (uf) novo.set("uf", uf);
    if (partido) novo.set("partido", partido);
    if (ordem !== "nome") novo.set("ordem", ordem);
    history.replaceState(null, "", novo.toString() ? "?" + novo : location.pathname);

    $("#contagem").textContent = `${filtrados.length} de ${deps.length} deputados em exercício`;
    if (!filtrados.length) { alvo.innerHTML = `<p class="vazio">Nenhum deputado com esses filtros. Tente limpar a busca ou escolher outro estado.</p>`; return; }
    alvo.innerHTML = `
      <div class="cabecalho-lista" aria-hidden="true"><span></span><span>Deputado</span><span>Votou</span><span class="so-largo">Proposições</span><span class="so-largo">Iniciativas próprias</span><span class="so-largo">Fiel ao partido</span><span class="so-largo">Pró-governo</span><span class="so-largo">Gastos no ano</span></div>
      <ul class="lista">${filtrados.map((d) => `
        <li><a class="linha-dep" href="deputado.html?id=${d.id}">
          ${foto(d)}
          <span><span class="nome">${esc(d.nome)}</span><br><span class="sigla">${esc(d.partido)}/${esc(d.uf)}</span></span>
          <span class="metrica"><b>${pct(d.votou, d.votacoes)}</b><span>das votações</span></span>
          <span class="metrica so-largo"><b>${d.proposicoes}</b><span>apresentadas</span></span>
          <span class="metrica so-largo" title="Projetos em que ${esc(d.nome)} é o primeiro a assinar, entre os ${d.autoriaColetada} com autoria já coletada"><b>${d.proprias}</b><span>${d.aprovadasProprias} aprovados</span></span>
          <span class="metrica so-largo" title="Votações em que votou como o partido orientou, entre as que o partido orientou Sim, Não ou Obstrução"><b>${d.fidelidade ? pct(d.fidelidade.seguiu, d.fidelidade.total) : "—"}</b><span>${d.fidelidade ? `de ${d.fidelidade.total} votações` : "sem orientação"}</span></span>
          <span class="metrica so-largo" title="Votações em que votou como o Governo orientou, entre as que o Governo orientou Sim, Não ou Obstrução"><b>${d.governismo ? pct(d.governismo.seguiu, d.governismo.total) : "—"}</b><span>${d.governismo ? `de ${d.governismo.total} votações` : "sem orientação"}</span></span>
          <span class="metrica so-largo"><b>${reais(d.gasto)}</b><span>cota parlamentar</span></span>
        </a></li>`).join("")}</ul>`;
  }
  ["busca", "uf", "partido", "ordem"].forEach((id) => $("#" + id).addEventListener("input", desenhar));
  desenhar();
}
