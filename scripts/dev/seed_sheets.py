#!/usr/bin/env python3
"""Cria abas e linhas iniciais na planilha Google Sheets (rodar dentro do container backend)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from src.infrastructure.sheets.seed import seed_spreadsheet  # noqa: E402

if __name__ == "__main__":
    seed_spreadsheet()
    print("Planilha inicializada.")
