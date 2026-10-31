/* Página do Senado: lista de senadores em exercício. */
import { esc, reais, pct } from "./util.js";
import { linkParlamentar } from "./apis.js";
import { listaParlamentares, metrica, celulaEmendas } from "./lista-parlamentares.js";

const taxa = (x) => (x ? x.seguiu / x.total : -1);

export const CONFIG_SENADO = {
  arquivo: "dados/senado.json",
  singular: "senador",
  plural: "senadores",
  rotuloNome: "Senador",
  href: (s) => linkParlamentar("senado", s.id),
  sub: (s) => `${esc(s.partido || "")}/${esc(s.uf)}${s.participacao && s.participacao !== "Titular" ? `, ${esc(s.participacao.toLowerCase())}` : ""}`,
  colunas: [
    { rotulo: "Presença", celula: (s) => metrica(s.votacoes ? pct(s.compareceu, s.votacoes) : "—", "das votações") },
    { rotulo: "Proposições", largo: true, ordens: ["proposicoes"], celula: (s) => metrica(s.proposicoes, "apresentadas", { largo: true }) },
    { rotulo: "Iniciativas próprias", largo: true, ordens: ["proprias"], celula: (s) => metrica(s.proprias, "como autor principal", { largo: true, titulo: `Projetos em que ${s.nome} é o primeiro a assinar` }) },
    { rotulo: "Com o partido", largo: true, ordens: ["partido"], valor: (s) => (s.alinhamentoPartido ? s.alinhamentoPartido.seguiu / s.alinhamentoPartido.total : null), formato: (n) => `${Math.round(n * 100)}%`,
      celula: (s, dica) => metrica(s.alinhamentoPartido ? pct(s.alinhamentoPartido.seguiu, s.alinhamentoPartido.total) : "—", s.alinhamentoPartido ? `de ${s.alinhamentoPartido.total} votos` : "sem dados", { largo: true, titulo: ["Votos Sim ou Não iguais ao da maioria dos colegas de partido na mesma votação (o Senado não publica orientação de bancada)", dica].filter(Boolean).join(". ") }) },
    { rotulo: "Mandato até", largo: true, celula: (s) => metrica(s.fimMandato ? esc(s.fimMandato.slice(0, 4)) : "—", "fim do mandato", { largo: true }) },
    { rotulo: "Gastos no ano", largo: true, ordens: ["gasto"], valor: (s) => s.gasto, formato: (n) => reais(n), celula: (s, dica) => metrica(s.gasto == null ? "—" : reais(s.gasto), "cota parlamentar", { largo: true, titulo: dica }) },
    { rotulo: "Emendas", largo: true, ordens: ["emendas"], celula: celulaEmendas },
  ],
  ordenadores: {
    nome: (a, b) => a.nome.localeCompare(b.nome, "pt-BR"),
    presenca: (a, b) => b.compareceu / (b.votacoes || 1) - a.compareceu / (a.votacoes || 1),
    proposicoes: (a, b) => b.proposicoes - a.proposicoes,
    proprias: (a, b) => b.proprias - a.proprias,
    gasto: (a, b) => (b.gasto || 0) - (a.gasto || 0),
    partido: (a, b) => taxa(b.alinhamentoPartido) - taxa(a.alinhamentoPartido),
    emendas: (a, b) => (b.empenhado || 0) - (a.empenhado || 0),
  },
};

export const paginaSenado = () => listaParlamentares(CONFIG_SENADO);
