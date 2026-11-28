/* Glossário único do site: termo com "?" e explicação aberta logo abaixo do bloco.
   Regra para um termo entrar (a mesma está no CLAUDE.md, seção Convenções):
   1. Aparece num texto que o site mostra (rótulo, situação, descrição de votação, nome de cargo ou de verba).
   2. É jargão legislativo, jurídico, orçamentário ou eleitoral, ou sigla, que um leigo não entenderia pelo contexto.
   3. Dá para explicar em até 2 frases, sem opinião, com fonte oficial.
   Fica de fora: palavra comum, termo explicado no próprio texto, nome próprio e termo sem fonte oficial (avise o usuário).
   Candidatos: python scripts/glossario_candidatos.py; quem aprova é o usuário. */
import { esc } from "./util.js";
import { linkCF } from "./ficha.js";

const SENADO_GLOSSARIO = "https://www12.senado.leg.br/noticias/glossario-legislativo";
const RISF = "https://www25.senado.leg.br/web/atividade/legislacao/regimento-interno";
const SITUACOES = "https://legis.senado.leg.br/dadosabertos/processo/tipos-situacao";
const doGlossario = (ancora) => ({ rotulo: "Glossário legislativo do Senado", url: `${SENADO_GLOSSARIO}#${ancora}-legislativo` });
const daCF = (art) => ({ rotulo: `Constituição Federal, art. ${art}`, url: linkCF(art) });
const doRegimento = { rotulo: "Regimento Interno do Senado Federal", url: RISF };

