"""Task que combina OCR + IA para extrair dados do comprovante."""
import asyncio
from decimal import Decimal

from src.application.use_cases.registrar_contribuicao import RegistrarContribuicaoUseCase
from src.config import get_settings
from src.domain.entities.contribuicao import StatusContribuicao
from src.domain.entities.pendencia import MotivoPendencia
from src.infrastructure.database.connection import async_session_factory
from src.infrastructure.database.models import PendenciaModel
from src.infrastructure.ocr.paddle_ocr_service import PaddleOCRService
from src.infrastructure.sheets.config_reader import ConfigReader
from src.infrastructure.sheets.sheets_writer import SheetsWriter
from src.tasks.celery_app import celery_app
import uuid


def _criar_ai():
    """Factory que devolve o serviço de IA (Ollama real)."""
    from src.infrastructure.ai.ollama_service import OllamaService

    return OllamaService()


@celery_app.task(name="processar_ocr_e_ia")
def processar_ocr_e_ia(
    telefone: str,
    membro_nome: str,
    membro_categoria: str,
    caminho_arquivo: str,
    hash_sha256: str,
) -> dict:
    return asyncio.run(
        _async_processar(
            telefone, membro_nome, membro_categoria, caminho_arquivo, hash_sha256
        )
    )


async def _async_processar(
    telefone: str,
    membro_nome: str,
    membro_categoria: str,
    caminho_arquivo: str,
    hash_sha256: str,
) -> dict:
    ocr = PaddleOCRService()
    resultado = ocr.processar(caminho_arquivo)
    ai = _criar_ai()
    dados = await ai.extrair_de_imagem(caminho_arquivo, resultado.texto_bruto)
    if dados is None:
        dados = await ai.extrair_de_texto(resultado.texto_bruto)

    config = ConfigReader()
    limiar = await config.get_float("LIMIAR_CONFIANCA", get_settings().limiar_confianca)

    async with async_session_factory() as session:
        if dados is None:
            session.add(
                PendenciaModel(
                    id=uuid.uuid4(),
                    telefone=telefone,
                    motivo=MotivoPendencia.ERRO_PROCESSAMENTO.value,
                )
            )
            SheetsWriter().append_pendencia(
                uuid.uuid4(), telefone, membro_nome, MotivoPendencia.ERRO_PROCESSAMENTO.value
            )
            await session.commit()
            return {"status": "erro"}

        # Adapta para o shape esperado pelo registrar_contribuicao
        from datetime import date as _date, time as _time
        from src.infrastructure.ai.response_parser import DadosComprovante

        valor = Decimal(str(getattr(dados, "valor")))
        data = getattr(dados, "data")
        if isinstance(data, str):
            data = _date.fromisoformat(data)
        hora = getattr(dados, "hora", None)
        if isinstance(hora, str) and hora:
            parts = hora.split(":")
            hora = _time(int(parts[0]), int(parts[1]))
        banco = getattr(dados, "banco", None)
        confianca = float(getattr(dados, "confianca", 0))

        parsed = DadosComprovante(
            valor=valor,
            data=data,
            hora=hora,
            banco=banco,
            confianca=confianca,
        )

        status = (
            StatusContribuicao.CONFIRMADO
            if parsed.confianca >= limiar
            else StatusContribuicao.REVISAO
        )

        uc = RegistrarContribuicaoUseCase(session)
        contrib = await uc.executar(
            telefone=telefone,
            membro_nome=membro_nome,
            membro_categoria=membro_categoria,
            valor=parsed.valor,
            data_pagamento=parsed.data,
            hora_pagamento=parsed.hora,
            banco=parsed.banco,
            confianca=parsed.confianca,
            hash_sha256=hash_sha256,
            status=status,
        )

        if status == StatusContribuicao.REVISAO:
            session.add(
                PendenciaModel(
                    id=uuid.uuid4(),
                    telefone=telefone,
                    contribuicao_id=contrib.id,
                    motivo=MotivoPendencia.IA_BAIXA_CONFIANCA.value,
                )
            )
        await session.commit()
        return {"status": status.value, "protocolo": contrib.protocolo}
