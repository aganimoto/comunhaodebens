# Testes de OCR + IA

## Como usar

1. Coloque imagens (jpg/png) ou PDFs de comprovantes em `test_ocr/samples/comprovantes/`
2. Coloque imagens que NÃO são comprovantes em `test_ocr/samples/nao_comprovantes/`
3. Execute o teste:

```bash
cd backend && python ../test_ocr/test_ocr.py
```

## O que o teste faz

Para cada arquivo na pasta `samples/`:
1. Executa OCR (PaddleOCR ou Tesseract)
2. Envia o texto para a IA (Ollama) extrair os dados
3. Exibe o resultado: se foi classificado como comprovante, os dados extraídos, confiança

## Estrutura

```
test_ocr/
├── README.md              ← este arquivo
├── test_ocr.py            ← script de teste
└── samples/
    ├── comprovantes/      ← coloque comprovantes PIX/TED reais aqui
    │   └── .gitkeep
    └── nao_comprovantes/  ← coloque fotos aleatórias aqui
        └── .gitkeep