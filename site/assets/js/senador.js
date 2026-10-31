/* Senador: presença, recursos e abas. */
import { esc, reais, reaisCentavos, pct, data, carregar, numeroBr, urlSegura } from "./util.js";
import { itemFicha, selosPar } from "./comum.js";
import { TIPOS_PROJETO, fontes, UFS, SENADO_API, SENADO_ADM_API, linkMateriaSenado, temResultado } from "./apis.js";
import { painelGastos } from "./deputado.js";
import { montarParlamentar, painelCoautoria } from "./parlamentar.js";
import { avisoLicenca } from "./ministros.js";
import { painelEleicaoDe } from "./eleicao.js";
import { carregarEmendas, painelEmendas } from "./emendas.js";

/* Comparecimento do senador às votações nominais (gerar.py: categoria_presenca). */
function painelPresenca(pr) {
  const faltas = [pr.naoCompareceu && `não compareceu a ${pr.naoCompareceu}`, pr.licenca && `${pr.licenca} em licença`,
    pr.missao && `${pr.missao} em missão oficial ou atividade parlamentar`, pr.outros && `${pr.outros} por outros motivos`].filter(Boolean);
  return `<h2>Comparecimento às votações</h2>
    <p>Compareceu a <b>${numeroBr(pr.compareceu || 0)}</b> de ${numeroBr(pr.votacoes)} votações nominais (<b>${pct(pr.compareceu || 0, pr.votacoes)}</b>), contando como presença quem votou ou registrou presença sem votar.
    ${faltas.length ? `Nas demais: ${faltas.join("; ")}.` : "Não faltou a nenhuma."} Fonte: <a href="${SENADO_API}/votacao" rel="noopener">votações nominais do Senado (Dados Abertos)</a>.</p>`;
}

/* Recursos e benefícios do senador (coletar.py: coletar_recursos_senado). */
function painelRecursos(rec) {
  const selos = (rec.beneficios || []).length
    ? selosPar(rec.beneficios.map(([b, u]) => [b, u === "Utilizou" ? "usa" : "não usa"]), true) : "";
  const pessoal = (rec.pessoal || []).filter(([, n]) => n);
  return `<h2>Recursos e benefícios em ${rec.ano}</h2>
    ${selos}
    ${pessoal.length ? `<p>Pessoal: ${pessoal.map(([l, n]) => `<b>${numeroBr(n)}</b> no ${esc(l.toLowerCase().replace("escritório(s) de apoio", "escritório de apoio"))}`).join("; ")}.</p>` : ""}
    ${rec.foraCota?.length ? `<h3>Gastos fora da cota: ${reaisCentavos(rec.totalForaCota)}</h3>
      <div class="rolagem"><table class="tabela"><thead><tr><th>Recurso</th><th>Valor</th></tr></thead><tbody>
      ${rec.foraCota.map(([r, v]) => `<tr><td>${esc(r)}</td><td>${reais(v)}</td></tr>`).join("")}</tbody></table></div>
      <p class="vazio">Diárias, correios e material pagos pelo Senado, que não entram na cota (CEAPS).</p>` : ""}
    ${rec.escritorios?.length ? `<h3>Escritório${rec.escritorios.length > 1 ? "s" : ""} de apoio no estado</h3>
      <ul>${rec.escritorios.map((e) => `<li>${esc(e.endereco || e.nome || "")}${e.telefone ? ` · ${esc(e.telefone)}` : ""}</li>`).join("")}</ul>` : ""}`;
}

