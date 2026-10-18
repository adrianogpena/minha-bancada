# Capitais sem dados dos projetos do prefeito

Situação em 2026-10. Das 26 capitais (Brasília não tem prefeito), 6 têm dados: São Paulo (SPLegis), Salvador e Goiânia (consulta própria de cada Câmara) e Rio Branco, Boa Vista, Natal e João Pessoa (SAPL). As outras 20 não têm.

## Avaliadas para coletor próprio e puladas (2026-10)
- Curitiba: a consulta de proposições (SPL II) exige CAPTCHA no login; não há outra listagem pública.
- Campo Grande e Florianópolis: o site da Câmara responde só com um desafio reCAPTCHA (`/.lsrecap/recaptcha`), sem acesso por script.
- Cuiabá: o site responde "Request Rejected" (firewall) ao script e ao Firefox automatizado.
- São Luís e Vitória: o site responde 403 (Vitória, desafio Cloudflare) ao script e ao Firefox automatizado.
- Teresina: o acompanhamento de processos (`protocolo.cmteresina.pi.gov.br`) pede número do processo e senha; o portal da transparência (`transparencia.teresina.pi.leg.br`) está fora do ar (404).
- Belém: o site tem listagens com exportação JSON, mas as de projetos de lei do Executivo, leis complementares do Executivo e emendas à Lei Orgânica vêm vazias ou sem autor; só há projetos de vereadores.
- Maceió: a pesquisa de projetos de lei (`maceio.al.leg.br/projetos-lei`) lista "PREFEITURA MUNICIPAL DE MACEIÓ" como autor, mas a ementa é só o cabeçalho da mensagem, não há situação nem link por projeto, e só aparecem projetos de lei (12 em 2025 e 27 em 2026, com numeração de mensagens que sugere lista incompleta). Sem confiança para publicar.
- Macapá: o site (`macapa.ap.leg.br`) é um aplicativo que não mostrou nenhuma API de proposições.
- Aracaju: o SAPL antigo (`190.15.122.10:8080/sapl`, só HTTP) responde 503 na pesquisa de matérias.

## Site da Câmara inalcançável da rede onde se testou (sem resposta, também pelo Firefox)
- Rio de Janeiro (`camara.rio`)
- Belo Horizonte (`cmbh.mg.gov.br`)
- Porto Alegre (`camarapoa.rs.gov.br`)

## Com SAPL, mas sem dados utilizáveis
- Recife: o SAPL (`sapl.recife.pe.leg.br`) continua em manutenção (503, testado em 2026-10-18); se voltar, basta uma linha em `CAMARAS`.
- Porto Velho e Fortaleza: o SAPL não registra o autor nas matérias do Executivo.
- Manaus e Palmas: sem dados atuais.
