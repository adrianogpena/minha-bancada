const test = require("node:test");
const assert = require("node:assert/strict");
const { Elemento, comPagina, js } = require("./apoio_dom.js");

globalThis.window = {};
globalThis.MutationObserver = class { observe() {} };
const { montarSenador } = js("senador.js");

const P = { id: "55", pessoa: "pes_1", partido: "ABC", uf: "SP", cargo: "Senador", participacao: "Titular", foto: "", fonte: "senado" };
const base = { votos: [], proposicoes: [] };

async function render(sen, extras = {}, p = P, respostas = {}) {
  let resultado;
  await comPagina({}, { "dados/senador/55.json": sen, "dados/votacoes_senado.json": extras.lista || [], ...respostas }, async () => {
    const alvo = new Elemento("main");
    const ok = await montarSenador(alvo, p, extras.nome || "Fulano <F>", extras.ficha || []);
    resultado = { ok, html: alvo.innerHTML };
  });
  return resultado;
}

test("montarSenador devolve false quando o arquivo do senador falta", async () => {
  let ok;
  await comPagina({}, { "dados/votacoes_senado.json": [] }, async () => {
    ok = await montarSenador(new Elemento("main"), P, "Fulano", []);
  });
  assert.equal(ok, false);
});

test("montarSenador devolve false quando a lista de votações falta", async () => {
  let ok;
  await comPagina({}, { "dados/senador/55.json": base }, async () => {
    ok = await montarSenador(new Elemento("main"), P, "Fulano", []);
  });
  assert.equal(ok, false);
});

test("montarSenador sem cota mostra o aviso com link da transparência e rótulo Perfil", async () => {
  const { ok, html } = await render(base);
  assert.equal(ok, true);
  assert.match(html, /<h1>Fulano &lt;F&gt;<\/h1>/);
  assert.match(html, /Os gastos da cota \(CEAPS\) não puderam ser carregados agora/);
  assert.match(html, /href="https:\/\/www6g\.senado\.leg\.br\/transparencia\/sen\/55"/);
  assert.match(html, /id="aba-perfil"[^>]*>Perfil<\/button>/);
  assert.match(html, /<span class="selo">ABC\/SP<\/span> Senador<\/div>|<span class="selo">ABC\/SP<\/span> Senador<\/p>/);
  assert.doesNotMatch(html, /Comparecimento às votações<\/h2>/);
  assert.doesNotMatch(html, /Recursos e benefícios/);
  assert.doesNotMatch(html, /Lideranças e cargos/);
  assert.doesNotMatch(html, /Discursos e apartes/);
  assert.doesNotMatch(html, /Presença por ano/);
  assert.doesNotMatch(html, /<h2>Relatorias/);
});

test("montarSenador mostra suplente, situação do mandato e página oficial só quando segura", async () => {
  const seguro = await render(base, {}, { ...P, participacao: "Suplente", fimMandato: "2031-01-31", pagina: "https://www25.senado.leg.br/x?a=1&b=2" });
  assert.match(seguro.html, /Senador, suplente/);
  assert.match(seguro.html, /Mandato até 31 de janeiro de 2031\./);
  assert.match(seguro.html, /<dt>Página oficial<\/dt><dd><a href="https:\/\/www25\.senado\.leg\.br\/x\?a=1&amp;b=2" rel="noopener">Perfil no Senado Federal<\/a>/);
  assert.match(seguro.html, /<dt>Onde atua<\/dt><dd>São Paulo<\/dd>/);
  const inseguro = await render(base, {}, { ...P, pagina: "javascript:alert(1)" });
  assert.doesNotMatch(inseguro.html, /Página oficial/);
  assert.doesNotMatch(inseguro.html, /javascript:/);
  assert.match(inseguro.html, /<p class="situacao"><\/p>/);
});

