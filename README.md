# Minha Bancada

Site estático que mostra como votam os deputados federais, o que propõem e quanto gastam da cota parlamentar. Os dados vêm da [API de Dados Abertos da Câmara](https://dadosabertos.camara.leg.br) e são atualizados sozinhos todo dia.

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
python scripts/gerar.py
python -m http.server 8000 -d site                # abra http://localhost:8000
```

Sem `--limite` a coleta pega todos os deputados em exercício. `--dias` só vale na primeira coleta; depois o script continua de onde parou.

## Estrutura

| Caminho | O que é |
|---|---|
| `scripts/coletar.py` | Baixa deputados, proposições, despesas e votações do Plenário (com o voto de cada um). |
| `scripts/gerar.py` | Monta os JSONs enxutos que o site lê. Não acessa a internet. |
| `dados/votacoes/` | Histórico de votações, um arquivo por ano. Vai crescendo a cada execução. |
| `site/` | O site: HTML, CSS e um único `assets/app.js`, sem framework nem etapa de build. |
| `.github/workflows/atualizar.yml` | Agenda diária, coleta, salva o histórico e publica. |

## Limites gratuitos para acompanhar

- **GitHub Pages:** site de até 1 GB e cerca de 100 GB de tráfego por mês. Com milhares de visitas por dia ainda sobra bastante. Se um dia passar disso, o Cloudflare Pages é gratuito e não tem limite de tráfego; é só apontar para a pasta `site/`.
- **GitHub Actions:** gratuito sem limite em repositório público. Cada execução dura poucos minutos depois da primeira.
- **Agendamento:** o GitHub pausa tarefas agendadas em repositórios sem atividade por 60 dias. Os commits diários do robô costumam contar como atividade, mas se a atualização parar, reative na aba Actions.

## Próximos passos possíveis

- Senado: API em `https://legis.senado.leg.br/dadosabertos`, com senadores, matérias e votações nominais.
- Orientação dos partidos em cada votação (`/votacoes/{id}/orientacoes`), para mostrar quem votou contra o próprio partido.
- Votações nas comissões, além do Plenário.
- TSE: bens declarados e doações de campanha (`https://dadosabertos.tse.jus.br`).
- Busca por tema nas ementas das proposições.

## Aviso

Projeto independente, sem vínculo com a Câmara dos Deputados ou com partidos. Os dados são exibidos como publicados pela fonte oficial, que prevalece em caso de divergência.
