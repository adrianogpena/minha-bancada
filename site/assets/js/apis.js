/* Constantes e URLs das fontes: APIs, UFs, desfecho de proposições, links de tramitação e fontes legíveis. */
import { esc, semAcento, urlSegura } from "./util.js";

export const TSE_CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele";
export const arquivoTse = (conjunto, p) => `${TSE_CDN}/${conjunto}/${conjunto}_${p.ano}.zip`;
export const arquivoRedesTse = (p) => `${TSE_CDN}/consulta_cand/rede_social_candidato_${p.ano}${p.ano === 2022 ? `_${p.uf === "BR" ? "BR" : p.uf}` : ""}.zip`;

export const CAMARA_API = "https://dadosabertos.camara.leg.br/api/v2";
/* Votação com resultado final (aprovada ou rejeitada); sem isso não entra na lista de votações do parlamentar. */
export const temResultado = (v) => v.aprovada === 0 || v.aprovada === 1;
export const resultado = (a) => (a === 1 ? ["Aprovada", "aprovada"] : a === 0 ? ["Rejeitada", "rejeitada"] : ["Sem resultado informado", "sem"]);

// projetos de verdade; o resto (requerimentos, emendas, pareceres) só aparece em "Outros documentos"
export const TIPOS_PROJETO = { PL: "Projeto de lei", PLP: "Projeto de lei complementar", PEC: "Proposta de emenda à Constituição", PDL: "Projeto de decreto legislativo",
  PRC: "Projeto de resolução", PLC: "Projeto de lei da Câmara", PLS: "Projeto de lei do Senado", PRS: "Projeto de resolução do Senado", PDS: "Projeto de decreto legislativo do Senado", PLN: "Projeto de lei do Congresso", PFC: "Proposta de fiscalização e controle", PLV: "Projeto de lei de conversão", MPV: "Medida provisória" };

/* Projeto com a situação atualizada no ano `ano`, qualquer que seja o desfecho (o que a página destaca no topo das propostas). */
export const movimentadoNoAno = (p, ano) => String(p.dataSituacao || "").startsWith(String(ano));

// resume a situação da Câmara em um destino compreensível
export function desfecho(p) {
  const s = semAcento(p.situacao || "");
  // a Câmara só deixa a situação vazia enquanto o projeto tramita (os desfechos sempre trazem situação); com tramitação lida, não é "não consultada"
  if (!p.situacao) return p.tramitacao || p.dataSituacao ? ["Em tramitação", "tramitando", "andamento"] : ["Situação ainda não consultada", "sem"];
  if (/tramitacao encerrada/.test(s)) return ["Tramitação encerrada", "sem"];
  if (/^(sancionad|promulgad)/.test(s)) return ["Aprovada", "aprovada"];
  if (/^aprovad/.test(s)) return ["Aprovada", "aprovada", "andamento"];
  if (/^rejeitad/.test(s)) return ["Rejeitada", "rejeitada"];
  if (/transformad[ao] em norma|transformad[ao] em lei|sancionad/.test(s)) return ["Virou lei", "aprovada"];
  if (/arquivad/.test(s)) return ["Arquivada", "rejeitada"];
  if (/retirad/.test(s)) return ["Retirada pelo autor", "rejeitada"];
  if (/vetad/.test(s)) return ["Vetada", "rejeitada"];
  if (/prejudicad/.test(s)) return ["Prejudicada", "rejeitada"];
  if (/remetid[ao] a camara/.test(s)) return ["Aprovada no Senado", "aprovada", "andamento"];
  if (/aguardando sancao|remetid.*(sancao|senado)/.test(s)) return ["Aprovada na Câmara", "aprovada", "andamento"];
  return ["Em tramitação", "tramitando", "andamento"];
}

export const linkTramitacao = (id) => `https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=${encodeURIComponent(id)}`;

/* Endereço da versão legível de um link de API: reaproveita as páginas do site quando existem
   (votação, deputado) e cai na página genérica fonte.html nos demais. Null se não for uma API. */