/* Aposentadoria parlamentar de ex-senador (apis.js: carregarAposentadoria). */
export function painelAposentadoria(a) {
  if (!a) return "";
  const rotulo = a.tipo === "EX-SENADOR IPC" ? "Instituto de Previdência dos Congressistas (IPC)" : a.tipo === "EX-SENADOR PSSC" ? "Plano de Seguridade Social dos Congressistas (PSSC)" : a.tipo;
  return `<h2>Aposentadoria parlamentar</h2>
    <p>Recebe aposentadoria de ex-senador pelo <b>${esc(rotulo)}</b>${a.inicio ? ` desde ${data(a.inicio, true)}` : ""}${a.valor ? `: <b>${reaisCentavos(a.valor)}</b> por mês` : ""}.
    A fonte traz só o nome, e a ligação a esta pessoa é pelo nome completo.</p>
    ${fontes([["Aposentados do Senado", `${SENADO_ADM_API}/senadores/aposentados`]])}`;
}

/* Comissões e mandatos do senador (coletar.py: coletar_ficha_senado). */
function painelComissoesMandatos(sen, id) {
  const comissoes = sen.comissoes || [], mandatos = sen.mandatos || [];
  const periodo = (a, b) => `${a ? `desde ${data(a)}` : ""}${b ? ` até ${data(b)}` : ""}`;
  const api = `${SENADO_API}/senador/${encodeURIComponent(id)}`;
  return `<h2>Comissões</h2>
    ${comissoes.length ? `<ul class="lista-simples">${comissoes.map((c) => `<li><b>${esc(c.sigla)}</b> ${esc(c.nome)}<br><span class="quando">${esc(c.cargo || "Membro")}${c.casa ? ` · ${esc(c.casa)}` : ""}, ${periodo(c.inicio, c.fim)}</span></li>`).join("")}</ul>`
      : `<p class="vazio">Nenhuma participação registrada no mandato atual.</p>`}
    ${mandatos.length ? `<h2>Mandatos no Senado</h2>
      <ul class="lista-simples">${mandatos.map((m) => `<li>${m.inicio ? data(m.inicio) : "?"} a ${m.fim ? data(m.fim) : "?"}, ${esc(m.uf || "")}${m.cargo ? ` (${esc(m.cargo.toLowerCase())})` : ""}
        ${(m.partidos || []).length ? `<br><span class="quando">Partidos: ${m.partidos.map((x) => `${esc(x.sigla)}${x.filiacao ? ` desde ${data(x.filiacao)}` : ""}${x.desfiliacao ? ` até ${data(x.desfiliacao)}` : ""}`).join(" · ")}</span>` : ""}</li>`).join("")}</ul>` : ""}
    ${fontes([["Comissões do senador (Dados Abertos do Senado)", `${api}/comissoes`], ["Mandatos do senador (Dados Abertos do Senado)", `${api}/mandatos`]])}`;
}

/* Presença por ano, com a mediana dos senadores (gerar.py: gerar_senadores). */
function painelPresencaAno(anos) {
  if (!anos?.length) return "";
  return `
    <section class="painel" aria-labelledby="t-presenca-ano">
      <div class="painel-titulo">
        <h2 id="t-presenca-ano">Presença por ano</h2>
        <p>Comparecimento às votações nominais do Plenário em cada ano, contando como presença quem votou ou registrou presença sem votar. A mediana é a dos senadores em exercício: metade compareceu a mais, metade a menos. O ano corrente ainda está em andamento.</p>
      </div>
      <div class="rolagem"><table class="tabela"><thead><tr><th>Ano</th><th>Votações nominais</th><th>Compareceu</th><th>Mediana dos senadores</th></tr></thead><tbody>
        ${anos.map((a) => `<tr><td>${a.ano}</td><td>${numeroBr(a.votacoes)}</td><td><b>${numeroBr(a.compareceu || 0)}</b> (${pct(a.compareceu || 0, a.votacoes)})</td><td>${pct(Math.round(a.mediana * 1000), 1000)}</td></tr>`).join("")}
      </tbody></table></div>
      ${fontes([["Votações nominais do Senado (Dados Abertos)", `${SENADO_API}/votacao`]])}
    </section>`;
}

