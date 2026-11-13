/* Assembleia de cada UF como órgão: contratos, atas de registro de preço, maiores fornecedores, regras da verba e normas
   (dados/assembleias.json, dados/orgao/<UF>.json e dados/leis/<UF>.json; scripts/gerar_estaduais.py). Despesa do órgão, não de deputado. */
import { $, esc, data, carregar, reaisCentavos, numeroBr, semAcento, param, urlSegura } from "./util.js";
import { erro, listaPaginada } from "./comum.js";
import { fontes, UFS } from "./apis.js";

const TIPOS = { contrato: "Contrato", ata_registro: "Ata de registro de preços", ata_adesao: "Adesão a ata de registro de preços" };

const DO = new Set(["AC", "AP", "AM", "CE", "DF", "ES", "MA", "PA", "PR", "PI", "RJ", "RN", "RS", "TO"]);
const DA = new Set(["BA", "PB"]);
/* "do Paraná", "da Bahia", "de São Paulo". */
export const deUf = (uf) => `${DO.has(uf) ? "do" : DA.has(uf) ? "da" : "de"} ${UFS[uf] || uf}`;

const link = (rotulo, url) => (urlSegura(url) ? `<a href="${esc(url)}" rel="noopener">${esc(rotulo)}</a>` : esc(rotulo));
const plural = (n, um, varios) => `${numeroBr(n)} ${n === 1 ? um : varios}`;

/* "Ata de registro de preços 12/2026" ou o título do PDF quando a fonte não separa número. */
export function tituloItem(i) {
  const tipo = TIPOS[i.tipo] || "Contrato";
  return i.numero ? `${tipo} ${i.numero}` : tipo;
}

export function vigencia(i) {
  if (i.inicio && i.fim) return `${data(i.inicio)} a ${data(i.fim)}`;
  if (i.inicio) return `desde ${data(i.inicio)}`;
  if (i.fim) return `até ${data(i.fim)}`;
  return i.ano ? `ano ${i.ano}` : "";
}

/* Valor de ata é o teto do registro de preços, não gasto; sem valor na fonte (PDF) não se inventa número. */
export function textoValor(i) {
  if (typeof i.valor !== "number") return i.fornecedor ? "valor não publicado" : "fornecedor e valor só no PDF";
  return i.tipo === "ata_registro" ? `até ${reaisCentavos(i.valor)} (teto registrado)` : reaisCentavos(i.valor);
}

function itemOrgao(i) {
  const arquivos = (i.arquivos || []).filter((a) => urlSegura(a.url)).slice(0, 4).map((a) => [a.nome || "Documento", a.url]);
  const quem = i.fornecedor ? `${esc(i.fornecedor)}${i.cnpj ? ` <span class="quando">CNPJ ${esc(i.cnpj)}</span>` : ""}` : "";
  const extra = [i.modalidade || i.especie || i.licitacao, i.situacao].filter(Boolean).map(esc).join(" · ");
  return `<li>
    <span class="quando">${esc(vigencia(i))}</span>
    <span class="texto"><b>${esc(tituloItem(i))}</b>${i.objeto ? `: ${esc(i.objeto)}` : ""}
      ${quem ? `<br>${quem}` : ""}<br><span class="quando">${esc(textoValor(i))}${extra ? ` · ${extra}` : ""}</span></span>
    ${fontes([["Página na fonte", i.fonte], ...arquivos])}</li>`;
}

function blocoRegras(r) {
  const docs = (r && r.documentos) || [];
  if (!docs.length) return "";
  const itens = docs.map((d) => `<li>${link(d.titulo || "Texto da regra", d.url)}${d.vigente === false ? ` <span class="quando">(revogado ou substituído)</span>` : ""}</li>`).join("");
  return `<section><h2>Regras da verba dos deputados</h2>
    <p class="nota-lista">Os atos e resoluções que a Assembleia publica sobre o ressarcimento (ou cota) da atividade parlamentar, como links para o texto.</p>
    <ul class="lista-simples">${itens}</ul>${fontes([["Página das regras", r.fonte]])}</section>`;
}

