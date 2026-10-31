// Testa os módulos de site/assets/js sem navegador (Node 24 carrega módulos ES com require).
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

globalThis.window = {};
const js = (nome) => require(path.join(__dirname, "../../site/assets/js", nome));
const { esc, reais, reaisCentavos, pct, data, semAcento, urlSegura } = js("util.js");
const { urlLegivel, fontes, temResultado, quorumCamara, movimentadoNoAno, desfecho } = js("apis.js");
const { resumosEstadual } = js("estadual.js");
const { linksRedes } = js("ficha.js");
const { foto } = js("comum.js");
const { blocoDescricao } = js("ministros.js");
const { painelEmendas, ehPix } = js("emendas.js");
const { painelCoautoria } = js("parlamentar.js");
const { linkParlamentar } = js("apis.js");
const { filtrarLista, consultaDaLista, mediasPor, dicaComparativa, celulaEmendas, celulaDaColuna, metrica } = js("lista-parlamentares.js");
const { CONFIG_CAMARA } = js("camara.js");
const { CONFIG_SENADO } = js("senado.js");
const { agruparPeriodos, chaveDe, juntarDias, doPolitico, maisRecente } = js("historico.js");

test("temResultado deixa de fora a votação sem aprovada nem rejeitada", () => {
  assert.equal(temResultado({ aprovada: 1 }), true);
  assert.equal(temResultado({ aprovada: 0 }), true);
  assert.equal(temResultado({ aprovada: null }), false);
  assert.equal(temResultado({}), false);
});

test("movimentadoNoAno pega o projeto com situação atualizada no ano, qualquer que seja o desfecho", () => {
  const p = { situacao: "Aguardando Parecer", dataSituacao: "2026-03-10" };
  assert.equal(movimentadoNoAno(p, 2026), true);
  assert.equal(movimentadoNoAno({ ...p, situacao: "Arquivada" }, 2026), true);
  assert.equal(movimentadoNoAno({ ...p, situacao: "Transformado em Norma Jurídica" }, 2026), true);
  assert.equal(movimentadoNoAno({ ...p, dataSituacao: "2025-08-22" }, 2026), false);
  assert.equal(movimentadoNoAno({ situacao: "Aguardando Parecer" }, 2026), false);
});

test("desfecho trata situação vazia com tramitação lida como projeto em tramitação", () => {
  assert.deepEqual(desfecho({ situacao: null, tramitacao: "Apresentação de Proposição" }).slice(0, 2), ["Em tramitação", "tramitando"]);
  assert.deepEqual(desfecho({ situacao: null, dataSituacao: "2026-08-25" }).slice(0, 2), ["Em tramitação", "tramitando"]);
  assert.deepEqual(desfecho({ situacao: null }).slice(0, 2), ["Situação ainda não consultada", "sem"]);
  assert.deepEqual(desfecho({ situacao: "Arquivada" }).slice(0, 2), ["Arquivada", "rejeitada"]);
});

test("esc escapa HTML e trata nulos", () => {
  assert.equal(esc(`<a href="x">'&'</a>`), "&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;");
  assert.equal(esc(null), "");
  assert.equal(esc(undefined), "");
  assert.equal(esc(0), "0");
});

test("reais formata em BRL", () => {
  assert.match(reais(1234.4), /R\$\s?1\.234/);
  assert.match(reais(null), /R\$\s?0/);
  assert.match(reaisCentavos(1.5), /1,50/);
});

test("pct arredonda e evita divisão por zero", () => {
  assert.equal(pct(1, 3), "33%");
  assert.equal(pct(2, 3), "67%");
  assert.equal(pct(5, 0), "—");
});

test("data usa UTC e aceita ISO completo", () => {
  assert.equal(data(""), "");
  assert.equal(data(null), "");
  assert.match(data("2026-01-01T00:00:00"), /01.*2026/);
  assert.match(data("2026-03-05", true), /5 de março de 2026/);
});

test("semAcento normaliza para busca", () => {
  assert.equal(semAcento("São José"), "sao jose");
  assert.equal(semAcento(null), "");
});

