# Capitais sem dados dos projetos do prefeito

Situação em 2026-10. Das 26 capitais (Brasília não tem prefeito), 6 têm dados: São Paulo (SPLegis), Salvador e Goiânia (consulta própria) e Rio Branco, Boa Vista, Natal e João Pessoa (SAPL). As outras 20 não têm.

## Verificadas e sem fonte estruturada
Sem SAPL nem API aberta localizada.
- Belém
- Maceió
- Teresina
- Macapá
- Cuiabá
- Florianópolis
- Curitiba
- Vitória

## Com SAPL, mas sem dados utilizáveis
- Recife: o SAPL (`sapl.recife.pe.leg.br`) estava em manutenção (503).
- Porto Velho e Fortaleza: o SAPL não registra o autor nas matérias do Executivo.
- Manaus e Palmas: sem dados atuais.

## Site da Câmara inalcançável na verificação
- Rio de Janeiro
- Belo Horizonte
- Porto Alegre

## Sem host SAPL achado
Não investigadas a fundo.
- São Luís
- Campo Grande
- Aracaju

## Próximos passos
- Recife é a única que pode entrar só com uma linha em `CAMARAS` (`scripts/coletar_prefeituras.py`), se o SAPL voltar.
- As demais precisam de um coletor próprio, como o de São Paulo, ou de uma fonte ainda não achada.
