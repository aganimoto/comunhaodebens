"""Testes para os value objects do domínio."""
from datetime import date
from decimal import Decimal

import pytest

from src.domain.value_objects.confianca import Confianca
from src.domain.value_objects.dinheiro import Dinheiro
from src.domain.value_objects.protocolo import Protocolo
from src.domain.value_objects.telefone import Telefone


def test_telefone_normaliza_br():
    t = Telefone("11999999999")
    assert t.valor.startswith("55")
    assert t.e164.startswith("+")


def test_telefone_invalido():
    with pytest.raises(ValueError):
        Telefone("abc")


def test_telefone_curto():
    with pytest.raises(ValueError):
        Telefone("123")


def test_protocolo_formato():
    p = Protocolo.gerar(date(2026, 6, 2), 154)
    assert str(p) == "CDB-20260602-000154"


def test_protocolo_invalido():
    with pytest.raises(ValueError):
        Protocolo("INVALID")


def test_dinheiro_centavos():
    d = Dinheiro(Decimal("150.50"))
    assert d.centavos == 15050


def test_dinheiro_quantiza():
    d = Dinheiro(Decimal("150.507"))
    assert d.valor == Decimal("150.51")


def test_dinheiro_zero_invalido():
    with pytest.raises(ValueError):
        Dinheiro(Decimal("0"))


def test_dinheiro_negativo_invalido():
    with pytest.raises(ValueError):
        Dinheiro(Decimal("-10"))


def test_confianca_limiar():
    c = Confianca(0.85)
    assert c.atende_limiar(0.80)
    assert not Confianca(0.5).atende_limiar(0.80)


def test_confianca_invalida():
    with pytest.raises(ValueError):
        Confianca(1.5)
    with pytest.raises(ValueError):
        Confianca(-0.1)
