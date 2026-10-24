/* Deputado estadual: resumos e abas. */
import { $, esc, reais, reaisCentavos, carregar, urlSegura } from "./util.js";
import { itemFicha, listaPaginada } from "./comum.js";
import { semFonte, blocoPatrimonioFontes } from "./ficha.js";
import { fontes, UFS } from "./apis.js";
import { montarParlamentar } from "./parlamentar.js";
import { painelEleicaoDe } from "./eleicao.js";

/* Resumos que o gerar_estaduais.py acrescenta ao JSON do deputado estadual quando a coleta da UF tem os arquivos (verba, remuneração, presença, diárias, emendas). Cada bloco traz a fonte. */
const MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
function rotuloMes(m) {
  const n = parseInt(String(m).split("-").pop(), 10);
  return n >= 1 && n <= 12 ? MESES_CURTOS[n - 1] : String(m ?? "");
}
const dataBr = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso || "") ? iso.split("-").reverse().join("/") : "");
const linkFonte = (url, texto) => (urlSegura(url) ? `<a href="${esc(url)}" rel="noopener">${esc(texto)}</a>` : "");
function secaoEstadual(titulo, texto, corpo, fonte, nomeFonte) {
  return `<h2>${esc(titulo)}</h2><p>${texto}</p>${corpo}${fonte ? fontes([[nomeFonte, fonte]]) : semFonte()}`;
}
export function resumosEstadual(dep) {
  const tabela = (cab, linhas) => `<div class="rolagem"><table class="tabela"><thead><tr>${cab.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${linhas.map((l) => `<tr>${l.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  let html = "";
  if (dep.verba?.anos?.length) {
    html += secaoEstadual("Verba/cota", "Gastos com a verba de gabinete ou cota parlamentar, por ano.", dep.verba.anos.map((a) => `
      <h3>${esc(a.ano ?? "")}: ${reaisCentavos(a.total)}</h3>
      <p>Por mês: ${a.meses.map((m) => `${esc(rotuloMes(m.mes))} ${reais(m.total)}`).join(", ")}.</p>
      ${tabela(["Categoria", "Total"], a.categorias.map((c) => [`<span title="${esc(c.originais.map(([r, v]) => `${r}: ${reais(v)}`).join("\n"))}">${esc(c.categoria)}</span>`, reais(c.total)]))}
      ${a.fornecedores.length ? tabela(["Maiores fornecedores", "CNPJ", "Total"], a.fornecedores.map((f) => [esc(f.fornecedor), esc(f.cnpj || ""), reais(f.total)])) : ""}
      ${a.lancamentos?.length ? `<h3>Lançamentos de ${esc(a.ano)}</h3>${tabela(["Emissão ou mês", "Fornecedor", "Documento", "Empenho", "Descrição", "Valor", "Fonte"],
        a.lancamentos.map((l) => [esc(dataBr(l.emissao) || rotuloMes(l.mes)), esc(l.fornecedor || ""), esc(l.documento || ""), esc(l.empenho || ""), esc(l.descricao || l.categoria || ""), reaisCentavos(l.valor), linkFonte(l.fonte, "fonte") || semFonte()]))}` : ""}`).join(""), dep.verba.fonte, "Verba/cota (Assembleia)");
  }
  if (dep.remuneracao) {
    const r = dep.remuneracao;
    html += secaoEstadual("Remuneração", `Último mês publicado: <b>${esc(rotuloMes(r.mes))}${r.ano ? `/${esc(r.ano)}` : ""}</b>. Bruto <b>${reaisCentavos(r.bruto)}</b>, líquido <b>${reaisCentavos(r.liquido)}</b>.`, "", r.fonte, "Remuneração (Assembleia)");
  }
  if (dep.presenca?.periodos?.length) {
    html += secaoEstadual("Presença", "Presença em sessões da Assembleia.", tabela(["Período", "Presente", "Ausente", "Licença", "Total de sessões"],
      dep.presenca.periodos.map((x) => [esc(x.periodo), x.presente ?? "", x.ausente ?? "", x.licenca ?? "", x.totalSessoes ?? ""])), dep.presenca.fonte, "Presença (Assembleia)");
  }
  if (dep.diarias?.anos?.length) {
    html += secaoEstadual("Diárias", "Diárias pagas ao deputado, por ano.", tabela(["Ano", "Quantidade", "Total"],
      dep.diarias.anos.map((a) => [esc(a.ano), a.quantidade, reais(a.total)])), dep.diarias.fonte, "Diárias (Assembleia)");
  }
  if (dep.emendas?.anos?.length) {
    html += secaoEstadual("Emendas", "Emendas ao orçamento indicadas pelo deputado, por ano.", tabela(["Ano", "Empenhado", "Pago"],
      dep.emendas.anos.map((a) => [esc(a.ano), reais(a.empenhado), reais(a.pago)])) + (dep.emendas.pagamentos?.length ? `<h3>Pagamentos das emendas</h3>${tabela(["Data", "Credor", "Objeto", "Valor", "Situação"],
      dep.emendas.pagamentos.map((x) => [esc(dataBr(x.data)), esc(x.credor || ""), esc(x.objeto || ""), reaisCentavos(x.valor), x.efetivado === false ? "não efetivado" : x.efetivado ? "efetivado" : ""]))}` : ""), dep.emendas.fonte, "Emendas (Assembleia)");
  }
  return html;
}

/* deputado estadual (Assembleias que usam o SAPL): mesmas abas do deputado federal. Devolve false se os dados ainda não existem. */
export async function montarEstadual(alvo, p, nome, ficha, situacao) {
  const { uf, id } = p.estadual;
  let dep, lista;
  try { [dep, lista] = await Promise.all([carregar(`dados/estadual/${encodeURIComponent(uf)}/${encodeURIComponent(id)}.json`), carregar(`dados/votacoes_estadual_${encodeURIComponent(uf)}.json`)]); } catch { return false; }
  const meus = new Map(dep.votos.map((v) => [v.id, v.voto]));
  const linhaDoTempo = lista.filter((v) => meus.has(v.id)).map((v) => ({ ...v, voto: meus.get(v.id) }));
  const api = dep.host ? `https://${dep.host}/api` : null;
  const bens = p.bens || [];
  if (!p.email && dep.email) ficha.push(["E-mail", `<a href="mailto:${esc(dep.email)}">${esc(dep.email)}</a>`, true]);
  if (dep.titular === false) ficha.push(["Exercício", "Suplente em exercício"]);
  montarParlamentar(alvo, {
    nome, foto: { nome, foto: p.foto || dep.foto }, painelEleicao: painelEleicaoDe(p, nome),
    subtitulo: `<span class="selo">${esc(p.partido || "")}/${esc(p.uf)}</span> ${esc(p.cargo)}`,
    painelPerfil: `<p class="situacao">${situacao}</p>
      <h2>Ficha</h2>
      <dl class="ficha">${ficha.map(itemFicha).join("")}
        <dt>Onde atua</dt><dd>${esc(UFS[p.uf] || p.uf)}</dd>
      </dl>
      <h2>Bens declarados em ${esc(p.ano)}</h2>
      <p>Total: <b>${reaisCentavos(p.totalBens)}</b>${bens.length ? `, em ${bens.length} ${bens.length === 1 ? "item" : "itens"}` : ""}. Valores informados pelo próprio candidato ao registrar a candidatura.</p>
      <div id="lista-bens"></div>
      ${blocoPatrimonioFontes(p, [], [dep.host ? ["Assembleia Legislativa (SAPL)", `https://${dep.host}`] : dep.fonte ? ["Assembleia Legislativa", dep.fonte] : null])}
      ${resumosEstadual(dep)}`,
    rotuloPerfil: "Perfil e bens",
    linhaDoTempo, proposicoes: dep.proposicoes, tipoProjeto: () => true,
    textoLegislatura: "como autor ou coautor nesta legislatura",
    papel: (x) => x.coautores && x.coautores.length ? `<b>autor ou coautor</b>, junto com ${esc(x.coautores.join(", "))}.` : "<b>autor ou coautor</b>. A Assembleia não lista outros deputados nesta proposta.",
    aviso: "Só entram projetos (de lei, resolução, decreto legislativo, emendas à Constituição e afins). A situação vem do sistema da Assembleia.",
    rotuloSem: "tramitação encerrada, sem resultado informado",
    semOutros: "Requerimentos, indicações e outros documentos da Assembleia não estão no site. Veja no sistema de tramitação da Assembleia.",
    fonteTramitacao: "Tramitação (Assembleia)",
    linkTramitacao: (x) => x.fonte || (dep.host ? `https://${dep.host}/materia/${encodeURIComponent(x.id)}` : null),
    linkApi: (x) => (x.fonte || !api ? null : `${api}/materia/materialegislativa/${encodeURIComponent(x.id)}/`),
    hrefVotacao: null,
    fontesVotacao: (v) => [v.fonte ? ["Dados da votação (Assembleia)", v.fonte] : api ? ["Dados da votação (API da Assembleia)", `${api}/sessao/registrovotacao/${encodeURIComponent(v.id)}/`] : null],
  });
  listaPaginada($("#lista-bens"), bens, ([tipo, desc, valor]) => `<li>
      <span class="quando"><b>${esc(tipo)}</b></span><b>${reais(valor)}</b>
      ${desc ? `<span class="texto">${esc(desc.charAt(0) + desc.slice(1).toLowerCase())}</span>` : ""}</li>`, 10, "Nenhum bem declarado.");
  return true;
}
