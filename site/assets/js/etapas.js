/* Em que pé está uma proposição: a tabela única ETAPAS_POR_TIPO (tradução de docs/regras-tramitacao.md; tests/js/paginas.test.js
   confere os dois), a faixa de etapas, a frase do estado e o bloco "O que pode acontecer agora". Só campos já coletados. */
import { esc, data, semAcento } from "./util.js";
import { marcarTermos } from "./glossario.js";
import { linkMateriaSenado, linkTramitacao } from "./apis.js";

const dmy = (iso) => (iso ? iso.slice(0, 10).split("-").reverse().join("/") : "");
const dm = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : "");
const existe = (v) => !!v;
const COMISSAO = /^c(?!n$|d$)[a-z]{1,7}$/;   // sigla de comissão (em minúsculas e sem acento, como o reconhecimento compara)
const aresta = (de, para, condicao) => ({ de, para, condicao });

/* reconhece: campo do fato -> RegExp (sobre o texto sem acento e em minúsculas) ou função (valor, fato). Basta um campo bater.
   Campos: situacao, deliberacao, despacho, orgao, outraCasa, norma. `parada` marca etapa em que a proposição para (só vale a situação atual).
   `falta` é a 2ª frase (o que ainda falta); `rotulo` e `falta` podem ser funções do contexto {senado, vemDeFora, revisora, origem, ng}. */
const ABRE = { situacao: /aguardando (despacho|recebimento de emendas|encaminhamento|designacao do relator)/ };
const COMISSOES = {
  situacao: /materia despachada|materia com a relatoria|incluida na pauta da reuniao|pronta para a pauta|aprovado parecer|pedido de vista|aguardando audiencia|aguardando designacao de relator|aguardando parecer|tramitando em conjunto|decisao terminativa|aguardando interposicao/,
  despacho: /analise/, orgao: COMISSAO,
};
const PLENARIO = { situacao: /pronto para deliberacao do plenario|incluida em ordem do dia|^aprovada$/, deliberacao: /plenario/, despacho: /(votacao|apreciacao|discussao|aprovad[ao]).*plenario/ };
const REVISORA = { situacao: /remetid[ao] a (camara|senado)|aguardando apreciacao pelo senado/, outraCasa: existe };
const RETORNO = { situacao: /(emendas?|substitutivo) d[oa] (senado|camara)/ };
const SANCAO = { situacao: /sancao/ };
const VETO = { situacao: /\bveto\b|vetad/ };
const NORMA = { norma: existe, situacao: /transformad[ao] em norma/ };
const PARADA = { situacao: /arquivad|retirad[ao] pelo autor|prejudicad|rejeitad/, deliberacao: /rejeitad/ };
const ARQUIVADO = (rotulo) => ({ id: "arquivado", rotulo, parada: true, reconhece: PARADA, falta: "Não tramita mais." });
const casaDe = (c) => (c.senado || c.vemDeFora ? "Câmara dos Deputados" : "Senado Federal");

const SEM_MUDAR = "Ainda não é lei.";
const REVISORA_FALTA = (c) => `${SEM_MUDAR} ${c.revisora}, como Casa revisora, pode aprovar, mudar ou rejeitar o texto; se mudar, ele volta ${c.origem}. Depois vai à sanção.`;
const REVISORA_FALTA_2 = (c, norma) => `Ainda não é ${norma}. ${c.revisora}, como Casa revisora, pode aprovar, mudar ou rejeitar o texto; se mudar, ele volta ${c.origem}. Depois ${norma === "decreto legislativo" ? "é promulgado, sem sanção" : "é promulgada, sem sanção"}.`;
const jaE = (o) => (c) => `Já é ${o}${c.ng ? `: ${c.ng}` : ""}.`;