test("urlSegura só aceita http e https", () => {
  assert.equal(urlSegura("https://exemplo.com/a?b=1"), "https://exemplo.com/a?b=1");
  assert.equal(urlSegura("http://exemplo.com"), "http://exemplo.com");
  assert.equal(urlSegura("  https://exemplo.com  "), "https://exemplo.com");
  assert.equal(urlSegura("javascript:alert(1)"), "");
  assert.equal(urlSegura("JavaScript:alert(1)"), "");
  assert.equal(urlSegura(" java\tscript:alert(1)"), "");
  assert.equal(urlSegura("data:text/html,<script>alert(1)</script>"), "");
  assert.equal(urlSegura("vbscript:x"), "");
  assert.equal(urlSegura("ftp://exemplo.com/x"), "");
  assert.equal(urlSegura(""), "");
  assert.equal(urlSegura(null), "");
  assert.equal(urlSegura(undefined), "");
});

test("urlSegura recusa caminho relativo, a não ser que seja pedido", () => {
  assert.equal(urlSegura("politico.html?f=x&i=1"), "");
  assert.equal(urlSegura("politico.html?f=x&i=1", true), "politico.html?f=x&i=1");
  assert.equal(urlSegura("fotos/1.jpg", true), "fotos/1.jpg");
  assert.equal(urlSegura("javascript:alert(1)", true), "");
  assert.equal(urlSegura("data:image/png;base64,AAAA", true), "");
});

test("links montados com dado externo não levam javascript: nem data:", () => {
  const ruim = "javascript:alert(1)";
  assert.equal(fontes([["Fonte", ruim], ["Outra", "data:text/html,x"]]), "");
  assert.match(fontes([["Fonte", "https://dadosabertos.camara.leg.br/api/v2/x"]]), /href="https:\/\/dadosabertos\.camara\.leg\.br\/api\/v2\/x"/);
  assert.doesNotMatch(foto({ nome: "Ana Souza", foto: ruim }), /<img|javascript:/);
  assert.match(foto({ nome: "Ana Souza", foto: "https://x.org/a.jpg" }), /<img[^>]*src="https:\/\/x\.org\/a\.jpg"/);
  assert.match(foto({ nome: "Ana Souza", foto: "fotos/1.jpg" }), /src="fotos\/1\.jpg"/);
  const redes = linksRedes([ruim, "https://instagram.com/anasouza"], { nome: "Ana Souza" });
  assert.doesNotMatch(redes, /javascript:/);
  assert.match(redes, /href="https:\/\/instagram\.com\/anasouza"/);
  assert.equal(linksRedes([ruim], { nome: "Ana Souza" }), null);
});

test("urlLegivel reaproveita páginas do site e usa fonte.html nas demais APIs", () => {
  const f = urlLegivel, api = "https://dadosabertos.camara.leg.br/api/v2";
  assert.equal(f(`${api}/votacoes/2270800-69/votos`), "votacao.html?id=2270800-69");
  assert.equal(f(`${api}/votacoes/2270800-69`), "votacao.html?id=2270800-69");
  assert.equal(f(`${api}/deputados/204379`), "deputado.html?id=204379");
  assert.equal(f(`${api}/proposicoes/1`), `fonte.html?u=${encodeURIComponent(`${api}/proposicoes/1`)}`);
  assert.match(f("https://legis.senado.leg.br/dadosabertos/processo/1"), /^fonte\.html\?u=/);
  assert.equal(f("https://cdn.tse.jus.br/estatistica/sead/odsele/x.zip"), null);
  assert.equal(f("https://www.camara.leg.br/deputados/1"), null);
  assert.equal(f("http://dadosabertos.camara.leg.br/api/v2/x"), null);
  assert.equal(f("https://exemplo.com/api/x"), null);
  assert.equal(f("lixo"), null);
});

test("resumosEstadual mostra cada seção com fonte e avisa quando falta", () => {
  assert.equal(resumosEstadual({}), "");
  const html = resumosEstadual({
    verba: { fonte: "https://v.org/dados", anos: [{ ano: 2024, total: 30, meses: [{ mes: 1, total: 30 }], categorias: [{ id: "imovel", categoria: "Imóvel e escritório de apoio", total: 30, originais: [["Aluguel", 30]] }], fornecedores: [{ fornecedor: "F", cnpj: "1", total: 30 }] }] },
    remuneracao: { fonte: "https://r.org/dados", ano: 2024, mes: 3, bruto: 100, liquido: 80 },
    diarias: { anos: [{ ano: 2024, total: 5, quantidade: 1 }] },
  });
  assert.match(html, /Verba\/cota/);
  assert.match(html, /jan/);
  assert.match(html, /href="https:\/\/v\.org\/dados"/);
  assert.match(html, /title="Aluguel: [^"]*">Imóvel e escritório de apoio/);
  assert.match(html, /Remuneração/);
  assert.match(html, /mar\/2024/);
  assert.match(html, /Diárias[\s\S]*sem-fonte/);
  assert.doesNotMatch(html, /Presença|Emendas/);
});