export const HOST_API = /\.(leg|gov|jus)\.br$/;
export function urlLegivel(h) {
  let u;
  try { u = new URL(h); } catch { return null; }
  if (u.protocol !== "https:" || !HOST_API.test(u.hostname)) return null;
  if (!/^\/(api\/|dadosabertos\/|adm-dadosabertos\/)/.test(u.pathname) || /\.(zip|csv|pdf)$/i.test(u.pathname)) return null;
  if (u.hostname === "dadosabertos.camara.leg.br" && !u.search) {
    let m = u.pathname.match(/^\/api\/v2\/votacoes\/([^/]+?)(\/votos)?\/?$/);
    if (m) return `votacao.html?id=${m[1]}`;
    m = u.pathname.match(/^\/api\/v2\/deputados\/(\d+)\/?$/);
    if (m) return `deputado.html?id=${m[1]}`;
  }
  return `fonte.html?u=${encodeURIComponent(h)}`;
}

export function fontes(links) {
  links = links.filter((l) => l && urlSegura(l[1]));
  if (!links.length) return "";
  const item = ([t, h]) => {
    const l = urlLegivel(h);
    const json = `<a href="${esc(h)}" rel="noopener">${esc(t)}</a>`;
    return l ? `<span class="fonte-par">${json} <a class="ver-legivel" href="${esc(l)}">ver legível</a></span>` : json;
  };
  return `<span class="fontes"><span class="rotulo-fonte">Fonte</span><span class="fontes-lista">${links.map(item).join("")}</span></span>`;
}


export const UFS = { AC: "Acre", AL: "Alagoas", AP: "Amapá", AM: "Amazonas", BA: "Bahia", CE: "Ceará", DF: "Distrito Federal",
  ES: "Espírito Santo", GO: "Goiás", MA: "Maranhão", MT: "Mato Grosso", MS: "Mato Grosso do Sul", MG: "Minas Gerais",
  PA: "Pará", PB: "Paraíba", PR: "Paraná", PE: "Pernambuco", PI: "Piauí", RJ: "Rio de Janeiro", RN: "Rio Grande do Norte",
  RS: "Rio Grande do Sul", RO: "Rondônia", RR: "Roraima", SC: "Santa Catarina", SP: "São Paulo", SE: "Sergipe", TO: "Tocantins" };

// grupos na ordem em que aparecem; k = ordem do cargo vinda do gerador

export const UF_COD = { 11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO", 21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
  28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR", 42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF" };
export const COD_UF = Object.fromEntries(Object.entries(UF_COD).map(([c, u]) => [u, c]));
export const MALHAS = "https://servicodados.ibge.gov.br/api/v3/malhas";

export const SENADO_API = "https://legis.senado.leg.br/dadosabertos";
export const SENADO_ADM_API = "https://adm.senado.gov.br/adm-dadosabertos/api/v1";
export const linkMateriaSenado = (id) => `https://www25.senado.leg.br/web/atividade/materias/-/materia/${encodeURIComponent(id)}`;

/* Inabilitações do TCU para cargo ou função pública (coletar_tcu.py; ligadas à pessoa em identidades.py: ligar_inabilitados). */
export const TCU_INABILITADOS = "https://contas.tcu.gov.br/ords/condenacao/consulta/inabilitados";
export async function carregarInabilitacoes(pessoa, carregar) {
  if (!pessoa) return [];
  try { return (await carregar("dados/inabilitados_tcu.json"))[pessoa] || []; } catch { return []; }
}

/* Aposentadoria parlamentar de ex-senador (coletar.py: coletar_aposentados_senado; ligada à pessoa em identidades.py). */
export async function carregarAposentadoria(pessoa, carregar) {
  if (!pessoa) return null;
  try { return (await carregar("dados/aposentados_senado.json"))[pessoa] || null; } catch { return null; }
}