/* Lideranças atuais, cargos em comissões e licenças (coletar.py: coletar_atividade_senado). */
function painelCargos(sen, id) {
  const lid = sen.liderancas || [], cargos = sen.cargos || [], lic = sen.licencas || [];
  if (!lid.length && !cargos.length && !lic.length) return "";
  const api = `${SENADO_API}/senador/${encodeURIComponent(id)}`;
  const periodo = (a, b) => `${a ? `desde ${data(a)}` : ""}${b ? ` até ${data(b)}` : ""}`;
  return `<h2>Lideranças e cargos</h2>
    ${lid.length ? `<h3>Lideranças em exercício</h3><ul class="lista-simples">${lid.map((l) => `<li><b>${esc(l.cargo || "Líder")}</b>${l.unidade ? `, ${esc(l.unidade)}` : ""}<br><span class="quando">${l.partido ? `${esc(l.partido)} · ` : ""}${periodo(l.desde)}</span></li>`).join("")}</ul>` : ""}
    ${cargos.length ? `<h3>Presidência, vice-presidência e relatoria de comissões</h3><ul class="lista-simples">${cargos.map((c) => `<li><b>${esc((c.cargo || "").toLowerCase())}</b> · ${esc(c.sigla)}${c.nome && c.nome !== c.sigla ? ` (${esc(c.nome)})` : ""}<br><span class="quando">${periodo(c.inicio, c.fim) || "sem data"}${c.fim ? "" : ", em exercício"}</span></li>`).join("")}</ul>` : ""}
    ${lic.length ? `<h3>Licenças e afastamentos <small class="sub">(${lic.length} desde 2023)</small></h3><details><summary>Ver as ${lic.length} licenças</summary><ul class="lista-simples">${lic.map((l) => `<li>${l.inicio ? data(l.inicio) : "?"}${l.fim && l.fim !== l.inicio ? ` a ${data(l.fim)}` : ""}<br><span class="quando">${esc(l.tipo || "Afastamento")}</span></li>`).join("")}</ul></details>` : ""}
    ${fontes([lid.length ? ["Lideranças do Senado", `${SENADO_API}/composicao/lideranca`] : null, ["Cargos do senador", `${api}/cargos`], ["Licenças do senador", `${api}/licencas`]])}`;
}

/* Pronunciamentos e apartes (coletar.py: discursos_senador). */
function painelDiscursos(d, id, nome) {
  if (!d) return "";
  const max = d.assuntos?.[0]?.[1] || 1;
  const api = `${SENADO_API}/senador/${encodeURIComponent(id)}`;
  return `<h2>Discursos e apartes</h2>
    <p>${esc(nome)} fez <b>${numeroBr(d.total)}</b> ${d.total === 1 ? "pronunciamento" : "pronunciamentos"} no Plenário desde 2023${d.apartes ? ` e <b>${numeroBr(d.apartes)}</b> ${d.apartes === 1 ? "aparte" : "apartes"}` : ""}.
    ${(d.porAno || []).length ? `Por ano: ${d.porAno.map(([a, n]) => `${a}: ${n}`).join(" · ")}.` : ""}</p>
    ${d.assuntos?.length ? `<h3>Assuntos mais indexados nos pronunciamentos</h3>
      <div class="barras">${d.assuntos.map(([t, n]) => `<div><div class="barra-rotulo"><span>${esc(t)}</span><b>${n}</b></div><div class="barra"><i style="width:${(n / max) * 100}%"></i></div></div>`).join("")}</div>
      <p class="quando">Termos que o Senado registra ao indexar cada pronunciamento; os que só descrevem o tipo de ato (como "alteração" ou "lei federal") ficam de fora. O Senado não classifica os projetos por tema, como a Câmara faz.</p>` : ""}
    ${d.recentes?.length ? `<h3>Pronunciamentos mais recentes</h3><ul class="lista-simples">${d.recentes.map((p) => `<li><span class="quando">${data(p.data)}${p.tipo ? ` · ${esc(p.tipo)}` : ""}</span><br>${esc(p.resumo || "Sem resumo")}${urlSegura(p.url) ? ` <a href="${esc(p.url)}" rel="noopener">texto completo</a>` : ""}</li>`).join("")}</ul>` : ""}
    ${fontes([["Pronunciamentos do senador", `${api}/discursos`], ["Apartes do senador", `${api}/apartes`]])}`;
}