const PL_PLP = {
  etapas: [
    { id: "apresentado", rotulo: "Apresentado", reconhece: ABRE, depois: "", falta: "Ainda não é lei. O projeto foi apresentado e aguarda o despacho que define por quais comissões ou plenário ele passa." },
    { id: "comissoes", rotulo: "Comissões", reconhece: COMISSOES, pulou: "não passou: foi direto ao Plenário", falta: "Ainda não é lei. O projeto está nas comissões, que dão parecer; depois segue ao Plenário, a não ser que a comissão decida sozinha (terminativa ou conclusiva)." },
    { id: "plenario-origem", rotulo: (c) => (c.senado ? "Plenário do Senado" : "Plenário da Câmara"), reconhece: PLENARIO, falta: "Ainda não é lei. O Plenário vota; se aprovar, o texto vai à outra Casa para ser revisto." },
    { id: "casa-revisora", rotulo: (c) => casaDe(c), reconhece: REVISORA, falta: REVISORA_FALTA },
    { id: "retorno-origem", rotulo: "Volta à Casa de origem", reconhece: RETORNO, falta: "Ainda não é lei. O texto foi mudado na outra Casa e voltou para a Casa de origem decidir sobre as mudanças. Depois vai à sanção." },
    { id: "sancao-veto", rotulo: "Sanção ou veto", reconhece: SANCAO, depois: "Presidente da República", falta: "Ainda não é lei. O Presidente da República decide em até 15 dias úteis se sanciona ou veta." },
    { id: "veto-congresso", rotulo: "Veto no Congresso", reconhece: VETO, falta: "O veto aguarda a sessão do Congresso, que pode derrubá-lo ou mantê-lo." },
    { id: "lei", rotulo: "Lei", reconhece: NORMA, final: true, depois: "publicada", falta: jaE("lei") },
    ARQUIVADO("Arquivado"),
  ],
  principal: ["apresentado", "comissoes", "plenario-origem", "casa-revisora", "sancao-veto", "lei"],
  arestas: [
    aresta("apresentado", "comissoes", "o presidente da Casa despacha o projeto às comissões"),
    aresta("apresentado", "plenario-origem", "urgência aprovada ou despacho direto \"Ao Plenário\": as comissões ficam puladas"),
    aresta("comissoes", "plenario-origem", "o parecer é aprovado e o projeto é incluído em pauta"),
    aresta("comissoes", "casa-revisora", "comissão em decisão terminativa (Senado) ou conclusiva (Câmara) aprova e ninguém recorre ao Plenário"),
    aresta("comissoes", "plenario-origem", "há recurso contra a decisão terminativa ou conclusiva e o projeto vai ao Plenário"),
    aresta("comissoes", "arquivado", "a comissão rejeita o projeto, o autor o retira ou ele fica prejudicado"),
    aresta("plenario-origem", "casa-revisora", "o Plenário aprova o texto e o remete à outra Casa"),
    aresta("plenario-origem", "arquivado", "o Plenário rejeita o projeto"),
    aresta("casa-revisora", "sancao-veto", "a Casa revisora aprova sem mudar o texto"),
    aresta("casa-revisora", "retorno-origem", "a Casa revisora muda o texto (emenda ou substitutivo) e ele volta à Casa de origem"),
    aresta("casa-revisora", "arquivado", "a Casa revisora rejeita o projeto"),
    aresta("retorno-origem", "sancao-veto", "a Casa de origem decide sobre as mudanças e remete à sanção"),
    aresta("sancao-veto", "lei", "o Presidente sanciona (ou deixa passar 15 dias úteis sem decidir)"),
    aresta("sancao-veto", "veto-congresso", "o Presidente veta, total ou parcialmente"),
    aresta("veto-congresso", "lei", "o veto é derrubado (partes vetadas promulgadas) ou é mantido só em parte"),
    aresta("veto-congresso", "arquivado", "veto total mantido"),
    aresta("arquivado", "comissoes", "desarquivamento a pedido do autor, por exemplo ao fim da legislatura"),
  ],
};

