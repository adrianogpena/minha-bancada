/* "O que isso significou": tipo, título, resultado e efeito de cada votação ou marco da tramitação.
   Tudo sai de tabelas (TIPOS_VOTACAO, RESULTADO, REGRAS); nenhuma regra fica fora delas.
   A frase diz só o efeito do procedimento, nunca resume o conteúdo do projeto. Sem regra que sirva: "". */
import { marcarTermos } from "./glossario.js";

const PREFIXO_SENADO = /^Vota[çc][ãa]o nominal d(?:o|a|os|as)\s+/i;
const PLACAR_CAMARA = /\s*Sim:\s*\d+;.*$/s;
const VERBO_CAMARA = /^(?:Aprovad|Rejeitad)[oa]s?\s+(?:o|a|os|as)\s+/i;

/* Texto oficial sem o prefixo do Senado, sem o placar da Câmara, com "nº 299/2026" no lugar de "n° 299, de 2026". */
function limpar(texto) {
  return String(texto ?? "")
    .replace(PLACAR_CAMARA, "")
    .replace(PREFIXO_SENADO, "")
    .replace(VERBO_CAMARA, "")
    .replace(/\bn[°º]\s*/g, "nº ")
    .replace(/(nº \d+(?:\.\d+)*),?\s+de\s+(\d{4})/g, "$1/$2")
    .replace(/[\s.]+$/, "")
    .trim();
}

const excecao = (texto) =>
  /ressalvados os destaques/i.test(texto) ? ", exceto os trechos destacados"
    : /ressalvado o destaque/i.test(texto) ? ", exceto o trecho destacado" : "";

export const TIPOS_VOTACAO = [
  { tipo: "turno-suplementar", quando: /turno suplementar/i,
    titulo: (m) => /subemenda|redacion/i.test(m.input)
      ? "Ajustes finais do relator no turno suplementar (emendas, subemenda e correções de redação)"
      : "Votação em turno suplementar" },
  { tipo: "requerimento", quando: /^Requerimento\b/i, titulo: (m) => m.input },
  { tipo: "texto-principal", quando: /^Emenda nº (\d+) \(Substitutivo\)/i,
    titulo: (m, texto) => `Texto do relator (substitutivo, Emenda nº ${m[1]})${excecao(texto)}` },
  { tipo: "texto-principal", quando: /^(Subemenda Substitutiva|Substitutivo)\b/i,
    titulo: (m, texto) => `Texto do relator (${m[1].toLowerCase()})${excecao(texto)}` },
  { tipo: "destaque-trecho", quando: /^(?:Art\.|Artigo|§|Par[áa]grafo|Inciso|Al[íi]nea|Cap[íi]tulo|Se[çc][ãa]o)/i,
    titulo: (m) => {
      const t = m.input.replace(/,?\s*destacad[oa]s?\s*$/i, "");
      const c = t.match(/^(Art\.\s*\S+)\s+(d[ao]\s+.+?),\s*constante\s+d[oa]\s+(art\.\s*\S+)\s+d[oa]\s+Substitutivo\b/i);
      if (c) return `${c[1]} ${c[2]}, como fica pelo ${c[3]} do substitutivo`;
      const s = t.match(/^(.+?)\s+d[oa]\s+Substitutivo\b/i);
      return s ? `${s[1]} do substitutivo` : t;
    } },
  { tipo: "destaque-emenda", quando: /^(Emenda nº \d+)\b.*\bdestacad[oa]s?\b/i, titulo: (m) => m[1] },
  { tipo: "emenda", quando: /^Emendas?(?: de Plenário)?(?: nº \d+)?/i, titulo: (m) => m[0] },
  { tipo: "redacao-final", quando: /reda[çc][ãa]o final/i, titulo: () => "Redação final" },
];

/* {tipo, titulo} do texto oficial da votação. Sem regra: {tipo: "outro", titulo: texto}. */
export function classificarVotacao(texto) {
  const limpo = limpar(texto);
  for (const r of TIPOS_VOTACAO) {
    const m = limpo.match(r.quando);
    if (m) return { tipo: r.tipo, titulo: r.titulo(m, String(texto)) };
  }
  return { tipo: "outro", titulo: texto };
}

/* Palavra do resultado por tipo: [quando aprovada, quando rejeitada]. */
export const RESULTADO = {
  "requerimento": ["Aprovado", "Rejeitado"],
  "texto-principal": ["Aprovado", "Rejeitado"],
  "destaque-emenda": ["Aprovada", "Rejeitada"],
  "destaque-trecho": ["Mantido", "Retirado"],
  "turno-suplementar": ["Aprovados", "Rejeitados"],
  "emenda": ["Aprovada", "Rejeitada"],
  "redacao-final": ["Aprovada", "Rejeitada"],
  "outro": ["Aprovado", "Rejeitado"],
};

/* "Aprovado por 40 a 38": o maior número vem primeiro. Sem placar ou sem resultado: "". */
export function rotuloResultado({ tipo, aprovada, placar } = {}) {
  if (aprovada == null || !placar || !Number.isFinite(placar.sim) || !Number.isFinite(placar.nao)) return "";
  const [sim, nao] = RESULTADO[tipo] || RESULTADO.outro;
  return `${aprovada ? sim : nao} por ${Math.max(placar.sim, placar.nao)} a ${Math.min(placar.sim, placar.nao)}`;
}

const ASSUNTOS_REQUERIMENTO = {
  "urgência": { aprovada: "o projeto passou a tramitar com urgência.", rejeitada: "o pedido de urgência não foi aprovado; o projeto segue o ritmo normal." },
};
const assuntoDe = (m, contexto) => contexto.assunto || (/urg[êe]ncia/i.test(m.input) ? "urgência" : "");
const frasePlural = (m, um, varios) => (/\bEmendas\b/i.test(m.input) ? varios : um);

