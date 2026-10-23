/* Poder Executivo: casas legislativas, etapas dos projetos, legendas e avisos. */
import { esc, data, urlSegura } from "./util.js";
import { linkTramitacao, UFS } from "./apis.js";

/* ---------- ficha de um político (TSE ou Senado) ---------- */
export const EXECUTIVOS = new Set(["PRESIDENTE", "VICE-PRESIDENTE", "GOVERNADOR", "VICE-GOVERNADOR", "PREFEITO", "VICE-PREFEITO"]);
const ASSEMBLEIAS = { AC: "aleac.gov.br", AL: "al.al.leg.br", AP: "al.ap.leg.br", AM: "aleam.gov.br", BA: "al.ba.gov.br", CE: "al.ce.gov.br", DF: "cl.df.gov.br",
  ES: "al.es.gov.br", GO: "al.go.leg.br", MA: "al.ma.leg.br", MT: "al.mt.gov.br", MS: "al.ms.gov.br", MG: "almg.gov.br", PA: "alepa.pa.gov.br", PB: "al.pb.leg.br",
  PR: "assembleia.pr.leg.br", PE: "alepe.pe.gov.br", PI: "alepi.pi.leg.br", RJ: "alerj.rj.gov.br", RN: "al.rn.leg.br", RS: "al.rs.gov.br", RO: "al.ro.leg.br",
  RR: "al.rr.leg.br", SC: "alesc.sc.gov.br", SP: "al.sp.gov.br", SE: "al.se.leg.br", TO: "al.to.leg.br" };

/* Site da Câmara Municipal de cada capital, pelo código TSE do município. */
const CAMARAS_CAPITAIS = { "01392": "riobranco.ac.leg.br", "27855": "maceio.al.leg.br", "06050": "macapa.ap.leg.br", "02550": "cmm.am.gov.br",
  "38490": "cms.ba.gov.br", "13897": "cmfor.ce.gov.br", "57053": "cmvv.es.gov.br", "93734": "goiania.go.leg.br", "90670": "camaracuiaba.mt.gov.br",
  "41238": "cmbh.mg.gov.br", "04278": "cmb.pa.gov.br", "20516": "joaopessoa.pb.leg.br", "75353": "cmc.pr.gov.br", "25313": "recife.pe.leg.br",
  "12190": "teresina.pi.leg.br", "60011": "camara.rio", "17612": "natal.rn.leg.br", "88013": "camarapoa.rs.gov.br", "00035": "portovelho.ro.leg.br",
  "03018": "boavista.rr.leg.br", "81051": "cmf.sc.gov.br", "71072": "saopaulo.sp.leg.br", "73440": "palmas.to.leg.br" };

/* A casa legislativa ligada ao cargo: quem vota, onde, e o link oficial quando conhecemos. */
export function casaLegislativa(p) {
  const c = p.cargoTse || "";
  if (p.fonte === "senado") return { quem: "o Senado", em: "no Senado", link: ["Senado Federal", "https://www25.senado.leg.br"] };
  if (c === "PRESIDENTE" || c === "VICE-PRESIDENTE") return { quem: "o Congresso Nacional", em: "no Congresso", link: ["Câmara dos Deputados", "https://www.camara.leg.br"] };
  if (c === "GOVERNADOR" || c === "VICE-GOVERNADOR") return { quem: `a Assembleia Legislativa${p.uf ? ` (${UFS[p.uf] || p.uf})` : ""}`, em: "na Assembleia", link: ASSEMBLEIAS[p.uf] ? ["Site da Assembleia Legislativa", `https://www.${ASSEMBLEIAS[p.uf]}`] : null };
  if (c === "PREFEITO" || c === "VICE-PREFEITO") return { quem: `a Câmara Municipal${p.municipio ? ` de ${p.municipio}` : ""}`, em: "na Câmara Municipal", link: CAMARAS_CAPITAIS[p.ue] ? ["Site da Câmara Municipal", `https://www.${CAMARAS_CAPITAIS[p.ue]}`] : null };
  if (c === "VEREADOR") return { quem: "", em: `na Câmara Municipal${p.municipio ? ` de ${p.municipio}` : ""}`, link: null };
  return { quem: "", em: `na Assembleia Legislativa${p.uf ? ` (${UFS[p.uf] || p.uf})` : ""}`, link: ASSEMBLEIAS[p.uf] ? ["Site da Assembleia Legislativa", `https://www.${ASSEMBLEIAS[p.uf]}`] : null };
}

