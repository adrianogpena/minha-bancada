/* Montagem da ficha de um parlamentar (deputado ou senador). */
import { $, esc, pct, data, dataHora, urlSegura } from "./util.js";
import { VOTOS, foto, selo, legenda, listaPaginada, abas, ligarAbas } from "./comum.js";
import { CAMARA_API, resultado, desfecho, movimentadoNoAno, fontes } from "./apis.js";
import { barraPlacar } from "./votacoes.js";
import { LEGENDA_PROJETOS, avisoDados } from "./executivo.js";
import { abaEventos, painelEventos, montarEventos } from "./eventos.js";

/* Tabela "Com quem assina projetos" das duas Casas. `c` traz projetos e outroPartido; `linhas` são as células [parceiro, partido, projetos] já em HTML. */
export function painelCoautoria({ c, quem, linhas, nota, fonte, vazio = "", intro = "" }) {
  if (!c) return vazio ? `<h2>Com quem assina projetos</h2><p class="vazio">${vazio}</p>` : "";
  return `
    <h2>Com quem assina projetos</h2>
    <p>${c.projetos} ${c.projetos === 1 ? "projeto assinado" : "projetos assinados"} com outros ${quem === "Deputado" ? "deputados" : "parlamentares"}, ${c.outroPartido} com ${quem === "Deputado" ? "deputado" : "parlamentar"} de outro partido (${pct(c.outroPartido, c.projetos)}).${intro}</p>
    <div class="rolagem"><table class="tabela"><thead><tr><th>${quem}</th><th>Partido</th><th>Projetos em comum</th></tr></thead><tbody>
      ${linhas.map(([n, pt, q]) => `<tr><td>${n}</td><td>${pt}</td><td>${q}</td></tr>`).join("")}
    </tbody></table></div>
    <p class="quando">${nota}</p>
    ${fontes([fonte])}`;
}

const TIPOS_SESSAO = { DOR: "Sessão deliberativa ordinária", DEX: "Sessão deliberativa extraordinária", NOR: "Sessão não deliberativa", ESP: "Sessão especial" };