/* Regras de efeito. `aprovada` chega como 1/0/null; resultado null vale para qualquer um (e para eventos). */
export const REGRAS = [
  { quando: /./s, resultado: "aprovada", tipo: "requerimento", frase: (m, c) => ASSUNTOS_REQUERIMENTO[assuntoDe(m, c)]?.aprovada || "" },
  { quando: /./s, resultado: "rejeitada", tipo: "requerimento", frase: (m, c) => ASSUNTOS_REQUERIMENTO[assuntoDe(m, c)]?.rejeitada || "" },
  { quando: /./s, resultado: "aprovada", tipo: "texto-principal", frase: (m) => {
    const nome = /Subemenda/i.test(m.input) ? "a subemenda substitutiva" : "o substitutivo";
    const base = `${nome} passou a ser o texto do projeto; o texto original e as outras emendas ficaram prejudicados.`;
    if (/ressalvados os destaques/i.test(m.input)) return `${base} Os trechos destacados ficaram para votação separada (ressalvados os destaques).`;
    if (/ressalvado o destaque/i.test(m.input)) return `${base} O trecho destacado ficou para votação separada (ressalvado o destaque).`;
    return base;
  } },
  { quando: /./s, resultado: "rejeitada", tipo: "texto-principal", frase: () => "o texto proposto pelo relator não passou a ser o texto do projeto." },
  { quando: /./s, resultado: "aprovada", tipo: "destaque-emenda", frase: (m) => frasePlural(m, "a mudança proposta pela emenda entrou no texto.", "as mudanças propostas pelas emendas entraram no texto.") },
  { quando: /./s, resultado: "rejeitada", tipo: "destaque-emenda", frase: (m) => frasePlural(m, "a mudança proposta pela emenda não entrou no texto.", "as mudanças propostas pelas emendas não entraram no texto.") },
  { quando: /./s, resultado: "aprovada", tipo: "emenda", frase: (m) => frasePlural(m, "a mudança proposta pela emenda entrou no texto.", "as mudanças propostas pelas emendas entraram no texto.") },
  { quando: /./s, resultado: "rejeitada", tipo: "emenda", frase: (m) => frasePlural(m, "a mudança proposta pela emenda não entrou no texto.", "as mudanças propostas pelas emendas não entraram no texto.") },
  { quando: /./s, resultado: "aprovada", tipo: "destaque-trecho", frase: () => "o trecho continua no texto." },
  { quando: /./s, resultado: "rejeitada", tipo: "destaque-trecho", frase: () => "o trecho saiu do texto." },
  { quando: /./s, resultado: "aprovada", tipo: "turno-suplementar", frase: () => "os ajustes do relator entraram no texto e o turno suplementar terminou." },
  { quando: /./s, resultado: "rejeitada", tipo: "turno-suplementar", frase: () => "os ajustes do relator não entraram no texto." },
  { quando: /./s, resultado: "aprovada", tipo: "redacao-final", frase: () => "o texto recebeu a sua redação final." },

  { quando: /veto.*(?:rejeitad|derrubad)|(?:rejeitad|derrubad).*veto/i, resultado: null, tipo: "evento", frase: () => "o Congresso derrubou o veto; o trecho vetado volta ao texto da lei." },
  { quando: /vetad[oa]\s+parcialmente|veto parcial/i, resultado: null, tipo: "evento", frase: () => "o presidente da República recusou alguns trechos; o Congresso ainda decide se mantém ou derruba o veto." },
  { quando: /vetad[oa]\s+totalmente|veto total/i, resultado: null, tipo: "evento", frase: () => "o presidente da República recusou o projeto inteiro; o Congresso ainda decide se mantém ou derruba o veto." },
  { quando: /remetid[oa]\s+à\s+Câmara dos Deputados/i, resultado: null, tipo: "evento", frase: () => "o Senado terminou a sua parte; agora a Câmara, como Casa revisora, analisa o texto." },
  { quando: /remetid[oa]\s+ao\s+Senado Federal/i, resultado: null, tipo: "evento", frase: () => "a Câmara terminou a sua parte; agora o Senado, como Casa revisora, analisa o texto." },
  { quando: /remetid[oa]\s+à\s+san[çc][ãa]o/i, resultado: null, tipo: "evento", frase: () => "o Congresso terminou a votação; o texto vai ao presidente da República, que pode sancionar ou vetar." },
  { quando: /transformad[oa]\s+em\s+(?:norma|lei)/i, resultado: null, tipo: "evento", frase: () => "o texto virou norma jurídica." },
  { quando: /arquivad[oa]\s+ao\s+final\s+da\s+legislatura/i, resultado: null, tipo: "evento", frase: () => "a proposição não foi concluída até o fim da legislatura e deixou de tramitar; só volta a ser analisada se for desarquivada." },
  { quando: /arquivad[oa]/i, resultado: null, tipo: "evento", frase: () => "a proposição deixou de tramitar; só volta a ser analisada se for desarquivada." },
];

/* HTML da frase do efeito (com "?" nos termos do glossário), ou "" se nenhuma regra serve. */
export function significado({ texto, aprovada, tipo, contexto = {} } = {}) {
  const t = String(texto ?? "");
  const tp = tipo || classificarVotacao(t).tipo;
  const res = aprovada == null ? null : aprovada ? "aprovada" : "rejeitada";
  for (const r of REGRAS) {
    if (r.tipo && r.tipo !== tp) continue;
    if (r.resultado && r.resultado !== res) continue;
    const m = t.match(r.quando);
    if (!m) continue;
    const frase = r.frase(m, contexto);
    if (frase) return marcarTermos(frase);
  }
  return "";
}
