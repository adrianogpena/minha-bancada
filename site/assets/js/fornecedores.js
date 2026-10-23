/* Fornecedores que mais recebem das cotas e verbas: Câmara, Senado e Assembleias. */
import { $, esc, reais, semAcento, carregar } from "./util.js";
import { listaPaginada, erro } from "./comum.js";

const CASAS = { camara: "Câmara", senado: "Senado", estadual: "Assembleias" };

export async function paginaFornecedores() {
  const alvo = $("#resultado");
  let j;
  try { j = await carregar("dados/fornecedores.json"); } catch (e) { return erro(alvo, e); }
  const link = (p) => {
    const nome = `${esc(p.nome)} (${esc(p.partido || "s/p")}-${esc(p.uf || "")}, ${reais(p.valor)})`;
    return p.pagina ? `<a href="${esc(p.pagina)}">${nome}</a>` : nome;
  };
  const render = (f) => `<li>
    <span class="quando">${reais(f.total)}</span>
    <span class="texto"><b>${esc(f.nome)}</b> <span class="quando">${f.documento ? esc(f.documento) : "sem CNPJ ou CPF na fonte"}</span></span>
    <span class="texto"><span class="quando">${f.politicos} ${f.politicos === 1 ? "político" : "políticos"}, ${f.notas} ${f.notas === 1 ? "nota" : "notas"}
      · ${Object.entries(f.porCasa).map(([c, v]) => `${CASAS[c] || esc(c)} ${reais(v)}`).join(" · ")}</span>
      <br>Mais usado por ${f.maioresPoliticos.map(link).join(", ")}</span></li>`;
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
}
