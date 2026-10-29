/* Perfil do deputado: gastos, painéis e abas. */
import { $, esc, reais, reaisCentavos, pct, data, param, carregar, pctBr, urlSegura } from "./util.js";
import { VOTOS, itemFicha, semDadosLocais } from "./comum.js";
import { linhaNoCargoAte, linhaSubsidio } from "./ficha.js";
import { CAMARA_API, TIPOS_PROJETO, linkTramitacao, fontes, temResultado } from "./apis.js";
import { montarParlamentar } from "./parlamentar.js";
import { avisoLicenca } from "./ministros.js";
import { painelEleicao } from "./eleicao.js";

/* gastos da cota (deputado: CEAP; senador: CEAPS); desp vem de gerar.py */
const LIMITE_COTA_URL = "https://www2.camara.leg.br/comunicacao/assessoria-de-imprensa/guia-para-jornalistas/cota-parlamentar";


/* Quanto da cota o deputado usou (limite mensal da UF x meses com despesa) e como se compara com a média da bancada do estado. */
function comparativoCota(desp) {
  const partes = [];
  if (desp.limite) {
    const acumulado = desp.limite.mensal * desp.limite.meses;
    partes.push(`O limite mensal da cota em ${esc(desp.mediaUF?.uf || "seu estado")} é de ${reaisCentavos(desp.limite.mensal)}, e o que sobra num mês acumula até o fim do ano. Com despesas lançadas até o mês ${desp.limite.meses}, o acumulado permitido é ${reaisCentavos(acumulado)}: o deputado usou <b>${pctBr((100 * desp.total) / acumulado)}</b>.`);
  }
  if (desp.mediaUF && desp.mediaUF.deputados > 1) {
    const dif = desp.mediaUF.media ? (100 * (desp.total - desp.mediaUF.media)) / desp.mediaUF.media : 0;
    partes.push(`A média dos ${desp.mediaUF.deputados} deputados em exercício de ${esc(desp.mediaUF.uf)} é de ${reaisCentavos(desp.mediaUF.media)}; este deputado gastou ${Math.abs(dif) < 0.05 ? "o mesmo" : `<b>${pctBr(Math.abs(dif))} ${dif > 0 ? "a mais" : "a menos"}</b>`}.`);
  }
  return partes.map((t) => `<p>${t}</p>`).join("");
}

function listaMaioresNotas(desp) {
  if (!desp.maiores || !desp.maiores.length) return "";
  return `<h3>Maiores notas do ano</h3>
    <div class="rolagem"><table class="tabela"><thead><tr><th>Data</th><th>Fornecedor</th><th>Tipo</th><th>Valor</th><th>Nota</th></tr></thead><tbody>
    ${desp.maiores.map((n) => `<tr><td>${n.data ? data(n.data) : `mês ${esc(n.mes)}`}</td><td>${esc(n.fornecedor || "Não informado")}</td><td>${esc(n.tipo || "")}</td><td>${reaisCentavos(n.valor)}</td>
      <td>${urlSegura(n.documento) ? `<a href="${esc(n.documento)}" rel="noopener">documento fiscal</a>` : "—"}</td></tr>`).join("")}</tbody></table></div>`;
}

export function painelGastos(desp, explicacao) {
  const maxTipo = desp.porCategoria[0]?.total || 1;
  return `
    <h2>Gastos da cota parlamentar em ${desp.ano}</h2>
    <p>Total no ano: <b>${reaisCentavos(desp.total)}</b>. ${esc(explicacao)}</p>
    ${comparativoCota(desp)}
    <div class="duas-colunas">
      <div>
        <h3>Por categoria de despesa</h3>
        ${desp.porCategoria.length ? `<div class="barras">${desp.porCategoria.map((c) => `
          <div><div class="barra-rotulo"><span title="${esc(c.originais.map(([r, v]) => `${r}: ${reais(v)}`).join("\n"))}">${esc(c.categoria)}</span><b>${reais(c.total)}</b></div><div class="barra"><i style="width:${(c.total / maxTipo) * 100}%"></i></div></div>`).join("")}</div>`
          : `<p class="vazio">Nenhuma despesa registrada neste ano.</p>`}
      </div>
      <div>
        <h3>Maiores fornecedores</h3>
        ${desp.fornecedores.length ? `<div class="rolagem"><table class="tabela"><thead><tr><th>Fornecedor</th><th>Valor</th></tr></thead><tbody>
          ${desp.fornecedores.map(([f, v]) => `<tr><td>${esc(f)}</td><td>${reais(v)}</td></tr>`).join("")}</tbody></table></div>`
          : `<p class="vazio">Sem fornecedores no período.</p>`}
      </div>
    </div>
    ${listaMaioresNotas(desp)}
  `;
}