const PEC = {
  etapas: [
    { id: "apresentado", rotulo: "Apresentada", reconhece: ABRE, falta: "Ainda não é emenda à Constituição. A proposta aguarda o despacho e a análise de admissibilidade." },
    { id: "comissoes", rotulo: "Comissão de Constituição e Justiça", reconhece: COMISSOES, pulou: "não passou por comissão", falta: "Ainda não é emenda à Constituição. A comissão examina se a proposta pode tramitar e dá o parecer." },
    { id: "plenario-1-turno", rotulo: "Plenário, 1º turno", reconhece: { situacao: /pronto para deliberacao do plenario|incluida em ordem do dia|1[ºo°] turno|primeiro turno/, deliberacao: /1[ºo°] turno|primeiro turno/, despacho: /1[ºo°] turno|primeiro turno/ }, falta: "Ainda não é emenda à Constituição. O Plenário vota em primeiro turno; precisa de três quintos." },
    { id: "plenario-2-turno", rotulo: "Plenário, 2º turno", reconhece: { situacao: /2[ºo°] turno|segundo turno/, deliberacao: /2[ºo°] turno|segundo turno/, despacho: /2[ºo°] turno|segundo turno/ }, falta: "Ainda não é emenda à Constituição. Falta a votação em segundo turno nesta Casa." },
    { id: "casa-revisora", rotulo: "Outra Casa (2 turnos)", reconhece: REVISORA, falta: "Ainda não é emenda à Constituição. A outra Casa também vota em dois turnos; se mudar o texto, ele volta à Casa de origem. Depois é promulgada, sem sanção." },
    { id: "retorno-origem", rotulo: "Volta à Casa de origem", reconhece: RETORNO, falta: "Ainda não é emenda à Constituição. O texto mudou na outra Casa e volta para decisão." },
    { id: "promulgacao", rotulo: "Promulgação", reconhece: NORMA, final: true, depois: "pelas Mesas da Câmara e do Senado", falta: jaE("emenda à Constituição") },
    ARQUIVADO("Arquivada"),
  ],
  principal: ["apresentado", "comissoes", "plenario-1-turno", "plenario-2-turno", "casa-revisora", "promulgacao"],
  arestas: [
    aresta("apresentado", "comissoes", "a proposta é despachada à comissão de constituição e justiça"),
    aresta("comissoes", "plenario-1-turno", "a proposta é admitida e o parecer é aprovado"),
    aresta("comissoes", "arquivado", "a comissão a declara inadmissível ou o autor a retira"),
    aresta("plenario-1-turno", "plenario-2-turno", "três quintos aprovam em 1º turno (há prazo entre os turnos, salvo calendário especial)"),
    aresta("plenario-1-turno", "arquivado", "não alcança três quintos"),
    aresta("plenario-2-turno", "casa-revisora", "aprovada em 2º turno na Casa de origem"),
    aresta("plenario-2-turno", "promulgacao", "aprovada em 2º turno na revisora sem mudança do texto"),
    aresta("casa-revisora", "promulgacao", "a outra Casa aprova nos dois turnos sem mudar o texto"),
    aresta("casa-revisora", "retorno-origem", "a outra Casa muda o texto"),
    aresta("casa-revisora", "arquivado", "rejeitada na outra Casa"),
    aresta("retorno-origem", "promulgacao", "a Casa de origem conclui a votação do texto final"),
    aresta("arquivado", "comissoes", "desarquivamento na legislatura seguinte"),
  ],
};

