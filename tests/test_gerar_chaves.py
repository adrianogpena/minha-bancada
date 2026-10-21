import base64
import json

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import gerar_chaves as g


def test_b64url_roundtrip():
    n = 65537
    bruto = g.b64url(n)
    assert "=" not in bruto and "+" not in bruto and "/" not in bruto
    assert int.from_bytes(base64.urlsafe_b64decode(bruto + "=" * (-len(bruto) % 4)), "big") == n


def test_gera_chaves_compatíveis(tmp_path, monkeypatch, capsys):
    destino = tmp_path / "chave_publica.json"
    monkeypatch.setattr(g, "SAIDA", destino)
    monkeypatch.setattr("sys.argv", ["gerar_chaves.py"])
    real = rsa.generate_private_key
    monkeypatch.setattr(g.rsa, "generate_private_key", lambda public_exponent, key_size: real(public_exponent=public_exponent, key_size=2048))
    g.main()
    jwk = json.loads(destino.read_text())
    assert jwk["kty"] == "RSA" and jwk["alg"] == "RSA-OAEP-256" and jwk["key_ops"] == ["encrypt"]
    saida = capsys.readouterr().out
    pem = saida[saida.index("-----BEGIN"):saida.index("-----END PRIVATE KEY-----") + len("-----END PRIVATE KEY-----")]
    privada = serialization.load_pem_private_key(pem.encode(), password=None)
    dec = lambda v: int.from_bytes(base64.urlsafe_b64decode(v + "=" * (-len(v) % 4)), "big")
    pub = rsa.RSAPublicNumbers(dec(jwk["e"]), dec(jwk["n"])).public_key()
    msg = pub.encrypt(b"segredo", padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    assert privada.decrypt(msg, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)) == b"segredo"


def test_nao_sobrescreve_sem_trocar(tmp_path, monkeypatch):
    destino = tmp_path / "chave_publica.json"
    destino.write_text("{}")
    monkeypatch.setattr(g, "SAIDA", destino)
    monkeypatch.setattr("sys.argv", ["gerar_chaves.py"])
    with pytest.raises(SystemExit):
        g.main()
    assert destino.read_text() == "{}"
