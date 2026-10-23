/* Ficha do político: redes sociais, patrimônio, campanha, disputa, partido e votos. */
import { esc, reaisCentavos, data, semAcento, pctBr, numeroBr, urlSegura } from "./util.js";
import { TSE_CDN, arquivoTse, arquivoRedesTse, fontes, SENADO_API } from "./apis.js";

const SOBRENOMES_COMUNS = new Set(["silva", "santos", "souza", "oliveira", "pereira", "costa", "filho", "junior", "neto", "sobrinho"]);

function perfilDoPolitico(url, p) {
  const nomes = `${p.urna || ""} ${p.nome || ""}`;
  const partes = semAcento(nomes).split(/[^a-z0-9]+/).filter((t) => t.length >= 4 && !SOBRENOMES_COMUNS.has(t));
  let alvo;
  try { const u = new URL(url); alvo = `${u.hostname}${u.pathname}`; } catch { alvo = url; }
  alvo = semAcento(decodeURIComponent(alvo.replace(/%(?![0-9a-f]{2})/gi, ""))).replace(/[^a-z0-9]/g, "");
  return partes.some((t) => alvo.includes(t));
}

export function linksRedes(redes, p) {
  const todas = [...new Set((redes || []).filter((r) => !/\s/.test(r) && urlSegura(r)))];
  const item = (r) => `<a class="link-rede" href="${esc(r)}" rel="noopener">${esc(r.replace(/^https?:\/\/(www\.)?/, "").replace(/[?#].*$/, "").replace(/\/$/, ""))}</a>`;
  const lista = (itens) => {
    const aberto = itens.slice(0, 6).join("");
    const resto = itens.slice(6);
    return resto.length ? `${aberto}<details><summary>mais ${resto.length}</summary>${resto.join("")}</details>` : aberto;
  };
  const proprios = todas.filter((r) => perfilDoPolitico(r, p));
  const outros = todas.filter((r) => !perfilDoPolitico(r, p));
  if (!todas.length) return null;
  const fonte = p.fonteRedes || "";
  let html = proprios.length ? lista(proprios.map((r) => `<span class="link-bloco">${item(r)}${fonte}</span>`)) : "";
  if (outros.length) {
    html += `${html ? "<br><br>" : ""}<b>Outros perfis e sites citados na candidatura</b> (sem o nome do político no endereço)<br>`
      + lista(outros.map((r) => `<span class="link-bloco">${item(r)}${fonte}</span>`));
  }
  return html;
}

/* linha da ficha: [rótulo, valor, valor é html, valor fica embaixo do rótulo] */

export const fonteRedesTse = (p) => {
  if (p.fonte !== "tse") return "";
  const d = divulgaUrl(p);
  return `<span class="fonte-link"><span class="rotulo-fonte">Fonte</span> ${d ? `<a href="${esc(d)}" rel="noopener">candidatura ${esc(p.ano)} no DivulgaCandContas</a> · ` : ""}<a href="${esc(arquivoRedesTse(p))}" rel="noopener">arquivo de redes do TSE</a></span>`;
};

export const divulgaUrl = (p) => p.fonte === "tse" && p.eleicao && p.unidadeEleitoral ? `https://divulgacandcontas.tse.jus.br/divulga/#/candidato/${encodeURIComponent(p.ano)}/${encodeURIComponent(p.eleicao)}/${encodeURIComponent(p.unidadeEleitoral)}/${encodeURIComponent(p.sequencial)}` : null;

const CF_URL = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm";
const EC111_URL = "https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc111.htm";
export const CODIGO_ELEITORAL_URL = "https://www.planalto.gov.br/ccivil_03/leis/l4737compilado.htm";
const ARTIGO_CARGO = { PRESIDENTE: 82, "VICE-PRESIDENTE": 79, GOVERNADOR: 28, "VICE-GOVERNADOR": 28, SENADOR: 46, "DEPUTADO FEDERAL": 44,
  "DEPUTADO ESTADUAL": 27, "DEPUTADO DISTRITAL": 32, PREFEITO: 29, "VICE-PREFEITO": 29, VEREADOR: 29 };