/* Presidente em exercício: projetos e medidas provisórias que enviou ao Congresso e o que aconteceu com cada um. */
const TIPOS_EXECUTIVO = { PL: "Projeto de lei", PLP: "Projeto de lei complementar", PEC: "Proposta de emenda à Constituição", MPV: "Medida provisória" };
function desfechoExecutivo(x) {
  const s = (x.situacao || "").toLowerCase();
  if (x.veto === "total" || s.startsWith("vetad")) return { rotulo: "Vetou", classe: "v-nao" };
  if (s.startsWith("transformad")) return { rotulo: x.veto === "parcial" ? "Virou lei, com vetos" : "Virou lei", classe: "v-sim" };
  if (s.includes("aguardando sanção")) return { rotulo: "Decide se sanciona", classe: "v-outro" };
  if (!x.situacao && x.tipo === "MPV") return { rotulo: "MP em vigor", classe: "v-outro" };
  if (s.startsWith("perdeu a efic")) return { rotulo: "MP deixou de valer", classe: "v-nao" };
  if (/^(arquivad|retirad|rejeitad|prejudicad)/.test(s)) return { rotulo: "Não virou lei", classe: "v-nao" };
  return { rotulo: "No Congresso", classe: "v-outro" };
}
/* Frases curtas, uma por etapa, dizendo quem fez o quê: o presidente (enviou, sancionou, vetou) ou o Congresso (aprovou, deixou caducar). */
function etapasExecutivo(x) {
  const mp = x.tipo === "MPV", s = (x.situacao || "").toLowerCase();
  const e = [mp ? `<b>O presidente editou</b> a medida provisória em ${data(x.dataApresentacao)}; ela vale como lei desde então, mas o Congresso precisa aprová-la em até 120 dias.`
    : `<b>O presidente enviou</b> o projeto ao Congresso em ${data(x.dataApresentacao)}.`];
  if (x.remessa) e.push(`<b>O Congresso aprovou</b> e mandou à sanção em ${data(x.remessa)}.`);
  if (x.veto === "total" || s.startsWith("vetad")) e.push(`<b>O presidente vetou o texto inteiro</b>${x.dataNorma ? ` em ${data(x.dataNorma)}` : ""}.${x.razoesVeto ? ` Razões do veto: ${esc(x.razoesVeto)}.` : ""}`);
  else if (s.startsWith("transformad")) {
    const lei = x.norma ? ` (<b>${esc(x.norma)}</b>)` : "";
    if (mp && !x.remessa) e.push(`<b>O Congresso aprovou</b> a medida provisória sem mudanças e ela virou lei${lei}${x.dataNorma ? ` em ${data(x.dataNorma)}` : ""}. Nesse caso não há sanção: quem promulga é o Congresso.`);
    else if (x.veto === "parcial") e.push(`<b>O presidente sancionou</b> o texto${x.dataNorma ? ` em ${data(x.dataNorma)}` : ""}${lei}, mas <b>vetou trechos</b>.${x.razoesVeto ? ` Razões do veto: ${esc(x.razoesVeto)}.` : ""} O Congresso ainda pode derrubar os vetos.`);
    else e.push(`<b>O presidente sancionou</b> o texto sem vetos${x.dataNorma ? ` em ${data(x.dataNorma)}` : ""}${lei}.`);
  } else if (s.includes("aguardando sanção")) e.push("<b>O presidente ainda não decidiu:</b> tem 15 dias úteis para sancionar ou vetar.");
  else if (s.startsWith("perdeu a efic")) e.push(`<b>O Congresso não votou a tempo</b> e a medida provisória perdeu a eficácia${x.dataSituacao ? ` em ${data(x.dataSituacao)}` : ""}.`);
  else if (/^(arquivad|retirad|rejeitad|prejudicad)/.test(s)) e.push(`<b>Não virou lei:</b> ${esc(x.situacao.toLowerCase())}${x.dataSituacao ? ` em ${data(x.dataSituacao)}` : ""}. Não houve sanção nem veto.`);
  else if (x.situacao) e.push(`<b>Ainda no Congresso:</b> ${esc(x.situacao.toLowerCase())}. Ainda não chegou à sanção.`);
  return e;
}
/* Governador e prefeito: o sistema de cada Casa só informa tipo, situação e ementa, então os desfechos são mais genéricos que os do presidente. */
function etapasGoverno(x, prefeito) {
  const chefe = prefeito ? "O prefeito" : "O governador", casa = prefeito ? "A Câmara" : "A Assembleia";
  const sit = (x.situacao || "").trim(), s = sit.toLowerCase(), td = (x.tipoDescricao || "").toLowerCase();
  const quando = x.dataApresentacao ? ` em ${data(x.dataApresentacao)}` : "";
  const alcance = /total|integral/i.test(`${x.tipoDescricao} ${x.ementa}`) ? "total" : /parcial/i.test(`${x.tipoDescricao} ${x.ementa}`) ? "parcial" : null;
  if (x.tipo === "VET") {
    const e = [`<b>${chefe} vetou</b> ${alcance === "total" ? "o texto inteiro" : alcance === "parcial" ? "trechos do texto" : "o texto (o sistema não informa se inteiro ou em parte)"}; a mensagem de veto chegou${prefeito ? "" : " à Assembleia"}${quando}.`];
    if (/^em tr(amita|âmite)/.test(s)) e.push(`<b>${casa} ainda vai decidir</b> se mantém o veto ou o derruba.`);
    else if (/encerrad|finalizad|arquivad|armazenad/.test(s)) e.push(`<b>${casa} já concluiu</b> a análise do veto. O sistema não informa se o veto foi mantido ou derrubado.`);
    else if (sit) e.push(`Situação no sistema da Casa: ${esc(sit.toLowerCase())}.`);
    return { rotulo: alcance === "total" ? "Vetou tudo" : alcance === "parcial" ? "Vetou em parte" : "Vetou", classe: "v-nao", etapas: e };
  }
  const mp = /medida provis/.test(td), msg = /^mensagem/.test(td);
  const enviou = mp ? `<b>${chefe} editou</b> a medida provisória${quando}; ela vale como lei até ${casa.toLowerCase()} votar.`
    : msg ? `<b>${chefe} enviou</b> uma mensagem${prefeito ? " à Câmara" : " à Assembleia"}${quando}.`
    : `<b>${chefe} enviou</b> o projeto${prefeito ? " à Câmara" : " à Assembleia"}${quando}.`;
  const e = [enviou];
  if (/^(sancionad|virou lei)/.test(s)) {
    const detalhe = (sit.match(/\((.*)\)/) || [])[1];
    e.push(`<b>Virou lei${/^sancionad/.test(s) ? ": o chefe do Executivo sancionou" : ""}</b>${detalhe ? ` (${esc(detalhe.replace(/\d{4}-\d{2}-\d{2}/g, (d) => data(d)))})` : ""}.`);
    return { rotulo: "Virou lei", classe: "v-sim", etapas: e };
  }
  if (/retirad/.test(s)) { e.push(`<b>${chefe} retirou</b> a proposta antes da votação final.`); return { rotulo: "Retirou", classe: "v-nao", etapas: e }; }
  if (/^em tr(amita|âmite)|aguardando/.test(s)) { e.push(`<b>Ainda em análise</b> ${prefeito ? "na Câmara" : "na Assembleia"}: sem decisão final.`); return { rotulo: prefeito ? "Na Câmara" : "Na Assembleia", classe: "v-outro", etapas: e }; }
  if (/encerrad|finalizad|arquivad|armazenad|anexad|encaminhad/.test(s)) {
    e.push(`<b>${casa} encerrou</b> a tramitação. O sistema não informa se virou lei, foi arquivada ou rejeitada.`);
    return { rotulo: "Encerrado", classe: "v-outro", etapas: e };
  }
  e.push(`Situação no sistema da Casa: ${esc(sit.toLowerCase() || "não informada")}.`);
  return { rotulo: sit || "Sem situação", classe: "v-outro", etapas: e };
}
export const itemGoverno = (prefeito) => (x) => {
  const d = etapasGoverno(x, prefeito);
  return `<li><span class="quando">${esc(x.tipoDescricao)} ${esc(x.numero)}/${esc(x.ano)}</span>
  <span class="voto ${d.classe}">${esc(d.rotulo)}</span>
  <span class="texto">${esc(x.ementa)}</span>
  <div class="texto"><ul class="etapas">${d.etapas.map((t) => `<li>${t}</li>`).join("")}</ul>
    ${urlSegura(x.linkTexto) ? `<a href="${esc(x.linkTexto)}" rel="noopener">${/\.pdf$/i.test(x.linkTexto) ? "Texto" : "Tramitação"}</a>` : ""}</div></li>`;
};