const MPV = {
  etapas: [
    { id: "publicada", rotulo: "Publicada (já vale)", reconhece: {}, falta: "Já vale como lei, mas só por tempo limitado. O Congresso precisa convertê-la em lei em até 120 dias." },
    { id: "comissao-mista", rotulo: "Comissão mista", reconhece: { despacho: /comissao mista/, situacao: /comissao mista/, orgao: /^cm/ }, pulou: "sem comissão mista", falta: "Já vale como lei. A comissão mista analisa antes de a Câmara votar." },
    { id: "plenario-camara", rotulo: "Câmara dos Deputados", reconhece: { situacao: /plenario da camara|remetid[ao] a camara/, despacho: /plenario da camara/ }, falta: "Já vale como lei. A Câmara vota primeiro; depois o Senado." },
    { id: "plenario-senado", rotulo: "Senado Federal", reconhece: { situacao: /pronto para deliberacao do plenario|incluida em ordem do dia|aguardando apreciacao pelo senado|remetid[ao] ao senado/ }, falta: "Já vale como lei. O Senado vota; se mudar o texto, o projeto de lei de conversão vai à sanção." },
    { id: "sancao-veto", rotulo: "Sanção ou veto", reconhece: SANCAO, pulou: "sem alteração: não precisou de sanção", falta: "Já vale como lei. Falta a sanção ou o veto do Presidente ao texto convertido." },
    { id: "veto-congresso", rotulo: "Veto no Congresso", reconhece: VETO, falta: "O veto aguarda a sessão do Congresso, que pode derrubá-lo ou mantê-lo." },
    { id: "lei", rotulo: "Lei de conversão", reconhece: NORMA, final: true, depois: "publicada", falta: (c) => `Convertida em lei${c.ng ? `: ${c.ng}` : ""}.` },
    { id: "perdeu-validade", rotulo: "Perdeu a validade", parada: true, reconhece: { situacao: /perd(a|eu) (de |a )?(eficacia|validade)|caducad/ }, falta: "Perdeu a validade: não foi votada a tempo." },
    ARQUIVADO("Arquivada (rejeitada)"),
  ],
  principal: ["publicada", "comissao-mista", "plenario-camara", "plenario-senado", "sancao-veto", "lei"],
  arestas: [
    aresta("publicada", "comissao-mista", "o Congresso instala a comissão mista"),
    aresta("publicada", "perdeu-validade", "os 120 dias acabam sem votação"),
    aresta("comissao-mista", "plenario-camara", "o parecer é aprovado, ou a matéria segue sem parecer no prazo"),
    aresta("comissao-mista", "perdeu-validade", "os 120 dias acabam"),
    aresta("plenario-camara", "plenario-senado", "a Câmara aprova"),
    aresta("plenario-camara", "arquivado", "a Câmara rejeita"),
    aresta("plenario-camara", "perdeu-validade", "os 120 dias acabam"),
    aresta("plenario-senado", "lei", "o Senado aprova sem mudar o texto"),
    aresta("plenario-senado", "sancao-veto", "o Senado aprova projeto de lei de conversão com alterações"),
    aresta("plenario-senado", "arquivado", "o Senado rejeita"),
    aresta("plenario-senado", "perdeu-validade", "os 120 dias acabam"),
    aresta("sancao-veto", "lei", "o Presidente sanciona"),
    aresta("sancao-veto", "veto-congresso", "o Presidente veta"),
    aresta("veto-congresso", "lei", "o veto é derrubado"),
    aresta("veto-congresso", "arquivado", "veto total mantido"),
  ],
};

const PDL = {
  etapas: [
    { id: "apresentado", rotulo: "Apresentado", reconhece: ABRE, falta: "Ainda não é decreto legislativo. Aguarda despacho às comissões." },
    { id: "comissoes", rotulo: "Comissões", reconhece: COMISSOES, pulou: "não passou: foi direto ao Plenário", falta: "Ainda não é decreto legislativo. As comissões dão o parecer; depois segue ao Plenário." },
    { id: "plenario-origem", rotulo: (c) => (c.senado ? "Plenário do Senado" : "Plenário da Câmara"), reconhece: PLENARIO, falta: "Ainda não é decreto legislativo. Se o Plenário aprovar, o texto vai à outra Casa." },
    { id: "casa-revisora", rotulo: (c) => casaDe(c), reconhece: REVISORA, falta: (c) => REVISORA_FALTA_2(c, "decreto legislativo") },
    { id: "retorno-origem", rotulo: "Volta à Casa de origem", reconhece: RETORNO, falta: "O texto mudou na outra Casa e volta para decisão." },
    { id: "promulgacao", rotulo: "Promulgação", reconhece: NORMA, final: true, depois: "sem sanção", falta: jaE("decreto legislativo") },
    ARQUIVADO("Arquivado"),
  ],
  principal: ["apresentado", "comissoes", "plenario-origem", "casa-revisora", "promulgacao"],
  arestas: [
    aresta("apresentado", "comissoes", "despacho às comissões"),
    aresta("apresentado", "plenario-origem", "urgência ou despacho ao Plenário: as comissões ficam puladas"),
    aresta("comissoes", "plenario-origem", "parecer aprovado"),
    aresta("comissoes", "casa-revisora", "comissão em caráter terminativo ou conclusivo aprova e ninguém recorre"),
    aresta("comissoes", "arquivado", "rejeitado, retirado ou prejudicado"),
    aresta("plenario-origem", "casa-revisora", "Plenário aprova"),
    aresta("plenario-origem", "arquivado", "Plenário rejeita"),
    aresta("casa-revisora", "promulgacao", "aprovado sem mudar o texto"),
    aresta("casa-revisora", "retorno-origem", "texto mudado"),
    aresta("casa-revisora", "arquivado", "rejeitado"),
    aresta("retorno-origem", "promulgacao", "a Casa de origem decide sobre as mudanças"),
    aresta("arquivado", "comissoes", "desarquivamento na legislatura seguinte"),
  ],
};

