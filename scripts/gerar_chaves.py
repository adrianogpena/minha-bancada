"""
Gera o par de chaves do aviso por e-mail do Fique informado (RSA 4096).

  - A chave PÚBLICA vai para site/chave_publica.json (pode ir para o git): o navegador de quem assina
    criptografa o e-mail com ela antes de enviar.
  - A chave PRIVADA sai na tela, uma vez só, e não é salva em lugar nenhum. Guarde como segredo
    ASSINANTES_CHAVE_PRIVADA do GitHub (assinaturas/LEIAME.md). Sem ela ninguém lê os e-mails; se perder, os
    assinantes precisam se cadastrar de novo.

Rode no seu computador, nunca em máquina compartilhada:
    python scripts/gerar_chaves.py
"""

import base64
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

SAIDA = Path(__file__).resolve().parent.parent / "site" / "chave_publica.json"


def b64url(n: int) -> str:
    return base64.urlsafe_b64encode(n.to_bytes((n.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()


def main() -> None:
    if SAIDA.exists() and "--trocar" not in sys.argv:
        sys.exit(f"{SAIDA} já existe. Trocar a chave invalida os cadastros atuais; use --trocar se for isso mesmo.")
    privada = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    pub = privada.public_key().public_numbers()
    SAIDA.write_text(json.dumps({"kty": "RSA", "alg": "RSA-OAEP-256", "n": b64url(pub.n), "e": b64url(pub.e), "ext": True,
                                 "key_ops": ["encrypt"]}), encoding="utf-8")
    pem = privada.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    print(f"Chave pública gravada em {SAIDA}.\n\nCHAVE PRIVADA (copie tudo, inclusive as linhas BEGIN/END; não será mostrada de novo):\n\n{pem}")


if __name__ == "__main__":
    main()