export const ARTIGO_ELEICAO = { PRESIDENTE: 77, "VICE-PRESIDENTE": 77, GOVERNADOR: 28, "VICE-GOVERNADOR": 28, SENADOR: 46, "DEPUTADO FEDERAL": 45,
  "DEPUTADO ESTADUAL": 27, "DEPUTADO DISTRITAL": 32, PREFEITO: 29, "VICE-PREFEITO": 29, VEREADOR: 29 };
export const MAJORITARIOS = new Set(["PRESIDENTE", "VICE-PRESIDENTE", "GOVERNADOR", "VICE-GOVERNADOR", "PREFEITO", "VICE-PREFEITO", "SENADOR"]);
const ALTERA_POSSE = new Set(["PRESIDENTE", "VICE-PRESIDENTE", "GOVERNADOR", "VICE-GOVERNADOR"]);
export const linkCF = (art) => `${CF_URL}#art${art}`;

export const semFonte = (porque) => `<span class="sem-fonte" title="Ainda não temos uma fonte pública para este dado">⚠ dado sem fonte${porque ? `: ${esc(porque)}` : ""}</span>`;

/* Linha "No cargo até" da ficha, com a fonte do prazo: Senado (senadores) ou Constituição (demais). */
export function linhaNoCargoAte(p, cargoTse = p.cargoTse) {
  if (!p.fimMandato) return ["No cargo até", semFonte("fim do mandato"), true];
  let origem;
  if (p.fonte === "senado") origem = `<a href="${esc(`${SENADO_API}/senador/${encodeURIComponent(p.id)}`)}" rel="noopener">Dados Abertos do Senado</a>`;
  else if (ARTIGO_CARGO[cargoTse]) {
    origem = `<a href="${linkCF(ARTIGO_CARGO[cargoTse])}" rel="noopener">Constituição Federal, art. ${ARTIGO_CARGO[cargoTse]}</a>`
      + (ALTERA_POSSE.has(cargoTse) ? ` e <a href="${EC111_URL}" rel="noopener">Emenda Constitucional 111/2021</a>` : "");
  }
  const antes = p.estado === "eleito" && p.inicioMandato ? `Toma posse em ${data(p.inicioMandato, true)}. Mandato até ` : p.estado === "2turno" ? "Se eleito, até " : "";
  return ["No cargo até", `${antes}${data(p.fimMandato, true)} ${origem ? `<span class="fonte-link"><span class="rotulo-fonte">Fonte</span> ${origem}</span>` : semFonte("prazo do mandato")}`, true];
}

/* Subsídio mensal bruto. Federal: Decreto Legislativo 172/2022 (4ª etapa, desde 1/2/2025), igual para deputados, senadores, presidente e vice.
   Estadual e distrital: até 75% do federal (CF, art. 27, §2º). Vereador: 20% a 75% do estadual, conforme a população (CF, art. 29, VI). */
const SUBSIDIO_FEDERAL = 46366.19;
const SUBSIDIO_ESTADUAL_MAX = Math.round(SUBSIDIO_FEDERAL * 0.75 * 100) / 100;
const SUBSIDIO_VEREADOR_MAX = Math.round(SUBSIDIO_ESTADUAL_MAX * 0.75 * 100) / 100;
const DL172_URL = "https://www2.camara.leg.br/legin/fed/decleg/2022/decretolegislativo-172-21-dezembro-2022-793529-republicacao-166629-pl.html";
const fonteLink = (texto, url) => `<span class="fonte-link"><span class="rotulo-fonte">Fonte</span> ${urlSegura(url) ? `<a href="${esc(url)}" rel="noopener">${esc(texto)}</a>` : esc(texto)}</span>`;
export function linhaSubsidio(p) {
  const c = p.cargoTse;
  if (p.estado !== "atual") return ["Subsídio mensal", null];
  if (["DEPUTADO FEDERAL", "SENADOR", "PRESIDENTE", "VICE-PRESIDENTE"].includes(c))
    return ["Subsídio mensal bruto", `${reaisCentavos(SUBSIDIO_FEDERAL)} (valor desde fev. de 2025) ${fonteLink("Decreto Legislativo 172/2022", DL172_URL)}`, true];
  if (c === "DEPUTADO ESTADUAL" || c === "DEPUTADO DISTRITAL")
    return ["Subsídio mensal (teto legal)", `até ${reaisCentavos(SUBSIDIO_ESTADUAL_MAX)}, 75% do subsídio de deputado federal. É o máximo permitido, não o valor pago: o valor exato está no portal de transparência da Casa. ${fonteLink(`Constituição Federal, art. ${c === "DEPUTADO ESTADUAL" ? 27 : 32}`, linkCF(c === "DEPUTADO ESTADUAL" ? 27 : 32))}`, true];
  if (c === "VEREADOR")
    return ["Subsídio mensal (teto legal)", `de 20% a 75% do subsídio de deputado estadual, conforme a população do município; no máximo ${reaisCentavos(SUBSIDIO_VEREADOR_MAX)}. É o máximo permitido, não o valor pago: o valor exato está no portal de transparência da Câmara Municipal. ${fonteLink("Constituição Federal, art. 29, VI", linkCF(29))}`, true];
  return ["Subsídio mensal", null];
}