export const GLOSSARIO = [
  { id: "iniciadora", termo: "Casa iniciadora", variantes: ["casa iniciadora", "iniciadora"],
    definicao: "A Casa (Câmara ou Senado) onde o projeto foi apresentado e votado primeiro.", fonte: daCF(65) },
  { id: "revisora", termo: "Casa revisora", variantes: ["casa revisora", "revisora"],
    definicao: "A outra Casa, que revisa o texto aprovado pela iniciadora. Se mudar o texto, ele volta à Casa iniciadora para a palavra final.", fonte: daCF(65) },
  { id: "lei-complementar", termo: "Lei complementar", variantes: ["lei complementar", "leis complementares"],
    definicao: "Lei que trata de temas que a Constituição manda regular por esse tipo de lei. Para ser aprovada precisa de maioria absoluta: 41 senadores e 257 deputados.", fonte: daCF(69) },
  { id: "sancao-veto", termo: "Sanção ou veto", variantes: ["sanção ou veto", "sanção", "veto", "vetos"],
    definicao: "Depois de aprovado pelas duas Casas, o projeto vai ao Presidente da República, que tem 15 dias úteis para sancionar (vira lei) ou vetar, no todo ou em parte. O Congresso pode derrubar o veto.", fonte: daCF(66) },
  { id: "rmcd", termo: "RMCD", variantes: ["RMCD"],
    definicao: "Sigla do Senado para “Remetida à Câmara dos Deputados”: o Senado terminou a sua parte e enviou o projeto à Câmara.", fonte: { rotulo: "Dados Abertos do Senado, tipos de situação", url: SITUACOES } },
  { id: "urgencia", termo: "Urgência", variantes: ["regime de urgência", "urgência"],
    definicao: "Regime que acelera o projeto: dispensa prazos e etapas, como a passagem por comissões, e leva o texto direto à votação no Plenário.", fonte: doGlossario("regime-de-urgencia") },
  { id: "relator", termo: "Relator", variantes: ["relator", "relatora", "relatores", "relatoria"],
    definicao: "Parlamentar escolhido para estudar o projeto e as emendas e recomendar ao colegiado se deve ser aprovado, com ou sem mudanças.", fonte: doRegimento },
  { id: "parecer", termo: "Parecer", variantes: ["parecer", "pareceres"],
    definicao: "Documento do relator (ou da comissão) com a recomendação sobre o projeto e as emendas: aprovar, aprovar com mudanças ou rejeitar.", fonte: doGlossario("parecer") },
  { id: "emenda", termo: "Emenda", variantes: ["emenda", "emendas"],
    definicao: "Proposta de mudança no texto do projeto, apresentada por um parlamentar. Só vale se for aprovada.", fonte: doRegimento },
  { id: "subemenda", termo: "Subemenda", variantes: ["subemenda", "subemendas"],
    definicao: "Mudança proposta dentro de uma emenda, para ajustar o texto dela.", fonte: doRegimento },
  { id: "substitutivo", termo: "Substitutivo", variantes: ["substitutivo", "substitutivos"],
    definicao: "Emenda que reescreve o projeto inteiro. Se aprovado, o texto dele passa a valer no lugar do original.", fonte: doGlossario("substitutivo") },
  { id: "destaque", termo: "Destaque", variantes: ["destaque", "destaques", "destacado", "destacada", "destacados", "destacadas"],
    definicao: "Pedido para votar um trecho do texto ou uma emenda em separado, depois do texto principal. Num trecho do texto, “sim” o mantém e “não” o retira; numa emenda, “sim” a inclui.", fonte: doGlossario("destaque-para-votacao-em-separado-dvs") },
  { id: "ressalvados", termo: "Ressalvados os destaques", variantes: ["ressalvados os destaques", "ressalvado o destaque", "ressalvados", "ressalvadas", "ressalvado", "ressalvada"],
    definicao: "O texto principal foi aprovado, menos os trechos destacados, que ainda seriam votados um a um.", fonte: doGlossario("destaque-para-votacao-em-separado-dvs") },
  { id: "prejudicado", termo: "Prejudicado", variantes: ["prejudicado", "prejudicados", "prejudicada", "prejudicadas"],
    definicao: "Deixa de ser votado porque perdeu o sentido, por exemplo quando outro texto aprovado já tratou do mesmo ponto.", fonte: doGlossario("prejudicialidade") },
  { id: "turno-suplementar", termo: "Turno suplementar", variantes: ["turno suplementar"],
    definicao: "No Senado, quando um substitutivo é aprovado em turno único, o texto passa por mais uma rodada de discussão e votação, em que ainda se podem apresentar emendas.", fonte: doGlossario("turno-suplementar") },
  { id: "ordem-do-dia", termo: "Ordem do Dia (pauta)", variantes: ["ordem do dia", "pauta"],
    definicao: "Lista do que será discutido e votado numa sessão do Plenário.", fonte: doGlossario("ordem-do-dia") },
  { id: "questao-de-ordem", termo: "Questão de ordem", variantes: ["questão de ordem", "questões de ordem"],
    definicao: "Dúvida sobre como aplicar o regimento, levantada por um parlamentar durante a sessão; quem decide é o presidente da sessão, e cabe recurso ao Plenário.", fonte: doGlossario("questao-de-ordem") },
  { id: "redacao-final", termo: "Redação final", variantes: ["redação final"],
    definicao: "Versão final do texto aprovado, com os ajustes de forma, que segue para a outra Casa ou para a sanção.", fonte: doRegimento },
  { id: "autografo", termo: "Autógrafo", variantes: ["autógrafo", "autógrafos"],
    definicao: "O texto final aprovado por uma Casa, assinado e enviado à outra Casa ou à sanção.", fonte: doGlossario("autografo") },
  { id: "terminativo", termo: "Terminativo", variantes: ["terminativo", "terminativa", "terminativos", "terminativas", "decisão terminativa"],
    definicao: "Quando a comissão decide no lugar do Plenário: se aprovar e ninguém recorrer, o projeto segue sem passar pelo Plenário.", fonte: doGlossario("decisao-terminativa") },
  { id: "aguardando-despacho", termo: "Aguardando despacho", variantes: ["aguardando despacho"],
    definicao: "O projeto foi apresentado e espera o presidente da Casa decidir por quais comissões (ou se direto ao Plenário) ele vai passar.", fonte: doRegimento },
  { id: "suplente", termo: "Suplente", variantes: ["suplente", "suplentes"],
    definicao: "Quem foi o próximo mais votado do partido ou da coligação e assume o mandato quando o titular deixa a vaga, assume outro cargo previsto na Constituição ou fica licenciado por mais de 120 dias.", fonte: daCF(56) },
  { id: "licenca", termo: "Licença", variantes: ["licenciado", "licenciada", "licenciados", "licença", "licenças"],
    definicao: "Afastamento temporário em que o parlamentar não perde o mandato: por doença, por interesse particular (até 120 dias por sessão legislativa, sem remuneração) ou para ocupar cargo como o de ministro de Estado.", fonte: daCF(56) },
  { id: "empenho", termo: "Empenho", variantes: ["empenhado", "empenhados", "empenhada", "empenhadas", "empenho", "empenhos"],
    definicao: "Primeira etapa da despesa pública: o governo reserva o valor e assume a obrigação de pagar. Empenhar não é pagar; o dinheiro só sai depois da liquidação e do pagamento.", fonte: { rotulo: "Lei 4.320/1964, art. 58", url: "https://www.planalto.gov.br/ccivil_03/leis/l4320.htm" } },
  { id: "liquidacao", termo: "Liquidação", variantes: ["liquidado", "liquidados", "liquidada", "liquidadas", "liquidação"],
    definicao: "Etapa da despesa pública em que se confere se o serviço foi prestado ou o bem entregue, para só então autorizar o pagamento.", fonte: { rotulo: "Lei 4.320/1964, art. 63", url: "https://www.planalto.gov.br/ccivil_03/leis/l4320.htm" } },
  { id: "emenda-pix", termo: "Emenda Pix", variantes: ["emenda pix", "emendas pix", "transferência especial", "transferências especiais"],
    definicao: "Emenda individual ao orçamento que envia o dinheiro direto ao caixa do estado ou do município, sem convênio. O nome oficial é transferência especial.", fonte: { rotulo: "Constituição Federal, art. 166-A", url: linkCF("166a") } },
  { id: "ceap", termo: "CEAP", variantes: ["CEAP"],
    definicao: "Cota para o Exercício da Atividade Parlamentar: valor mensal que cada deputado federal pode gastar, com comprovante, em despesas do mandato, como passagens, aluguel de escritório e divulgação.", fonte: { rotulo: "Câmara dos Deputados, cota parlamentar", url: "https://www2.camara.leg.br/comunicacao/assessoria-de-imprensa/guia-para-jornalistas/cota-parlamentar" } },
  { id: "ceaps", termo: "CEAPS", variantes: ["CEAPS"],
    definicao: "Cota para o Exercício da Atividade Parlamentar dos Senadores: valor que o Senado reembolsa a cada senador por despesas do mandato, como passagens, aluguel de escritório e divulgação.", fonte: { rotulo: "Portal da Transparência do Senado", url: "https://www6g.senado.leg.br/transparencia/sen/" } },
  { id: "ata-registro-precos", termo: "Ata de registro de preços", variantes: ["ata de registro de preços", "atas de registro de preços", "ata de registro de preço", "atas de registro de preço"],
    definicao: "Documento que registra o fornecedor e os preços de uma licitação para compras futuras. O órgão pode comprar até o valor registrado, mas não é obrigado a comprar.", fonte: { rotulo: "Lei 14.133/2021, arts. 6º e 83", url: "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm" } },
];