test("resumosEstadual mostra lançamentos da verba e pagamentos das emendas com data e fonte", () => {
  const html = resumosEstadual({
    verba: { fonte: "https://v.org/dados", anos: [{ ano: 2026, total: 30, meses: [{ mes: 2, total: 30 }], categorias: [], fornecedores: [],
      lancamentos: [{ mes: 2, fornecedor: "F", valor: 30.5, documento: "NF-1", emissao: "2026-02-03", fonte: "https://c.org/nf.pdf" }, { mes: 3, empenho: "2026NE1", descricao: "Combustível", valor: 1, fonte: "javascript:x" }] }] },
    emendas: { fonte: "https://e.org", anos: [{ ano: 2025, empenhado: 10, pago: 5 }],
      pagamentos: [{ data: "2026-02-23", credor: "Credor <b>", objeto: "Obra", valor: 20, efetivado: true }, { data: "2026-01-20", credor: "B", valor: 1, efetivado: false }] },
  });
  assert.match(html, /Lançamentos de 2026/);
  assert.match(html, /03\/02\/2026[\s\S]*NF-1[\s\S]*href="https:\/\/c\.org\/nf\.pdf"/);
  assert.match(html, /2026NE1[\s\S]*Combustível/);
  assert.doesNotMatch(html, /javascript:/);
  assert.match(html, /Pagamentos das emendas/);
  assert.match(html, /23\/02\/2026<\/td><td>Credor &lt;b&gt;/);
  assert.match(html, /não efetivado/);
});

test("completarEleicao monta disputa, votos do partido e aliança a partir do que o local tem em comum", () => {
  const { completarEleicao } = js("ficha.js");
  const comuns = {
    disputa: { "VEREADOR|71072": { vagas: 55, turnos: { 1: { aptos: 10 } } }, "GOVERNADOR|SP": { vagas: 1, turnos: {} } },
    partidos: { "VEREADOR|71072": { totalVotos: 770, partidos: { PT: [100, 300, "PT/PC do B/PV"], "PC do B": [10, 20, "PT/PC do B/PV"], PL: [50, 290, ""] } } },
    coligacoes: { "VEREADOR|71072": { coligacoes: [["F", "", "Federação X", "Deferido"], ["I", "", "PL", "Deferido"]], coligacaoDoPartido: { PT: 0, "PC do B": 0, PL: 1 } } },
  };
  const pt = completarEleicao({ cargoTse: "VEREADOR", unidadeEleitoral: "71072", partido: "PT" }, comuns);
  assert.deepEqual(pt.disputa, comuns.disputa["VEREADOR|71072"]);
  assert.deepEqual(pt.partidoVotos, { votosLegenda: 100, votosNominais: 300, totalVotosPartidos: 770, federacao: "PT/PC do B/PV", votosLegendaFederacao: 110, votosNominaisFederacao: 320 });
  assert.deepEqual(pt.alianca, { tipo: "F", nome: "", composicao: "Federação X", situacao: "Deferido" });
  const pl = completarEleicao({ cargoTse: "VEREADOR", unidadeEleitoral: "71072", partido: "PL" }, comuns);
  assert.deepEqual(pl.partidoVotos, { votosLegenda: 50, votosNominais: 290, totalVotosPartidos: 770 });   // sem federação: só os do partido
  assert.equal(pl.alianca.tipo, "I");
  // o vice disputa com o titular; votos por partido e coligações usam o cargo do próprio vice
  const vice = completarEleicao({ cargoTse: "VICE-GOVERNADOR", unidadeEleitoral: "SP", partido: "PT" }, comuns);
  assert.equal(vice.disputa.vagas, 1);
  assert.equal(vice.partidoVotos, undefined);
  assert.equal(vice.alianca, undefined);
  // partido sem votos no local, ficha sem `_disputas` e ficha que já traz os campos ficam como estão
  assert.equal(completarEleicao({ cargoTse: "VEREADOR", unidadeEleitoral: "71072", partido: "NOVO" }, comuns).partidoVotos, undefined);
  const solta = { cargoTse: "SENADOR", unidadeEleitoral: "SP" };
  assert.equal(completarEleicao(solta, undefined), solta);
  const pronta = { cargoTse: "VEREADOR", unidadeEleitoral: "71072", partido: "PT", disputa: { vagas: 1 } };
  assert.deepEqual(completarEleicao(pronta, comuns).disputa, { vagas: 1 });
  assert.equal(pronta.partidoVotos, undefined);
});