export const rotuloResultado = (r) => /turno/i.test(r) ? "Vai ao 2º turno" : ({ "eleito por qp": "Eleito por quociente partidário", "eleito por média": "Eleito por média", "eleito por media": "Eleito por média" })[r.toLowerCase()] || r;

/* Custo do voto (receita por voto) comparado à mediana dos eleitos do mesmo cargo e partido, e quanto da receita veio do partido. */
function blocoCustoDoVoto(c, e) {
  const partes = [];
  const v = c.custoVoto;
  if (v) {
    const turnos = (e.votos || []).length > 1 ? ", somando os turnos" : "";
    const comp = [v.cargo && `mediana dos eleitos para o mesmo cargo: ${reaisCentavos(v.cargo.mediana)} (${numeroBr(v.cargo.n)} eleitos)`,
      v.partido && `mediana do ${esc(e.partido)} nesse cargo: ${reaisCentavos(v.partido.mediana)} (${numeroBr(v.partido.n)} eleitos)`].filter(Boolean);
    partes.push(`<p>Custo do voto: <b>${reaisCentavos(v.valor)}</b> de receita de campanha por voto recebido${turnos}.${comp.length ? ` Para comparar, ${comp.join("; ")}.` : ""}</p>`);
  }
  const doPartido = (c.origensReceita || []).filter(([o]) => /partido pol[ií]tico/i.test(o)).reduce((t, [, x]) => t + x, 0);
  if (c.receitas && doPartido) partes.push(`<p>Dependência do partido: <b>${pctBr((100 * doPartido) / c.receitas)}</b> da receita veio de recursos do partido (fundo eleitoral e fundo partidário).</p>`);
  return partes.join("");
}

/* Total de bens declarado em cada eleição do mesmo político. A ligação entre eleições é por nome e data de nascimento (o TSE não publica mais o CPF). */
function blocoPatrimonio(p, fontesLista) {
  const h = p.patrimonio;
  if (!h || h.length < 2) return "";
  h.forEach(([ano]) => fontesLista.push([`Bens de candidatos ${ano} (TSE)`, arquivoTse("bem_candidato", { ano })]));
  const itens = h.map(([ano, cargo, total], i) => {
    const antes = i ? h[i - 1][2] : null;
    const variacao = antes === null ? "" : antes > 0 ? ` (${total >= antes ? "+" : "−"}${pctBr((100 * Math.abs(total - antes)) / antes)} em relação a ${h[i - 1][0]})` : ` (antes: ${reaisCentavos(antes)})`;
    return `<li><span class="quando">${esc(ano)}, ${esc(cargo.charAt(0) + cargo.slice(1).toLowerCase())}</span> <b>${reaisCentavos(total)}</b>${variacao}</li>`;
  });
  return `<h3>Evolução do patrimônio declarado</h3><ul class="lista-eleicao">${itens.join("")}</ul>
    <p>Valores declarados à Justiça Eleitoral em cada candidatura, sem correção pela inflação. As eleições foram ligadas pelo nome e pela data de nascimento, porque o TSE não publica mais o CPF.</p>`;
}

/* Evolução do patrimônio e as fontes da seção de bens. */
export function blocoPatrimonioFontes(p, fonteTse, outras = []) {
  const lista = [...fonteTse, ["Bens de candidatos (TSE)", arquivoTse("bem_candidato", p)], ["Portal de Dados Abertos do TSE", "https://dadosabertos.tse.jus.br"], ...outras];
  return blocoPatrimonio(p, lista) + fontes(lista);
}

