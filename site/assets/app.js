/* Minha Bancada — ponto de entrada. Cada página declara <body data-pagina="..."> e carrega só o módulo dela. */
import { moldura } from "./js/comum.js";

const PAGINAS = {
  inicio: ["politicos", "paginaPoliticos"],
  politico: ["politico", "paginaPolitico"],
  camara: ["camara", "paginaCamara"],
  fornecedores: ["fornecedores", "paginaFornecedores"],
  coautoria: ["coautoria", "paginaCoautoria"],
  ministerios: ["ministros", "paginaMinisterios"],
  ministro: ["ministros", "paginaMinistro"],
  deputado: ["deputado", "paginaDeputado"],
  votacoes: ["votacoes", "paginaVotacoes"],
  votacao: ["votacoes", "paginaVotacao"],
  proposicoes: ["proposicoes", "paginaProposicoes"],
  proposicao: ["proposicoes", "paginaProposicao"],
  fonte: ["fonte", "paginaFonte"],
  informado: ["informado", "paginaInformado"],
  historico: ["historico", "paginaHistorico"],
  sobre: ["status", "paginaSobre"],
};

const pagina = document.body.dataset.pagina;
moldura(pagina);
const destino = PAGINAS[pagina];
if (destino) (await import(`./js/${destino[0]}.js`))[destino[1]]();