function blocoFornecedores(lista) {
  if (!lista.length) return "";
  const linhas = lista.slice(0, 20).map((f) => {
    const nucleo = f.idFornecedor ? `<br><a class="ver-legivel" href="fornecedores.html?busca=${esc(f.idFornecedor.slice(4))}">também nas cotas e verbas</a>` : "";
    return `<tr><td>${esc(f.nome)}${f.cnpj ? `<br><span class="quando">CNPJ ${esc(f.cnpj)}</span>` : ""}${nucleo}</td>
      <td>${numeroBr(f.contratos)}</td><td>${reaisCentavos(f.valorContratado)}</td><td>${numeroBr(f.atas)}</td><td>${reaisCentavos(f.valorRegistrado)}</td></tr>`;
  }).join("");
  return `<section><h2>Maiores fornecedores</h2>
    <p class="nota-lista">Soma dos contratos coletados, agrupados pelo CNPJ (ou pelo nome, quando a fonte não traz CNPJ). O valor das atas de registro de preços é o teto
      que a Assembleia pode comprar, não o que gastou, e por isso fica separado. Contrato que só existe em PDF fica fora desta soma.</p>
    <div class="rolagem"><table class="tabela"><thead><tr><th>Fornecedor</th><th>Contratos</th><th>Valor contratado</th><th>Atas</th><th>Valor registrado</th></tr></thead>
    <tbody>${linhas}</tbody></table></div>
    ${lista.length > 20 ? `<p class="nota-lista">Mostrando os 20 maiores de ${numeroBr(lista.length)} fornecedores.</p>` : ""}</section>`;
}

function filtrarItens(itens, busca, tipo) {
  const b = semAcento(busca.trim());
  const digitos = b.replace(/\D/g, "");
  return itens.filter((i) => (!tipo || (tipo === "contrato" ? i.tipo === "contrato" : i.tipo !== "contrato")) &&
    (!b || semAcento(`${i.objeto || ""} ${i.fornecedor || ""} ${i.numero || ""}`).includes(b) || (digitos.length >= 4 && (i.cnpj || "").includes(digitos))));
}

function montarContratos(alvo, o) {
  if (!o.itens.length) return;
  const sec = document.createElement("section");
  const temAtas = o.itens.some((i) => i.tipo !== "contrato");
  sec.innerHTML = `<h2>Contratos e atas</h2>
    <div class="filtros"><label class="campo">Objeto, fornecedor, número ou CNPJ<input id="busca-orgao" type="search" autocomplete="off"></label>
      ${temAtas ? `<label class="campo">Tipo<select id="tipo-orgao"><option value="">Todos</option><option value="contrato">Contratos</option><option value="ata">Atas e adesões</option></select></label>` : ""}</div>
    <p class="contagem" id="contagem-orgao" aria-live="polite"></p><div id="lista-orgao"></div>`;
  alvo.append(sec);
  const busca = $("#busca-orgao", sec), tipo = $("#tipo-orgao", sec);
  const desenhar = () => {
    const f = filtrarItens(o.itens, busca.value, tipo ? tipo.value : "");
    $("#contagem-orgao", sec).textContent = `${numeroBr(f.length)} de ${plural(o.itens.length, "documento", "documentos")}, do mais novo ao mais antigo`;
    listaPaginada($("#lista-orgao", sec), f, itemOrgao, 20, "Nenhum contrato ou ata com essa busca.");
  };
  busca.addEventListener("input", desenhar);
  if (tipo) tipo.addEventListener("change", desenhar);
  desenhar();
}

function itemNorma(n) {
  return `<li><span class="quando">${esc(n.ano || "")}</span>
    <span class="texto"><b>${esc(n.tipo || "Norma")} ${esc(n.numero || "")}${n.ano ? `/${esc(n.ano)}` : ""}</b>${n.ementa ? `: ${esc(n.ementa)}` : ""}</span>
    ${fontes([["Texto da norma", n.link], ["Banco de leis", n.fonte]])}</li>`;
}

