/* Fornecedores que mais recebem das cotas e verbas: Câmara, Senado e Assembleias. */
import { $, esc, reais, data, semAcento, carregar, urlSegura } from "./util.js";
import { listaPaginada, erro } from "./comum.js";

const CASAS = { camara: "Câmara", senado: "Senado", estadual: "Assembleias" };

export async function paginaFornecedores() {
  const alvo = $("#resultado");
  let j;
  try { j = await carregar("dados/fornecedores.json"); } catch (e) { return erro(alvo, e); }
  const empresa = await blocoEmpresa();
  const link = (p) => {
    const nome = `${esc(p.nome)} (${esc(p.partido || "s/p")}-${esc(p.uf || "")}, ${reais(p.valor)})`;
    return p.pagina ? `<a href="${esc(p.pagina)}">${nome}</a>` : nome;
  };
  const render = (f) => `<li>
    <span class="quando">${reais(f.total)}</span>
    <span class="texto"><b>${esc(f.nome)}</b> <span class="quando">${f.documento ? esc(f.documento) : "sem CNPJ ou CPF na fonte"}</span></span>
    <span class="texto"><span class="quando">${f.politicos} ${f.politicos === 1 ? "político" : "políticos"}, ${f.notas} ${f.notas === 1 ? "nota" : "notas"}
      · ${Object.entries(f.porCasa).map(([c, v]) => `${CASAS[c] || esc(c)} ${reais(v)}`).join(" · ")}</span>
      <br>Mais usado por ${f.maioresPoliticos.map(link).join(", ")}</span>
    ${empresa(f.id)}</li>`;
  const desenhar = () => {
    const b = semAcento($("#busca").value.trim());
    const casa = $("#casa").value;
    const digitos = b.replace(/\D/g, "");
    const f = j.fornecedores.filter((x) => (!casa || x.porCasa[casa]) &&
      (!b || semAcento(x.nome).includes(b) || (digitos && (x.documento || "").replace(/\D/g, "").includes(digitos))));
    $("#contagem").textContent = `${f.length} dos ${j.fornecedores.length} fornecedores que mais receberam em ${j.ano}`;
    listaPaginada(alvo, f, render, 20, "Nenhum fornecedor encontrado com essa busca.");
  };
  $("#busca").addEventListener("input", desenhar);
  $("#casa").addEventListener("change", desenhar);
  desenhar();
  doadoresEFornecedores(CASAS, empresa);
}

const LIGACAO = { cnpj: "mesmo CNPJ nas duas fontes", nome: "mesmo nome (a prestação de contas coletada não trazia o CNPJ)" };

/* Empresas que doaram a campanhas e foram pagas pela cota (scripts/doadores.py). Some se o arquivo não existe. */
async function doadoresEFornecedores(casas, empresa) {
  let cruz, forn, pessoas;
  try {
    [cruz, forn, pessoas] = await Promise.all([carregar("dados/doadores_fornecedores.json"), carregar("dados/nucleo/fornecedores.json"), carregar("dados/nucleo/pessoas.json")]);
  } catch { return; }
  if (!cruz.cruzamentos.length) return;
  const cadastro = new Map(forn.map((f) => [f.id, f]));
  const pessoa = new Map(pessoas.map((p) => [p.id, p]));
  const fonte = (f) => (f && urlSegura(f.url) ? `<a href="${esc(f.url)}" rel="noopener">${esc(f.nome)}</a>` : esc(f ? f.nome : ""));
  const paginaPaga = (p) => (p.casa === "camara" ? `deputado.html?id=${encodeURIComponent(p.id)}` : p.casa === "senado" ? `politico.html?f=senado&i=${encodeURIComponent(p.id)}` : null);
  const doacao = (d) => {
    const quem = pessoa.get(d.pessoa);
    const nome = quem ? esc(quem.nome) : "um eleito";
    const ficha = `politico.html?f=t/${encodeURIComponent(d.eleicao)}/${encodeURIComponent(d.uf)}&i=${encodeURIComponent(d.sequencial)}`;
    const como = d.via === "repasse" ? "por trás de um repasse de partido ou de outro candidato" : `doação${d.origem ? ` (${esc(d.origem.toLowerCase())})` : ""}`;
    const pagos = (d.pagoPeloMesmoPolitico || []).map((p) => {
      const rotulo = `${casas[p.casa] || esc(p.casa)} ${reais(p.valor)}`;
      return paginaPaga(p) ? `<a href="${esc(paginaPaga(p))}">${rotulo}</a>` : rotulo;
    });
    return `<span class="texto">Campanha de <a href="${esc(ficha)}">${nome}</a> em ${esc(d.eleicao)}: ${como}, <b>${reais(d.valor)}</b>.
      <span class="quando">Ligação: ${LIGACAO[d.ligacao[0]] || esc(d.ligacao[0])} (confiança ${esc(d.ligacao[1])}).</span>
      ${pagos.length ? `<br><b>O mesmo político pagou a esta empresa em ${esc(cruz.anoPagamentos)}:</b> ${pagos.join(", ")}.` : ""}</span>`;
  };
  const render = (c) => {
    const f = cadastro.get(c.fornecedor) || { nome: c.fornecedor };
    return `<li><span class="texto"><b>${esc(f.nome)}</b> <span class="quando">${f.documento ? esc(f.documento) : ""}</span></span>
      ${c.doacoes.map(doacao).join("")}${empresa(c.fornecedor)}</li>`;
  };
  $("#doadores").hidden = false;
  $("#contagem-doadores").textContent = `${cruz.cruzamentos.length} empresas; ${cruz.resumo.comPagamentoAoMesmoPolitico} receberam da cota do mesmo político que recebeu a doação`;
  listaPaginada($("#resultado-doadores"), cruz.cruzamentos, render, 20, "Nenhuma empresa em comum.");
  const pag = Object.entries(cruz.fontes.pagamentos).map(([c, f]) => `${casas[c] || esc(c)}: ${fonte(f)}`).join("; ");
  $("#fontes-doadores").innerHTML = `Fontes: doações, ${fonte(cruz.fontes.doacoes)}; pagamentos da cota em ${esc(cruz.anoPagamentos)}, ${pag}.`;
}

