/* Fornecedores com mais gastos da cota. */
import { $, esc, reais, semAcento, carregar } from "./util.js";
import { listaPaginada, erro } from "./comum.js";

export async function paginaFornecedores() {
  const alvo = $("#resultado");
  let j;
  try { j = await carregar("dados/fornecedores_cota.json"); } catch (e) { return erro(alvo, e); }
  if (j.ano) $("#fonte-csv").href = `https://www.camara.leg.br/cotas/Ano-${j.ano}.csv.zip`;
  const cnpj = (c) => c.length === 14 ? c.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5") : c.length === 11 ? c.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, "$1.$2.$3-$4") : c;
  const render = (f) => `<li>
    <span class="quando">${reais(f.total)}</span>
    <span class="texto"><b>${esc(f.nome)}</b> <span class="quando">${esc(cnpj(f.cnpj))}</span></span>
    <span class="texto"><span class="quando">${f.deputados} ${f.deputados === 1 ? "deputado" : "deputados"}, ${f.notas} ${f.notas === 1 ? "nota" : "notas"}</span>
      <br>Mais usado por ${f.maioresDeputados.map((d) => `<a href="deputado.html?id=${d.id}">${esc(d.nome)}</a> (${esc(d.partido)}-${esc(d.uf)}, ${reais(d.valor)})`).join(", ")}</span></li>`;
  const desenhar = () => {
    const b = semAcento($("#busca").value.trim());
    const f = j.fornecedores.filter((x) => !b || semAcento(`${x.nome} ${x.cnpj} ${cnpj(x.cnpj)}`).includes(b));
    $("#contagem").textContent = `${f.length} fornecedores com mais gastos da cota em ${j.ano}`;
    listaPaginada(alvo, f, render, 20, "Nenhum fornecedor encontrado com essa busca.");
  };
  $("#busca").addEventListener("input", desenhar);
  desenhar();
}
