# Plano: o que cada ministério faz (camada 1)

Objetivo: a página `ministerios.html?pasta=<chave>` explica em linguagem simples o que a pasta faz, e a página do ministro
(`ministro.html`) mostra o que o cargo comporta. Só texto escrito por nós e conferido nas fontes oficiais; sem coletor novo e
sem endpoint novo (os links oficiais são só links, não consultas). As camadas 2 (números: orçamento, servidores) e 3 (atuação
da pessoa) estão em `FUTURAS_IMPLEMENTACOES.md`, pacotes 3.4 e 3.5.

> **Andamento (2026-10-30):** etapa 1 feita. `scripts/ministerios_descricao.json` tem as 38 pastas, escritas a partir do texto da Lei 14.600/2023 (versão original, no portal da Câmara; o Planalto bloqueia a coleta automática) e da Lei 14.816/2024 (Ministério do Empreendedorismo; revoga os incisos IX e X do art. 34). `vinculados` ficou de fora desta primeira versão: a lei não os lista e a lista só entra após conferência no decreto de estrutura de cada pasta. Alterações posteriores à Lei 14.816/2024 ainda não foram conferidas pasta a pasta. O teste de cobertura já existe em `tests/test_ministros.py`.
>
> **Etapas 2 a 5 feitas (2026-10-30):** gerador (`descricoes()`), front (`blocoDescricao` em `ministros.js`, resumo na ficha do ministro), testes Python e JS, nota no `sobre.html` e `CHANGELOG.md`. Falta apenas a conferência dos `vinculados` e das alterações legais posteriores a 2024.

## 1. Dados: `scripts/ministerios_descricao.json`

Arquivo versionado à mão (como `ministros_posse.json`), indexado pela chave de `PASTAS` em `scripts/ministerios.py`:

```json
{
  "saude": {
    "resumo": "Coordena o SUS e a política nacional de saúde.",
    "areas": ["Vigilância em saúde e vacinação", "Hospitais federais", "Atenção primária"],
    "vinculados": [{"nome": "Anvisa", "url": "https://www.gov.br/anvisa"}],
    "site": "https://www.gov.br/saude",
    "base": [{"rotulo": "Lei 14.600/2023", "url": "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/lei/L14600.htm"}],
    "revisadoEm": "2026-10-30"
  }
}
```

- `resumo` (1 a 2 frases), `areas` (3 a 6 itens) e `base` são obrigatórios; `vinculados` e `site` quando existirem.
- Texto só com o que consta na lei de organização da Presidência e dos ministérios (Lei 14.600/2023 e alterações), no decreto
  de estrutura da pasta ou no site oficial. Nada de memória sem conferir; a fonte de cada pasta fica em `base`.
- Valem as 38 chaves de `PASTAS`. Pasta extinta ou renomeada ganha chave nova, como já ocorre.

## 2. Geração: `scripts/gerar_ministros.py`

- Ler o arquivo e gravar `descricao` (o objeto acima, sem `revisadoEm` duplicado em cada página se não for exibido) dentro de
  `site/dados/ministerio/<pasta>.json`. Não copiar para `ministerios.json` (lista) nem para `ministro/<pessoa>.json`: a página
  do ministro busca a pasta por id, como já faz para os pedidos (regra "um lugar só").
- Pasta sem descrição: campo ausente e aviso em `gerar.py` (`avisar`), sem quebrar a geração.

## 3. Front: `site/assets/js/ministros.js` e `site/ministerios.html`

- `paginaMinisterio`: bloco "O que faz" entre o título e "Ministros": resumo, lista de áreas, órgãos vinculados com link, link
  "Site oficial" e `fontes([...])` com a base legal (padrão já usado na página).
- `paginaMinistro`: em cada cargo, o `resumo` da pasta e o link "Ver o ministério" (já existe), mais a frase fixa sobre as
  atribuições do ministro de Estado (Constituição, art. 87: orientar, coordenar e supervisionar a pasta, referendar atos do
  presidente, expedir instruções, apresentar relatório anual).
- Sem descrição: o bloco some, nada de texto vazio. Escapar tudo com `esc`; URLs só `https://` (validar no gerador).

## 4. Testes

- `tests/test_ministros.py`: toda chave de `PASTAS` tem descrição com `resumo`, `areas` e `base`; chaves do JSON existem em
  `PASTAS`; URLs começam com `https://`; o gerador grava `descricao` na pasta e avisa quando falta.
- `tests/js/app.test.js`: `paginaMinisterio` renderiza resumo, áreas e vinculados; omite o bloco sem descrição; escapa HTML.
- Fumaça (`tests/e2e/fumaca.test.js`): se já abre `ministerios.html?pasta=...`, conferir o bloco "O que faz" nos dados mínimos
  (`tests/e2e/preparar_site.py` ganha uma descrição).

## 5. Documentação

- `site/sobre.html`: nota de que as descrições são resumos escritos pelo projeto a partir da lei de organização dos ministérios
  e dos sites oficiais, com a data da última revisão.
- `CHANGELOG.md`: entrada da camada 1 (sem endpoint novo, nada a registrar em `ENDPOINTS.md`).
- `FUTURAS_IMPLEMENTACOES.md`: mover o que for feito para o `CHANGELOG.md`.

## 6. Ordem de trabalho

1. Redigir as 38 descrições, conferindo cada uma na lei e no site da pasta (a etapa mais longa).
2. Gerador + testes Python.
3. Front + testes JS e fumaça.
4. Docs e `CHANGELOG.md`.

Risco principal: reforma ministerial deixa texto velho. Mitigação: `revisadoEm` por pasta e o teste de cobertura; pasta que
mudar de nome ou de competência é revisada junto com a atualização de `PASTAS`.