const cnae = (c) => (c && c.length === 7 ? `${c.slice(0, 4)}-${c.slice(4, 5)}/${c.slice(5)}` : c);

/* Dados cadastrais da empresa pela Receita (nucleo/empresas.json, scripts/empresas.py). Devolve uma função id -> HTML; vazia se não há o arquivo. */
async function blocoEmpresa() {
  let j;
  try { j = await carregar("dados/nucleo/empresas.json"); } catch { return () => ""; }
  if (!j.fonte) return () => "";
  const t = j.tabelas;
  const nome = (tabela, c) => (c ? `${esc(cnae(c))}${t[tabela] && t[tabela][c] ? ` ${esc(t[tabela][c])}` : ""}` : "");
  const fonte = `${urlSegura(j.fonte.url) ? `<a href="${esc(j.fonte.url)}" rel="noopener">${esc(j.fonte.nome)}</a>` : esc(j.fonte.nome)}, base de ${esc(j.fonte.competencia)}`;
  return (id) => {
    const e = j.empresas[id];
    if (!e) return "";
    const partes = [
      e.abertura ? `Aberta em ${data(e.abertura)}` : null,
      e.situacao ? `situação: ${esc(t.situacao[e.situacao] || e.situacao)}${e.situacaoData ? ` desde ${data(e.situacaoData)}` : ""}` : null,
      e.cnaePrincipal ? `atividade principal: ${nome("cnae", e.cnaePrincipal)}${e.cnaesSecundarios ? ` (mais ${e.cnaesSecundarios.length} secundárias)` : ""}` : null,
      e.natureza ? `natureza jurídica: ${nome("natureza", e.natureza)}` : null,
      e.porte ? esc(t.porte[e.porte] || e.porte) : null,
      e.capitalSocial ? `capital social ${reais(e.capitalSocial)}` : null,
      e.uf ? `${e.municipio && t.municipio[e.municipio] ? `${esc(t.municipio[e.municipio])}/` : ""}${esc(e.uf)}` : null,
      e.estabelecimentos > 1 ? `${e.estabelecimentos} estabelecimentos` : null,
    ].filter(Boolean);
    const recente = e.diasAteNota != null && e.diasAteNota >= 0 && e.diasAteNota <= j.recenteDias;
    const nota = e.primeiraNota && e.diasAteNota != null
      ? `<br>${recente ? "<b>" : ""}A primeira nota do ano nesta base é de ${data(e.primeiraNota)}, ${e.diasAteNota} dias depois da abertura.${recente ? "</b>" : ""}` : "";
    const socios = (e.socios || []).length
      ? `<details><summary>${e.socios.length} ${e.socios.length === 1 ? "sócio" : "sócios"} no cadastro</summary><ul>${e.socios.map(([n, q, entrada, tipo]) =>
        `<li>${esc(n)} <span class="quando">${esc((t.tipoSocio[tipo] || "").toLowerCase())}${q && t.qualificacao[q] ? `, ${esc(t.qualificacao[q])}` : ""}${entrada ? `, desde ${data(entrada)}` : ""}</span></li>`).join("")}</ul></details>` : "";
    return `<span class="texto"><span class="quando">Receita Federal: ${partes.join(" · ")}.</span>${nota}${socios}
      <br><span class="quando">Fonte: ${fonte}. Fato cadastral; não indica irregularidade.</span></span>`;
  };
}
