# Minha Bancada

Site estático com todos os políticos com mandato no Brasil, de vereador a presidente, e os eleitos de 2026. Para deputados federais, mostra também como votam, o que propõem e quanto gastam. Os dados vêm do [TSE](https://dadosabertos.tse.jus.br), da [Câmara](https://dadosabertos.camara.leg.br) e do [Senado](https://legis.senado.leg.br/dadosabertos) e são atualizados sozinhos todo dia.

**Site: https://adrianogpena.github.io/minha-bancada/**

**Custo: zero.** Tudo roda no GitHub: o GitHub Actions coleta os dados e o GitHub Pages hospeda o site.

## Como funciona

```
API da Câmara ──> scripts/coletar.py ──> dados/        (cache bruto; o histórico de votações fica no git)
                                         │
                  scripts/gerar.py  <────┘
                         │
                         └──> site/dados/  ──> GitHub Pages
```

O arquivo `.github/workflows/atualizar.yml` roda as duas etapas todo dia às 6h17 (Brasília) e publica o resultado.

## Colocar no ar (uns 10 minutos)

1. Crie uma conta no [GitHub](https://github.com), se ainda não tiver.
2. Crie um repositório **público** chamado `minha-bancada` (ou o nome que preferir). Repositório público é o que deixa o Actions gratuito e ilimitado.
3. Envie os arquivos deste projeto para o repositório. O jeito mais simples, no computador:
   ```bash
   cd minha-bancada
   git init -b master
   git add .
   git commit -m "Primeira versão"
   git remote add origin https://github.com/SEU_USUARIO/minha-bancada.git
   git push -u origin master
   ```
   Se preferir pelo site do GitHub ("Add file" > "Upload files"), confira depois se a pasta `.github/workflows` subiu. Ela começa com ponto e alguns sistemas a escondem. Se não subiu, crie o arquivo pelo botão "Add file" > "Create new file", digitando o caminho `.github/workflows/atualizar.yml`, e cole o conteúdo.
4. No repositório, vá em **Settings > Pages** e, em "Source", escolha **GitHub Actions**.
5. Vá em **Settings > Actions > General** e confirme que "Workflow permissions" está em **Read and write permissions**.
6. Vá na aba **Actions**, abra "Atualizar dados e publicar site" e clique em **Run workflow**. A primeira coleta leva uns 15 a 30 minutos (são mais de 500 deputados).
7. Pronto: o site fica em `https://SEU_USUARIO.github.io/minha-bancada/`.

## Rodar no seu computador

Precisa de Python 3.10 ou mais novo.

```bash
pip install -r requirements.txt
python scripts/coletar.py --limite 20 --dias 30   # amostra rápida: 20 deputados, 30 dias
python scripts/coletar_tse.py --anos 2024           # eleitos municipais (baixa ~100 MB)
python scripts/gerar.py
python -m http.server 8000 -d site                # abra http://localhost:8000
```

Sem `--limite` a coleta pega todos os deputados em exercício. `--dias` só vale na primeira coleta; depois o script continua de onde parou.

## Estrutura

| Caminho | O que é |
|---|---|
| `scripts/coletar.py` | Baixa deputados, proposições, despesas e votações do Plenário (com o voto de cada um). |
| `scripts/coletar_tse.py` | Baixa do TSE os eleitos de 2022, 2024 e 2026, com bens declarados. Anos encerrados são baixados uma vez só. |
| `scripts/baixar_tse.py` | Baixa arquivos extras do TSE (prestação de contas, votos por seção, perfil do eleitorado…) para `dados/tse_bruto/` e registra no CHANGELOG. |
| `CHANGELOG.md` | De onde vem cada dado, quando entrou e como foi baixado. |
| `scripts/gerar.py` | Monta os JSONs enxutos que o site lê. Não acessa a internet. |
| `scripts/gerar_politicos.py` | Junta TSE, Câmara e Senado no índice de todos os políticos (chamado pelo `gerar.py`). |
| `dados/proposicoes_detalhe.json` | Situação atual de cada projeto (aprovado, arquivado, em tramitação), da API da Câmara. Cada execução consulta até 4000 projetos (`DETALHES_POR_EXECUCAO`), então o cache se completa em alguns dias. |
| `dados/senado_votacoes/` | Votações nominais do Plenário do Senado, com o voto de cada senador. |
| `dados/senado_ceaps.json` | Gastos da cota (CEAPS) do ano corrente, de todos os senadores, da API administrativa do Senado. Fica fora do git: é baixado de novo a cada execução. |
| `dados/senado_materias.json` | Situação atual dos projetos de senadores, da API do Senado (até 1500 por execução, `MATERIAS_POR_EXECUCAO`). |
| `dados/votacoes/` | Histórico de votações, um arquivo por ano. Vai crescendo a cada execução. |
| `scripts/coletar_prefeituras.py` | Baixa o que os prefeitos de capitais enviaram às Câmaras Municipais que usam o SAPL (Rio Branco, Boa Vista, Natal e João Pessoa), incluindo vetos. As outras capitais mostram só o link oficial da Câmara. |
| `scripts/coletar_prefeitura_sp.py` | O mesmo para São Paulo, que não usa SAPL: lê o webservice do SPLegis. Nova capital com sistema próprio entra em `OUTRAS`, em `coletar_prefeituras.py`, com um coletor assim. |
| `scripts/coletar_prefeitura_ba.py` | O mesmo para Salvador: consulta de proposições da Câmara (grade Scriptcase), filtrada pelo autor "Executivo Municipal"; o link de cada projeto é o PDF do texto integral. |
| `scripts/coletar_prefeitura_go.py` | O mesmo para Goiânia: consulta pública de processos do SUAP da Câmara, filtrada pelo interessado "Prefeito de Goiânia"; o link de cada projeto é a página pública do processo. Usa o certificado intermediário de `scripts/certs/`, que o servidor não envia. |
| `dados/municipais/` | Cache dessas coletas, um arquivo por ano e capital. |
| `dados/tse/` | Eleitos de cada eleição, um arquivo por estado. |
| `dados/proposicoes/` | Proposições já coletadas de cada deputado. A API só aceita 3 meses por consulta, então a primeira coleta é longa e as seguintes buscam só o período novo. |
| `site/` | O site: HTML, CSS e um único `assets/app.js`, sem framework nem etapa de build. |
| `.github/workflows/atualizar.yml` | Agenda diária, coleta, salva o histórico e publica. |

## Limites gratuitos para acompanhar

- **GitHub Pages:** site de até 1 GB e cerca de 100 GB de tráfego por mês. Com milhares de visitas por dia ainda sobra bastante. Se um dia passar disso, o Cloudflare Pages é gratuito e não tem limite de tráfego; é só apontar para a pasta `site/`.
- **GitHub Actions:** gratuito sem limite em repositório público. Cada execução dura poucos minutos depois da primeira.
- **Agendamento:** o GitHub pausa tarefas agendadas em repositórios sem atividade por 60 dias. Os commits diários do robô costumam contar como atividade, mas se a atualização parar, reative na aba Actions.

## Próximos passos possíveis

- Página de detalhe de cada votação do Senado.
- Assembleias legislativas e câmaras municipais que publicam dados abertos.
- Orientação dos partidos em cada votação (`/votacoes/{id}/orientacoes`), para mostrar quem votou contra o próprio partido.
- Votações nas comissões, além do Plenário.
- Doações e gastos de campanha (TSE).
- Seguir políticos: lista salva no navegador de cada pessoa.
- Busca por tema nas ementas das proposições.

## Aviso

Projeto independente, sem vínculo com a Câmara dos Deputados ou com partidos. Os dados são exibidos como publicados pela fonte oficial, que prevalece em caso de divergência.