const PRS_PRC = {
  etapas: [
    { id: "apresentado", rotulo: "Apresentado", reconhece: ABRE, falta: "Ainda não é resolução. Aguarda o despacho às comissões ou ao Plenário." },
    { id: "comissoes", rotulo: "Comissões", reconhece: COMISSOES, pulou: "não passou: foi direto ao Plenário", falta: "Ainda não é resolução. As comissões dão o parecer; depois vota o Plenário." },
    { id: "plenario", rotulo: (c) => (c.senado ? "Plenário do Senado" : "Plenário da Câmara"), reconhece: PLENARIO, falta: "Ainda não é resolução. O Plenário desta Casa decide; aprovado, é promulgado sem passar pela outra Casa." },
    { id: "promulgacao", rotulo: "Promulgação", reconhece: NORMA, final: true, depois: "sem sanção", falta: jaE("resolução") },
    ARQUIVADO("Arquivado"),
  ],
  principal: ["apresentado", "comissoes", "plenario", "promulgacao"],
  arestas: [
    aresta("apresentado", "comissoes", "despacho às comissões"),
    aresta("apresentado", "plenario", "urgência ou despacho ao Plenário: as comissões ficam puladas"),
    aresta("comissoes", "plenario", "parecer aprovado"),
    aresta("comissoes", "arquivado", "rejeitado, retirado ou prejudicado"),
    aresta("plenario", "promulgacao", "o Plenário aprova: a resolução é promulgada pela Casa, sem sanção"),
    aresta("plenario", "arquivado", "o Plenário rejeita"),
    aresta("arquivado", "comissoes", "desarquivamento na legislatura seguinte"),
  ],
};

export const ETAPAS_POR_TIPO = { PL: PL_PLP, PLP: PL_PLP, PEC, MPV, PDL, PRS: PRS_PRC, PRC: PRS_PRC };

/* Modelos da frase do estado, do mais específico ao mais geral; [campo] é uma lacuna e modelo com lacuna vazia é pulado.
   etapa: só quando a etapa atual (ou onde parou) é uma destas; parado: true/false; situacao: sobre a situação atual. */
export const MODELOS = [
  { etapa: ["lei", "promulgacao"], texto: "Transformado em [ng] em [ng.dt]" },
  { etapa: ["lei", "promulgacao"], texto: "Transformado em [ng]" },
  { parado: true, texto: "Parou nesta etapa: [ps], desde [desde]" },
  { parado: true, texto: "Parou nesta etapa: [ps]" },
  { etapa: "casa-revisora", texto: "[dl.t] em [dl.d] e enviado [dl.p] em [rmcd], onde tem o número [cn]" },
  { etapa: "casa-revisora", texto: "[dl.t] em [dl.d] e enviado [dl.p], onde tem o número [cn]" },
  { etapa: "casa-revisora", texto: "[dl.t] em [dl.d] e enviado [dl.p]" },
  { etapa: "casa-revisora", texto: "[vemSenado] e a situação na Câmara é [ps]" },
  { etapa: "comissoes", situacao: /decisao terminativa/, texto: "Apreciado em decisão terminativa em [desde]; prazo de recurso para o Plenário" },
  { etapa: "comissoes", texto: "Em análise na [destino]; situação: [ps] desde [desde]" },
  { etapa: "comissoes", texto: "Em análise na [destino]; situação: [ps]" },
  { etapa: "sancao-veto", texto: "Aprovado pelo Congresso e remetido à sanção em [rmsancao]" },
  { texto: "[ps], desde [desde]" },
  { texto: "[ps]" },
];