/* Dinheiro da campanha (prestação de contas ao TSE): quanto arrecadou, de onde veio, quem mais doou e em que gastou. */
export function blocoCampanha(e, fontesLista) {
  const c = e.contas;
  if (!c) return e.ano < 2026 ? `<h3>Campanha de ${esc(e.ano)}</h3><p>${semFonte("prestação de contas desta eleição ainda não coletada")}</p>` : "";
  const linhas = (itens, rotuloDe) => `<ul class="lista-eleicao">${itens.map((x) => `<li>${rotuloDe(x)}</li>`).join("")}</ul>`;
  fontesLista.unshift([`Prestação de contas de campanha ${e.ano} (TSE)`, `${TSE_CDN}/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_${e.ano}.zip`]);
  return `<h3>Campanha de ${esc(e.ano)}: quem pagou</h3>
    <p>Arrecadou <b>${reaisCentavos(c.receitas)}</b> e contratou <b>${reaisCentavos(c.despesasContratadas)}</b> em despesas. ${c.despesasPagas != null && c.despesasContratadas - c.despesasPagas > 1 ? `Pagou <b>${reaisCentavos(c.despesasPagas)}</b> até a prestação de contas; <b>${reaisCentavos(c.despesasContratadas - c.despesasPagas)}</b> ficaram contratados e sem pagamento registrado.` : ""} Valores declarados pelo próprio candidato na prestação de contas ao TSE.</p>
    ${blocoCustoDoVoto(c, e)}
    ${c.origensReceita.length ? `<h4>De onde veio o dinheiro</h4>${linhas(c.origensReceita, ([o, v]) => `<span class="quando">${esc(o)}</span> <b>${reaisCentavos(v)}</b>${c.receitas ? ` (${Math.round((100 * v) / c.receitas)}%)` : ""}`)}` : ""}
    ${c.principaisDoadores.length ? `<h4>Maiores doadores</h4>${linhas(c.principaisDoadores, ([n, o, v]) => `<b>${esc(n)}</b> <span class="quando">${esc(o)}</span> <b>${reaisCentavos(v)}</b>`)}
      <p>"Recursos de partido político" inclui o fundo eleitoral e o fundo partidário repassados pelo partido.</p>` : ""}
    ${c.doadoresOriginarios && c.doadoresOriginarios.length ? `<h4>Quem está por trás dos repasses</h4>${linhas(c.doadoresOriginarios, ([n, v]) => `<b>${esc(n)}</b> <b>${reaisCentavos(v)}</b>`)}
      <p>Pessoas e empresas que doaram ao partido (ou a outro candidato) e tiveram o dinheiro repassado a esta campanha, segundo o TSE. O repasse de fundo público não tem doador originário.</p>` : ""}
    ${c.gastosPorCategoria.length ? `<h4>Em que gastou</h4>${linhas(c.gastosPorCategoria, ([g, v]) => `<span class="quando">${esc(g)}</span> <b>${reaisCentavos(v)}</b>`)}` : ""}`;
}

/* Fichas do TSE (dados/p/t/...) trazem uma vez só, em `_disputas`, o que os eleitos do mesmo cargo e local têm em comum
   (scripts/gerar_politicos.py, comuns_de). Monta a partir disso `disputa`, `partidoVotos` e `alianca` da ficha, como os
   blocos abaixo esperam; ficha que já os traz (eleição aninhada de senador e deputado) fica como está. */
export function completarEleicao(e, comuns) {
  if (!comuns || e.disputa !== undefined || e.partidoVotos !== undefined || e.alianca !== undefined) return e;
  const local = e.unidadeEleitoral;
  const disputa = comuns.disputa && comuns.disputa[`${e.cargoTse.replace("VICE-", "")}|${local}`];
  if (disputa) e.disputa = disputa;
  const votos = comuns.partidos && comuns.partidos[`${e.cargoTse}|${local}`];
  const p = votos && votos.partidos[e.partido];
  if (p) {
    e.partidoVotos = { votosLegenda: p[0], votosNominais: p[1], totalVotosPartidos: votos.totalVotos };
    if (p[2]) {
      const membros = Object.values(votos.partidos).filter((v) => v[2] === p[2]);
      Object.assign(e.partidoVotos, { federacao: p[2], votosLegendaFederacao: membros.reduce((t, v) => t + v[0], 0), votosNominaisFederacao: membros.reduce((t, v) => t + v[1], 0) });
    }
  }
  const aliancas = comuns.coligacoes && comuns.coligacoes[`${e.cargoTse}|${local}`];
  const i = aliancas && aliancas.coligacaoDoPartido[e.partido];
  if (i !== undefined && i !== null) {
    const [tipo, nome, composicao, situacao] = aliancas.coligacoes[i];
    e.alianca = { tipo, nome, composicao, situacao };
  }
  return e;
}