/* Profissões, mandatos fora da Câmara, histórico de partido e situação e últimos discursos (coletar.py: coletar_complementos). */
function painelTrajetoria(dep) {
  const api = `${CAMARA_API}/deputados/${encodeURIComponent(dep.id)}`;
  const { profissoes, ocupacoes, mandatosExternos, historico, discursos, discursosResumo, eventos } = dep;
  if (!profissoes && !ocupacoes && !mandatosExternos && !historico && !discursos && !discursosResumo && !eventos) return "";
  const porAno = (m) => Object.entries(m || {}).map(([a, n]) => `${esc(a)}: ${n}`).join(" · ");
  const resumo = discursosResumo?.total
    ? `<h3>Discursos na legislatura</h3><p><b>${discursosResumo.total}</b> discursos (${porAno(discursosResumo.porAno)}).</p>
       ${Object.keys(discursosResumo.porTipo || {}).length ? `<p><b>Por tipo:</b> ${Object.entries(discursosResumo.porTipo).map(([t, n]) => `${esc(t)} (${n})`).join(", ")}.</p>` : ""}
       ${discursosResumo.temas?.length ? `<p><b>Palavras mais frequentes nos sumários:</b> ${discursosResumo.temas.map(([p, n]) => `${esc(p)} (${n})`).join(", ")}.</p>` : ""}`
    : "";
  const agenda = eventos?.total
    ? `<h3>Audiências e reuniões</h3><p><b>${eventos.total}</b> eventos como participante (${porAno(eventos.porAno)}). Mais recentes:</p>
       <ul class="lista-simples">${eventos.recentes.map((e) => `<li><span class="quando">${e.data ? data(e.data) : ""}${e.tipo ? `, ${esc(e.tipo.toLowerCase())}` : ""}${e.orgao ? ` (${esc(e.orgao)})` : ""}</span>${e.titulo ? `<br>${esc(e.titulo)}` : ""}${e.id ? `<br><a href="https://www.camara.leg.br/evento-legislativo/${encodeURIComponent(e.id)}" rel="noopener">Ver o evento</a>` : ""}</li>`).join("")}</ul>`
    : "";
  const periodo = (a, b) => (a && b ? `${esc(a)} a ${esc(b)}` : a ? `desde ${esc(a)}` : b ? `até ${esc(b)}` : "");
  const mudancas = (historico || []).filter((h, i, l) => i === 0 || h.partido !== l[i - 1].partido || h.situacao !== l[i - 1].situacao || h.descricao);
  return `
    <h2>Trajetória</h2>
    ${profissoes?.length ? `<p><b>Profissão:</b> ${profissoes.map((x) => esc(x.titulo)).join(", ")}.</p>` : ""}
    ${ocupacoes?.length ? `<h3>Ocupações anteriores</h3><ul class="lista-simples">${ocupacoes.map((o) => `<li>${esc(o.titulo)}${o.entidade ? ` · ${esc(o.entidade)}` : ""}${o.uf ? `/${esc(o.uf)}` : ""}${periodo(o.inicio, o.fim) ? `<br><span class="quando">${periodo(o.inicio, o.fim)}</span>` : ""}</li>`).join("")}</ul>` : ""}
    ${mandatosExternos?.length ? `<h3>Mandatos fora da Câmara</h3><ul class="lista-simples">${mandatosExternos.map((m) => `<li>${esc(m.cargo)}${m.municipio ? ` em ${esc(m.municipio)}` : ""}${m.uf ? `/${esc(m.uf)}` : ""}<br><span class="quando">${periodo(m.inicio, m.fim)}${m.partido ? `, pelo ${esc(m.partido)}` : ""}</span></li>`).join("")}</ul>` : ""}
    ${mudancas.length ? `<h3>Partido e situação nesta legislatura</h3><ul class="lista-simples">${mudancas.map((h) => `<li><span class="quando">${h.data ? data(h.data) : ""}</span> ${esc([h.partido, h.situacao].filter(Boolean).join(" · "))}${h.descricao ? `<br><span class="quando">${esc(h.descricao)}</span>` : ""}</li>`).join("")}</ul>` : ""}
    ${resumo}
    ${discursos?.length ? `<h3>Discursos mais recentes</h3><ul class="lista-simples">${discursos.map((d) => `<li><span class="quando">${d.data ? data(d.data) : ""}${d.tipo ? `, ${esc(d.tipo.toLowerCase())}` : ""}${d.fase ? ` (${esc(d.fase)})` : ""}</span>${d.sumario ? `<br>${esc(d.sumario)}` : ""}${urlSegura(d.link) ? `<br><a href="${esc(d.link)}" rel="noopener">Ver o discurso</a>` : ""}</li>`).join("")}</ul>` : ""}
    ${agenda}
    ${fontes([["Eventos (API da Câmara)", `${api}/eventos`], ["Profissões (API da Câmara)", `${api}/profissoes`], ["Ocupações (API da Câmara)", `${api}/ocupacoes`], ["Mandatos externos (API da Câmara)", `${api}/mandatosExternos`], ["Histórico (API da Câmara)", `${api}/historico`], ["Discursos (API da Câmara)", `${api}/discursos`]])}`;
}