const PORID = new Map(GLOSSARIO.map((t) => [t.id, t]));

/* Botão "?" de um termo: `texto` é o que aparece (padrão: o nome do termo). */
export const termo = (id, texto) => {
  const t = PORID.get(id);
  const visivel = texto ?? t?.termo ?? id;
  return `<button type="button" class="termo" data-termo="${esc(id)}" aria-expanded="false" aria-label="${esc(visivel)}: o que é?">${esc(visivel)}</button>`;
};

/* Texto minúsculo e sem acento, com o mesmo comprimento do original (índices valem nos dois). */
const simples = (s) => Array.from(s, (c) => { const n = c.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase(); return n.length === 1 ? n : c; }).join("");
const ehSigla = (v) => v.length >= 2 && v === v.toUpperCase() && v !== v.toLowerCase();
const letra = /[\p{L}\p{N}]/u;

const BUSCAS = GLOSSARIO.flatMap((t) => t.variantes.map((v) => ({ id: t.id, v, sigla: ehSigla(v), chave: ehSigla(v) ? v : simples(v) })))
  .sort((a, b) => b.v.length - a.v.length);

function ocorrencias(texto, norm, b) {
  const base = b.sigla ? texto : norm;
  const achados = [];
  for (let i = base.indexOf(b.chave); i >= 0; i = base.indexOf(b.chave, i + 1)) {
    const fim = i + b.chave.length;
    if ((i > 0 && letra.test(base[i - 1])) || (fim < base.length && letra.test(base[fim]))) continue;
    achados.push([i, fim]);
  }
  return achados;
}

