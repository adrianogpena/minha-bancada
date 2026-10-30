/* Senador: presença, recursos e abas. */
import { esc, reais, reaisCentavos, pct, data, carregar, numeroBr, urlSegura } from "./util.js";
import { itemFicha, selosPar } from "./comum.js";
import { TIPOS_PROJETO, fontes, UFS, SENADO_API, SENADO_ADM_API, linkMateriaSenado, temResultado } from "./apis.js";
import { painelGastos } from "./deputado.js";
import { montarParlamentar } from "./parlamentar.js";
import { avisoLicenca } from "./ministros.js";
import { painelEleicaoDe } from "./eleicao.js";
import { carregarEmendas, painelEmendas } from "./emendas.js";

/* Comparecimento do senador às votações nominais (gerar.py: categoria_presenca). */
function painelPresenca(pr) {
  const faltas = [pr.naoCompareceu && `não compareceu a ${pr.naoCompareceu}`, pr.licenca && `${pr.licenca} em licença`,
    pr.missao && `${pr.missao} em missão oficial ou atividade parlamentar`, pr.outros && `${pr.outros} por outros motivos`].filter(Boolean);
  return `<h2>Comparecimento às votações</h2>
    <p>Compareceu a <b>${numeroBr(pr.compareceu || 0)}</b> de ${numeroBr(pr.votacoes)} votações nominais (<b>${pct(pr.compareceu || 0, pr.votacoes)}</b>), contando como presença quem votou ou registrou presença sem votar.
    ${faltas.length ? `Nas demais: ${faltas.join("; ")}.` : "Não faltou a nenhuma."} Fonte: <a href="${SENADO_API}/votacao" rel="noopener">votações nominais do Senado (Dados Abertos)</a>.</p>`;
}

/* Recursos e benefícios do senador (coletar.py: coletar_recursos_senado). */
function painelRecursos(rec) {
  const selos = (rec.beneficios || []).length
    ? selosPar(rec.beneficios.map(([b, u]) => [b, u === "Utilizou" ? "usa" : "não usa"]), true) : "";
  const pessoal = (rec.pessoal || []).filter(([, n]) => n);
  return `<h2>Recursos e benefícios em ${rec.ano}</h2>
    ${selos}
    ${pessoal.length ? `<p>Pessoal: ${pessoal.map(([l, n]) => `<b>${numeroBr(n)}</b> no ${esc(l.toLowerCase().replace("escritório(s) de apoio", "escritório de apoio"))}`).join("; ")}.</p>` : ""}
    ${rec.foraCota?.length ? `<h3>Gastos fora da cota: ${reaisCentavos(rec.totalForaCota)}</h3>
      <div class="rolagem"><table class="tabela"><thead><tr><th>Recurso</th><th>Valor</th></tr></thead><tbody>
      ${rec.foraCota.map(([r, v]) => `<tr><td>${esc(r)}</td><td>${reais(v)}</td></tr>`).join("")}</tbody></table></div>
      <p class="vazio">Diárias, correios e material pagos pelo Senado, que não entram na cota (CEAPS).</p>` : ""}
    ${rec.escritorios?.length ? `<h3>Escritório${rec.escritorios.length > 1 ? "s" : ""} de apoio no estado</h3>
      <ul>${rec.escritorios.map((e) => `<li>${esc(e.endereco || e.nome || "")}${e.telefone ? ` · ${esc(e.telefone)}` : ""}</li>`).join("")}</ul>` : ""}`;
}

/* Aposentadoria parlamentar de ex-senador (apis.js: carregarAposentadoria). */
export function painelAposentadoria(a) {
  if (!a) return "";
  const rotulo = a.tipo === "EX-SENADOR IPC" ? "Instituto de Previdência dos Congressistas (IPC)" : a.tipo === "EX-SENADOR PSSC" ? "Plano de Seguridade Social dos Congressistas (PSSC)" : a.tipo;
  return `<h2>Aposentadoria parlamentar</h2>
    <p>Recebe aposentadoria de ex-senador pelo <b>${esc(rotulo)}</b>${a.inicio ? ` desde ${data(a.inicio, true)}` : ""}${a.valor ? `: <b>${reaisCentavos(a.valor)}</b> por mês` : ""}.
    A fonte traz só o nome, e a ligação a esta pessoa é pelo nome completo.</p>
    ${fontes([["Aposentados do Senado", `${SENADO_ADM_API}/senadores/aposentados`]])}`;
}

/* Comissões e mandatos do senador (coletar.py: coletar_ficha_senado). */
function painelComissoesMandatos(sen, id) {
  const comissoes = sen.comissoes || [], mandatos = sen.mandatos || [];
  const periodo = (a, b) => `${a ? `desde ${data(a)}` : ""}${b ? ` até ${data(b)}` : ""}`;
  const api = `${SENADO_API}/senador/${encodeURIComponent(id)}`;
  return `<h2>Comissões</h2>
    ${comissoes.length ? `<ul class="lista-simples">${comissoes.map((c) => `<li><b>${esc(c.sigla)}</b> ${esc(c.nome)}<br><span class="quando">${esc(c.cargo || "Membro")}${c.casa ? ` · ${esc(c.casa)}` : ""}, ${periodo(c.inicio, c.fim)}</span></li>`).join("")}</ul>`
      : `<p class="vazio">Nenhuma participação registrada no mandato atual.</p>`}
    ${mandatos.length ? `<h2>Mandatos no Senado</h2>
      <ul class="lista-simples">${mandatos.map((m) => `<li>${m.inicio ? data(m.inicio) : "?"} a ${m.fim ? data(m.fim) : "?"}, ${esc(m.uf || "")}${m.cargo ? ` (${esc(m.cargo.toLowerCase())})` : ""}
        ${(m.partidos || []).length ? `<br><span class="quando">Partidos: ${m.partidos.map((x) => `${esc(x.sigla)}${x.filiacao ? ` desde ${data(x.filiacao)}` : ""}${x.desfiliacao ? ` até ${data(x.desfiliacao)}` : ""}`).join(" · ")}</span>` : ""}</li>`).join("")}</ul>` : ""}
    ${fontes([["Comissões do senador (Dados Abertos do Senado)", `${api}/comissoes`], ["Mandatos do senador (Dados Abertos do Senado)", `${api}/mandatos`]])}`;
}