/* Comparecimento e vagas da eleição (TSE: detalhe da votação e vagas). */
export function blocoDisputa(e, fontesLista) {
  const d = e.disputa;
  if (!d) return e.ano < 2026 ? `<h3>Comparecimento e vagas</h3><p>${semFonte("comparecimento desta eleição ainda não coletado")}</p>` : "";
  fontesLista.push([`Detalhe da votação ${e.ano} (TSE)`, `${TSE_CDN}/detalhe_votacao_munzona/detalhe_votacao_munzona_${e.ano}.zip`]);
  if (d.vagas != null) fontesLista.push([`Vagas ${e.ano} (TSE)`, `${TSE_CDN}/consulta_vagas/consulta_vagas_${e.ano}.zip`]);
  const pct = (a, b) => (b ? `${((100 * a) / b).toFixed(1).replace(".", ",")}%` : "");
  const turnos = Object.entries(d.turnos).sort(([a], [b]) => a - b).map(([n, t]) => `<li><span class="quando">${esc(n)}º turno</span>
    ${numeroBr(t.aptos)} eleitores aptos · compareceram <b>${numeroBr(t.comparecimento)}</b> (${pct(t.comparecimento, t.aptos)}) · abstenção ${numeroBr(t.abstencoes)} (${pct(t.abstencoes, t.aptos)})
    · brancos ${numeroBr(t.brancos)} · nulos ${numeroBr(t.nulos)} · votos válidos ${numeroBr(t.validos)}</li>`).join("");
  return `<h3>Comparecimento e vagas</h3>${d.vagas != null ? `<p>Vagas em disputa neste cargo e local: <b>${numeroBr(d.vagas)}</b>.</p>` : ""}<ul class="lista-eleicao">${turnos}</ul>`;
}

/* Votos do partido (TSE: votação por partido): legenda, nominais e quociente eleitoral, nos cargos proporcionais. */
export function blocoPartido(e, fontesLista) {
  const v = e.partidoVotos;
  if (!v) return e.ano < 2026 && !MAJORITARIOS.has(e.cargoTse) ? `<h3>Votos do partido</h3><p>${semFonte("votos do partido nesta eleição")}</p>` : "";
  fontesLista.push([`Votação por partido ${e.ano} (TSE)`, `${TSE_CDN}/votacao_partido_munzona/votacao_partido_munzona_${e.ano}.zip`]);
  const pct = (a, b) => (b ? ` (${((100 * a) / b).toFixed(1).replace(".", ",")}%)` : "");
  const total = v.votosLegenda + v.votosNominais;
  const vagas = e.disputa && e.disputa.vagas;
  const qe = vagas ? v.totalVotosPartidos / vagas : 0;
  const nome = esc(e.partido);
  let html = `<h3>Votos do partido</h3><p>O ${nome} teve <b>${numeroBr(total)}</b> votos válidos${pct(total, v.totalVotosPartidos)}: <b>${numeroBr(v.votosNominais)}</b> em candidatos e <b>${numeroBr(v.votosLegenda)}</b> só na legenda (o eleitor digitou o número do partido).</p>`;
  if (v.federacao) html += `<p>O ${nome} concorreu na federação ${esc(v.federacao.replace(/\//g, " / "))}, que conta como um partido só para dividir as vagas: <b>${numeroBr(v.votosLegendaFederacao + v.votosNominaisFederacao)}</b> votos${pct(v.votosLegendaFederacao + v.votosNominaisFederacao, v.totalVotosPartidos)}, sendo ${numeroBr(v.votosLegendaFederacao)} de legenda.</p>`;
  if (qe) html += `<p>Quociente eleitoral: ${numeroBr(v.totalVotosPartidos)} votos válidos ÷ ${numeroBr(vagas)} vagas = <b>${numeroBr(Math.round(qe))}</b> votos por vaga. ${v.federacao ? "A federação" : "O partido"} teve ${((v.federacao ? v.votosLegendaFederacao + v.votosNominaisFederacao : total) / qe).toFixed(1).replace(".", ",")} quocientes.</p>`;
  return html;
}