const preencher = (texto, campos) => {
  let vazio = false;
  const saida = texto.replace(/\[([\w.]+)\]/g, (_, k) => { if (!campos[k]) vazio = true; return campos[k] || ""; });
  return vazio ? null : saida;
};

const bate = (reconhece, fato) => Object.entries(reconhece).some(([campo, teste]) => {
  const v = fato[campo];
  if (v == null || v === "") return false;
  return teste instanceof RegExp ? teste.test(semAcento(v)) : !!teste(v, fato);
});

/* Os fatos que a proposição já tem (situações, despachos, deliberação, outra Casa, norma), cada um com o dia, quando há. */
function fatosDe({ senado, p, f, t }) {
  const fatos = [];
  if (t && senado) {
    (t.situacoes || []).forEach(([ini, , , desc, col]) => fatos.push({ dia: ini, situacao: desc, orgao: col }));
    (t.despachos || []).forEach(([dia, prov, destinos]) => {
      fatos.push({ dia, despacho: prov });
      (destinos || []).forEach((d) => fatos.push({ dia, despacho: prov, orgao: d }));
    });
  } else if (t) {
    (t.eventos || []).forEach(([dia, orgao, tipo, situacao, despacho]) => fatos.push({ dia, orgao, situacao, despacho: [tipo, despacho].filter(Boolean).join(" ") }));
  }
  if (f.dl) fatos.push({ dia: f.dl.d, deliberacao: [f.dl.t, f.dl.p].filter(Boolean).join(" "), decisivo: true });
  if (p.s) fatos.push({ dia: f.ds || null, situacao: p.s, decisivo: true });
  if (f.cn || f.sf) fatos.push({ dia: null, outraCasa: f.cn || f.sf });
  if (f.ng) fatos.push({ dia: f.ng.dt || null, norma: f.ng.d || "norma" });
  return fatos;
}

const ultimoDia = (fatos) => fatos.map((x) => x.dia).filter(Boolean).sort().pop() || null;

