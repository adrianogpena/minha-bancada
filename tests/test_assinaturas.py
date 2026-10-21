import base64
import hashlib
import json
import os

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import assinaturas as a


@pytest.fixture(scope="module")
def privada():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def cifrar(privada, conteudo: dict, token=None, h=None, **linha):
    """Faz o mesmo que o navegador: AES-GCM no conteúdo e RSA-OAEP na chave AES."""
    token = token or "a" * 64
    conteudo = {"token": token, **conteudo}
    chave, iv = os.urandom(32), os.urandom(12)
    c = AESGCM(chave).encrypt(iv, json.dumps(conteudo).encode(), None)
    k = privada.public_key().encrypt(chave, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return {"k": base64.b64encode(k).decode(), "iv": base64.b64encode(iv).decode(), "c": base64.b64encode(c).decode(),
            "h": h or hashlib.sha256(token.encode()).hexdigest(), **linha}


def test_decifrar_ok(privada):
    linha = cifrar(privada, {"email": "a@b.co", "locais": ["BR", "UF:SP"], "politicos": ["dep:12"], "rotulos": ["Brasil"]},
                   criado="2026-01-01", confirmado=True)
    d = a.decifrar(linha, privada)
    assert d["email"] == "a@b.co"
    assert d["regras"] == {"BR", "UF:SP", "dep:12"}
    assert d["confirmado"] and not d["enviada"]
    assert d["rotulos"] == ["Brasil"]


def test_decifrar_filtra_regras_invalidas(privada):
    linha = cifrar(privada, {"email": "a@b.co", "locais": ["BR", "XX", "UF:sp", "<script>"], "politicos": ["dep:abc", "pres"]})
    assert a.decifrar(linha, privada)["regras"] == {"BR", "pres"}


def test_decifrar_limita_quantidade(privada):
    linha = cifrar(privada, {"email": "a@b.co", "locais": ["BR"], "politicos": [f"dep:{i}" for i in range(100)]})
    assert len(a.decifrar(linha, privada)["regras"]) == 61  # 60 políticos + BR


@pytest.mark.parametrize("conteudo", [
    {"email": "sem-arroba", "locais": ["BR"]},
    {"email": "a@b.co", "locais": [], "politicos": []},
    {"email": "a" * 130 + "@b.co", "locais": ["BR"]},
])
def test_decifrar_rejeita_conteudo_invalido(privada, conteudo):
    assert a.decifrar(cifrar(privada, conteudo), privada) is None


def test_decifrar_rejeita_hash_que_nao_confere(privada):
    linha = cifrar(privada, {"email": "a@b.co", "locais": ["BR"]}, h="0" * 64)
    assert a.decifrar(linha, privada) is None


def test_decifrar_rejeita_token_malformado(privada):
    linha = cifrar(privada, {"email": "a@b.co", "locais": ["BR"]}, token="curto")
    assert a.decifrar(linha, privada) is None


def test_decifrar_rejeita_lixo_e_chave_errada(privada):
    assert a.decifrar({"k": "x", "iv": "y", "c": "z", "h": "h"}, privada) is None
    assert a.decifrar({}, privada) is None
    outra = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    linha = cifrar(privada, {"email": "a@b.co", "locais": ["BR"]})
    assert a.decifrar(linha, outra) is None


def linha(privada, email, token_char, criado, confirmado=False, enviada=False):
    token = token_char * 64
    return cifrar(privada, {"email": email, "locais": ["BR"]}, token=token, criado=criado, confirmado=confirmado, enviada=enviada)


def test_organizar_confirmada_mais_nova_vale_e_antigas_sao_apagadas(privada):
    velha = linha(privada, "a@b.co", "1", "2026-01-01", confirmado=True)
    nova = linha(privada, "A@b.co", "2", "2026-02-01", confirmado=True)  # e-mail sem distinção de caixa
    ativos, pendentes, apagar = a.organizar([velha, nova], privada)
    assert [x["h"] for x in ativos] == [nova["h"]]
    assert pendentes == []
    assert apagar == [velha["h"]]


def test_organizar_pendente_mais_nova_que_a_confirmada_fica_a_confirmar(privada):
    conf = linha(privada, "a@b.co", "1", "2026-01-01", confirmado=True)
    pend = linha(privada, "a@b.co", "2", "2026-02-01")
    ativos, pendentes, apagar = a.organizar([conf, pend], privada)
    assert len(ativos) == 1 and len(pendentes) == 1 and apagar == []


def test_organizar_pendente_mais_velha_e_descartada(privada):
    conf = linha(privada, "a@b.co", "1", "2026-02-01", confirmado=True)
    pend = linha(privada, "a@b.co", "2", "2026-01-01")
    ativos, pendentes, apagar = a.organizar([conf, pend], privada)
    assert pendentes == [] and apagar == [pend["h"]]


def test_organizar_pendente_ja_enviada_nao_reenvia(privada):
    pend = linha(privada, "a@b.co", "1", "2026-01-01", enviada=True)
    ativos, pendentes, apagar = a.organizar([pend], privada)
    assert ativos == [] and pendentes == [] and apagar == []


def test_organizar_ilegivel_vai_para_apagar(privada):
    ruim = {"k": "", "iv": "", "c": "", "h": "hash-ruim"}
    assert a.organizar([ruim], privada) == ([], [], ["hash-ruim"])


def test_link(monkeypatch):
    monkeypatch.setenv("ASSINANTES_URL", "https://script.example/exec")
    assert a.link("cancelar", "tok") == "https://script.example/exec?acao=cancelar&t=tok"
    monkeypatch.setenv("ASSINANTES_URL", "https://script.example/exec?x=1")
    assert a.link("confirmar", "tok") == "https://script.example/exec?x=1&acao=confirmar&t=tok"


def test_rodape_e_confirmacao_escapam_rotulos(monkeypatch):
    monkeypatch.setenv("ASSINANTES_URL", "https://script.example/exec")
    ass = {"token": "t" * 64, "rotulos": ["<img src=x>", "Estado: SP"]}
    h, t = a.rodape(ass)
    assert "<img" not in h and "&lt;img" in h
    assert "Cancelar o aviso: https://script.example/exec?acao=cancelar" in t
    h2, t2 = a.confirmacao(ass)
    assert "<img" not in h2
    assert "acao=confirmar" in h2 and "acao=confirmar" in t2
    assert "- Estado: SP" in t2


def test_main_sem_segredos_nao_faz_nada(monkeypatch, capsys):
    monkeypatch.delenv("ASSINANTES_CHAVE_PRIVADA", raising=False)
    monkeypatch.delenv("ASSINANTES_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["assinaturas.py"])
    a.main()
    assert "pulando" in capsys.readouterr().out
