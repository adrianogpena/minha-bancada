const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

globalThis.window = {};
const js = (nome) => require(path.join(__dirname, "../../site/assets/js", nome));
const { dataHora, param, carregar, carregarMalha, pctBr, numeroBr } = js("util.js");
const { resultado, linkTramitacao, carregarInabilitacoes, carregarAposentadoria, arquivoRedesTse } = js("apis.js");
const { selosPar, itemFicha, foto, selo, legenda, erro, semDadosLocais } = js("comum.js");
const { quandoPosse, textoRelatorias } = js("tribunais.js");
const { ultimosEventos } = js("eventos.js");
const { carregarEmendas } = js("emendas.js");
const { linkPolitico, linhaPolitico } = js("mapa.js");
const { situacaoPedido } = js("ministros.js");
const { barraPlacar } = js("votacoes.js");
const { itemHistorico } = js("historico.js");
const { semFonte, linkCF, rotuloResultado, linhaNoCargoAte, linhaSubsidio, blocoCampanha, divulgaUrl, fonteRedesTse } = js("ficha.js");

function comFetch(respostas, corpo) {
  const original = globalThis.fetch;
  const chamadas = [];
  globalThis.fetch = async (url) => {
    chamadas.push(url);
    const r = respostas[url];
    if (r === undefined) return { ok: false, status: 404, json: async () => ({}) };
    if (r instanceof Error) throw r;
    return { ok: true, status: 200, json: async () => r };
  };
  return Promise.resolve(corpo(chamadas)).finally(() => { globalThis.fetch = original; });
}

test("carregar devolve o JSON e lança erro com o status quando a resposta falha", async () => {
  await comFetch({ "a.json": { x: 1 } }, async () => {
    assert.deepEqual(await carregar("a.json"), { x: 1 });
    await assert.rejects(() => carregar("b.json"), /Não foi possível carregar b\.json \(404\)/);
  });
});

test("carregarMalha usa a cópia local e só cai na remota quando a local falha", async () => {
  await comFetch({ "geo/br.json": { de: "local" }, "http://ibge/br": { de: "remoto" } }, async (chamadas) => {
    assert.deepEqual(await carregarMalha("geo/br.json", "http://ibge/br"), { de: "local" });
    assert.deepEqual(chamadas, ["geo/br.json"]);
    assert.deepEqual(await carregarMalha("geo/falta.json", "http://ibge/br"), { de: "remoto" });
    await assert.rejects(() => carregarMalha("geo/falta.json", "http://ibge/falta"), /404/);
  });
});

test("dataHora devolve vazio para valor ausente ou inválido e formata data e hora", () => {
  assert.equal(dataHora(""), "");
  assert.equal(dataHora(null), "");
  assert.equal(dataHora("lixo"), "");
  assert.match(dataHora("2026-03-10T12:30:00-03:00"), /2026, \d{2}:\d{2}$/);
  assert.match(dataHora("2026-03-10T12:30:00-03:00", true), /de 2026, às \d{2}:\d{2}$/);
});

test("param lê o valor da query e devolve null quando falta", () => {
  globalThis.location = { search: "?id=12&f=senado" };
  try {
    assert.equal(param("id"), "12");
    assert.equal(param("f"), "senado");
    assert.equal(param("x"), null);
  } finally { delete globalThis.location; }
});

test("pctBr e numeroBr usam vírgula decimal e ponto de milhar", () => {
  assert.equal(pctBr(12.345), "12,3%");
  assert.equal(pctBr(0), "0,0%");
  assert.equal(numeroBr(1234567), "1.234.567");
});

test("resultado traduz aprovada, rejeitada e ausente", () => {
  assert.deepEqual(resultado(1), ["Aprovada", "aprovada"]);
  assert.deepEqual(resultado(0), ["Rejeitada", "rejeitada"]);
  assert.deepEqual(resultado(null), ["Sem resultado informado", "sem"]);
});

test("linkTramitacao codifica o id", () => {
  assert.equal(linkTramitacao("12 3"), "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=12%203");
});