/* Com quem o senador mais assina projetos (gerar.py: resumir_coautoria). */
function coautoriaSenador(c) {
  return painelCoautoria({
    c, quem: "Parlamentar",
    linhas: (c?.parceiros || []).map(([n, pt, uf, q]) => [esc(n), pt ? `${esc(pt)}${uf ? `/${esc(uf)}` : ""}` : "—", q]),
    nota: 'Só projetos (PL, PEC e afins) com mais de um autor e até 30 autores. Os parceiros vêm do campo de autoria do Senado, e "outro partido" compara com o partido atual do senador.',
    fonte: ["Autoria das matérias (Dados Abertos do Senado)", `${SENADO_API}/processo`],
  });
}

/* Relatorias na legislatura (coletar.py: relatorias_senador). */
function painelRelatorias(r, id, nome) {
  if (!r) return "";
  return `<h2>Relatorias <small class="sub">(${numeroBr(r.total)})</small></h2>
    <p>Matérias em que ${esc(nome)} foi designado relator desde 2023: <b>${numeroBr(r.total)}</b>, das quais <b>${numeroBr(r.tramitando)}</b> ainda tramitam.
    ${(r.porAno || []).length ? `Por ano: ${r.porAno.map(([a, n]) => `${a}: ${n}`).join(" · ")}.` : ""}
    ${(r.porColegiado || []).length ? `Onde mais relatou: ${r.porColegiado.map(([s, n]) => `${esc(s)} (${n})`).join(", ")}.` : ""}</p>
    <h3>As ${r.recentes.length} designações mais recentes</h3>
    <ul class="lista-simples">${r.recentes.map((x) => `<li><b>${esc(x.materia || "Matéria")}</b> <span class="quando">${esc(x.colegiado || "")}${x.tipo ? ` · ${esc(x.tipo.toLowerCase())}` : ""} · designado em ${data(x.desde)}${x.ate ? `, até ${data(x.ate)}` : ""}</span><br>${esc(x.ementa || "Sem ementa")}
      <a href="${esc(linkMateriaSenado(x.id))}" rel="noopener">tramitação</a></li>`).join("")}</ul>
    ${fontes([["Relatorias do senador (Dados Abertos do Senado)", `${SENADO_API}/processo/relatoria?codigoParlamentar=${encodeURIComponent(id)}`]])}`;
}