/* Com quem o deputado mais assina projetos (scripts/gerar_coautoria.py). `lista` é dados/deputados.json, para nome e partido dos parceiros. */
function painelCoautoria(dep, lista) {
  const c = dep.coautoria;
  if (!c) return `<h2>Com quem assina projetos</h2><p class="vazio">Nenhum projeto assinado junto com outro deputado, entre os que já tiveram a autoria coletada.</p>`;
  const por = new Map(lista.map((d) => [String(d.id), d]));
  return `
    <h2>Com quem assina projetos</h2>
    <p>${c.projetos} ${c.projetos === 1 ? "projeto assinado" : "projetos assinados"} com outros deputados, ${c.outroPartido} com deputado de outro partido (${pct(c.outroPartido, c.projetos)}). <a href="coautoria.html">Ver a rede entre os partidos</a>.</p>
    <div class="rolagem"><table class="tabela"><thead><tr><th>Deputado</th><th>Partido</th><th>Projetos em comum</th></tr></thead><tbody>
      ${c.parceiros.map(([j, n]) => { const d = por.get(String(j)); return `<tr><td>${d ? `<a href="deputado.html?id=${encodeURIComponent(j)}">${esc(d.nome)}</a>` : `Deputado ${esc(j)}`}</td><td>${d ? `${esc(d.partido)}/${esc(d.uf)}` : "—"}</td><td>${n}</td></tr>`; }).join("")}
    </tbody></table></div>
    <p class="quando">Só projetos (PL, PEC e afins) com mais de um deputado em exercício entre os autores; não entram autores que não são deputados nem projetos com mais de 30 deputados.</p>
    ${fontes([["Autores de cada proposição (API da Câmara)", `${CAMARA_API}/proposicoes`]])}`;
}