test("arquivoRedesTse inclui a UF só em 2022", () => {
  assert.match(arquivoRedesTse({ ano: 2022, uf: "SP" }), /rede_social_candidato_2022_SP\.zip$/);
  assert.match(arquivoRedesTse({ ano: 2022, uf: "BR" }), /rede_social_candidato_2022_BR\.zip$/);
  assert.match(arquivoRedesTse({ ano: 2024, uf: "SP" }), /rede_social_candidato_2024\.zip$/);
});

test("carregarInabilitacoes e carregarAposentadoria tratam pessoa ausente, achada, ausente no arquivo e falha", async () => {
  const bom = async () => ({ pes_1: [{ a: 1 }] });
  const ruim = async () => { throw new Error("falhou"); };
  assert.deepEqual(await carregarInabilitacoes("", bom), []);
  assert.deepEqual(await carregarInabilitacoes("pes_1", bom), [{ a: 1 }]);
  assert.deepEqual(await carregarInabilitacoes("pes_2", bom), []);
  assert.deepEqual(await carregarInabilitacoes("pes_1", ruim), []);
  const apos = async () => ({ pes_1: { valor: 5 } });
  assert.equal(await carregarAposentadoria(null, apos), null);
  assert.deepEqual(await carregarAposentadoria("pes_1", apos), { valor: 5 });
  assert.equal(await carregarAposentadoria("pes_2", apos), null);
  assert.equal(await carregarAposentadoria("pes_1", ruim), null);
});

test("carregarEmendas rejeita id fora do padrão sem buscar, devolve o JSON e null na falha", async () => {
  await comFetch({ "dados/emendas/pes_1.json": { anos: [2025] } }, async (chamadas) => {
    assert.equal(await carregarEmendas(""), null);
    assert.equal(await carregarEmendas("../x"), null);
    assert.deepEqual(chamadas, []);
    assert.deepEqual(await carregarEmendas("pes_1"), { anos: [2025] });
    assert.equal(await carregarEmendas("pes_2"), null);
  });
});

test("selosPar escapa rótulo e valor e marca a variante longa", () => {
  const html = selosPar([["<a>", "x&y"]]);
  assert.match(html, /<span>&lt;a&gt;:<\/span> <span>x&amp;y<\/span>/);
  assert.doesNotMatch(html, /<a>/);
  assert.match(html, /class="selos-par"/);
  assert.match(selosPar([["a", "b"]], true), /class="selos-par longo"/);
});

test("itemFicha escapa o valor, exceto quando é html, e marca o item embaixo", () => {
  assert.equal(itemFicha(["R", "<b>v</b>"]), "<dt>R</dt><dd>&lt;b&gt;v&lt;/b&gt;</dd>");
  assert.equal(itemFicha(["R", "<b>v</b>", true]), "<dt>R</dt><dd><b>v</b></dd>");
  assert.equal(itemFicha(["R", "v", false, true]), '<dt class="embaixo">R</dt><dd class="embaixo">v</dd>');
});

test("foto grande usa a classe grande e escapa as iniciais", () => {
  assert.match(foto({ nome: "<Ana> Silva" }, true), /class="foto grande"[^>]*>&lt;S<\/span>/);
  assert.match(foto({ nome: "Ana Silva", foto: "javascript:alert(1)" }), /^<span class="foto" aria-hidden="true">AS<\/span>$/);
});

test("selo escapa o voto desconhecido e cai em Outro", () => {
  assert.equal(selo("sim"), '<span class="voto v-sim">Sim</span>');
  assert.equal(selo('"><script>'), '<span class="voto v-&quot;&gt;&lt;script&gt;">Outro</span>');
});

