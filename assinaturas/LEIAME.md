# Fique informado: como ligar

A página `site/informado.html` deixa a pessoa escolher o que acompanhar e digitar o e-mail. Como o site é estático, o cadastro fica numa planilha do Google privada, atendida por um script (`apps_script.gs`). Tudo gratuito. A lista de e-mails **nunca** vai para o repositório.

## 1. Planilha e script (uns 5 minutos)

1. Crie uma planilha no Google Sheets (nome livre). Em **Extensões > Apps Script**, apague o conteúdo e cole `assinaturas/apps_script.gs`.
2. Em **Configurações do projeto > Propriedades do script**, adicione `CHAVE` com uma senha longa (a mesma irá para o GitHub no passo 2).
3. **Implantar > Nova implantação > App da Web**: executar como **você**, acesso **qualquer pessoa**. Autorize e copie a URL terminada em `/exec`.
4. Teste: abra `URL?acao=lista&chave=SUA_CHAVE`. Deve mostrar `[]`.

Limite do Google: ~100 e-mails de confirmação por dia (conta gratuita). Os avisos diários saem pelo SMTP do GitHub Actions, sem esse limite.

## 2. Segredos no GitHub

Em **Settings > Secrets and variables > Actions**, além dos `SMTP_*` que o resumo diário já usa:

| Segredo | Valor |
|---|---|
| `ASSINANTES_URL` | a URL `/exec` do passo 1 |
| `ASSINANTES_CHAVE` | o valor de `CHAVE` |

## 3. Site

Em `site/assets/app.js`, preencha `URL_ASSINATURAS` com a mesma URL `/exec` (ela não é secreta; sem a chave só aceita cadastros). Enquanto estiver vazia, a página mostra "em breve".

## Como funciona

- Quem assina recebe um e-mail de confirmação (evita cadastrar terceiros). Só depois de clicar no link a escolha vale; refazer o cadastro com o mesmo e-mail troca a escolha, também após confirmar.
- Todo dia, depois da coleta agendada, `scripts/assinaturas.py` baixa a lista, filtra o que mudou por assinante e envia. Quem não tem novidade não recebe nada. Execuções por push ou manuais não enviam.
- Cada e-mail tem o link para cancelar.
- Testar sem enviar: `python scripts/assinaturas.py HEAD~1 HEAD --arquivo assinantes.json --saida /tmp/avisos` (formato da lista no topo do script).
