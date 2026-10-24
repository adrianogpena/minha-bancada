# Aviso por e-mail do Fique informado (e-mail criptografado)

O RSS (`scripts/feeds.py`) não precisa de nada disto. Este é o canal opcional por e-mail, desenhado para que ninguém consiga ler os endereços sem a chave privada.

```
navegador  --cifra (AES-256-GCM + RSA-OAEP 4096)-->  Apps Script / planilha  --só texto cifrado-->  GitHub Actions (chave privada)  --> e-mail
```

- O navegador cifra `{e-mail, escolhas, token}` com a chave **pública** (`site/chave_publica.json`). O site e a planilha nunca veem o endereço.
- A planilha acha cada linha pelo SHA-256 do token, que só existe no e-mail do assinante (confirmação e cancelamento).
- A chave **privada** fica só como segredo do GitHub. `scripts/assinaturas.py` decifra na memória, envia e não imprime endereços no log.
- Cadastro não confirmado some em 7 dias. A confirmação sai em até 15 minutos (`.github/workflows/confirmacoes.yml`); o aviso das mudanças sai no envio diário.

## Limite honesto

Quem controla o repositório controla o workflow que tem a chave; tecnicamente poderia alterá-lo para ler os endereços. A criptografia protege contra vazamento da planilha, da conta do Google, do repositório e de terceiros, não contra o administrador. Para anonimato total, o canal é o RSS. Reduza o risco assim:
- guarde a chave privada como segredo do **Environment `github-pages`** (Settings > Environments) e deixe a regra "Deployment branches" só em `master`: workflows de outras branches não a recebem;
- ative proteção de branch em `master` (revisão obrigatória, se houver mais de um mantenedor).

## Configurar

1. **Chaves** (no seu computador): `python scripts/gerar_chaves.py`. Faça commit de `site/chave_publica.json`. Copie a chave privada que sai na tela (aparece uma vez; não é salva).
2. **Planilha e script**: crie uma planilha no Google Sheets, abra **Extensões > Apps Script**, cole `assinaturas/apps_script.gs`. Em **Configurações do projeto > Propriedades do script**, crie `CHAVE` com uma senha longa. **Implantar > Nova implantação > App da Web**: executar como você, acesso qualquer pessoa. Copie a URL `/exec`.
3. **Segredos do GitHub** (além dos `SMTP_*` já usados): `ASSINANTES_URL` (URL `/exec`), `ASSINANTES_CHAVE` (o valor de `CHAVE`) e `ASSINANTES_CHAVE_PRIVADA` (a chave privada inteira, com as linhas BEGIN/END).
4. **Site**: preencha `URL_ASSINATURAS` (a mesma URL `/exec`) em `site/assets/app.js`. Com a constante vazia ou sem `site/chave_publica.json`, a seção de e-mail não aparece.

Perder a chave privada ou trocá-la (`--trocar`) invalida os cadastros: as pessoas precisam assinar de novo.

## Testar sem enviar

```
export ASSINANTES_URL=https://exemplo/exec ASSINANTES_CHAVE_PRIVADA="$(cat privada.pem)"
python scripts/assinaturas.py HEAD~1 HEAD --arquivo linhas.json --saida /tmp/avisos
```
(`linhas.json`: lista de `{h, k, iv, c, criado, confirmado, enviada}` como o Apps Script devolve; sem `--enviar` nada sai. A pasta de saída contém os endereços em claro: apague depois.)