const ARQUIVOS_CAMARA = "https://dadosabertos.camara.leg.br/arquivos";
function painelTematico(dep) {
  const api = `${CAMARA_API}/deputados/${encodeURIComponent(dep.id)}`;
  const temas = dep.temas || [], max = temas[0]?.[1] || 1;
  const orgaos = dep.orgaos || [], frentes = dep.frentes;
  const anos = [...new Set(dep.proposicoes.filter((p) => p.temas).map((p) => p.ano))].sort();
  return `
    <h2>Em que áreas atua</h2>
    <p>Temas oficiais dos projetos que ${esc(dep.nome)} apresentou como autor ou coautor, as comissões de que participa e as frentes parlamentares de que faz parte.</p>
    <div class="duas-colunas">
      <div>
        <h3>Temas dos projetos</h3>
        ${temas.length ? `<div class="barras">${temas.map(([t, n, ap, pr]) => `
          <div><div class="barra-rotulo"><span>${esc(t)}</span><b>${n} ${n === 1 ? "projeto" : "projetos"}</b></div><div class="barra"><i style="width:${(n / max) * 100}%"></i></div>
          <span class="quando">${ap} aprovado${ap === 1 ? "" : "s"} · ${pr} como autor principal</span></div>`).join("")}</div>
          <p class="quando">Um projeto pode ter mais de um tema e conta em cada um. Para ver os projetos de um tema, use o filtro na aba Propostas.</p>`
          : `<p class="vazio">Nenhum projeto com tema classificado pela Câmara.</p>`}
      </div>
      <div>
        <h3>Comissões e órgãos</h3>
        ${orgaos.length ? `<ul class="lista-simples">${orgaos.map((o) => `<li><b>${esc(o.sigla)}</b> ${esc(o.nome)}<br><span class="quando">${esc(o.cargo || "Membro")}${o.inicio ? `, desde ${data(o.inicio)}` : ""}${o.fim ? ` até ${data(o.fim)}` : ""}</span></li>`).join("")}</ul>`
          : `<p class="vazio">Nenhuma participação registrada nesta legislatura.</p>`}
      </div>
    </div>
    <h3>Frentes parlamentares${frentes ? ` <small class="sub">(${frentes.length})</small>` : ""}</h3>
    ${frentes === null || frentes === undefined ? `<p class="vazio">Frentes ainda não coletadas.</p>`
      : frentes.length ? `<details><summary>Ver as ${frentes.length} frentes</summary><ul class="lista-simples">${frentes.map((f) => `<li><a href="https://www.camara.leg.br/internet/deputado/frenteDetalhe.asp?id=${encodeURIComponent(f.id)}" rel="noopener">${esc(f.titulo)}</a></li>`).join("")}</ul></details>`
      : `<p class="vazio">Não consta em nenhuma frente nesta legislatura.</p>`}
    ${fontes([["Órgãos do deputado (API da Câmara)", `${api}/orgaos`], ["Frentes do deputado (API da Câmara)", `${api}/frentes`],
      ...anos.map((a) => [`Temas dos projetos de ${a} (arquivo da Câmara)`, `${ARQUIVOS_CAMARA}/proposicoesTemas/json/proposicoesTemas-${a}.json`])])}`;
}


/* Fidelidade ao partido e governismo do deputado, a partir das orientações de bancada nas votações nominais. */
function painelComportamento(dep) {
  const c = dep.comportamento;
  if (!c) return "";
  const caixa = (k, titulo, quem) => c[k].total
    ? `<div><b>${pct(c[k].seguiu, c[k].total)}</b><span>${titulo}: votou como ${quem} orientou em ${c[k].seguiu} de ${c[k].total} votações</span></div>` : "";
  const div = c.divergencias || [];
  return `
    <section class="painel" aria-labelledby="t-comportamento">
      <div class="painel-titulo">
        <h2 id="t-comportamento">Fidelidade ao partido e ao governo</h2>
        <p>Compara o voto de ${esc(dep.nome)} com a orientação que a bancada do partido (${esc(dep.partido)}) e o Governo deram em cada votação. Só entram as votações em que votou e a orientação foi Sim, Não ou Obstrução; "Liberado" não conta. Usa o partido atual do deputado; blocos partidários contam pela composição atual.</p>
      </div>
      <div class="numeros">${caixa("partido", "Fidelidade ao partido", "o partido")}${caixa("governo", "Governismo", "o Governo")}</div>
      ${c.partido.total ? "" : `<p class="vazio">Sem orientação da bancada do ${esc(dep.partido)}: o partido aparece nas votações dentro de um bloco que a Câmara registra com o nome truncado, e não foi possível ligá-lo ao bloco.</p>`}
      ${div.length ? `<h3>Quando votou diferente</h3><ul class="lista-simples">${div.map((x) => `<li><span class="quando">${data(x.data)}</span> ${x.proposicao ? `<b>${esc(x.proposicao)}</b>: ` : ""}votou <b>${esc(VOTOS[x.voto]?.rotulo || x.voto)}</b>, a orientação ${x.contra === "governo" ? "do Governo" : `da bancada (${esc(x.bancada)})`} foi <b>${esc(x.orientacao)}</b>. <a href="votacao.html?id=${encodeURIComponent(x.id)}">Ver votação</a></li>`).join("")}</ul>` : ""}
      ${fontes([["Orientações de bancada (arquivo da Câmara)", `${ARQUIVOS_CAMARA}/votacoesOrientacoes/json/votacoesOrientacoes-${(div[0]?.data || new Date().toISOString()).slice(0, 4)}.json`]])}
    </section>`;
}

