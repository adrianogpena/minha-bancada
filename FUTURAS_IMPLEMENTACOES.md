# Futuras implementações

Ideias levantadas e ainda não feitas. Cada item diz de onde vêm os dados e o custo de coleta.
Ao implementar um endpoint novo, registre-o no `ENDPOINTS.md` e o conjunto no `CHANGELOG.md`.

Já feito a partir de `/proposicoes/{id}/autores`: autor principal/coautor, nomes e partido dos coautores,
total de autores e de partidos, iniciativa (Executivo, Senado, comissão) quando o principal não é deputado.

## Novos endpoints da Câmara (API v2, `https://dadosabertos.camara.leg.br/api/v2`)

| Ideia | Endpoint | Custo | O que daria no site |
|---|---|---|---|
| Temas oficiais | `/proposicoes/{id}/temas` | 1 chamada por projeto (como os autores) | filtrar e agregar propostas por tema (saúde, segurança, economia...) |
| Proposições relacionadas | `/proposicoes/{id}/relacionadas` | 1 por projeto | ligar projetos apensados, substitutos e do mesmo assunto |
| Votações do projeto | `/proposicoes/{id}/votacoes` | 1 por projeto | ligar o projeto às votações já guardadas em `dados/votacoes/` |
| Tramitação completa | `/proposicoes/{id}/tramitacoes` | 1 por projeto; já usada só para o Executivo | linha do tempo, relator e comissões por onde passou |
| Comissões do deputado | `/deputados/{id}/orgaos` | 1 por deputado | "projetos na área da comissão que ele integra" |
| Frentes parlamentares | `/deputados/{id}/frentes` | 1 por deputado | perfil temático do deputado |

## Campos que já coletamos e o site ainda não usa

- `/proposicoes/{id}`: `uriPropPrincipal`, `uriPropAnterior`, `uriPropPosterior` (apensados e substitutos).
- Partido do coautor na data da assinatura: hoje usamos o partido atual e só de deputados em exercício;
  ex-deputados e trocas de partido ficam sem sigla. Exigiria histórico (`/deputados/{id}/historico`).

## Indicadores derivados (só cruzamento dos dados que já temos)

- Proporção de projetos como autor principal versus coautor, por deputado.
- Rede de coautoria: com quem cada deputado mais coassina e índice de colaboração entre partidos.
- Aprovados ou sancionados em que foi autor principal (situação em `proposicoes_detalhe.json`).
- Projetos suprapartidários (`pp` alto) versus de bancada única.
- Ranking de deputados por iniciativas próprias (principal) em vez de coautorias.

## Cobertura

- A primeira coleta de autores é limitada a 6.000 projetos por execução (`AUTORES_POR_EXECUCAO`),
  então proposições antigas ficam sem `principal` por alguns dias.
- Senado e assembleias estaduais: só o Senado já separa principal e coautor; avaliar o mesmo nível de detalhe
  (partido dos coautores, total) para senadores.