test("agruparPeriodos junta dias em semanas (segunda a domingo) e meses", () => {
  const indice = [{ data: "2026-10-26", total: 1 }, { data: "2026-10-25", total: 2 }, { data: "2026-10-19", total: 3 }, { data: "2026-09-30", total: 4 }];
  assert.deepEqual(agruparPeriodos(indice, "semana").map((g) => [g.chave, g.total]), [["2026-10-26", 1], ["2026-10-19", 5], ["2026-09-28", 4]]);
  assert.deepEqual(agruparPeriodos(indice, "mes").map((g) => [g.chave, g.dias.length]), [["2026-10", 3], ["2026-09", 1]]);
  assert.equal(chaveDe("semana", "2026-10-25"), "2026-10-19");
  const g = agruparPeriodos(indice, "30dias");
  assert.deepEqual(g.map((x) => [x.chave, x.dias.length, x.total]), [["recentes", 4, 10]]);
});

test("maisRecente ordena por dia, do mais novo ao mais antigo, e mantém a ordem do arquivo no mesmo dia", () => {
  const e = [{ t: "a", _dia: "2026-10-19", _n: 0 }, { t: "b", _dia: "2026-10-20", _n: 2 }, { t: "c", _dia: "2026-10-20", _n: 1 }];
  assert.deepEqual([...e].sort(maisRecente).map((x) => x.t), ["c", "b", "a"]);
});

test("doPolitico casa o evento pelo código ou pela página do político", () => {
  const e = { politicos: [{ codigo: null, pagina: "politico.html?f=senado&i=9" }, { codigo: "dep:1" }] };
  assert.ok(doPolitico(e, ["dep:1"]));
  assert.ok(doPolitico(e, ["x", "politico.html?f=senado&i=9"]));
  assert.ok(!doPolitico(e, ["dep:2"]));
  assert.ok(!doPolitico({}, ["dep:1"]));
});

test("juntarDias soma contagens, marca o dia de cada evento e só dá cobertura vazia a quem não teve item no período", () => {
  const dia = (d, locais, eventos, cobertura) => ({ data: d, locais, contagem: Object.fromEntries(Object.keys(locais).map((c) => [c, { nova: eventos.filter((e) => e.local === c).length }])), cobertura, eventos });
  const novo = dia("2026-10-20", { BR: "Brasil", "UF:SP": "São Paulo" }, [{ local: "UF:SP", titulo: "b" }], { BR: { itens: 0, status: "parado" }, "UF:SP": { itens: 1 } });
  const velho = dia("2026-10-19", { BR: "Brasil" }, [{ local: "BR", titulo: "a" }], { BR: { itens: 1 } });
  const j = juntarDias([novo, velho], "2026-10-19");
  assert.deepEqual(Object.keys(j.locais), ["BR", "UF:SP"]);
  assert.deepEqual(j.eventos.map((e) => [e.titulo, e._dia]), [["a", "2026-10-19"], ["b", "2026-10-20"]]);
  assert.equal(j.contagem.BR.nova, 1);
  assert.equal(j.cobertura.BR.itens, 1);
  assert.deepEqual([j.de, j.ate], ["2026-10-19", "2026-10-20"]);
});

test("juntarDias: mudança em qualquer dia vale para o período, falha antiga não, e soma itens fora da janela", () => {
  const dia = (d, cobertura) => ({ data: d, locais: {}, contagem: {}, cobertura, eventos: [] });
  const j = juntarDias([
    dia("2026-10-21", { A: { itens: 0, status: "parado", ultimaMudanca: "2026-10-19" }, B: { itens: 0, status: "parado" }, C: { itens: 0, status: "falha", ultimaColeta: "2026-10-18" } }),
    dia("2026-10-20", { A: { itens: 0, status: "irrelevante", mudancas: ["verbas"], foraDaJanela: 2 }, B: { itens: 0, status: "falha", ultimaColeta: "2026-10-17" }, C: { itens: 0, status: "irrelevante", mudancas: ["verbas"] } }),
  ], "2026-10-19");
  assert.equal(j.cobertura.A.status, "irrelevante");
  assert.deepEqual([j.cobertura.A.mudancas, j.cobertura.A.foraDaJanela, j.cobertura.A.ultimaMudanca], [["verbas"], 2, "2026-10-19"]);
  assert.equal(j.cobertura.B.status, "parado");
  assert.equal(j.cobertura.C.status, "irrelevante");
});

