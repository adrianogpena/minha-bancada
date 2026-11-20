/* Página do "Sem Nome" (pessoa pes_sem_nome, id "sem-nome"): para onde vai todo registro de fonte que cita um parlamentar que não achamos
   no banco, e por que isso acontece. Lista os nomes como as Assembleias os publicaram (dados/nucleo/ligacoes.json, `registros`). */
import { $, esc, carregar } from "./util.js";
import { erro } from "./comum.js";
import { UFS } from "./apis.js";

export const SEM_NOME = "sem-nome";
export const PAGINA_SEM_NOME = "sem-nome.html";

const MOTIVOS = [
  ["Ex-deputado ou suplente", "A fonte registra um voto, uma autoria ou um gasto de quem já saiu da Casa, ou de um suplente que assumiu por pouco tempo. Nosso banco só tem quem está em exercício ou foi candidato em eleição que coletamos."],
  ["Nome escrito de outro jeito", "A fonte usa apelido, título (\"Dr.\", \"Delegado\", \"Coronel\"), partido junto do nome, abreviatura ou erro de digitação, e a comparação segura por nome não encontra o parlamentar."],
  ["Dois parlamentares com o mesmo nome", "Quando o nome serve a mais de uma pessoa, não ligamos a nenhuma delas: ligar errado seria pior do que não ligar."],
  ["Não é político eleito", "A autoria pode ser de uma comissão, do Poder Executivo, de um tribunal, de um órgão ou de uma pessoa sem mandato, que não têm ficha de político."],
  ["Político de outra esfera ou ainda não coletado", "O nome pode ser de um senador, deputado federal ou estadual de uma legislatura que ainda não está no banco, ou de uma Assembleia cuja coleta ainda não cobre aquele período."],
  ["Dado incompleto na API", "A fonte publica o registro sem id nem CPF do parlamentar, só o nome, e o nome vem cortado, em branco ou trocado."],
];

function porUf(registros) {
  return Object.entries(registros || {}).map(([uf, t]) => ({ uf, semPar: t.semPar || [], ambiguos: Object.keys(t.ambiguos || {}) }))
    .filter((x) => x.semPar.length || x.ambiguos.length).sort((a, b) => a.uf.localeCompare(b.uf));
}

export async function paginaSemNome() {
  const alvo = $("#conteudo");
  let lig;
  try { lig = await carregar("dados/nucleo/ligacoes.json"); } catch (e) { return erro(alvo, e); }
  document.title = "Sem Nome | Minha Bancada";
  const ufs = porUf(lig.registros);
  const total = ufs.reduce((n, x) => n + x.semPar.length + x.ambiguos.length, 0);
  alvo.innerHTML = `
    <h1>Sem Nome</h1>
    <p class="aviso">Esta página não é de uma pessoa. É o lugar onde ficam ligados os registros das fontes oficiais que citam um parlamentar que não está no nosso banco de políticos. Em votos, autorias e outros dados, o nome original continua aparecendo; só a ligação aponta para cá, para o dado funcionar normalmente em vez de sumir.</p>
    <h2>Por que a API cita alguém que não está no banco?</h2>
    <ul>${MOTIVOS.map(([t, d]) => `<li><b>${esc(t)}.</b> ${esc(d)}</li>`).join("")}</ul>
    <p class="quando">Nome ambíguo nunca é ligado a ninguém. Ligações manuais corrigem casos conhecidos (<code>scripts/ligacoes_manuais.json</code>).</p>
    <h2>O que está ligado aqui${total ? ` (${total} ${total === 1 ? "nome" : "nomes"} nas Assembleias)` : ""}</h2>
    ${ufs.length ? ufs.map((x) => `<details class="texto"><summary>${esc(UFS[x.uf] || x.uf)}: ${x.semPar.length} sem par${x.ambiguos.length ? `, ${x.ambiguos.length} ambíguos` : ""}</summary>
      <ul class="itens">${[...x.semPar.map((n) => [n, "sem par no banco"]), ...x.ambiguos.map((n) => [n, "mais de um parlamentar com esse nome"])].map(([n, m]) => `<li><span class="texto">${esc(n.trim())} <span class="quando">${esc(m)}</span></span></li>`).join("")}</ul></details>`).join("")
      : `<p class="vazio">Nenhum nome sem ligação nas Assembleias na última coleta.</p>`}
    <p class="quando">Também ligam a esta página os autores de proposições que são parlamentares sem ficha no site (por exemplo, ex-senadores e ex-deputados). Fonte dos nomes: dados abertos de cada Assembleia, da Câmara e do Senado.</p>`;
}
