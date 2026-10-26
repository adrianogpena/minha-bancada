import fuso


def test_hora_sem_offset_e_de_brasilia():
    assert fuso.iso("2026-10-21T15:00:00") == "2026-10-21T15:00:00-03:00"
    assert fuso.dia("2026-10-21T23:30") == "2026-10-21"


def test_offset_utc_e_convertido_para_brasilia():
    assert fuso.iso("2026-10-21T01:00:00+00:00") == "2026-10-20T22:00:00-03:00"
    assert fuso.dia("2026-10-21T01:00:00Z") == "2026-10-20"


def test_usa_o_horario_de_verao_da_epoca():
    assert fuso.iso("2018-12-01T12:00:00") == "2018-12-01T12:00:00-02:00"


def test_vazio_ou_invalido_vira_none():
    assert fuso.iso("") is None and fuso.dia(None) is None and fuso.iso("lixo") is None