export async function montarSenador(alvo, p, nome, ficha) {
  let sen, lista;
  try { [sen, lista] = await Promise.all([carregar(`dados/senador/${encodeURIComponent(p.id)}.json`), carregar("dados/votacoes_senado.json")]); } catch { return false; }
  const emendas = await carregarEmendas(p.pessoa);
  const meus = new Map(sen.votos.map((v) => [v.id, v.voto]));
  const linhaDoTempo = lista.filter((v) => temResultado(v) && meus.has(v.id)).map((v) => ({ ...v, voto: meus.get(v.id) }));
  const situacao = p.fimMandato ? `Mandato até ${data(p.fimMandato, true)}.` : "";
  const apiVotacao = (v) => `${SENADO_API}/votacao?dataInicio=${v.data.replaceAll("-", "")}&dataFim=${v.data.replaceAll("-", "")}`;
  montarParlamentar(alvo, {
    nome, fichas: [`politico.html?f=senado&i=${p.id}`], foto: { nome, foto: p.foto }, antes: sen.ministro ? await avisoLicenca(sen.ministro, "senador") : "", painelEleicao: painelEleicaoDe(p, nome),
    subtitulo: `<span class="selo">${esc(p.partido || "")}/${esc(p.uf)}</span> ${esc(p.cargo)}${p.participacao && p.participacao !== "Titular" ? `, ${esc(p.participacao.toLowerCase())}` : ""}`,
    painelPerfil: `<p class="situacao">${esc(situacao)}</p>
      <h2>Ficha</h2>
      <dl class="ficha">${ficha.map(itemFicha).join("")}
        <dt>Onde atua</dt><dd>${esc(UFS[p.uf] || p.uf)}</dd>
        ${urlSegura(p.pagina) ? `<dt>Página oficial</dt><dd><a href="${esc(p.pagina)}" rel="noopener">Perfil no Senado Federal</a></dd>` : ""}
      </dl>
      ${sen.presenca ? painelPresenca(sen.presenca) : ""}
      ${sen.despesas ? painelGastos(sen.despesas, "A cota (CEAPS) reembolsa despesas do mandato, como passagens, aluguel de escritório e divulgação. Os valores são os reembolsados pelo Senado.")
        : `<p class="aviso">Os gastos da cota (CEAPS) não puderam ser carregados agora. Veja no <a href="https://www6g.senado.leg.br/transparencia/sen/${encodeURIComponent(p.id)}" rel="noopener">Portal da Transparência do Senado</a>.</p>`}
      ${sen.recursos ? painelRecursos(sen.recursos) : ""}
      ${painelEmendas(emendas)}
      ${painelAposentadoria(p.aposentadoria)}
      ${sen.comissoes || sen.mandatos ? painelComissoesMandatos(sen, p.id) : ""}
      ${painelCargos(sen, p.id)}
      ${painelDiscursos(sen.discursos, p.id, nome)}
      ${coautoriaSenador(sen.coautoria)}
      ${fontes([["Dados Abertos do Senado", `${SENADO_API}/senador/${encodeURIComponent(p.id)}`], sen.despesas ? ["Cota parlamentar (CEAPS)", `${SENADO_ADM_API}/senadores/despesas_ceaps/${sen.despesas.ano}`] : null, sen.recursos ? ["Recursos utilizados", `${SENADO_ADM_API}/senadores/${encodeURIComponent(p.id)}/recursos-utilizados?ano=${sen.recursos.ano}`] : null, sen.recursos?.escritorios ? ["Escritórios de apoio", `${SENADO_ADM_API}/senadores/escritorios-apoio`] : null, ["Portal da Transparência do Senado", `https://www6g.senado.leg.br/transparencia/sen/${encodeURIComponent(p.id)}`]])}`,
    painelComportamento: painelPresencaAno(sen.presencaAno), painelRelatorias: painelRelatorias(sen.relatorias, p.id, nome),
    rotuloPerfil: sen.despesas ? "Perfil e gastos" : "Perfil",
    linhaDoTempo, proposicoes: sen.proposicoes, tipoProjeto: (x) => !!TIPOS_PROJETO[x.tipo],
    textoLegislatura: "como autor ou coautor desde 2019",
    papel: (x) => x.principal ? "<b>autor principal</b> (o primeiro a assinar)." : "<b>coautor</b> (assinou depois do autor principal).",
    aviso: "A situação vem da tramitação no Senado e é atualizada aos poucos todo dia.",
    fonteTramitacao: "Tramitação (Senado)",
    fonteEmenta: "Senado",
    hrefProposicao: (x) => `proposicao.html?k=s-${encodeURIComponent(x.id)}`,
    linkTramitacao: (x) => linkMateriaSenado(x.id),
    linkApi: (x) => `${SENADO_API}/processo/${encodeURIComponent(x.proc)}`,
    hrefVotacao: (v) => `votacao.html?casa=senado&id=${encodeURIComponent(v.id)}`,
    fontesVotacao: (v) => [["Votos de cada senador (API do Senado)", apiVotacao(v)], v.propId ? ["Tramitação da matéria", linkMateriaSenado(v.propId)] : null],
  });
  return true;
}