test("blocoDescricao mostra resumo, áreas e fontes, escapa HTML e some sem descrição", () => {
  assert.equal(blocoDescricao(undefined), "");
  assert.equal(blocoDescricao({}), "");
  const html = blocoDescricao({ resumo: "Cuida de <b>tudo</b>", areas: ["Saúde & vida"], site: "https://www.gov.br/saude",
    base: [{ rotulo: "Lei 14.600/2023, art. 45", url: "https://www.planalto.gov.br/x" }], revisadoEm: "2026-10-30" });
  assert.match(html, /O que faz/);
  assert.match(html, /Cuida de &lt;b&gt;tudo&lt;\/b&gt;/);
  assert.match(html, /Saúde &amp; vida/);
  assert.match(html, /Lei 14\.600\/2023, art\. 45/);
  assert.match(html, /Site oficial do ministério/);
  assert.doesNotMatch(blocoDescricao({ resumo: "x", site: "javascript:alert(1)" }), /javascript:/);
  const v = blocoDescricao({ resumo: "x", vinculados: [{ nome: "Anvisa <i>", url: "https://www.gov.br/anvisa" }, { nome: "Sem link", url: "javascript:alert(1)" }] });
  assert.match(v, /<a href="https:\/\/www\.gov\.br\/anvisa" rel="noopener">Anvisa &lt;i&gt;<\/a>/);
  assert.match(v, /<li>Sem link<\/li>/);
  assert.doesNotMatch(v, /javascript:/);
  assert.doesNotMatch(blocoDescricao({ resumo: "x" }), /vinculados/);
});

test("quorumCamara: PLP e PEC têm mínimo; requerimento e projeto comum não", () => {
  assert.equal(quorumCamara("PLP 281/2019", "Rejeitada a Subemenda").minimo, 257);
  assert.equal(quorumCamara("PEC 45/2019", "Aprovada a Emenda").minimo, 308);
  assert.equal(quorumCamara("PLP 281/2019", "Aprovado o Requerimento"), null);
  assert.equal(quorumCamara("PL 1/2020", "Aprovada"), null);
});

test("painelEmendas some sem dados, escapa o texto da fonte e limita a lista", () => {
  assert.equal(painelEmendas(null), "");
  assert.equal(painelEmendas({ anos: [] }), "");
  const itens = Array.from({ length: 60 }, (_, n) => ({ codigo: String(n), ano: 2024, local: "<b>X</b>", empenhado: 1, pago: 1 }));
  const html = painelEmendas({ anos: [{ ano: 2024, n: 60, empenhado: 60, liquidado: 0, pago: 60 }], municipios: [], itens });
  assert.match(html, /as 50 maiores de 60/);
  assert.match(html, /&lt;b&gt;X&lt;\/b&gt;/);
  assert.match(html, /portaldatransparencia\.gov\.br\/emendas\/consulta\?ano=2024/);
});