export async function montarSenador(alvo, p, nome, ficha) {
  let sen, lista;
  try { [sen, lista] = await Promise.all([carregar(`dados/senador/${encodeURIComponent(p.id)}.json`), carregar("dados/votacoes_senado.json")]); } catch { return false; }
  const emendas = await carregarEmendas(p.pessoa);
  const meus = new Map(sen.votos.map((v) => [v.id, v.voto]));
  const linhaDoTempo = lista.filter((v) => temResultado(v) && meus.has(v.id)).map((v) => ({ ...v, voto: meus.get(v.id) }));
  const situacao = p.fimMandato ? `Mandato até ${data(p.fimMandato, true)}.` : "";
  const apiVotacao = (v) => `${SENADO_API}/votacao?dataInicio=${v.data.replaceAll("-", "")}&dataFim=${v.data.replaceAll("-", "")}`;
  montarParlamentar(alvo, {
    nome, foto: { nome, foto: p.foto }, antes: sen.ministro ? await avisoLicenca(sen.ministro, "senador") : "", painelEleicao: painelEleicaoDe(p, nome),
    subtitulo: `<span class="selo">${esc(p.partido || "")}/${esc(p.uf)}</span> ${esc(p.cargo)}${p.participacao && p.participacao !== "Titular" ? `, ${esc(p.participacao.toLowerCase())}` : ""}`,
    painelPerfil: `<p class="situacao">${esc(situacao)}</p>
      <h2>Ficha</h2>
      <dl class="ficha">${ficha.map(itemFicha).join("")}
        <dt>Onde atua</dt><dd>${esc(UFS[p.uf] || p.uf)}</dd>
        ${urlSegura(p.pagina) ? `<dt>Página oficial</dt><dd><a href="${esc(p.pagina)}" rel="noopener">Perfil no Senado Federal</a></dd>` : ""}
      </dl>
      ${sen.presenca ? painelPresenca(sen.presenca) : ""}
      ${sen.despesas ? painelGastos(sen.despesas, "A cota (CEAPS) reembolsa despesas do mandato, como passagens, aluguel de escritório e divulgação. Os valores são os reembolsados pelo Senado.")
        : `<p class="aviso">Os gastos da cota (CEAPS) não puderam ser carregados agora. Veja no <a href="https://www6g.senado.leg.br/transparencia/sen/${encodeURIComponent(p.id)}" rel="noopener">Portal da Transparência do Senado</a>.</p>`}
      ${sen.recursos ? painelRecursos(sen.recursos) : ""}
      ${painelEmendas(emendas)}
      ${painelAposentadoria(p.aposentadoria)}
      ${sen.comissoes || sen.mandatos ? painelComissoesMandatos(sen, p.id) : ""}
      ${fontes([["Dados Abertos do Senado", `${SENADO_API}/senador/${encodeURIComponent(p.id)}`], sen.despesas ? ["Cota parlamentar (CEAPS)", `${SENADO_ADM_API}/senadores/despesas_ceaps/${sen.despesas.ano}`] : null, sen.recursos ? ["Recursos utilizados", `${SENADO_ADM_API}/senadores/${encodeURIComponent(p.id)}/recursos-utilizados?ano=${sen.recursos.ano}`] : null, sen.recursos?.escritorios ? ["Escritórios de apoio", `${SENADO_ADM_API}/senadores/escritorios-apoio`] : null, ["Portal da Transparência do Senado", `https://www6g.senado.leg.br/transparencia/sen/${encodeURIComponent(p.id)}`]])}`,
    rotuloPerfil: sen.despesas ? "Perfil e gastos" : "Perfil",
    linhaDoTempo, proposicoes: sen.proposicoes, tipoProjeto: (x) => !!TIPOS_PROJETO[x.tipo],
    textoLegislatura: "como autor ou coautor desde 2019",
    papel: (x) => x.principal ? "<b>autor principal</b> (o primeiro a assinar)." : "<b>coautor</b> (assinou depois do autor principal).",
    aviso: "A situação vem da tramitação no Senado e é atualizada aos poucos todo dia.",
    fonteTramitacao: "Tramitação (Senado)",
    fonteEmenta: "Senado",
    hrefProposicao: (x) => `proposicao.html?k=s-${encodeURIComponent(x.id)}`,
    linkTramitacao: (x) => linkMateriaSenado(x.id),
    linkApi: (x) => `${SENADO_API}/processo/${encodeURIComponent(x.proc)}`,
    hrefVotacao: (v) => `votacao.html?casa=senado&id=${encodeURIComponent(v.id)}`,
    fontesVotacao: (v) => [["Votos de cada senador (API do Senado)", apiVotacao(v)], v.propId ? ["Tramitação da matéria", linkMateriaSenado(v.propId)] : null],
  });
  return true;
}