/* Presença do deputado em sessões e reuniões (gerar.py: presenca_do_deputado). */
function painelPresencaDeputado(dep) {
  const anos = dep.presenca || [];
  if (!anos.length) return "";
  return `
    <section class="painel" aria-labelledby="t-presenca">
      <div class="painel-titulo">
        <h2 id="t-presenca">Presença em sessões e reuniões</h2>
        <p>Eventos da Câmara em que ${esc(dep.nome)} registrou presença. Nas sessões deliberativas do Plenário há o total do ano para comparar; as reuniões de comissão e audiências não têm total, porque dependem das comissões de que o deputado participa. O ano corrente ainda está em andamento.</p>
      </div>
      <div class="rolagem"><table class="tabela"><thead><tr><th>Ano</th><th>Sessões deliberativas</th><th>Mediana dos deputados</th><th>Reuniões e audiências</th><th>Outros eventos</th></tr></thead><tbody>
        ${anos.map((a) => `<tr><td>${a.ano}</td><td><b>${a.sessoes}</b> de ${a.sessoesDeliberativas} (${pct(a.sessoes, a.sessoesDeliberativas)})</td><td>${a.medianaSessoes}</td><td>${a.comissoes}</td><td>${a.outros}</td></tr>`).join("")}
      </tbody></table></div>
      ${fontes(anos.flatMap((a) => [[`Presença em eventos de ${a.ano} (arquivo da Câmara)`, `${ARQUIVOS_CAMARA}/eventosPresencaDeputados/json/eventosPresencaDeputados-${a.ano}.json`], [`Eventos de ${a.ano} (arquivo da Câmara)`, `${ARQUIVOS_CAMARA}/eventos/json/eventos-${a.ano}.json`]]))}
    </section>`;
}

/* Recursos e verba de gabinete do deputado, raspados do portal da Câmara (coletar.py: coletar_recursos_camara). */
function painelRecursosDeputado(dep) {
  const rec = dep.recursos;
  if (!rec) return "";
  const v = rec.verba, mes = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const total = v ? v.gasto + v.naoUtilizado : 0;
  const portal = `https://www.camara.leg.br/deputados/${encodeURIComponent(dep.id)}`;
  return `
    <h2>Recursos e benefícios em ${rec.ano}</h2>
    <div class="rolagem"><table class="tabela"><thead><tr><th>Recurso</th><th>Situação</th></tr></thead><tbody>
      ${rec.beneficios.map(([t, x]) => `<tr><td>${esc(t)}</td><td>${esc(x)}</td></tr>`).join("")}
    </tbody></table></div>
    ${v ? `<h3>Verba de gabinete: ${pct(v.gasto, total)} usada no ano</h3>
      <p>Gastou <b>${reaisCentavos(v.gasto)}</b> de ${reaisCentavos(total)} (não utilizado: ${reaisCentavos(v.naoUtilizado)}).${v.limiteMensal ? ` O limite mensal é de ${reaisCentavos(v.limiteMensal)}, para pagar os secretários parlamentares.` : ""}</p>
      ${v.porMes.length ? `<p>${v.porMes.map(([m, x]) => `<span class="selo">${mes[m - 1]}: ${reais(x)}</span>`).join(" ")}</p>` : ""}` : ""}
    ${fontes([["Recursos do deputado (portal da Câmara)", portal], v ? ["Verba de gabinete (portal da Câmara)", `${portal}/verba-gabinete?ano=${rec.ano}`] : null])}
    ${rec.atualizadoEm ? `<p class="vazio">Informações do portal atualizadas em ${data(rec.atualizadoEm.slice(0, 10), true)}.</p>` : ""}`;
}