/* Legenda recolhida com o significado de cada selo, e aviso do que a fonte não informa. */
const legendaStatus = (itens) => `<details class="legenda-status"><summary>O que significa cada status</summary>
  <dl>${itens.map(([nome, texto]) => `<dt>${esc(nome)}</dt><dd>${texto}</dd>`).join("")}</dl></details>`;
export const LEGENDA_PROJETOS = legendaStatus([
  ["Em tramitação", "Ainda em análise na Casa. Ainda não foi votado até o fim."],
  ["Aprovada / Aprovada na Câmara / Aprovada no Senado", "Passou por uma Casa e segue para a próxima etapa (outra Casa ou sanção)."],
  ["Virou lei", "Foi sancionado ou promulgado e virou norma jurídica."],
  ["Arquivada / Retirada pelo autor / Rejeitada / Vetada / Prejudicada", "Não seguiu adiante: arquivado, retirado pelo próprio autor, rejeitado, vetado ou perdeu o sentido por outra decisão."],
  ["Tramitação encerrada", "A Casa encerrou o processo, mas a fonte não diz como (aprovado, arquivado ou rejeitado)."],
  ["Situação ainda não consultada", "O site ainda não leu a situação deste projeto; veja a tramitação."]]);
export const LEGENDA_PRESIDENTE = legendaStatus([
  ["Virou lei", "O Congresso aprovou e o presidente sancionou o texto sem vetos. Medida provisória aprovada sem mudanças também vira lei, sem sanção."],
  ["Virou lei, com vetos", "O presidente sancionou, mas vetou trechos. O Congresso ainda pode derrubar esses vetos."],
  ["Vetou", "O presidente vetou o texto inteiro."],
  ["Decide se sanciona", "O Congresso já aprovou. O presidente tem 15 dias úteis para sancionar ou vetar."],
  ["MP em vigor", "Medida provisória editada pelo presidente. Vale como lei, mas o Congresso precisa votá-la em até 120 dias."],
  ["MP deixou de valer", "O Congresso não votou a tempo e a medida provisória perdeu a eficácia."],
  ["Não virou lei", "Arquivado, retirado, rejeitado ou prejudicado no Congresso. Não houve sanção nem veto."],
  ["No Congresso", "Ainda em análise na Câmara ou no Senado."]]);