test("montarSenador mostra o aviso de licença do ministro e omite quando não há", async () => {
  const ministro = { nome: "Min <I>", cargos: [{ atual: true, cargo: "Ministro da Casa", inicio: "2025-03-01" }] };
  const com = await render({ ...base, ministro: "pes_9" }, {}, P, { "dados/ministro/pes_9.json": ministro });
  assert.match(com.html, /<p class="aviso"><b>Licenciado: /);
  assert.match(com.html, /Min &lt;I&gt; deixou o exercício do mandato de senador/);
  assert.match(com.html, /href="ministro\.html\?id=pes_9"/);
  const sem = await render(base);
  assert.doesNotMatch(sem.html, /Licenciado:/);
  const falha = await render({ ...base, ministro: "pes_9" });
  assert.doesNotMatch(falha.html, /Licenciado:/);
});

test("montarSenador com cota usa o rótulo Perfil e gastos e a fonte da CEAPS", async () => {
  const despesas = { ano: 2025, total: 1000, porCategoria: [], fornecedores: [], maioresNotas: [] };
  const { html } = await render({ ...base, despesas });
  assert.match(html, /id="aba-perfil"[^>]*>Perfil e gastos<\/button>/);
  assert.match(html, /Gastos da cota parlamentar em 2025/);
  assert.doesNotMatch(html, /não puderam ser carregados agora/);
  assert.match(html, /despesas_ceaps\/2025/);
});

