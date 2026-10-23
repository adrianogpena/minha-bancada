/* Ficha de um político (TSE ou Senado). */
import { $, esc, reais, reaisCentavos, data, param, carregar, urlSegura } from "./util.js";
import { itemFicha, foto, listaPaginada, erro, ligarAbas } from "./comum.js";
import { linksRedes, fonteRedesTse, divulgaUrl, linhaNoCargoAte, linhaSubsidio, blocoPatrimonioFontes, completarEleicao } from "./ficha.js";
import { arquivoTse, fontes, UFS } from "./apis.js";
import { linkPolitico } from "./mapa.js";
import { EXECUTIVOS, casaLegislativa, itemGoverno, LEGENDA_PRESIDENTE, legendaGoverno, AVISO_PRESIDENTE, AVISO_PROPOSTAS_PRESIDENTE, avisoGovernoPropostas, avisoGoverno, itemExecutivo } from "./executivo.js";
import { painelEleicaoDe } from "./eleicao.js";
import { montarSenador } from "./senador.js";
import { montarEstadual } from "./estadual.js";

export async function paginaPolitico() {
  const alvo = $("#conteudo");
  const f = param("f"), i = param("i");
  let p;
  try {
    if (!f || !/^[\w/-]+$/.test(f)) throw new Error("Endereço incompleto");
    const fichas = await carregar(`dados/p/${f}.json`);
    p = i === "_disputas" ? null : fichas[i];
    if (!p) throw new Error("Político não encontrado. Ele pode ter deixado o cargo desde a última atualização");
    completarEleicao(p, fichas._disputas);
  } catch (e) { return erro(alvo, e); }

  const nome = p.urna || p.nome;
  const local = p.municipio ? `${p.municipio} (${p.uf})` : p.uf === "BR" ? "Brasil" : UFS[p.uf] || p.uf;
  document.title = `${nome}, ${p.cargo} | Minha Bancada`;
  const idade = p.nascimento ? Math.floor((Date.now() - new Date(p.nascimento + "T12:00:00Z")) / 31557600000) : null;

  let situacao = "";
  if (p.estado === "atual") situacao = p.fimMandato ? `No cargo, com mandato até ${data(p.fimMandato, true)}.` : "No cargo.";
  if (p.estado === "eleito") situacao = `Eleito em 2026. Toma posse em 2027.`;
  if (p.estado === "2turno") situacao = `Disputa o 2º turno da eleição de 2026.`;
  if (p.fonte === "senado" && p.participacao && p.participacao !== "Titular") situacao += ` Em exercício como ${esc(p.participacao.toLowerCase())}.`;

  const ficha = [
    ["Nome completo", p.nomeCivil || p.nome],
    ["Nome social", p.nomeSocial],
    ["Número", p.numero],
    ["Partido", p.partido],
    ["Federação", p.federacao],
    ["Coligação", p.coligacao ? `${esc(p.coligacao)}${p.composicaoColigacao ? ` (${esc(p.composicaoColigacao)})` : ""}` : null, true],
    ["Nascimento", p.nascimento ? `${data(p.nascimento, true)}${idade ? ` (${idade} anos)` : ""}` : null],
    ["Estado civil", p.estadoCivil],
    ["Nasceu em (UF)", p.ufNascimento && UFS[p.ufNascimento] ? UFS[p.ufNascimento] : null],
    ["Gênero", p.genero ? p.genero[0] + p.genero.slice(1).toLowerCase() : null],
    ["Cor ou raça", p.corRaca],
    ["Escolaridade", p.instrucao],
    ["Ocupação declarada", p.ocupacao],
    ["E-mail", p.email ? `<a href="mailto:${esc(p.email)}">${esc(p.email)}</a>` : null, true],
    linhaSubsidio(p),
    linhaNoCargoAte(p),
    ["Redes e sites declarados na candidatura", linksRedes(p.redes, { ...p, fonteRedes: fonteRedesTse(p) }), true, true],
  ].filter(([, v]) => v);

  if (p.fonte === "senado") {
    const montado = await montarSenador(alvo, p, nome, ficha);
    if (montado) return;
  }
  if (p.estadual) {
    const montado = await montarEstadual(alvo, p, nome, ficha, situacao);
    if (montado) return;
  }

  const bens = p.bens || [];
  const executivo = EXECUTIVOS.has(p.cargoTse);
  const casa = casaLegislativa(p);
  const divulga = divulgaUrl(p);
  const fonteTse = divulga ? [["Candidatura no DivulgaCandContas (TSE)", divulga]] : [];

  const painelPerfil = `
    <p class="situacao">${situacao}</p>
    ${urlSegura(p.paginaAtual, true) ? `<p class="aviso">Já tem mandato hoje. <a href="${esc(p.paginaAtual)}">Ver votos, projetos e gastos do mandato atual</a>.</p>` : ""}
    ${p.fonte === "senado" ? `<p class="aviso">Os votos e projetos deste senador não puderam ser carregados agora. Veja no ${urlSegura(p.pagina) ? `<a href="${esc(p.pagina)}" rel="noopener">perfil oficial no Senado</a>` : "perfil oficial no Senado"}.</p>` : ""}

    <h2>Ficha</h2>
    <dl class="ficha">${ficha.map(itemFicha).join("")}
      <dt>Onde atua</dt><dd>${esc(local)}</dd>
    </dl>
    ${p.fonte === "tse" ? fontes([...fonteTse, ["Dados de candidatos (TSE)", arquivoTse("consulta_cand", p)]]) : ""}

    ${p.fonte === "tse" ? `
    <h2>Bens declarados em ${esc(p.ano)}</h2>
    <p>Total: <b>${reaisCentavos(p.totalBens)}</b>${bens.length ? `, em ${bens.length} ${bens.length === 1 ? "item" : "itens"}` : ""}. Valores informados pelo próprio candidato ao registrar a candidatura.</p>
    <div id="lista-bens"></div>
    ${blocoPatrimonioFontes(p, fonteTse)}`
    : `<p class="fonte"><span class="rotulo-fonte">Fonte</span> <a href="https://legis.senado.leg.br/dadosabertos">Dados Abertos do Senado Federal</a>.${p.fimMandato ? ` Mandato até ${data(p.fimMandato, true)}.` : ""}</p>`}`;

  /* Para estes cargos ainda não temos votos nem projetos coletados; as abas dizem isso e levam à fonte oficial. */
  const presidente = p.cargoTse === "PRESIDENTE" && p.estado === "atual";
  let enviados = [];
  if (presidente) { try { enviados = await carregar("dados/executivo.json"); } catch { /* sem dados: cai no texto padrão */ } }
  const comDados = presidente && enviados.length > 0;
  /* Governador em exercício: o que enviou à Assembleia, quando ela usa um sistema que já coletamos. */
  let governo = null;
  if (p.cargoTse === "GOVERNADOR" && p.estado === "atual" && /^[A-Z]{2}$/.test(p.uf || "")) {
    try { governo = await carregar(`dados/governo/${p.uf}.json`); } catch { /* sem dados: cai no texto padrão */ }
  }
  /* Vice-governador: não propõe nem veta; quando a Assembleia está coletada, leva à página do governador. */
  let doVice = null;
  if (p.cargoTse === "VICE-GOVERNADOR" && p.estado === "atual" && /^[A-Z]{2}$/.test(p.uf || "")) {
    try {
      const [g, indice] = await Promise.all([carregar(`dados/governo/${p.uf}.json`), carregar(`dados/indice/${p.uf}.json`)]);
      const gov = indice.find((x) => x.ordemCargo === 5 && x.estado === "atual");
      if (gov && g.materias.length) doVice = { gov, host: g.host };
    } catch { /* sem dados: cai no texto padrão */ }
  }
  /* Prefeito de capital em exercício: o que enviou à Câmara Municipal, quando ela usa um sistema que já coletamos. */
  const prefeito = p.cargoTse === "PREFEITO";
  if (prefeito && p.estado === "atual" && p.unidadeEleitoral) {
    try { governo = await carregar(`dados/prefeitura/${p.unidadeEleitoral}.json`); } catch { /* sem dados: cai no texto padrão */ }
  }
  const orgao = prefeito ? "à Câmara Municipal" : "à Assembleia";
  const vetosGov = governo ? governo.materias.filter((x) => x.tipo === "VET") : [];
  const enviadosGov = governo ? governo.materias.filter((x) => x.tipo !== "VET") : [];
  const comGoverno = enviadosGov.length + vetosGov.length > 0;
  const aprovados = enviados.filter((x) => /^(transformad|vetad|aguardando sanção)/i.test(x.situacao || "") || x.veto);
  const painelVotacoes = comGoverno
    ? `<section class="painel"><div class="painel-titulo"><h2>Vetos</h2></div>
        <p>${esc(p.cargo)} não vota em plenário. O que faz é propor leis, sancionar ou vetar o que ${prefeito ? "a Câmara" : "a Assembleia"} aprova, e editar decretos. Aqui estão os vetos enviados ${orgao} desde ${prefeito ? 2025 : 2023}: <b>${vetosGov.length}</b>. A situação é a que ${prefeito ? "a Câmara" : "a Assembleia"} registra no sistema dela, e nem sempre é atualizada.</p>
        ${legendaGoverno(prefeito)}<div id="lista-vetos"></div>
        ${avisoGoverno(prefeito)}<p>Quem vota é ${esc(casa.quem)}.</p>
        ${fontes([casa.link, ["Sistema de processo legislativo", `https://${governo.host}`]])}</section>`
    : doVice
    ? `<section class="painel"><div class="painel-titulo"><h2>Votações</h2></div>
        <p>${esc(p.cargo)} não vota projetos em plenário nem envia ou veta leis: quem faz isso é o governador. Substitui o governador quando ele se ausenta e assume se o cargo ficar vago.</p>
        <p>Veja o que <a href="${esc(linkPolitico(doVice.gov))}">${esc(doVice.gov.n)}</a> enviou e vetou na Assembleia.</p>
        ${fontes([casa.link, ["Sistema de processo legislativo", `https://${doVice.host}`]])}</section>`
    : comDados
    ? `<section class="painel"><div class="painel-titulo"><h2>Sanções e vetos</h2></div>
        <p>${esc(p.cargo)} não vota em plenário. O que faz é propor leis, sancionar ou vetar o que o Congresso aprova, e editar decretos. Aqui estão os projetos e medidas provisórias que enviou e que o Congresso aprovou: <b>${aprovados.length}</b>, sendo <b>${aprovados.filter((x) => x.veto === "parcial").length}</b> sancionados com vetos parciais. Cada item mostra, passo a passo, o que o presidente fez (enviou, editou, sancionou ou vetou) e o que o Congresso fez.</p>
        ${LEGENDA_PRESIDENTE}<div id="lista-sancoes"></div>
        ${AVISO_PRESIDENTE}<p>Quem vota o que ${esc(p.cargo.toLowerCase())} envia é ${esc(casa.quem)}.</p>
        ${fontes([["Planalto: decretos e leis", "https://www.planalto.gov.br/ccivil_03/"], casa.link, ["Dados abertos da Câmara", "https://dadosabertos.camara.leg.br"]])}</section>`
    : executivo
    ? `<section class="painel"><div class="painel-titulo"><h2>Votações</h2></div>
        <p>${esc(p.cargo)} é cargo do Poder Executivo: não vota projetos em plenário. O que faz é propor leis, sancionar ou vetar o que o Legislativo aprova, e editar decretos.</p>
        <p>Quem vota é ${esc(casa.quem)}. Para saber como os legisladores votaram o que ${esc(p.cargo.toLowerCase())} enviou, veja a fonte oficial.</p>
        ${fontes([casa.link, ...fonteTse].filter(Boolean))}</section>`
    : `<section class="painel"><div class="painel-titulo"><h2>Votações</h2></div>
        <p>Ainda não temos os votos nominais de ${esc(p.cargo.toLowerCase())} ${esc(casa.em)}: cada casa legislativa publica seus dados de um jeito, e só a Câmara dos Deputados e o Senado estão no site por enquanto.</p>
        <p>As votações e a presença ficam no site oficial da casa.</p>
        ${fontes([casa.link].filter(Boolean))}</section>`;

  const painelPropostas = `<section class="painel"><div class="painel-titulo"><h2>Propostas</h2></div>
      ${comDados ? `<p>Projetos de lei, leis complementares, emendas à Constituição e medidas provisórias enviados por ${esc(nome)} ao Congresso desde 2023: <b>${enviados.length}</b>. As propostas de campanha ficam no plano de governo da candidatura no TSE.</p><p>${esc(nome)} é o <b>autor</b> de todos: são propostas do Poder Executivo. Cada item mostra o que ele fez e o que o Congresso fez depois.</p>${LEGENDA_PRESIDENTE}<div id="lista-enviados"></div>${AVISO_PROPOSTAS_PRESIDENTE}` : ""}
      ${comGoverno ? `<p>Projetos de lei, leis complementares, ${prefeito ? "emendas à Lei Orgânica" : "emendas à Constituição"}, medidas provisórias e mensagens enviados por ${esc(nome)} ${orgao} desde ${prefeito ? 2025 : 2023}: <b>${enviadosGov.length}</b>. As propostas de campanha ficam no plano de governo da candidatura no TSE.</p><p>${esc(nome)} é o <b>autor</b> de todos: são propostas do Executivo. Cada item mostra o que ${prefeito ? "o prefeito" : "o governador"} fez e o que ${prefeito ? "a Câmara" : "a Assembleia"} fez depois.</p>${legendaGoverno(prefeito)}<div id="lista-enviados-gov"></div>${avisoGovernoPropostas(prefeito)}` : ""}
      ${doVice ? `<p>${esc(p.cargo)} não apresenta projetos à Assembleia. Os projetos enviados pelo governo, e os vetos, estão na página de <a href="${esc(linkPolitico(doVice.gov))}">${esc(doVice.gov.n)}</a>.</p>` : ""}
      ${comDados || comGoverno || doVice ? "" : executivo
        ? `<p>As propostas de ${esc(nome)} estão no plano de governo registrado na candidatura, quando o candidato o apresentou ao TSE. Ele fica na página da candidatura, junto com as certidões e a prestação de contas.</p>`
        : `<p>Ainda não temos os projetos apresentados por ${esc(nome)} ${esc(casa.em)}. A lista de autoria e a tramitação ficam no site oficial da casa.</p>
           <p>As propostas de campanha, quando registradas, ficam na página da candidatura no TSE.</p>`}
      ${fontes([...(executivo ? [] : [casa.link]), ...fonteTse].filter(Boolean))}</section>`;

  alvo.innerHTML = `
    <section class="perfil">
      ${foto({ nome, foto: p.foto }, true)}
      <div>
        <h1>${esc(nome)}</h1>
        <p class="sub"><span class="selo">${esc(p.partido || "")}${p.uf && p.uf !== "BR" ? "/" + esc(p.uf) : ""}</span> ${esc(p.cargo)}${p.municipio ? ` em ${esc(p.municipio)}` : ""}</p>
      </div>
    </section>
    <div class="abas-pagina" role="tablist" aria-label="Seções do perfil">
      <button type="button" role="tab" id="aba-perfil" aria-controls="painel-perfil" data-aba="perfil">Perfil e bens</button>
      <button type="button" role="tab" id="aba-eleicao" aria-controls="painel-eleicao" data-aba="eleicao">Quem o elegeu?</button>
      <button type="button" role="tab" id="aba-votacoes" aria-controls="painel-votacoes" data-aba="votacoes">${comDados ? "Sanções e vetos" : comGoverno ? "Vetos" : "Votações"}</button>
      <button type="button" role="tab" id="aba-propostas" aria-controls="painel-propostas" data-aba="propostas">Propostas</button>
    </div>
    <div role="tabpanel" id="painel-perfil" aria-labelledby="aba-perfil">${painelPerfil}</div>
    <div role="tabpanel" id="painel-eleicao" aria-labelledby="aba-eleicao" hidden>${painelEleicaoDe(p, nome)}</div>
    <div role="tabpanel" id="painel-votacoes" aria-labelledby="aba-votacoes" hidden>${painelVotacoes}</div>
    <div role="tabpanel" id="painel-propostas" aria-labelledby="aba-propostas" hidden>${painelPropostas}</div>`;
  ligarAbas(alvo);
  if (comGoverno) {
    listaPaginada($("#lista-vetos"), vetosGov, itemGoverno(prefeito), 15, "Nenhum veto registrado.");
    listaPaginada($("#lista-enviados-gov"), enviadosGov, itemGoverno(prefeito), 15);
  }
  if (comDados) {
    listaPaginada($("#lista-sancoes"), aprovados, itemExecutivo, 15, "Nenhum projeto virou lei ainda.");
    listaPaginada($("#lista-enviados"), enviados, itemExecutivo, 15);
  }

  if (p.fonte === "tse") {
    listaPaginada($("#lista-bens"), bens, ([tipo, desc, valor]) => `<li>
      <span class="quando"><b>${esc(tipo)}</b></span><b>${reais(valor)}</b>
      ${desc ? `<span class="texto">${esc(desc.charAt(0) + desc.slice(1).toLowerCase())}</span>` : ""}</li>`, 10, "Nenhum bem declarado.");
  }
}