function montarNormas(alvo, leis) {
  if (!leis || !leis.normas || !leis.normas.length) return;
  const sec = document.createElement("section");
  sec.innerHTML = `<h2>Leis e normas</h2>
    <p class="nota-lista">Catálogo de normas que a Assembleia publica sem a autoria; por isso não aparecem na ficha de cada deputado.</p>
    <div class="filtros"><label class="campo">Número ou assunto<input id="busca-normas" type="search" autocomplete="off"></label></div>
    <p class="contagem" id="contagem-normas" aria-live="polite"></p><div id="lista-normas"></div>`;
  alvo.append(sec);
  const busca = $("#busca-normas", sec);
  const desenhar = () => {
    const b = semAcento(busca.value.trim());
    const f = leis.normas.filter((n) => !b || semAcento(`${n.tipo} ${n.numero}/${n.ano} ${n.ementa || ""}`).includes(b));
    $("#contagem-normas", sec).textContent = `${numeroBr(f.length)} de ${plural(leis.normas.length, "norma", "normas")}`;
    listaPaginada($("#lista-normas", sec), f, itemNorma, 20, "Nenhuma norma com essa busca.");
  };
  busca.addEventListener("input", desenhar);
  desenhar();
}

function resumoUf(a) {
  const partes = [];
  if (a.contratos) partes.push(plural(a.contratos, "contrato", "contratos"));
  if (a.atas) partes.push(plural(a.atas, "ata", "atas"));
  if (a.regras) partes.push(plural(a.regras, "regra da verba", "regras da verba"));
  if (a.normas) partes.push(plural(a.normas, "norma", "normas"));
  return partes.join(" · ");
}

function paginaIndice(alvo, indice) {
  const itens = indice.map((a) => `<li><span class="texto"><a href="assembleia.html?uf=${esc(a.uf)}"><b>${esc(UFS[a.uf] || a.uf)}</b></a>
    <br><span class="quando">${esc(resumoUf(a))}</span></span></li>`).join("");
  alvo.innerHTML = `
    <section class="abertura"><h1>Assembleias Legislativas</h1>
      <p>O que cada Assembleia gasta como órgão: contratos, atas de registro de preços e os maiores fornecedores, com as regras da verba dos deputados e,
        quando a Assembleia publica, o catálogo de leis. Os gastos de cada deputado estadual ficam na ficha dele.</p></section>
    ${indice.length ? `<ul class="itens">${itens}</ul>` : `<p class="vazio">Nenhuma Assembleia com esses dados ainda.</p>`}
    <p class="nota-lista">Só aparecem as Assembleias que publicam esses dados num formato que a coleta lê.</p>`;
}

export async function paginaAssembleia() {
  const alvo = $("#conteudo");
  const uf = (param("uf") || "").toUpperCase();
  let indice;
  try { indice = await carregar("dados/assembleias.json"); } catch (e) { return erro(alvo, e); }
  const resumo = indice.find((a) => a.uf === uf);
  if (!resumo) return paginaIndice(alvo, indice);
  document.title = `Assembleia ${deUf(uf)} | Minha Bancada`;
  let o = { itens: [], fornecedores: [] }, leis = null;
  try {
    if (resumo.contratos || resumo.atas || resumo.regras) o = await carregar(`dados/orgao/${uf}.json`);
    if (resumo.normas) leis = await carregar(`dados/leis/${uf}.json`);
  } catch (e) { return erro(alvo, e); }
  const contagem = [o.itens.length ? plural(o.itens.length, "contrato ou ata", "contratos e atas") : "",
    o.fornecedores.length ? plural(o.fornecedores.length, "fornecedor", "fornecedores") : ""].filter(Boolean).join(" · ");
  alvo.innerHTML = `
    <section class="abertura"><h1>Assembleia Legislativa ${esc(deUf(uf))}</h1>
      <p>Despesas da Assembleia como órgão (não de um deputado): contratos, atas de registro de preços e quem mais vende a ela.
        <a href="assembleia.html">Outras Assembleias</a></p></section>
    ${contagem ? `<p class="contagem">${contagem}</p>` : ""}
    ${o.itens.length ? `<p class="nota-lista">Cada linha tem o link da página ou do PDF na fonte. Quando a Assembleia publica só o PDF, o fornecedor e o valor ficam dentro dele e não são lidos.</p>${fontes([["Contratos no portal da Assembleia", o.fonte]])}` : ""}
    ${blocoFornecedores(o.fornecedores)}${blocoRegras(o.regrasRessarcimento)}`;
  montarContratos(alvo, o);
  montarNormas(alvo, leis);
}