test("legenda lista o rótulo de cada voto pedido", () => {
  const html = legenda(["sim", "ausente"]);
  assert.match(html, /--c:var\(--sim\)">Sim</);
  assert.match(html, /Sem voto registrado/);
  assert.doesNotMatch(html, /Não/);
});

test("erro escapa a mensagem no alvo e registra no console", () => {
  const alvo = {};
  const original = console.error;
  const registrados = [];
  console.error = (e) => registrados.push(e);
  try {
    erro(alvo, new Error("<img src=x onerror=1>"));
  } finally { console.error = original; }
  assert.match(alvo.innerHTML, /^<p class="aviso">&lt;img src=x onerror=1&gt;\. /);
  assert.equal(registrados.length, 1);
});

test("semDadosLocais redireciona para a fonte quando há API e mostra o erro quando não há", () => {
  const destinos = [];
  globalThis.location = { replace: (u) => destinos.push(u) };
  const original = console.error;
  console.error = () => {};
  try {
    semDadosLocais({}, new Error("x"), "https://api.exemplo/a?b=1&c=2");
    assert.deepEqual(destinos, ["fonte.html?u=https%3A%2F%2Fapi.exemplo%2Fa%3Fb%3D1%26c%3D2"]);
    const alvo = {};
    semDadosLocais(alvo, new Error("sem arquivo"), "");
    assert.equal(destinos.length, 1);
    assert.match(alvo.innerHTML, /sem arquivo/);
  } finally { console.error = original; delete globalThis.location; }
});

test("quandoPosse prefere a data, depois o texto escapado, depois o traço", () => {
  assert.match(quandoPosse({ posse: "2020-05-10" }), /2020/);
  assert.equal(quandoPosse({ posseTexto: "<b>2019</b>" }), "&lt;b&gt;2019&lt;/b&gt;");
  assert.equal(quandoPosse({}), "—");
});

test("textoRelatorias ordena do ano mais novo ao mais antigo e devolve vazio sem contagem", () => {
  assert.equal(textoRelatorias({ 2025: 890, 2026: 1234 }), "2026: <b>1.234</b> · 2025: <b>890</b>");
  assert.equal(textoRelatorias(null), "");
  assert.equal(textoRelatorias({}), "");
});

test("ultimosEventos devolve vazio sem índice, filtra pelo político, respeita o limite e marca o dia", async () => {
  const dia = (d, n) => ({ data: d, eventos: Array.from({ length: n }, (_, i) => ({ id: `${d}-${i}`, politicos: [{ codigo: "pes_1" }] })) });
  await comFetch({}, async () => {
    assert.deepEqual(await ultimosEventos(["pes_1"]), []);
  });
  const respostas = {
    "dados/historico/indice.json": [{ data: "2026-03-03" }, { data: "2026-03-02" }],
    "dados/historico/2026-03-03.json": dia("2026-03-03", 2),
    "dados/historico/2026-03-02.json": dia("2026-03-02", 2),
  };
  await comFetch(respostas, async () => {
    const todos = await ultimosEventos(["pes_1"], 3);
    assert.equal(todos.length, 3);
    assert.equal(todos[0]._dia, "2026-03-03");
    assert.equal(todos[2]._dia, "2026-03-02");
    assert.deepEqual(await ultimosEventos(["pes_9"]), []);
  });
});

test("linkPolitico prefere a página segura e codifica a ficha quando não há", () => {
  assert.equal(linkPolitico({ pagina: "deputado.html?id=1" }), "deputado.html?id=1");
  assert.equal(linkPolitico({ pagina: "javascript:alert(1)", arquivoFicha: "a b", id: "x&y" }), "politico.html?f=a%20b&i=x%26y");
});

test("linhaPolitico escapa os dados e mostra etiqueta do estado", () => {
  const html = linhaPolitico({ nome: "<Zé>", cargo: "PREFEITO", partido: "A&B", municipio: "São <Paulo>", arquivoFicha: "f", id: "1", estado: "eleito" });
  assert.match(html, /&lt;Zé&gt;/);
  assert.match(html, /PREFEITO, A&amp;B em São &lt;Paulo&gt;/);
  assert.match(html, /Eleito em 2026/);
  assert.doesNotMatch(html, /<Zé>|<Paulo>/);
  assert.match(linhaPolitico({ nome: "X", cargo: "SENADOR", uf: "SP", arquivoFicha: "f", id: "1", estado: "2turno" }), /SENADOR, SP[\s\S]*No 2º turno/);
  assert.doesNotMatch(linhaPolitico({ nome: "X", cargo: "SENADOR", arquivoFicha: "f", id: "1" }), /etiqueta/);
});

test("situacaoPedido cobre resposta, prazo, remessa e pedido não enviado", () => {
  const base = { natureza: "informacao", fonte: "camara" };
  assert.equal(situacaoPedido({ ...base, natureza: "outra" }), null);
  assert.equal(situacaoPedido({ ...base, fonte: "senado" }), null);
  assert.deepEqual(situacaoPedido({ ...base, resposta: "2026-01-05" }), ["Respondido", "aprovada", "respondido"]);
  assert.deepEqual(situacaoPedido({ ...base, resposta: "2026-01-05", prazoFim: "2026-01-10" }), ["Respondido no prazo", "aprovada", "no-prazo"]);
  assert.deepEqual(situacaoPedido({ ...base, resposta: "2026-01-15", prazoFim: "2026-01-10" }), ["Respondido fora do prazo", "rejeitada", "fora-do-prazo"]);
  assert.deepEqual(situacaoPedido({ ...base, prazoFim: "2026-01-10" }, "2026-01-11"), ["Prazo vencido sem resposta", "rejeitada", "vencido"]);
  const aguardando = situacaoPedido({ ...base, prazoFim: "2026-01-10" }, "2026-01-10");
  assert.deepEqual([aguardando[1], aguardando[2]], ["tramitando", "aguardando"]);
  assert.match(aguardando[0], /^Aguardando resposta, prazo até .*2026/);
  assert.deepEqual(situacaoPedido({ ...base, remessa: "2026-01-01" }), ["Enviado ao ministério, prazo ainda não registrado", "tramitando", "aguardando"]);
  assert.deepEqual(situacaoPedido(base), ["Ainda não enviado ao ministério", "sem", "sem-envio"]);
});

test("barraPlacar calcula a largura proporcional e ignora votos zerados", () => {
  const html = barraPlacar({ sim: 3, nao: 1, abstencao: 0 });
  assert.match(html, /aria-label="Sim: 3, Não: 1, Abstenção: 0"/);
  assert.match(html, /width:75%;background:var\(--sim\)/);
  assert.match(html, /width:25%;background:var\(--nao\)/);
  assert.equal((html.match(/<i /g) || []).length, 2);
  assert.equal((barraPlacar({}).match(/<i /g) || []).length, 0);
});

test("barraPlacar escapa chave desconhecida no aria-label", () => {
  const html = barraPlacar({ 'x"><script>': 2 });
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /aria-label="x&quot;&gt;&lt;script&gt;: 2"/);
});

