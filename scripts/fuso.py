"""Fuso das datas e horas das fontes: a Câmara, o Senado e as Assembleias publicam hora de Brasília, quase sempre sem offset.
Quem converte ou corta data e hora usa este módulo, nunca um offset fixo (Brasília teve horário de verão até 2019)."""
from datetime import datetime
from zoneinfo import ZoneInfo

BRASILIA = ZoneInfo("America/Sao_Paulo")


def instante(texto) -> datetime | None:
    """Data e hora da fonte como instante em Brasília: texto sem offset é hora de Brasília; com offset ou `Z` é convertido."""
    if not texto:
        return None
    try:
        d = datetime.fromisoformat(str(texto).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.replace(tzinfo=BRASILIA) if d.tzinfo is None else d.astimezone(BRASILIA)


def iso(texto) -> str | None:
    """ISO com o offset de Brasília daquele dia (`2026-10-21T15:00:00-03:00`); o site mostra no fuso de quem abre."""
    d = instante(texto)
    return d.isoformat(timespec="seconds") if d else None


def dia(texto) -> str | None:
    """AAAA-MM-DD do dia em Brasília."""
    d = instante(texto)
    return d.date().isoformat() if d else None