/* Põe o "?" na 1ª ocorrência de cada termo do bloco, só no texto entre tags e fora de <a> e <button>. */
export function marcarTermos(html) {
  const pedacos = String(html ?? "").split(/(<[^>]*>)/);
  let dentro = 0;
  const textos = [];
  pedacos.forEach((p, i) => {
    if (p.startsWith("<")) {
      if (/^<(a|button)[\s>]/i.test(p)) dentro++;
      else if (/^<\/(a|button)\s*>/i.test(p)) dentro = Math.max(0, dentro - 1);
    } else if (p && !dentro) textos.push({ i, texto: p, norm: simples(p), usado: [] });
  });
  /* Todas as ocorrências, das variantes mais longas às mais curtas, sem sobreposição; depois fica a 1ª (no texto) de cada termo. */
  const aceitas = [];
  for (const b of BUSCAS) {
    for (const t of textos) {
      for (const [a, z] of ocorrencias(t.texto, t.norm, b)) {
        if (t.usado.some(([x, y]) => a < y && z > x)) continue;
        t.usado.push([a, z]);
        aceitas.push({ id: b.id, i: t.i, a, z });
      }
    }
  }
  aceitas.sort((x, y) => x.i - y.i || x.a - y.a);
  const feitos = new Set();
  const marcas = new Map();
  for (const m of aceitas) {
    if (feitos.has(m.id)) continue;
    feitos.add(m.id);
    (marcas.get(m.i) || marcas.set(m.i, []).get(m.i)).push(m);
  }
  /* Uma variante longa pode vir depois de uma curta de outro termo na ordem do texto; só a ordem das posições importa. */
  for (const [i, lista] of marcas) {
    const texto = pedacos[i];
    let saida = "", pos = 0;
    for (const m of lista.sort((x, y) => x.a - y.a)) {
      saida += texto.slice(pos, m.a) + termo(m.id, desfazer(texto.slice(m.a, m.z)));
      pos = m.z;
    }
    pedacos[i] = saida + texto.slice(pos);
  }
  return pedacos.join("");
}

/* O texto vem de HTML já escapado; termo() escapa de novo, então devolve as entidades ao normal antes. */
const desfazer = (s) => s.replace(/&(amp|lt|gt|quot|#39);/g, (_, e) => ({ amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'" }[e]));

let contador = 0;
const ligadas = new WeakSet();

function alternar(botao) {
  const aberta = botao.getAttribute("aria-controls");
  const existente = aberta && document.getElementById(aberta);
  if (existente) {
    existente.remove();
    botao.setAttribute("aria-expanded", "false");
    botao.focus?.();
    return;
  }
  const t = PORID.get(botao.dataset.termo);
  if (!t) return;
  const id = `def-${++contador}`;
  const caixa = document.createElement("span");
  caixa.className = "definicao";
  caixa.id = id;
  caixa.setAttribute("role", "note");
  caixa.innerHTML = `<button type="button" class="fechar" aria-label="Fechar explicação">Fechar</button><b>${esc(t.termo)}.</b> ${esc(t.definicao)} <span class="fonte-link"><span class="rotulo-fonte">Fonte:</span> <a href="${esc(t.fonte.url)}" rel="noopener">${esc(t.fonte.rotulo)}</a></span>`;
  (botao.closest("li, p, dd, h4, .estado") || botao).insertAdjacentElement("afterend", caixa);
  botao.setAttribute("aria-controls", id);
  botao.setAttribute("aria-expanded", "true");
}

/* Um ouvinte de clique delegado para todos os "?" da página (inclusive os criados depois). */
export function ligarGlossario(raiz = document) {
  if (!raiz || ligadas.has(raiz)) return;
  ligadas.add(raiz);
  raiz.addEventListener("click", (ev) => {
    const alvo = ev.target;
    if (!alvo?.closest) return;
    const botao = alvo.closest(".termo");
    if (botao) return alternar(botao);
    const fechar = alvo.closest(".definicao .fechar");
    if (fechar) {
      const caixa = fechar.closest(".definicao");
      const dono = document.querySelector(`[aria-controls="${caixa.id}"]`);
      if (dono) alternar(dono); else caixa.remove();
    }
  });
}