test("itemHistorico escapa título, texto e mudança e usa a relevância padrão", () => {
  const html = itemHistorico({ categoria: "x<y", titulo: "<b>T</b>", texto: "a&b", mudanca: ["<de>", "<para>"], resumo: "r<", titulos: ["<t1>", "t2"] });
  assert.match(html, /hist-item r-2/);
  assert.match(html, /&lt;b&gt;T&lt;\/b&gt;/);
  assert.match(html, /<p class="texto">a&amp;b<\/p>/);
  assert.match(html, /<span>&lt;de&gt;<\/span> → <b>&lt;para&gt;<\/b>/);
  assert.match(html, /Ver os 2 títulos/);
  assert.match(html, /&lt;t1&gt; · t2/);
  assert.doesNotMatch(html, /<b>T<\/b>|<para>|<t1>/);
  assert.match(itemHistorico({ categoria: "c", titulo: "t", relevancia: 1 }), /r-1/);
});

test("semFonte avisa dado sem fonte e escapa o motivo", () => {
  assert.match(semFonte(), /dado sem fonte<\/span>$/);
  assert.match(semFonte("<x>"), /dado sem fonte: &lt;x&gt;/);
  assert.equal(linkCF(46), "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art46");
});

test("rotuloResultado traduz os resultados do TSE e preserva os desconhecidos", () => {
  assert.equal(rotuloResultado("2º TURNO"), "Vai ao 2º turno");
  assert.equal(rotuloResultado("Eleito por QP"), "Eleito por quociente partidário");
  assert.equal(rotuloResultado("ELEITO POR MÉDIA"), "Eleito por média");
  assert.equal(rotuloResultado("Suplente"), "Suplente");
});