/* Com quem o partido se aliou na eleição (TSE: consulta de coligações): tipo, partidos e situação da legenda. */
export function blocoAlianca(e, fontesLista) {
  const a = e.alianca;
  if (!a) return e.ano < 2026 ? `<h3>Alianças do partido</h3><p>${semFonte("coligação ou federação desta eleição")}</p>` : "";
  fontesLista.push([`Coligações e federações ${e.ano} (TSE)`, `${TSE_CDN}/consulta_coligacao/consulta_coligacao_${e.ano}.zip`]);
  const nome = esc(e.partido);
  const quais = esc(a.composicao.replace(/\(\d+-/g, "(").replace(/ \/ \d+-/g, " / "));
  const frase = { C: `O ${nome} concorreu em coligação${a.nome ? ` <b>${esc(a.nome)}</b>` : ""}, com os partidos: ${quais}.`,
    F: `O ${nome} concorreu em federação, que vale como um partido só: ${quais}.`,
    I: `O ${nome} concorreu sozinho, sem coligação nem federação.` }[a.tipo];
  const aviso = a.situacao && a.situacao !== "Deferido" ? ` Situação da legenda no TSE: <b>${esc(a.situacao)}</b>.` : "";
  return `<h3>Alianças do partido</h3><p>${frase}${aviso}</p>`;
}

/* Onde foi votado: mapa dos locais de votação com mais votos e, nos cargos estaduais e federais, os municípios. */
export function blocoOndeVotou(e, fontesLista) {
  const s = e.secoes;
  if (!s) return e.ano < 2026 ? `<h3>Onde foi votado</h3><p>${semFonte("votos por seção desta eleição ainda não coletados")}</p>` : "";
  fontesLista.push([`Votação por seção ${e.ano} (TSE)`, `${TSE_CDN}/votacao_secao/votacao_secao_${e.ano}_${e.uf}.zip`],
    [`Locais de votação ${e.ano} (TSE)`, `${TSE_CDN}/eleitorado_locais_votacao/eleitorado_local_votacao_${e.ano}.zip`]);
  const pct = (v) => (s.totalVotos ? ` (${((100 * v) / s.totalVotos).toFixed(1).replace(".", ",")}%)` : "");
  const pontos = (s.locaisDeVotacao || []).filter(([, la, lo]) => la != null && lo != null);
  let html = `<h3>Onde foi votado</h3><p>${(s.locaisDeVotacao || []).length ? "Locais de votação" : "Municípios"} com mais votos no ${esc(s.turno)}º turno de ${esc(e.ano)}, de um total de ${numeroBr(s.totalVotos)} votos.</p>`;
  if (pontos.length) html += `<div class="mapa-votos" role="img" aria-label="Mapa dos locais de votação com mais votos" data-pontos="${esc(JSON.stringify(pontos))}"></div>`;
  if (s.locaisDeVotacao && s.locaisDeVotacao.length) html += `<ol class="lista-eleicao">${s.locaisDeVotacao.map(([n, , , v]) => `<li>${esc(n)}: <b>${numeroBr(v)} votos</b>${pct(v)}</li>`).join("")}</ol>`;
  if (s.votosPorMunicipio && s.votosPorMunicipio.length) {
    fontesLista.push(["Malhas municipais (IBGE)", "https://servicodados.ibge.gov.br/api/v3/malhas"]);
    html += `<h4>Votos por município</h4><div class="mapa mapa-mun" role="img" aria-label="Mapa dos votos em cada município" data-uf="${esc(e.uf)}" data-votos-por-municipio="${esc(JSON.stringify(s.votosPorMunicipio))}"></div>
      <p class="legenda-mapa"><span>menos votos</span><i></i><span>mais votos</span></p>`;
  }
  if (s.municipios && s.municipios.length) html += `<h4>Municípios com mais votos</h4><ol class="lista-eleicao">${s.municipios.map(([n, v]) => `<li>${esc(n)}: <b>${numeroBr(v)} votos</b>${pct(v)}</li>`).join("")}</ol>`;
  return html;
}