export async function paginaDeputado() {
  const alvo = $("#conteudo");
  const id = param("id");
  let dep, votacoes, lista;
  try {
    [dep, votacoes, lista] = await Promise.all([carregar(`dados/deputado/${encodeURIComponent(id)}.json`), carregar("dados/votacoes.json"), carregar("dados/deputados.json")]);
  } catch (e) { return semDadosLocais(alvo, e, `${CAMARA_API}/deputados/${encodeURIComponent(id)}`); }
  document.title = `${dep.nome} (${dep.partido}/${dep.uf}) | Minha Bancada`;

  let indice = [];
  if (dep.relatorias?.length) { try { indice = await carregar("dados/proposicoes.json"); } catch { /* sem o índice, a seção de relatorias fica de fora */ } }
  const porChave = new Map(indice.map((x) => [x.k, x]));
  const relatorias = (dep.relatorias || []).map((id) => porChave.get(`c-${id}`)).filter(Boolean);

  const meus = new Map(dep.votos.map((v) => [v.id, v.voto]));
  const desp = dep.despesas;
  const painelPerfil = `
    ${painelGastos(desp, "A cota paga despesas do mandato, como passagens, aluguel de escritório e divulgação.")}
    ${fontes([["Cota parlamentar (API da Câmara)", `${CAMARA_API}/deputados/${encodeURIComponent(dep.id)}/despesas?ano=${desp.ano}`], desp.limite ? ["Limite mensal da cota por estado (Câmara)", LIMITE_COTA_URL] : null, ["Portal da Câmara", `https://www.camara.leg.br/deputados/${encodeURIComponent(dep.id)}`]])}

    ${painelRecursosDeputado(dep)}

    ${painelTematico(dep)}

    ${painelCoautoria(dep, lista)}

    ${painelTrajetoria(dep)}

    <h2>Ficha</h2>
    <dl class="ficha">
      ${dep.nomeCivil ? `<dt>Nome civil</dt><dd>${esc(dep.nomeCivil)}</dd>` : ""}
      ${dep.nascimento ? `<dt>Nascimento</dt><dd>${data(dep.nascimento, true)}${dep.naturalidade ? `, ${esc(dep.naturalidade)}` : ""}</dd>` : ""}
      ${dep.escolaridade ? `<dt>Escolaridade</dt><dd>${esc(dep.escolaridade)}</dd>` : ""}
      <dt>No cargo até</dt><dd>${linhaNoCargoAte({ fimMandato: "2027-01-31", estado: "atual" }, "DEPUTADO FEDERAL")[1]}</dd>
      ${itemFicha(linhaSubsidio({ cargoTse: "DEPUTADO FEDERAL", estado: "atual" }))}
      ${dep.email ? `<dt>E-mail</dt><dd><a href="mailto:${esc(dep.email)}">${esc(dep.email)}</a></dd>` : ""}
      ${dep.gabinete ? `<dt>Gabinete</dt><dd>${esc([dep.gabinete.predio && `Prédio ${dep.gabinete.predio}`, dep.gabinete.andar && `${dep.gabinete.andar}º andar`, dep.gabinete.sala && `sala ${dep.gabinete.sala}`].filter(Boolean).join(", "))}${dep.gabinete.telefone ? `, tel. ${esc(dep.gabinete.telefone)}` : ""}${dep.gabinete.email && dep.gabinete.email !== dep.email ? `, <a href="mailto:${esc(dep.gabinete.email)}">${esc(dep.gabinete.email)}</a>` : ""} <span class="fonte-link"><span class="rotulo-fonte">Fonte</span> <a href="${CAMARA_API}/deputados/${encodeURIComponent(dep.id)}" rel="noopener">cadastro na API da Câmara</a></span></dd>` : ""}
      <dt>Página oficial</dt><dd><a href="https://www.camara.leg.br/deputados/${encodeURIComponent(dep.id)}">camara.leg.br/deputados/${esc(dep.id)}</a></dd>
      ${(dep.redesSociais || []).filter((r) => urlSegura(r)).map((r) => `<dt>Rede social</dt><dd><span class="link-bloco"><a class="link-rede" href="${esc(r)}" rel="noopener">${esc(r.replace(/^https?:\/\/(www\.)?/, ""))}</a> <span class="fonte-link"><span class="rotulo-fonte">Fonte</span> <a href="${CAMARA_API}/deputados/${encodeURIComponent(dep.id)}" rel="noopener">cadastro na API da Câmara</a></span></span></dd>`).join("")}
    </dl>
    ${fontes([["Cadastro do deputado (API da Câmara)", `${CAMARA_API}/deputados/${encodeURIComponent(dep.id)}`], ["Portal da Câmara", `https://www.camara.leg.br/deputados/${encodeURIComponent(dep.id)}`]])}`;

  montarParlamentar(alvo, {
    nome: dep.nome, foto: dep, antes: dep.ministro ? await avisoLicenca(dep.ministro, "deputado federal") : "",
    painelEleicao: painelEleicao(dep.nome, dep.eleicao, { suplente: /suplente/i.test(dep.condicao || ""), condicao: dep.condicao, cargoTse: "DEPUTADO FEDERAL",
      fontes: [["Cadastro do deputado (API da Câmara)", `${CAMARA_API}/deputados/${encodeURIComponent(dep.id)}`]] }),
    subtitulo: `<span class="selo">${esc(dep.partido)}/${esc(dep.uf)}</span> ${dep.situacao ? esc(dep.situacao) : ""}`,
    painelPerfil, rotuloPerfil: "Perfil e gastos",
    linhaDoTempo: votacoes.filter(temResultado).map((v) => ({ ...v, voto: meus.get(v.id) || "ausente" })), // mais recente primeiro
    painelComportamento: painelComportamento(dep) + painelPresencaDeputado(dep),
    relatorias, proposicoes: dep.proposicoes, tipoProjeto: (p) => !!TIPOS_PROJETO[p.tipo],
    textoLegislatura: "como autor ou coautor nesta legislatura (desde fev. de 2023)", suprapartidarios: true,
    papel: (p) => p.principal === undefined ? "autor ou coautor. A Câmara lista os dois juntos e a ordem de assinatura desta proposição ainda não foi coletada."
      : p.principal ? "<b>autor principal</b> (o primeiro a assinar)." : "<b>coautor</b> (assinou depois do autor principal).",
    aviso: "A situação vem da ficha de tramitação da Câmara e é atualizada aos poucos todo dia.",
    fonteTramitacao: "Ficha de tramitação (Câmara)",
    hrefProposicao: (p) => `proposicao.html?k=c-${encodeURIComponent(p.id)}`,
    linkTramitacao: (p) => linkTramitacao(p.id),
    linkApi: (p) => `${CAMARA_API}/proposicoes/${encodeURIComponent(p.id)}`,
    hrefVotacao: (v) => `votacao.html?id=${encodeURIComponent(v.id)}`,
    fontesVotacao: (v) => [["Votos de cada deputado (API da Câmara)", `${CAMARA_API}/votacoes/${encodeURIComponent(v.id)}/votos`], ["Detalhes da votação", `${CAMARA_API}/votacoes/${encodeURIComponent(v.id)}`], v.propId ? ["Tramitação do projeto", linkTramitacao(v.propId)] : null],
  });
}
