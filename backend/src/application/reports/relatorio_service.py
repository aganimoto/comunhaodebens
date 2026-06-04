"""Geração de relatórios mensais em PDF via WeasyPrint.

Consolida as contribuições do mês de referência, agrupa por categoria
e por membro, e renderiza um PDF A4 pronto para impressão/envio.
"""
from __future__ import annotations

import calendar
import html
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.infrastructure.database.models import ContribuicaoModel
from src.infrastructure.sheets.sheets_client import SheetsClient

MESES_PT = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


@dataclass
class ContribuicaoResumo:
    protocolo: str
    nome: str
    categoria: str
    valor: Decimal
    data: date
    status: str
    banco: str | None
    confianca: float | None


@dataclass
class RelatorioMensal:
    ano: int
    mes: int
    total_geral: Decimal
    total_por_categoria: dict[str, Decimal]
    total_por_membro: dict[str, Decimal]
    quantidade: int
    itens: list[ContribuicaoResumo]
    gerado_em: datetime

    @property
    def mes_nome(self) -> str:
        return MESES_PT[self.mes]


def _month_range(ano: int, mes: int) -> tuple[date, date]:
    inicio = date(ano, mes, 1)
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    fim = date(ano, mes, ultimo_dia)
    return inicio, fim


class RelatorioService:
    """Orquestra a coleta dos dados, geração do PDF e registro na planilha."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    async def coletar(self, ano: int, mes: int) -> RelatorioMensal:
        inicio, fim = _month_range(ano, mes)
        stmt = (
            select(ContribuicaoModel)
            .where(ContribuicaoModel.data_pagamento >= inicio)
            .where(ContribuicaoModel.data_pagamento <= fim)
            .where(ContribuicaoModel.status == "confirmado")
            .order_by(ContribuicaoModel.data_pagamento.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()

        itens: list[ContribuicaoResumo] = []
        total_por_categoria: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        total_por_membro: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        total_geral = Decimal("0")

        for r in rows:
            valor = Decimal(str(r.valor))
            # nome/categoria vêm do Sheets historicamente; aqui usamos o que
            # foi gravado no payload; mantemos string vazia como fallback.
            nome = getattr(r, "nome_cache", "") or ""
            categoria = getattr(r, "categoria_cache", "") or "sem-categoria"
            total_geral += valor
            total_por_categoria[categoria] += valor
            if nome:
                total_por_membro[nome] += valor
            itens.append(
                ContribuicaoResumo(
                    protocolo=r.protocolo,
                    nome=nome,
                    categoria=categoria,
                    valor=valor,
                    data=r.data_pagamento,
                    status=r.status,
                    banco=r.banco,
                    confianca=float(r.confianca) if r.confianca is not None else None,
                )
            )

        tz = ZoneInfo(self._settings.app_timezone)
        return RelatorioMensal(
            ano=ano,
            mes=mes,
            total_geral=total_geral,
            total_por_categoria=dict(total_por_categoria),
            total_por_membro=dict(total_por_membro),
            quantidade=len(itens),
            itens=itens,
            gerado_em=datetime.now(tz),
        )

    def renderizar_html(self, rel: RelatorioMensal) -> str:
        return _render_template(rel)

    def renderizar_pdf(self, rel: RelatorioMensal, destino: Path) -> Path:
        html_str = self.renderizar_html(rel)
        destino.parent.mkdir(parents=True, exist_ok=True)
        # Import tardio: WeasyPrint é pesado e exige libs do sistema.
        try:
            from weasyprint import HTML

            HTML(string=html_str).write_pdf(str(destino))
        except OSError:
            if not self._settings.dev_mode:
                raise
            destino.write_bytes(
                b"%PDF-1.4\n"
                b"1 0 obj<<>>endobj\n"
                b"2 0 obj<< /Type /Catalog /Pages 3 0 R >>endobj\n"
                b"3 0 obj<< /Type /Pages /Count 0 >>endobj\n"
                b"trailer<< /Root 2 0 R >>\n%%EOF\n"
            )
        return destino

    async def gerar_e_salvar(self, ano: int, mes: int) -> Path:
        rel = await self.coletar(ano, mes)
        base = Path(self._settings.effective_relatorios_path)
        filename = f"relatorio_{ano:04d}-{mes:02d}.pdf"
        destino = base / filename
        path = self.renderizar_pdf(rel, destino)
        await self._registrar_na_planilha(rel, path)
        return path

    async def _registrar_na_planilha(self, rel: RelatorioMensal, path: Path) -> None:
        client = SheetsClient()
        if not client.available:
            return
        try:
            client.append_row(
                "Relatórios",
                [
                    f"{rel.mes:02d}/{rel.ano}",
                    str(rel.ano),
                    rel.gerado_em.isoformat(timespec="seconds"),
                    str(path),
                    "gerado",
                ],
            )
        except Exception:
            # A geração do PDF é a entrega principal; a planilha é secundária.
            return


# ---------------------------------------------------------------------------
# Template HTML
# ---------------------------------------------------------------------------

_CSS = """
@page { size: A4; margin: 20mm 18mm; }
body { font-family: 'Helvetica', 'Arial', sans-serif; color: #1f2937; font-size: 11pt; }
h1 { color: #1e4d3a; margin: 0 0 4px; font-size: 22pt; }
h2 { color: #1e4d3a; border-bottom: 1px solid #1e4d3a; padding-bottom: 4px; margin-top: 22px; }
.subtitle { color: #6b7280; font-size: 10pt; margin-bottom: 18px; }
.cards { display: flex; gap: 12px; margin-bottom: 12px; }
.card { flex: 1; background: #f1f5f4; border-left: 4px solid #1e4d3a; padding: 10px 14px; border-radius: 4px; }
.card .label { font-size: 9pt; color: #475569; text-transform: uppercase; letter-spacing: 0.04em; }
.card .value { font-size: 16pt; font-weight: 700; color: #1e4d3a; margin-top: 4px; }
table { width: 100%; border-collapse: collapse; margin-top: 8px; }
th { background: #1e4d3a; color: white; text-align: left; padding: 6px 8px; font-size: 9.5pt; }
td { padding: 5px 8px; border-bottom: 1px solid #e5e7eb; font-size: 9.5pt; }
tr:nth-child(even) td { background: #f8fafc; }
.right { text-align: right; }
.footer { margin-top: 24px; font-size: 8.5pt; color: #6b7280; text-align: center; }
.muted { color: #6b7280; }
.tag { display: inline-block; background: #ecfdf5; color: #065f46; padding: 1px 6px; border-radius: 3px; font-size: 8.5pt; }
"""


def _money(v: Decimal) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _render_template(rel: RelatorioMensal) -> str:
    linhas = "\n".join(_render_linha(i) for i in rel.itens)
    cat_rows = "\n".join(
        f"<tr><td>{html.escape(cat)}</td><td class='right'>{_money(v)}</td></tr>"
        for cat, v in sorted(rel.total_por_categoria.items(), key=lambda x: -x[1])
    )
    membro_rows = "\n".join(
        f"<tr><td>{html.escape(nome)}</td><td class='right'>{_money(v)}</td></tr>"
        for nome, v in sorted(rel.total_por_membro.items(), key=lambda x: -x[1])
    )

    return f"""<!DOCTYPE html>
<html lang='pt-BR'>
<head><meta charset='utf-8'><style>{_CSS}</style></head>
<body>
  <h1>Relatório Financeiro Mensal</h1>
  <p class='subtitle'>Comunhão de Bens Shalom — {html.escape(rel.mes_nome)} de {rel.ano}</p>

  <div class='cards'>
    <div class='card'>
      <div class='label'>Total arrecadado</div>
      <div class='value'>{_money(rel.total_geral)}</div>
    </div>
    <div class='card'>
      <div class='label'>Contribuições confirmadas</div>
      <div class='value'>{rel.quantidade}</div>
    </div>
    <div class='card'>
      <div class='label'>Categorias ativas</div>
      <div class='value'>{len(rel.total_por_categoria)}</div>
    </div>
  </div>

  <h2>Por categoria</h2>
  {("<table><thead><tr><th>Categoria</th><th class='right'>Valor</th></tr></thead><tbody>" + cat_rows + "</tbody></table>") if rel.total_por_categoria else "<p class='muted'>Sem dados no período.</p>"}

  <h2>Por membro</h2>
  {("<table><thead><tr><th>Membro</th><th class='right'>Valor</th></tr></thead><tbody>" + membro_rows + "</tbody></table>") if rel.total_por_membro else "<p class='muted'>Sem dados no período.</p>"}

  <h2>Lançamentos do mês</h2>
  {("<table><thead><tr><th>Protocolo</th><th>Data</th><th>Membro</th><th>Categoria</th><th>Banco</th><th class='right'>Valor</th></tr></thead><tbody>" + linhas + "</tbody></table>") if linhas else "<p class='muted'>Nenhuma contribuição confirmada no período.</p>"}

  <p class='footer'>Gerado em {rel.gerado_em.strftime('%d/%m/%Y às %H:%M')} — Sistema CDB Shalom</p>
</body>
</html>"""


def _render_linha(item: ContribuicaoResumo) -> str:
    return (
        "<tr>"
        f"<td><span class='tag'>{html.escape(item.protocolo)}</span></td>"
        f"<td>{item.data.strftime('%d/%m')}</td>"
        f"<td>{html.escape(item.nome) or '<span class=muted>—</span>'}</td>"
        f"<td>{html.escape(item.categoria)}</td>"
        f"<td>{html.escape(item.banco) if item.banco else '<span class=muted>—</span>'}</td>"
        f"<td class='right'>{_money(item.valor)}</td>"
        "</tr>"
    )


def iterar_meses_faltantes(ultimo_gerado: date | None) -> Iterable[tuple[int, int]]:
    """Gera tuplas (ano, mês) a gerar do mais antigo para o mais recente."""
    tz = ZoneInfo(get_settings().app_timezone)
    hoje = datetime.now(tz).date()
    if ultimo_gerado is None:
        yield (hoje.year, hoje.month)
        return
    cursor = date(ultimo_gerado.year, ultimo_gerado.month, 1)
    while cursor <= date(hoje.year, hoje.month, 1):
        yield (cursor.year, cursor.month)
        # avança um mês
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
