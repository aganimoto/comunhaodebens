"""Testes para o parser de resposta da IA."""
from datetime import time

from src.infrastructure.ai.response_parser import parse_dados_comprovante


def test_parse_json_limpo():
    raw = '{"valor": 150.00, "data": "2026-06-02", "hora": "14:32", "banco": "Nubank", "confianca": 0.92}'
    dados = parse_dados_comprovante(raw)
    assert dados is not None
    assert float(dados.valor) == 150.0
    assert dados.confianca == 0.92
    assert dados.hora == time(14, 32)
    assert dados.banco == "Nubank"


def test_parse_json_em_markdown():
    raw = '```json\n{"valor": 10, "data": "2026-01-01", "hora": null, "banco": null, "confianca": 0.5}\n```'
    dados = parse_dados_comprovante(raw)
    assert dados is not None
    assert dados.confianca == 0.5
    assert dados.hora is None


def test_parse_invalido():
    assert parse_dados_comprovante("sem json") is None


def test_parse_valor_invalido():
    raw = '{"valor": -1, "data": "2026-01-01", "confianca": 0.5}'
    assert parse_dados_comprovante(raw) is None


def test_parse_confianca_invalida():
    raw = '{"valor": 1, "data": "2026-01-01", "confianca": 1.5}'
    assert parse_dados_comprovante(raw) is None