export const legendaGoverno = (prefeito) => legendaStatus([
  ["Vetou tudo / Vetou em parte", `Veto ${prefeito ? "do prefeito" : "do governador"} a um projeto aprovado ${prefeito ? "pela Câmara" : "pela Assembleia"}. Cada item é a mensagem de veto.`],
  ["Virou lei", "O sistema da Casa informa que o projeto foi sancionado ou virou lei."],
  [prefeito ? "Na Câmara" : "Na Assembleia", "Ainda em análise, sem decisão final. Num veto, significa que ainda não se decidiu se ele fica ou cai."],
  ["Encerrado", "A Casa encerrou a tramitação. O sistema não diz se foi aprovado, arquivado ou rejeitado."],
  ["Retirou", `${prefeito ? "O prefeito" : "O governador"} retirou a proposta antes da votação final.`]]);
export const avisoDados = (itens) => `<p class="aviso-dados"><b>O que ainda não temos:</b> ${itens.join(" ")}</p>`;
export const AVISO_PRESIDENTE = avisoDados(["O trecho exato que foi vetado (só a referência ao Diário Oficial com as razões do veto).",
  "Se o Congresso manteve ou derrubou cada veto.", "Decretos.", "Os votos de cada parlamentar nesses projetos: veja a aba do parlamentar na Câmara ou no Senado."]);
export const AVISO_PROPOSTAS_PRESIDENTE = avisoDados(["Propostas feitas antes de 2023 e as que o presidente apoiou sem ser o autor.", "O texto de cada emenda que o Congresso aprovou e quem foi o relator.",
  "O trecho exato que foi vetado (só a referência ao Diário Oficial com as razões do veto).", "O voto de cada parlamentar: veja a página do parlamentar na Câmara ou no Senado."]);
export const avisoGovernoPropostas = (prefeito) => avisoDados(["Propostas anteriores ao início da coleta e as que não são do Executivo.", `O texto das emendas aprovadas e quem foi o relator ${prefeito ? "na Câmara" : "na Assembleia"}.`,
  "Se o projeto virou lei, quando não há \"Virou lei\" na situação: \"Encerrado\" não diz como terminou.", "A situação vem do sistema de cada Casa e pode estar desatualizada."]);
export const avisoGoverno = (prefeito) => avisoDados(["O trecho exato que foi vetado: o arquivo ligado em \"Texto\" é a mensagem de veto, quando a Casa o publica.",
  `Se ${prefeito ? "a Câmara" : "a Assembleia"} manteve ou derrubou cada veto.`, "A data da sanção e o número da lei, salvo quando o sistema da Casa informa.",
  "Decretos.", "A situação vem do sistema de cada Casa e pode estar desatualizada ou incompleta."]);
export const itemExecutivo = (x) => {
  const d = desfechoExecutivo(x);
  return `<li><span class="quando">${esc(TIPOS_EXECUTIVO[x.tipo] || x.tipo)} ${esc(x.numero)}/${esc(x.ano)}</span>
    <span class="voto ${d.classe}">${esc(d.rotulo)}</span>
    <span class="texto">${esc(x.ementa)}</span>
    <div class="texto"><ul class="etapas">${etapasExecutivo(x).map((t) => `<li>${t}</li>`).join("")}</ul>
      <a href="${esc(linkTramitacao(x.id))}" rel="noopener">Tramitação</a>${urlSegura(x.inteiroTeor) ? ` · <a href="${esc(x.inteiroTeor)}" rel="noopener">Texto original</a>` : ""}</div></li>`;
};