test("linhaNoCargoAte avisa quando falta o fim do mandato e cita a fonte do prazo", () => {
  const sem = linhaNoCargoAte({ cargoTse: "PREFEITO" });
  assert.equal(sem[0], "No cargo até");
  assert.match(sem[1], /dado sem fonte: fim do mandato/);
  const sen = linhaNoCargoAte({ fimMandato: "2031-01-31", fonte: "senado", id: "a/b", cargoTse: "SENADOR" });
  assert.match(sen[1], /senador\/a%2Fb/);
  assert.match(sen[1], /Dados Abertos do Senado/);
  const gov = linhaNoCargoAte({ fimMandato: "2031-01-01", cargoTse: "GOVERNADOR", estado: "eleito", inicioMandato: "2027-01-01" });
  assert.match(gov[1], /^Toma posse em .*2027.*Mandato até .*2031/);
  assert.match(gov[1], /art\. 28/);
  assert.match(gov[1], /Emenda Constitucional 111\/2021/);
  assert.match(linhaNoCargoAte({ fimMandato: "2031-01-01", cargoTse: "VEREADOR", estado: "2turno" })[1], /^Se eleito, até /);
  assert.match(linhaNoCargoAte({ fimMandato: "2031-01-01", cargoTse: "OUTRO" })[1], /dado sem fonte: prazo do mandato/);
});

test("linhaSubsidio varia por cargo e some quando o político não está no cargo", () => {
  assert.deepEqual(linhaSubsidio({ estado: "eleito", cargoTse: "SENADOR" }), ["Subsídio mensal", null]);
  assert.equal(linhaSubsidio({ estado: "atual", cargoTse: "SENADOR" })[0], "Subsídio mensal bruto");
  assert.match(linhaSubsidio({ estado: "atual", cargoTse: "DEPUTADO FEDERAL" })[1], /46\.366,19/);
  assert.equal(linhaSubsidio({ estado: "atual", cargoTse: "DEPUTADO ESTADUAL" })[0], "Subsídio mensal (teto legal)");
  assert.match(linhaSubsidio({ estado: "atual", cargoTse: "VEREADOR" })[1], /20% a 75%/);
  assert.deepEqual(linhaSubsidio({ estado: "atual", cargoTse: "PREFEITO" }), ["Subsídio mensal", null]);
});

test("blocoCampanha sem contas avisa só antes de 2026 e cita o ano", () => {
  assert.match(blocoCampanha({ ano: 2022 }, []), /Campanha de 2022[\s\S]*dado sem fonte/);
  assert.equal(blocoCampanha({ ano: 2026 }, []), "");
  assert.match(blocoCampanha({ ano: 2020 }, []), /Campanha de 2020/);
});

test("divulgaUrl exige fonte TSE com eleição e unidade, e fonteRedesTse só existe para o TSE", () => {
  assert.ok(!divulgaUrl({ fonte: "senado" }));
  assert.match(divulgaUrl({ fonte: "tse", ano: 2022, eleicao: 544, unidadeEleitoral: "SP", sequencial: "1 2" }), /^https:\/\/divulgacandcontas\.tse\.jus\.br\/divulga\/#\/candidato\/2022\/544\/SP\//);
  assert.equal(fonteRedesTse({ fonte: "camara" }), "");
  const html = fonteRedesTse({ fonte: "tse", ano: 2022, uf: "SP" });
  assert.match(html, /arquivo de redes do TSE/);
  assert.doesNotMatch(html, /DivulgaCandContas/);
});
