/* Página da Câmara: lista de deputados federais. */
import { esc, reais, pct } from "./util.js";
import { linkParlamentar } from "./apis.js";
import { listaParlamentares, metrica, celulaEmendas } from "./lista-parlamentares.js";

const taxa = (x) => (x ? x.seguiu / x.total : -1);
const contra = (d) => (d.fidelidade ? d.fidelidade.total - d.fidelidade.seguiu : -1);
const pctNum = (n) => `${Math.round(n * 100)}%`;

export const CONFIG_CAMARA = {
  arquivo: "dados/deputados.json",
  singular: "deputado",
  plural: "deputados",
  rotuloNome: "Deputado",
  href: (d) => linkParlamentar("camara", d.id),
  sub: (d) => `${esc(d.partido)}/${esc(d.uf)}${d.partidosAntes?.length ? ` <span class="troca" title="Passou por ${esc(d.partidosAntes.join(", "))} nesta legislatura (histórico da API da Câmara)">· trocou de partido</span>` : ""}`,
  colunas: [
    { rotulo: "Votou", celula: (d) => metrica(pct(d.votou, d.votacoes), "das votações") },
    { rotulo: "Proposições", largo: true, ordens: ["proposicoes"], celula: (d) => metrica(d.proposicoes, "apresentadas", { largo: true }) },
    { rotulo: "Iniciativas próprias", largo: true, ordens: ["proprias", "aprovadas"], celula: (d) => metrica(d.proprias, `${d.aprovadasProprias} aprovados`, { largo: true, titulo: `Projetos em que ${d.nome} é o primeiro a assinar, entre os ${d.autoriaColetada} com autoria já coletada` }) },
    { rotulo: "Fiel ao partido", largo: true, ordens: ["fidelidade", "contraPartido"], valor: (d) => (d.fidelidade ? taxa(d.fidelidade) : null), formato: pctNum,
      celula: (d, dica) => metrica(d.fidelidade ? pct(d.fidelidade.seguiu, d.fidelidade.total) : "—", d.fidelidade ? `${contra(d)} contra, de ${d.fidelidade.total}` : "sem orientação", { largo: true, titulo: ["Votações em que votou como o partido orientou, entre as que o partido orientou Sim, Não ou Obstrução", dica].filter(Boolean).join(". ") }) },
    { rotulo: "Pró-governo", largo: true, ordens: ["governismo"], valor: (d) => (d.governismo ? taxa(d.governismo) : null), formato: pctNum,
      celula: (d, dica) => metrica(d.governismo ? pct(d.governismo.seguiu, d.governismo.total) : "—", d.governismo ? `de ${d.governismo.total} votações` : "sem orientação", { largo: true, titulo: ["Votações em que votou como o Governo orientou, entre as que o Governo orientou Sim, Não ou Obstrução", dica].filter(Boolean).join(". ") }) },
    { rotulo: "Gastos no ano", largo: true, ordens: ["gasto"], valor: (d) => d.gasto, formato: (n) => reais(n), celula: (d, dica) => metrica(reais(d.gasto), "cota parlamentar", { largo: true, titulo: dica }) },
    { rotulo: "Emendas", largo: true, ordens: ["emendas"], celula: celulaEmendas },
  ],
  ordenadores: {
    nome: (a, b) => a.nome.localeCompare(b.nome, "pt-BR"),
    participacao: (a, b) => b.votou / (b.votacoes || 1) - a.votou / (a.votacoes || 1),
    proposicoes: (a, b) => b.proposicoes - a.proposicoes,
    gasto: (a, b) => b.gasto - a.gasto,
    proprias: (a, b) => b.proprias - a.proprias || b.aprovadasProprias - a.aprovadasProprias,
    aprovadas: (a, b) => b.aprovadasProprias - a.aprovadasProprias || b.proprias - a.proprias,
    suprapartidarios: (a, b) => b.suprapartidarios - a.suprapartidarios,
    fidelidade: (a, b) => taxa(b.fidelidade) - taxa(a.fidelidade),
    governismo: (a, b) => taxa(b.governismo) - taxa(a.governismo),
    contraPartido: (a, b) => contra(b) - contra(a),
    emendas: (a, b) => (b.empenhado || 0) - (a.empenhado || 0),
  },
};

export const paginaCamara = () => listaParlamentares(CONFIG_CAMARA);
