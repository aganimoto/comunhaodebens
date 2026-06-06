"""Script para testar OCR + IA com imagens de comprovantes.

Uso:
    cd backend
    python ../test_ocr/test_ocr.py

Coloque imagens em:
    test_ocr/samples/comprovantes/     — comprovantes PIX/TED reais
    test_ocr/samples/nao_comprovantes/ — fotos aleatórias (selfies, paisagens, etc.)
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Força UTF-8 no terminal Windows
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# Adiciona o diretório backend ao path para importar os módulos
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from src.infrastructure.ocr.paddle_ocr_service import PaddleOCRService
from src.infrastructure.ocr.tesseract_ocr_service import TesseractOCRService
from src.infrastructure.ai.ollama_service import OllamaService, SYSTEM_PROMPT
from src.infrastructure.ai.response_parser import parse_dados_comprovante


async def testar_arquivo(caminho: Path, engine: str) -> dict:
    """Testa OCR + IA em um único arquivo."""
    print(f"\n{'='*60}")
    print(f"[ARQUIVO] {caminho.name}")
    print(f"  Engine: {engine}")

    # 1) OCR
    if engine == "tesseract":
        ocr = TesseractOCRService()
    else:
        ocr = PaddleOCRService()

    try:
        resultado_ocr = ocr.processar(str(caminho))
    except Exception as e:
        return {"arquivo": caminho.name, "status": "erro_ocr", "erro": str(e)}

    texto_ocr = resultado_ocr.texto_bruto.strip() if resultado_ocr.texto_bruto else ""
    if texto_ocr:
        print(f"  [OCR] ({len(texto_ocr)} chars): {texto_ocr[:200]}...")
    else:
        print("  [OCR] (vazio) -> tentando IA multimodal direto na imagem")

    # 2) IA — tenta primeiro multimodal (imagem + OCR)
    ai = OllamaService()
    dados = await ai.extrair_de_imagem(str(caminho), texto_ocr)
    engine_usada = "multimodal"

    # Se multimodal falhou, tenta só texto (apenas se tiver OCR)
    if dados is None and texto_ocr:
        dados = await ai.extrair_de_texto(texto_ocr)
        engine_usada = "texto"

    if dados is None:
        return {
            "arquivo": caminho.name,
            "status": "nao_comprovante",
            "engine": engine_usada,
            "texto_ocr": texto_ocr[:200] if texto_ocr else "(vazio)",
        }

    # 3) Resultado
    return {
        "arquivo": caminho.name,
        "status": "comprovante",
        "engine": engine_usada,
        "valor": float(dados.valor),
        "data_pix": dados.data_pix,
        "favorecido": dados.favorecido,
        "tipo_documento": dados.tipo_documento,
        "confidence": dados.confidence,
        "texto_ocr": resultado_ocr.texto_bruto[:200],
    }


async def main():
    base = Path(__file__).resolve().parent
    samples_dir = base / "samples"
    engines = ["paddle", "tesseract"]

    if not samples_dir.exists():
        print(f"Criando diretório {samples_dir}...")
        (samples_dir / "comprovantes").mkdir(parents=True, exist_ok=True)
        (samples_dir / "nao_comprovantes").mkdir(parents=True, exist_ok=True)
        (samples_dir / "comprovantes" / ".gitkeep").write_text("")
        (samples_dir / "nao_comprovantes" / ".gitkeep").write_text("")
        print(f"\n⚠️  Diretórios criados em {samples_dir}")
        print("Coloque imagens (jpg/png) nas pastas e execute novamente.\n")
        return

    # Coletar arquivos
    arquivos = []
    for pasta in ["comprovantes", "nao_comprovantes"]:
        p = samples_dir / pasta
        if p.exists():
            for f in sorted(p.iterdir()):
                if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".pdf"):
                    arquivos.append((f, pasta))

    if not arquivos:
        print(f"\n⚠️  Nenhuma imagem encontrada em {samples_dir}/")
        print("Coloque imagens (jpg/png) nas pastas comprovantes/ e nao_comprovantes/\n")
        return

    print(f"\n[TESTE] {len(arquivos)} arquivo(s) com {len(engines)} engine(s)...\n")

    resultados = []
    for caminho, categoria in arquivos:
        for engine in engines:
            try:
                r = await testar_arquivo(caminho, engine)
                r["categoria"] = categoria
                r["engine"] = engine
                resultados.append(r)
            except Exception as e:
                resultados.append({
                    "arquivo": caminho.name,
                    "categoria": categoria,
                    "engine": engine,
                    "status": "erro",
                    "erro": str(e),
                })

    # Exibir resumo
    print(f"\n{'='*60}")
    print("RESUMO DOS TESTES")
    print(f"{'='*60}")
    acertos = 0
    total = len(resultados)
    for r in resultados:
        esperado = r["categoria"] == "comprovantes"
        obtido = r["status"] == "comprovante"
        acertou = esperado == obtido
        if acertou:
            acertos += 1

        status_icone = "[OK]" if acertou else "[ERRO]"
        print(f"\n{status_icone} {r['arquivo']} ({r['engine']})")
        print(f"  Esperado: {'comprovante' if esperado else 'nao comprovante'}")
        print(f"  Obtido:   {r['status']}")
        if r["status"] == "comprovante":
            print(f"  Valor:     R$ {r['valor']:.2f}")
            print(f"  Data:      {r['data_pix']}")
            print(f"  Favorecido: {r['favorecido']}")
            print(f"  Tipo:      {r['tipo_documento']}")
            print(f"  Confianca: {r['confidence']:.0%}")

    print(f"\n{'='*60}")
    print(f"ACERTOS: {acertos}/{total} ({acertos/total*100:.0f}%)")
    print(f"{'='*60}")

    # Salvar resultados em JSON
    relatorio = base / "resultados_teste.json"
    relatorio.write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nResultados salvos em: {relatorio}")


if __name__ == "__main__":
    asyncio.run(main())