/* As três abas (perfil, votações, propostas) de um parlamentar. Serve a deputados e senadores. */
export function montarParlamentar(alvo, c) {
  const nome = c.nome, linhaDoTempo = c.linhaDoTempo;
  const projetos = c.proposicoes.filter(c.tipoProjeto), outros = c.proposicoes.filter((p) => !c.tipoProjeto(p));
  const contagem = linhaDoTempo.reduce((m, v) => ((m[v.voto] = (m[v.voto] || 0) + 1), m), {});
  const votou = linhaDoTempo.length - (contagem.ausente || 0) - (contagem.obstrucao || 0);

  const painelVotacoes = `
    <section class="painel" aria-labelledby="t-painel">
      <div class="painel-titulo">
        <h2 id="t-painel">Votos no Plenário</h2>
        <p>${linhaDoTempo.length} votações nominais${linhaDoTempo.length ? `, de ${data(linhaDoTempo.at(-1).data)} a ${data(linhaDoTempo[0].data)}` : ""}. Da mais antiga para a mais recente.</p>
      </div>
      <div class="faixa" role="list">${[...linhaDoTempo].reverse().map((v) =>
        `<a role="listitem" class="v-${v.voto}" ${c.hrefVotacao ? `href="${esc(c.hrefVotacao(v))}"` : ""} title="${esc(data(v.data))}: ${esc(VOTOS[v.voto]?.rotulo)}. ${esc(v.proposicao || "")} ${esc((v.descricao || "").slice(0, 120))}" aria-label="${esc(data(v.data))}, ${esc(VOTOS[v.voto]?.rotulo)}"></a>`).join("")}</div>
      ${legenda(["sim", "nao", "abstencao", "obstrucao", ...(contagem.secreto ? ["secreto"] : []), "ausente"])}
      <div class="numeros">
        <div><b>${pct(votou, linhaDoTempo.length)}</b><span>votou (sim, não ou abstenção)</span></div>
        <div><b>${contagem.sim || 0}</b><span>votos sim</span></div>
        <div><b>${contagem.nao || 0}</b><span>votos não</span></div>
        <div><b>${contagem.abstencao || 0}</b><span>abstenções</span></div>
        <div><b>${(contagem.obstrucao || 0) + (contagem.art17 || 0) + (contagem.outro || 0)}</b><span>obstrução e outros</span></div>
        ${contagem.secreto ? `<div><b>${contagem.secreto}</b><span>votos secretos</span></div>` : ""}
        <div><b>${contagem.ausente || 0}</b><span>sem voto registrado</span></div>
      </div>
    </section>
    ${c.painelComportamento || ""}
    <h2 id="votos">Como votou</h2>
    <p>Cada linha mostra o voto de ${esc(nome)}, o resultado final da votação e o placar geral.</p>
    <div class="abas" id="abas-votos"></div>
    <div id="lista-votos"></div>`;

  const painelPropostas = `
    <section class="painel">
      <div class="painel-titulo"><h2>Propostas de ${esc(nome)}</h2>
        <p>${c.proposicoes.length} documentos apresentados ${esc(c.textoLegislatura)}.</p></div>
      <div class="numeros" id="numeros-prop"></div>
    </section>
    <section id="destaque-ano"></section>
    <section id="relatorias">${c.painelRelatorias || ""}</section>
    <h2 id="proposicoes">Projetos <small class="sub">(${projetos.length})</small></h2>
    <p>Projetos de lei, emendas à Constituição e similares. ${esc(c.aviso)}</p>
    ${LEGENDA_PROJETOS}
    <div class="abas" id="abas-proj"></div>
    <div id="filtro-tema"></div>
    <div id="lista-proj"></div>
    ${avisoDados(["O voto de cada parlamentar nesses projetos (só aparece na aba de votações, e apenas nas votações nominais).", "O texto exato de cada emenda ou substitutivo aprovado, e quem foi o relator.",
      "Se foi o próprio parlamentar quem pediu a retirada ou o arquivamento. \"Tramitação encerrada\" não diz se o projeto virou lei.", "A situação vem do sistema da Casa e pode estar atrasada."])}
    ${c.semOutros ? `<p class="aviso">${esc(c.semOutros)}</p>` : `
    <h2>Outros documentos <small class="sub">(${outros.length})</small></h2>
    <p>Requerimentos, indicações, emendas a outros projetos, pareceres e afins. Cada um tem a tramitação como fonte.</p>
    <div class="abas" id="abas-outros"></div>
    <div id="lista-outros"></div>`}`;

  alvo.innerHTML = `
    <section class="perfil">
      ${foto(c.foto, true)}
      <div>
        <h1>${esc(nome)}</h1>
        <p class="sub">${c.subtitulo}</p>
      </div>
    </section>
    ${c.antes || ""}
    <div class="abas-pagina" role="tablist" aria-label="Seções do perfil">
      <button type="button" role="tab" id="aba-perfil" aria-controls="painel-perfil" data-aba="perfil">${esc(c.rotuloPerfil)}</button>
      <button type="button" role="tab" id="aba-eleicao" aria-controls="painel-eleicao" data-aba="eleicao">Quem o elegeu?</button>
      <button type="button" role="tab" id="aba-votacoes" aria-controls="painel-votacoes" data-aba="votacoes">Votações <small>${linhaDoTempo.length}</small></button>
      <button type="button" role="tab" id="aba-propostas" aria-controls="painel-propostas" data-aba="propostas">Propostas <small>${c.proposicoes.length}</small></button>
      ${abaEventos}
    </div>
    <div role="tabpanel" id="painel-perfil" aria-labelledby="aba-perfil">${c.painelPerfil}</div>
    <div role="tabpanel" id="painel-eleicao" aria-labelledby="aba-eleicao" hidden>${c.painelEleicao}</div>
    <div role="tabpanel" id="painel-votacoes" aria-labelledby="aba-votacoes" hidden>${painelVotacoes}</div>
    <div role="tabpanel" id="painel-propostas" aria-labelledby="aba-propostas" hidden>${painelPropostas}</div>
    ${painelEventos}`;

  ligarAbas(alvo);
  montarEventos(alvo, c.fichas);

  /* --- aba Votações --- */
  const textoPlacar = (v) => {
    const pl = v.placar || {};
    const partes = [`Sim ${pl.sim || 0}`, `Não ${pl.nao || 0}`, `Abstenção ${pl.abstencao || 0}`];
    if (pl.obstrucao) partes.push(`Obstrução ${pl.obstrucao}`);
    if (pl.secreto) partes.push(`Voto secreto ${pl.secreto}`);
    if (pl.art17) partes.push(`Presidente (art. 51) ${pl.art17}`);
    if (pl.outro) partes.push(`Outros ${pl.outro}`);
    if (v.ausentes) partes.push(`Sem voto registrado ${v.ausentes}`);
    return partes.join(" · ");
  };
  const renderVoto = (v) => {
    const [res, classe] = resultado(v.aprovada);
    const pl = v.placar || {};
    const sessao = v.sessao ? [v.sessao.tipo && (TIPOS_SESSAO[v.sessao.tipo] || `Sessão ${v.sessao.tipo}`), v.sessao.numero && `nº ${v.sessao.numero}`, v.sessao.votacao && `votação ${v.sessao.votacao} do dia`].filter(Boolean).join(", ") : "";
    return `<li class="cartao-item">
      <span class="quando">${v.dataHora ? esc(dataHora(v.dataHora)) : `${data(v.data)}${v.hora ? `, ${esc(v.hora)}` : ""}`}${v.proposicao ? `, <b>${esc(v.proposicao)}</b>` : ""}</span>
      <span>${selo(v.voto)} <span class="resultado r-${classe}">${esc(res)}</span></span>
      ${c.hrefVotacao ? `<a class="texto" href="${esc(c.hrefVotacao(v))}">${esc(v.descricao || "Votação sem descrição")}</a>` : `<span class="texto">${esc(v.descricao || "Votação sem descrição")}</span>`}
      ${v.secreta ? `<span class="texto aviso-ementa"><b>Votação secreta:</b> o Senado informa que cada senador votou, mas não como. O voto individual não é público.</span>` : ""}
      ${v.ementa ? `<span class="texto ementa">${esc(v.ementa)}</span>` : `<span class="texto ementa sem-ementa">Ementa não informada${c.fonteEmenta ? ` pelo ${esc(c.fonteEmenta)}` : ""}.</span>`}
      <span class="texto">${barraPlacar(pl)}<span class="quando">Placar${v.placarOficial === undefined ? "" : v.placarOficial ? " oficial" : " (contado dos votos individuais)"}: ${esc(textoPlacar(v))}</span></span>
      ${sessao ? `<span class="texto quando">${esc(sessao)}${v.resultadoTexto ? ` · Resultado informado: ${esc(v.resultadoTexto)}` : ""}</span>` : ""}
      <span class="texto">${fontes(c.fontesVotacao(v))}</span>
    </li>`;
  };
  const filtrosVoto = { todos: () => true, sim: (v) => v.voto === "sim", nao: (v) => v.voto === "nao", outros: (v) => ["abstencao", "obstrucao", "art17", "outro"].includes(v.voto), secreto: (v) => v.voto === "secreto", ausente: (v) => v.voto === "ausente" };
  const mostrarVotos = (f) => listaPaginada($("#lista-votos"), linhaDoTempo.filter(filtrosVoto[f]), renderVoto, 10, "Nenhuma votação nesse filtro.");
  abas($("#abas-votos"), [{ valor: "todos", rotulo: "Todas" }, { valor: "sim", rotulo: "Sim" }, { valor: "nao", rotulo: "Não" }, { valor: "outros", rotulo: "Abstenção e obstrução" }, ...(contagem.secreto ? [{ valor: "secreto", rotulo: "Voto secreto" }] : []), { valor: "ausente", rotulo: "Sem voto" }], mostrarVotos);
  mostrarVotos("todos");

  /* --- aba Propostas --- */
  const destinos = projetos.map((p) => desfecho(p)[1]);
  const cont = destinos.reduce((m, d) => ((m[d] = (m[d] || 0) + 1), m), {});
  $("#numeros-prop").innerHTML = `
    <div><b>${projetos.length}</b><span>projetos</span></div>
    <div><b>${cont.tramitando || 0}</b><span>em tramitação</span></div>
    <div><b>${cont.aprovada || 0}</b><span>aprovados ou viraram lei</span></div>
    <div><b>${cont.rejeitada || 0}</b><span>arquivados ou retirados</span></div>
    <div><b>${cont.sem || 0}</b><span>${esc(c.rotuloSem || "situação a consultar")}</span></div>`;
  const comAutoria = projetos.filter((p) => p.principal !== undefined), proprias = comAutoria.filter((p) => p.principal);
  if (comAutoria.length) {
    const aprovadasProprias = proprias.filter((p) => desfecho(p)[1] === "aprovada").length, supra = comAutoria.filter((p) => p.partidosDistintos > 1).length;
    $("#numeros-prop").insertAdjacentHTML("beforeend", `
      <div><b>${proprias.length}</b><span>como autor principal (${pct(proprias.length, comAutoria.length)} dos ${comAutoria.length} com autoria coletada)</span></div>
      <div><b>${comAutoria.length - proprias.length}</b><span>como coautor</span></div>
      <div><b>${aprovadasProprias}</b><span>aprovados, sendo autor principal</span></div>
      ${c.suprapartidarios ? `<div><b>${supra}</b><span>suprapartidários (de 2 ou mais partidos)</span></div>` : ""}`);
  }
  const porId = new Map(c.proposicoes.map((x) => [String(x.id), x]));
  const ligacao = (rotulo, id) => {
    const outro = porId.get(String(id));
    const href = c.linkTramitacao(outro || { id });
    const texto = outro ? esc(`${outro.tipo} ${outro.numero}/${outro.ano}`) : "ver tramitação";
    return `${rotulo}: ${urlSegura(href) ? `<a href="${esc(href)}" rel="noopener">${texto}</a>` : texto}`;
  };

  const renderProj = (p) => {
    const [texto, destino, cor] = desfecho(p), classe = cor || destino;
    return `<li class="cartao-item">
      <span class="quando"><b>${esc(p.tipo)} ${esc(p.numero)}/${esc(p.ano)}</b>${p.dataApresentacao ? `, apresentado em ${data(p.dataApresentacao)}` : ""}${p.principal ? ", autor principal" : ""}</span>
      <span class="resultado r-${classe}">${esc(texto)}</span>
      <span class="texto">${esc(p.ementa || "Sem ementa")}</span>
      ${p.ementaDetalhada && p.ementaDetalhada !== p.ementa ? `<details class="texto"><summary>Ementa detalhada</summary>${esc(p.ementaDetalhada)}</details>` : ""}
      ${typeof p.emTramitacao === "boolean" ? `<span class="texto quando">${p.emTramitacao ? "Em tramitação" : "Fora de tramitação"} segundo a Casa.</span>` : ""}
      ${c.papel ? `<span class="texto"><b>Papel de ${esc(nome)}:</b> ${c.papel(p)}</span>` : ""}
      ${!p.situacao && p.tramitacao ? `<span class="texto"><b>Última tramitação:</b> ${esc(p.tramitacao)}${p.orgao ? ` (${esc(p.orgao)})` : ""}${p.dataSituacao ? `, em ${data(p.dataSituacao)}` : ""}.${p.despacho ? ` <span class="quando">Despacho: ${esc(p.despacho.slice(0, 300))}</span>` : ""}</span>` : ""}
      ${p.situacao ? `<span class="texto"><b>Situação:</b> ${esc(p.situacao)}${p.orgao ? ` (${esc(p.orgao)})` : ""}${p.dataSituacao ? `, em ${data(p.dataSituacao)}` : ""}.${p.despacho ? ` <span class="quando">Despacho: ${esc(p.despacho.slice(0, 300))}</span>` : ""}</span>` : ""}
      ${p.tipoDescricao || p.tramitacao || p.regime || p.coautores || p.iniciativa ? `<span class="texto quando">${[p.tipoDescricao && `Tipo: ${esc(p.tipoDescricao)}`, p.iniciativa && `Iniciativa: ${esc(p.iniciativa)}`, p.totalAutores && `Assinado por ${p.totalAutores} autores${p.partidosDistintos ? ` de ${p.partidosDistintos} partidos` : ""}`, p.regime && `Regime: ${esc(p.regime)}`, p.tramitacao && `Tramitação: ${esc(p.tramitacao)}`, p.coautores && `Coautores: ${esc(p.coautores.join(", "))}`].filter(Boolean).join(" · ")}</span>` : ""}
      ${p.apensadoA || p.anterior || p.posterior ? `<span class="texto quando">${[p.apensadoA && ligacao("Apensado ao projeto principal", p.apensadoA), p.anterior && ligacao("Proposição anterior", p.anterior), p.posterior && ligacao("Proposição posterior", p.posterior)].filter(Boolean).join(" · ")}</span>` : ""}
      ${p.votacoes ? votacoesDoProjeto(p) : ""}
      ${p.temas ? `<span class="texto quando">Tema oficial: ${esc(p.temas.join(", "))}</span>` : ""}
      ${p.palavrasChave ? `<span class="texto quando">Temas: ${esc(p.palavrasChave)}</span>` : ""}
      ${c.hrefProposicao && c.tipoProjeto(p) ? `<span class="texto"><a href="${esc(c.hrefProposicao(p))}">Ver todos os políticos ligados a esta proposição</a></span>` : ""}
      <span class="texto">${fontes([[c.fonteTramitacao, c.linkTramitacao(p)], p.linkTexto ? ["Texto integral", p.linkTexto] : null, ["Dados na API", c.linkApi(p)]])}</span>
    </li>`;
  };
  const tiposProj = [...new Set(projetos.map((p) => p.tipo))].sort();
  let abaProj = "todos", temaProj = "";
  const filtroProj = (f) => projetos.filter((p) => (!temaProj || (p.temas || []).includes(temaProj))
    && (f === "todos" ? true : ["tramitando", "aprovada", "rejeitada"].includes(f) ? desfecho(p)[1] === f : p.tipo === f));
  const mostrarProj = (f) => listaPaginada($("#lista-proj"), filtroProj(f), renderProj, 10, "Nenhum projeto nesse filtro.");
  abas($("#abas-proj"), [{ valor: "todos", rotulo: "Todos" }, { valor: "tramitando", rotulo: "Em tramitação" }, { valor: "aprovada", rotulo: "Aprovados" }, { valor: "rejeitada", rotulo: "Arquivados" }, ...tiposProj.map((t) => ({ valor: t, rotulo: t }))], (f) => mostrarProj((abaProj = f)));
  const nomesTemas = [...new Set(projetos.flatMap((p) => p.temas || []))].sort((a, b) => a.localeCompare(b, "pt-BR"));
  if (nomesTemas.length) {
    $("#filtro-tema").innerHTML = `<label class="campo">Tema do projeto<select><option value="">Todos os temas</option>${nomesTemas.map((t) => `<option>${esc(t)}</option>`).join("")}</select></label>`;
    $("#filtro-tema select").addEventListener("input", (e) => { temaProj = e.target.value; mostrarProj(abaProj); });
  }
  mostrarProj("todos");

  const anoAtual = new Date().getFullYear();
  const destaque = projetos.filter((p) => movimentadoNoAno(p, anoAtual)).sort((a, b) => b.dataSituacao.localeCompare(a.dataSituacao));
  if (destaque.length) {
    const porDestino = destaque.reduce((m, p) => { const d = desfecho(p)[1]; m[d] = (m[d] || 0) + 1; return m; }, {});
    const resumo = [[porDestino.tramitando, "em tramitação"], [porDestino.aprovada, "aprovados"], [porDestino.rejeitada, "arquivados ou retirados"], [porDestino.sem, "sem desfecho claro"]]
      .filter(([n]) => n).map(([n, r]) => `${n} ${r}`).join(", ");
    $("#destaque-ano").innerHTML = `<h2>Movimentados em ${anoAtual} <small class="sub">(${destaque.length})</small></h2>
      <p>Projetos do parlamentar cuja situação mudou neste ano, com o status atual de cada um: ${esc(resumo)}. Do movimento mais recente para o mais antigo.</p>
      <div id="lista-destaque"></div>`;
    listaPaginada($("#lista-destaque"), destaque, renderProj, 5, "");
  }

  if (c.relatorias?.length) {
    const renderRelatoria = (x) => `<li class="cartao-item">
      <span class="quando"><b>${esc(x.t)} ${esc(x.n)}/${esc(x.a)}</b></span>
      <span class="resultado r-${esc(x.d)}">${esc(x.s || "Em tramitação")}</span>
      <span class="texto">${esc(x.e || "Sem ementa")}</span>
      <span class="texto"><a href="proposicao.html?k=${encodeURIComponent(x.k)}">Ver todos os políticos ligados a esta proposição</a></span></li>`;
    $("#relatorias").innerHTML = `<h2>Relatorias <small class="sub">(${c.relatorias.length})</small></h2>
      <p>Projetos em que ${esc(nome)} é o último relator informado pela Câmara. Valem só os projetos de deputados da legislatura atual, e o relator pode já ter mudado.</p>
      <div id="lista-relatorias"></div>`;
    listaPaginada($("#lista-relatorias"), c.relatorias, renderRelatoria, 5, "");
  }

  const renderOutro = (p) => `<li>
      <span class="quando"><b>${esc(p.tipo)} ${esc(p.numero)}/${esc(p.ano)}</b></span>
      <span class="texto">${esc(p.ementa || "Sem ementa")}</span>
      <span class="texto">${fontes([[c.fonteTramitacao, c.linkTramitacao(p)]])}</span></li>`;
  if (!c.semOutros) {
    const tiposOutros = [...new Set(outros.map((p) => p.tipo))].sort();
    const mostrarOutros = (t) => listaPaginada($("#lista-outros"), outros.filter((p) => t === "todos" || p.tipo === t), renderOutro, 10, "Nenhum documento apresentado no período.");
    abas($("#abas-outros"), [{ valor: "todos", rotulo: "Todos" }, ...tiposOutros.map((t) => ({ valor: t, rotulo: t }))], mostrarOutros);
    mostrarOutros("todos");
  }
}