test("painelEmendas resume as emendas Pix e prepara o mapa só com municípios de código IBGE", () => {
  assert.equal(ehPix("Emenda Individual - Transferências Especiais"), true);
  assert.equal(ehPix("Emenda Individual - Transferências com Finalidade Definida"), false);
  const html = painelEmendas({
    anos: [{ ano: 2024, n: 2, empenhado: 30, liquidado: 0, pago: 10 }],
    municipios: [{ nome: "SANTOS", uf: "SP", ibge: "3548500", empenhado: 20, pago: 10, n: 1, pixEmpenhado: 20, pixPago: 10, pixN: 1 }, { nome: "X", uf: "SP", empenhado: 10, pago: 0, n: 1 }],
    itens: [{ codigo: "1", ano: 2024, tipo: "Emenda Individual - Transferências Especiais", empenhado: 20, pago: 10 }, { codigo: "2", ano: 2024, tipo: "Individual", empenhado: 10, pago: 0 }],
  });
  assert.match(html, /Emendas Pix<\/b>[^<]*\(transferências especiais[^<]*<b>1<\/b>/);
  assert.match(html, /class="mapa-emendas" data-municipios="[^"]*3548500[^"]*" data-pix="1"/);
  assert.doesNotMatch(html.match(/data-municipios="[^"]*"/)[0], /&quot;X&quot;/);
  assert.match(html, /<th>Pix \(empenhado\)<\/th>/);
});

test("filtrarLista filtra por nome sem acento, UF e partido e ordena pela Casa", () => {
  const itens = [
    { nome: "Ana Souza", uf: "SP", partido: "PT", proposicoes: 5, votou: 1, votacoes: 2, gasto: 1, proprias: 1, aprovadasProprias: 0 },
    { nome: "Álvaro Lima", uf: "RJ", partido: "PL", proposicoes: 9, votou: 2, votacoes: 2, gasto: 2, proprias: 2, aprovadasProprias: 1 },
  ];
  const o = CONFIG_CAMARA.ordenadores;
  assert.deepEqual(filtrarLista(itens, { busca: "alvaro" }, o).map((d) => d.nome), ["Álvaro Lima"]);
  assert.deepEqual(filtrarLista(itens, { uf: "SP" }, o).map((d) => d.nome), ["Ana Souza"]);
  assert.deepEqual(filtrarLista(itens, { ordem: "proposicoes" }, o).map((d) => d.nome), ["Álvaro Lima", "Ana Souza"]);
  assert.deepEqual(filtrarLista(itens, { ordem: "inexistente" }, CONFIG_SENADO.ordenadores).map((d) => d.nome), ["Álvaro Lima", "Ana Souza"]);
});

test("consultaDaLista só leva o que foge do padrão", () => {
  assert.equal(consultaDaLista({ busca: " ", ordem: "nome" }), "");
  assert.equal(consultaDaLista({ busca: "ana", uf: "SP", ordem: "gasto" }), "busca=ana&uf=SP&ordem=gasto");
});

test("painelCoautoria serve às duas Casas e linkParlamentar conhece as duas rotas", () => {
  const c = { projetos: 1, outroPartido: 0, parceiros: [] };
  const html = painelCoautoria({ c, quem: "Deputado", linhas: [["Ana", "PT/SP", 3]], nota: "n", fonte: ["F", "https://dadosabertos.camara.leg.br/api/v2/x"] });
  assert.match(html, /1 projeto assinado com outros deputados, 0 com deputado de outro partido/);
  assert.match(html, /<td>Ana<\/td><td>PT\/SP<\/td><td>3<\/td>/);
  assert.match(painelCoautoria({ c: null, quem: "Deputado", linhas: [], vazio: "Nada." }), /class="vazio">Nada\./);
  assert.equal(painelCoautoria({ c: null, quem: "Parlamentar", linhas: [] }), "");
  assert.equal(linkParlamentar("camara", 5), "deputado.html?id=5");
  assert.equal(linkParlamentar("senado", "a b"), "politico.html?f=senado&i=a%20b");
});

test("mediasPor e dicaComparativa comparam com o partido e a bancada do estado, ignorando quem não tem valor", () => {
  const itens = [{ partido: "PT", uf: "SP", v: 10 }, { partido: "PT", uf: "RJ", v: 20 }, { partido: "PL", uf: "SP", v: 30 }, { partido: "PL", uf: "SP", v: null }];
  const porPartido = mediasPor(itens, "partido", (d) => d.v), porUf = mediasPor(itens, "uf", (d) => d.v);
  assert.deepEqual(porPartido(itens[0]), { media: 15, n: 2 });
  assert.deepEqual(porPartido(itens[3]), { media: 30, n: 1 });
  assert.equal(dicaComparativa(itens[0], porPartido, porUf, (n) => `${n}`), "média do partido (2): 15; média da bancada de SP (2): 20");
  assert.equal(dicaComparativa({ partido: "X", uf: "ZZ" }, porPartido, porUf, String), "");
});

test("celulaEmendas mostra empenhado e pago, ou avisa que não há emendas ligadas", () => {
  assert.match(celulaEmendas({ empenhado: 1000, pago: 400 }), /R\$\s?1\.000.*R\$\s?400[^<]* pagos/s);
  assert.match(celulaEmendas({}), /sem emendas ligadas/);
});

test("celulaDaColuna marca como ativa só a coluna que explica a ordenação escolhida", () => {
  const col = { ordens: ["emendas"], celula: () => metrica("1", "x", { largo: true }) };
  assert.match(celulaDaColuna(col, {}, "", "emendas"), /class="metrica ativa so-largo"/);
  assert.doesNotMatch(celulaDaColuna(col, {}, "", "nome"), /ativa/);
  assert.doesNotMatch(celulaDaColuna({ celula: () => metrica("1", "x") }, {}, "", "nome"), /ativa/);
});