test("montarSenador filtra a linha do tempo pelos votos do senador e usa links do Senado", async () => {
  const lista = [
    { id: "a", data: "2025-05-10", aprovada: 1, proposicao: "PL 1", descricao: "d", propId: "77" },
    { id: "b", data: "2025-05-11", aprovada: 1, proposicao: "PL 2", descricao: "d" },
    { id: "c", data: "2025-05-12", aprovada: null, proposicao: "PL 3", descricao: "d" },
  ];
  const { html } = await render({ ...base, votos: [{ id: "a", voto: "sim" }, { id: "c", voto: "nao" }, { id: "zzz", voto: "nao" }] }, { lista });
  assert.match(html, /1 votações nominais/);
  assert.match(html, /href="votacao\.html\?casa=senado&amp;id=a"/);
  assert.doesNotMatch(html, /id=b"/);
  assert.match(html, /Votações <small>1<\/small>/);
  assert.match(html, /<b>1<\/b><span>votos sim<\/span>/);
});

test("painelPresenca lista os motivos de falta ou diz que não faltou", async () => {
  const completa = await render({ ...base, presenca: { votacoes: 200, compareceu: 150, naoCompareceu: 20, licenca: 10, missao: 15, outros: 5 } });
  assert.match(completa.html, /Compareceu a <b>150<\/b> de 200 votações nominais \(<b>75%<\/b>\)/);
  assert.match(completa.html, /Nas demais: não compareceu a 20; 10 em licença; 15 em missão oficial ou atividade parlamentar; 5 por outros motivos\./);
  const perfeita = await render({ ...base, presenca: { votacoes: 3, compareceu: 3 } });
  assert.match(perfeita.html, /Não faltou a nenhuma\./);
  assert.doesNotMatch(perfeita.html, /Nas demais/);
});

test("painelRecursos mostra selos, pessoal, fora da cota e escritório no singular e no plural", async () => {
  const rec = {
    ano: 2025,
    beneficios: [["Auxílio-moradia", "Utilizou"], ["Imóvel funcional", "Não utilizou"]],
    pessoal: [["Gabinete", 12], ["Escritório(s) de apoio", 2], ["Vazio", 0]],
    foraCota: [["Diárias <x>", 1234]], totalForaCota: 1234.5,
    escritorios: [{ endereco: "Rua <A>, 1", telefone: "1111" }],
  };
  const um = await render({ ...base, recursos: rec });
  assert.match(um.html, /Recursos e benefícios em 2025/);
  assert.match(um.html, /Pessoal: <b>12<\/b> no gabinete; <b>2<\/b> no escritório de apoio\./);
  assert.doesNotMatch(um.html, /Vazio/);
  assert.match(um.html, /Gastos fora da cota: R\$\s1\.234,50/);
  assert.match(um.html, /<td>Diárias &lt;x&gt;<\/td>/);
  assert.match(um.html, /<h3>Escritório de apoio no estado<\/h3>/);
  assert.match(um.html, /<li>Rua &lt;A&gt;, 1 · 1111<\/li>/);
  assert.match(um.html, /recursos-utilizados\?ano=2025/);
  assert.match(um.html, /escritorios-apoio/);
  const dois = await render({ ...base, recursos: { ano: 2024, escritorios: [{ nome: "N1" }, { nome: "N2" }] } });
  assert.match(dois.html, /<h3>Escritórios de apoio no estado<\/h3>/);
  assert.match(dois.html, /<li>N1<\/li><li>N2<\/li>/);
  assert.doesNotMatch(dois.html, /fora da cota/);
  assert.doesNotMatch(dois.html, /Pessoal:/);
});

test("painelComissoesMandatos lista comissões e mandatos ou mostra o vazio", async () => {
  const cheio = await render({ ...base, comissoes: [{ sigla: "CCJ", nome: "Constituição <e> Justiça", cargo: "Titular", casa: "Senado", inicio: "2025-02-01", fim: "2026-01-31" }, { sigla: "CAE", nome: "Assuntos" }],
    mandatos: [{ inicio: "2019-02-01", fim: "2027-01-31", uf: "SP", cargo: "Senador", partidos: [{ sigla: "ABC", filiacao: "2018-01-01", desfiliacao: "2020-01-01" }, { sigla: "XYZ" }] }, { uf: "RJ" }] });
  assert.match(cheio.html, /<b>CCJ<\/b> Constituição &lt;e&gt; Justiça<br><span class="quando">Titular · Senado, desde .+ até /);
  assert.match(cheio.html, /<b>CAE<\/b> Assuntos<br><span class="quando">Membro, <\/span>/);
  assert.match(cheio.html, /Mandatos no Senado/);
  assert.match(cheio.html, /, SP \(senador\)/);
  assert.match(cheio.html, /Partidos: ABC desde .+ até .+ · XYZ<\/span>/);
  assert.match(cheio.html, /\? a \?, RJ/);
  assert.match(cheio.html, /senador\/55\/comissoes/);
  assert.match(cheio.html, /senador\/55\/mandatos/);
  const vazio = await render({ ...base, comissoes: [] });
  assert.match(vazio.html, /Nenhuma participação registrada no mandato atual\./);
  assert.doesNotMatch(vazio.html, /Mandatos no Senado/);
  const nenhum = await render(base);
  assert.doesNotMatch(nenhum.html, /<h2>Comissões<\/h2>/);
});

test("painelPresencaAno fica fora quando vazio e mostra uma linha por ano com a mediana", async () => {
  for (const anos of [undefined, null, []]) {
    const { html } = await render({ ...base, presencaAno: anos });
    assert.doesNotMatch(html, /t-presenca-ano/);
  }
  const { html } = await render({ ...base, presencaAno: [{ ano: 2024, votacoes: 100, compareceu: 80, mediana: 0.874 }, { ano: 2025, votacoes: 0, mediana: 0.5 }] });
  assert.match(html, /<h2 id="t-presenca-ano">Presença por ano<\/h2>/);
  assert.match(html, /<tr><td>2024<\/td><td>100<\/td><td><b>80<\/b> \(80%\)<\/td><td>87%<\/td><\/tr>/);
  assert.match(html, /<tr><td>2025<\/td><td>0<\/td><td><b>0<\/b> \(—\)<\/td><td>50%<\/td><\/tr>/);
  assert.match(html, /Votações nominais do Senado \(Dados Abertos\)/);
});

test("painelCargos fica fora sem dados e mostra lideranças, cargos e licenças", async () => {
  const vazio = await render({ ...base, liderancas: [], cargos: [], licencas: [] });
  assert.doesNotMatch(vazio.html, /Lideranças e cargos/);

  const cheio = await render({
    ...base,
    liderancas: [{ cargo: "Líder <do> Governo", unidade: "Senado", partido: "ABC", desde: "2025-02-01" }, {}],
    cargos: [{ cargo: "PRESIDENTE", sigla: "CCJ", nome: "Constituição", inicio: "2025-03-01" }, { cargo: "Vice", sigla: "CAE", nome: "CAE", inicio: "2023-03-01", fim: "2024-03-01" }, { sigla: "CE" }],
    licencas: [{ inicio: "2025-01-10", fim: "2025-01-20", tipo: "Licença <saúde>" }, { inicio: "2025-02-01", fim: "2025-02-01" }, {}],
  });
  assert.match(cheio.html, /<h2>Lideranças e cargos<\/h2>/);
  assert.match(cheio.html, /<h3>Lideranças em exercício<\/h3>/);
  assert.match(cheio.html, /<b>Líder &lt;do&gt; Governo<\/b>, Senado<br><span class="quando">ABC · desde /);
  assert.match(cheio.html, /<li><b>Líder<\/b><br><span class="quando"><\/span><\/li>/);
  assert.match(cheio.html, /<b>presidente<\/b> · CCJ \(Constituição\)<br><span class="quando">desde .+, em exercício<\/span>/);
  assert.match(cheio.html, /<b>vice<\/b> · CAE<br><span class="quando">desde .+ até .+<\/span>/);
  assert.doesNotMatch(cheio.html, /CAE \(CAE\)/);
  assert.match(cheio.html, /<b><\/b> · CE<br><span class="quando">sem data, em exercício<\/span>/);
  assert.match(cheio.html, /\(3 desde 2023\)/);
  assert.match(cheio.html, /Ver as 3 licenças/);
  assert.match(cheio.html, / a .+<br><span class="quando">Licença &lt;saúde&gt;<\/span>/);
  assert.match(cheio.html, /<li>[^<]+<br><span class="quando">Afastamento<\/span><\/li>/);
  assert.match(cheio.html, /<li>\?<br><span class="quando">Afastamento<\/span><\/li>/);
  assert.match(cheio.html, /composicao\/lideranca/);
  assert.match(cheio.html, /senador\/55\/cargos/);
  assert.match(cheio.html, /senador\/55\/licencas/);

  const semLider = await render({ ...base, licencas: [{ inicio: "2025-01-10", tipo: "Particular" }] });
  assert.match(semLider.html, /Lideranças e cargos/);
  assert.doesNotMatch(semLider.html, /Lideranças em exercício/);
  assert.doesNotMatch(semLider.html, /Presidência, vice-presidência/);
  assert.doesNotMatch(semLider.html, /composicao\/lideranca/);
});

test("painelDiscursos fica fora quando nulo e trata singular, plural, apartes, anos, assuntos e URLs", async () => {
  const nulo = await render({ ...base, discursos: null });
  assert.doesNotMatch(nulo.html, /Discursos e apartes/);

  const um = await render({ ...base, discursos: { total: 1, apartes: 1 } });
  assert.match(um.html, /Fulano &lt;F&gt; fez <b>1<\/b> pronunciamento no Plenário desde 2023 e <b>1<\/b> aparte\./);
  assert.doesNotMatch(um.html, /Por ano:/);
  assert.doesNotMatch(um.html, /Assuntos mais indexados/);
  assert.doesNotMatch(um.html, /Pronunciamentos mais recentes/);

  const varios = await render({ ...base, discursos: {
    total: 1200, apartes: 3, porAno: [[2024, 10], [2025, 20]],
    assuntos: [["Saúde <x>", 8], ["Educação", 4]],
    recentes: [
      { data: "2025-05-10", tipo: "Discurso", resumo: "Resumo <b>", url: "https://www.senado.leg.br/d?a=1&b=2" },
      { data: "2025-05-09", url: "javascript:alert(1)" },
      { data: "2025-05-08", resumo: "Sem link", url: "" },
    ],
  } });
  assert.match(varios.html, /<b>1\.200<\/b> pronunciamentos no Plenário/);
  assert.match(varios.html, /<b>3<\/b> apartes/);
  assert.match(varios.html, /Por ano: 2024: 10 · 2025: 20\./);
  assert.match(varios.html, /<span>Saúde &lt;x&gt;<\/span><b>8<\/b><\/div><div class="barra"><i style="width:100%">/);
  assert.match(varios.html, /<span>Educação<\/span><b>4<\/b><\/div><div class="barra"><i style="width:50%">/);
  assert.match(varios.html, /Discurso<\/span><\/span>|Discurso<\/span>/);
  assert.match(varios.html, /Resumo &lt;b&gt; <a href="https:\/\/www\.senado\.leg\.br\/d\?a=1&amp;b=2" rel="noopener">texto completo<\/a>/);
  assert.match(varios.html, /Sem resumo<\/li>/);
  assert.match(varios.html, /Sem link<\/li>/);
  assert.equal((varios.html.match(/texto completo/g) || []).length, 1);
  assert.doesNotMatch(varios.html, /javascript:/);
  assert.match(varios.html, /senador\/55\/discursos/);
  assert.match(varios.html, /senador\/55\/apartes/);

  const semAparte = await render({ ...base, discursos: { total: 0, apartes: 0 } });
  assert.match(semAparte.html, /fez <b>0<\/b> pronunciamentos no Plenário desde 2023\./);
});

test("painelRelatorias fica fora quando nulo e lista totais, anos, colegiados e designações", async () => {
  const nulo = await render({ ...base, relatorias: null });
  assert.doesNotMatch(nulo.html, /<h2>Relatorias/);

  const { html } = await render({ ...base, relatorias: {
    total: 1500, tramitando: 7, porAno: [[2024, 3], [2025, 4]], porColegiado: [["CCJ <x>", 5], ["CAE", 2]],
    recentes: [
      { id: "99", materia: "PL 1/2025", colegiado: "CCJ", tipo: "RELATOR", desde: "2025-04-01", ate: "2025-05-01", ementa: "Ementa <e>" },
      { id: "a/b", desde: "2025-03-01" },
    ],
  } });
  assert.match(html, /<h2>Relatorias <small class="sub">\(1\.500\)<\/small><\/h2>/);
  assert.match(html, /relator desde 2023: <b>1\.500<\/b>, das quais <b>7<\/b> ainda tramitam\./);
  assert.match(html, /Por ano: 2024: 3 · 2025: 4\./);
  assert.match(html, /Onde mais relatou: CCJ &lt;x&gt; \(5\), CAE \(2\)\./);
  assert.match(html, /<h3>As 2 designações mais recentes<\/h3>/);
  assert.match(html, /<b>PL 1\/2025<\/b> <span class="quando">CCJ · relator · designado em .+, até .+<\/span><br>Ementa &lt;e&gt;/);
  assert.match(html, /<a href="https:\/\/www25\.senado\.leg\.br\/web\/atividade\/materias\/-\/materia\/99" rel="noopener">tramitação<\/a>/);
  assert.match(html, /<b>Matéria<\/b>/);
  assert.match(html, /Sem ementa/);
  assert.match(html, /materia\/a%2Fb/);
  assert.match(html, /relatoria\?codigoParlamentar=55/);

  const minima = await render({ ...base, relatorias: { total: 0, tramitando: 0, recentes: [] } });
  assert.match(minima.html, /<h3>As 0 designações mais recentes<\/h3>/);
  assert.doesNotMatch(minima.html, /Por ano:/);
  assert.doesNotMatch(minima.html, /Onde mais relatou/);
});

test("coautoriaSenador mostra a tabela com partido e UF ou traço e some sem coautoria", async () => {
  const sem = await render(base);
  assert.doesNotMatch(sem.html, /Com quem assina projetos/);
  const { html } = await render({ ...base, coautoria: { projetos: 2, outroPartido: 1, parceiros: [["Ana <A>", "ABC", "SP", 4], ["Beto", "XYZ", "", 3], ["Caio", "", "RJ", 1]] } });
  assert.match(html, /2 projetos assinados com outros parlamentares, 1 com parlamentar de outro partido \(50%\)/);
  assert.match(html, /<td>Ana &lt;A&gt;<\/td><td>ABC\/SP<\/td><td>4<\/td>/);
  assert.match(html, /<td>Beto<\/td><td>XYZ<\/td><td>3<\/td>/);
  assert.match(html, /<td>Caio<\/td><td>—<\/td><td>1<\/td>/);
  assert.match(html, /Autoria das matérias \(Dados Abertos do Senado\)/);
});