export function estadoProposicao({ tipo, senado, p = {}, f = {}, t = null } = {}) {
  const def = ETAPAS_POR_TIPO[tipo || p.t];
  if (!def) return null;
  const id = String(p.k || "").slice(2);
  const ctx = { senado: !!senado, vemDeFora: !senado && !!f.sf, ng: f.ng?.d || "" };
  ctx.revisora = casaDe(ctx) === "Câmara dos Deputados" ? "A Câmara" : "O Senado";
  ctx.origem = ctx.revisora === "A Câmara" ? "ao Senado" : "à Câmara";
  const texto = (v) => (typeof v === "function" ? v(ctx) : v);
  const fatos = fatosDe({ senado, p, f, t });
  const achados = def.etapas.map((e) => fatos.filter((x) => (!e.parada || x.decisivo) && bate(e.reconhece, x)));

  const visiveis = def.etapas.map((e, i) => i).filter((i) => !def.etapas[i].parada && (def.principal.includes(def.etapas[i].id) || achados[i].length));
  const parou = def.etapas.findIndex((e, i) => e.parada && achados[i].length);
  let alto = -1;
  visiveis.forEach((i, pos) => { if (achados[i].length) alto = pos; });
  if (alto < 0 && (p.s || parou >= 0)) alto = 0;
  const viaOutraCasa = alto >= 0 && achados[visiveis[alto]].length > 0 && achados[visiveis[alto]].every((x) => x.outraCasa != null);

  const etapas = visiveis.map((i, pos) => {
    const e = def.etapas[i], quando = ultimoDia(achados[i]);
    let estado = "futuro", detalhe = e.depois || "";
    if (pos < alto) {
      const passou = achados[i].length > 0 || pos === 0 || viaOutraCasa;
      estado = passou ? "feito" : "pulado";
      detalhe = passou ? dm(quando) : e.pulou || "não passou por aqui";
    } else if (pos === alto) {
      if (parou >= 0) { estado = "parado"; detalhe = `parou aqui${quando ? ` em ${dm(quando)}` : ""}`; }
      else if (e.final) { estado = "feito"; detalhe = dm(quando); }
      else { estado = "atual"; detalhe = `${quando ? `desde ${dm(quando)} · ` : ""}agora`; }
    }
    return { id: e.id, rotulo: texto(e.rotulo), estado, quando, detalhe };
  });

  const ref = alto >= 0 ? def.etapas[visiveis[alto]] : null;
  const fim = parou >= 0 ? def.etapas[parou] : ref;
  const ultimo = (re) => dmy([...fatos].reverse().find((x) => x.situacao && re.test(semAcento(x.situacao)))?.dia);
  const destinos = [...(t?.despachos || [])].reverse().find((d) => (d[2] || []).length)?.[2] || [];
  const dl = f.dl || {};
  const campos = {
    ng: ctx.ng, "ng.dt": dmy(f.ng?.dt), ps: p.s || "", desde: dmy(f.ds || ultimoDia(fatos.filter((x) => x.decisivo && x.situacao))),
    "dl.t": (dl.t || "").replace(/^Aprovada/, "Aprovado").replace(/Plen[aá]rio$/, (m) => `${m} ${senado ? "do Senado" : "da Câmara"}`),
    "dl.d": dmy(dl.d), "dl.p": (dl.p || "").replace(/^À /, "à "), cn: f.cn || "", vemSenado: f.sf ? "Veio do Senado" : "",
    rmcd: ultimo(/remetid[ao] a (camara|senado)/), rmsancao: ultimo(/sancao/), destino: destinos.join(", ") || f.o || "",
  };
  const modelo = MODELOS.find((m) => ref && (m.parado === undefined || m.parado === (parou >= 0)) && (!m.etapa || [].concat(m.etapa).includes(fim.id))
    && (!m.situacao || m.situacao.test(semAcento(p.s || ""))) && preencher(m.texto, campos) !== null);
  const frase = modelo ? preencher(modelo.texto, campos) : "";
  const falta = fim ? texto(fim.falta) : "";
  const rotuloDe = (pid) => texto(def.etapas.find((e) => e.id === pid)?.rotulo) || pid;
  const proximos = fim ? def.arestas.filter((a) => a.de === fim.id).map((a) => ({ rotulo: rotuloDe(a.para), condicao: a.condicao })) : [];
  const ps = p.s || "";
  return {
    etapas, frase, segunda: falta, proximos,
    crua: { texto: ps ? `${ps}${f.o ? ` (${f.o})` : ""}` : "ainda não consultada", desde: f.ds || null, fonte: id ? (senado ? linkMateriaSenado(id) : linkTramitacao(id)) : null },
  };
}

const PONTO = { feito: "✓", pulado: "–", parado: "✕" };

export function faixaEtapas(estado) {
  const itens = estado.etapas.map((e, i) => `<li class="${e.estado}"${e.estado === "atual" ? ` aria-current="step"` : ""}><span class="ponto" aria-hidden="true">${PONTO[e.estado] || i + 1}</span><b>${esc(e.rotulo)}</b>${e.detalhe ? `<span>${esc(e.detalhe)}</span>` : ""}</li>`);
  return `<ol class="etapas" aria-label="Etapas do projeto" style="--n:${estado.etapas.length}">${itens.join("")}</ol>`;
}

export function blocoEstado(estado) {
  const { frase, segunda, proximos, crua } = estado;
  const desde = crua.desde ? `, desde ${esc(data(crua.desde))}` : `<span class="quando"> · data da situação não informada pela fonte</span>`;
  return `<div class="estado">
    ${frase ? `<p><b>${esc(frase)}.</b></p>` : ""}
    ${segunda ? `<p class="pequeno">${marcarTermos(esc(segunda))}</p>` : ""}
    ${proximos.length ? `<h3>O que pode acontecer agora</h3><ul class="itens">${proximos.map((x) => `<li><span class="texto"><b>${esc(x.rotulo)}:</b> ${marcarTermos(esc(x.condicao))}</span></li>`).join("")}</ul>` : ""}
    <p class="pequeno"><b>Situação na fonte:</b> ${marcarTermos(esc(crua.texto))}${desde}${crua.fonte ? ` · <a href="${esc(crua.fonte)}" rel="noopener">ver na fonte</a>` : ""}</p>
  </div>`;
}