/* Votações do projeto (gerar.py: juntar_votacoes): as nominais levam placar e a orientação de cada bancada. */
function votacoesDoProjeto(p) {
  const item = (v) => `<li><span class="quando">${data(v.data)}${v.orgao ? ` · ${esc(v.orgao)}` : ""}</span> ${esc(v.descricao || "Votação")}
      ${v.nominal ? `<br><span class="quando">${v.aprovada === true ? "Aprovada" : v.aprovada === false ? "Rejeitada" : "Resultado não informado"}: ${["sim", "nao", "abstencao", "obstrucao"].filter((k) => v.placar[k]).map((k) => `${v.placar[k]} ${VOTOS[k]?.rotulo || k}`).join(", ")}.</span>
        ${v.orientacoes ? `<br><span class="quando">Orientação das bancadas: ${Object.entries(v.orientacoes).map(([b, o]) => `${esc(b)} ${esc(o)}`).join(" · ")}.</span>` : ""}
        <br><a href="votacao.html?id=${encodeURIComponent(v.id)}">Ver como cada partido votou</a>`
      : ` <a href="${CAMARA_API}/votacoes/${encodeURIComponent(v.id)}" rel="noopener">Dados da votação</a> <span class="quando">(sem voto nominal)</span>`}</li>`;
  return `<details class="texto"><summary><b>${p.totalVotacoes} ${p.totalVotacoes === 1 ? "votação" : "votações"}</b> deste projeto</summary>
    <ul class="lista-simples">${p.votacoes.map(item).join("")}</ul>
    ${p.totalVotacoes > p.votacoes.length ? `<p class="quando">Mostrando as ${p.votacoes.length} mais recentes.</p>` : ""}
    ${fontes([["Votações do projeto (API da Câmara)", `${CAMARA_API}/proposicoes/${encodeURIComponent(p.id)}/votacoes`]])}</details>`;
}
