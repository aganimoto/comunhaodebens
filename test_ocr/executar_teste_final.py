"""
Executor do teste OCR final - processa incrementalmente salvando cada resultado.
Nao precisa reiniciar o EasyOCR a cada execucao.
"""
import sys, os, json, re, time, pickle
from pathlib import Path

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

CACHE_FILE = Path(__file__).resolve().parent / ".reader_cache.pkl"

def get_reader():
    """Inicializa EasyOCR reader e faz pickle para cache."""
    import easyocr
    print("[EASYOCR] Inicializando reader (pt + en)...", flush=True)
    reader = easyocr.Reader(["pt", "en"], gpu=False, verbose=False)
    print("[EASYOCR] Reader pronto!", flush=True)
    # Salvar em pickle para reuso
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(reader, f)
    return reader

def processar_imagem(caminho: Path) -> dict:
    from PIL import Image, ImageFilter, ImageEnhance
    import numpy as np
    import easyocr
    
    # Tentar carregar reader do cache
    reader = None
    if CACHE_FILE.exists():
        try:
            reader = pickle.load(open(CACHE_FILE, "rb"))
            print(f"  Reader carregado do cache", flush=True)
        except:
            pass
    
    if reader is None:
        reader = get_reader()
    
    pil_img = Image.open(caminho)
    w, h = pil_img.size
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    
    enhancer = ImageEnhance.Contrast(pil_img)
    pil_img = enhancer.enhance(1.3)
    pil_img = pil_img.filter(ImageFilter.SHARPEN)
    img_array = np.array(pil_img)
    
    start = time.time()
    results = reader.readtext(img_array, detail=1, paragraph=False)
    elapsed = time.time() - start
    
    textos, confs, blocos = [], [], []
    for item in results:
        if len(item) == 3:
            bbox, texto, conf = item
            texto = texto.strip()
            if texto:
                textos.append(texto)
                confs.append(float(conf))
                blocos.append({"texto": texto, "conf": round(float(conf), 4)})
    
    texto_completo = " ".join(textos)
    
    valores = []
    for padrao in [r'R\$\s*(\d+(?:,\d{2})?)', r'R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)']:
        for match in re.findall(padrao, texto_completo):
            try:
                v = float(match.replace(".", "").replace(",", "."))
                if 0 < v < 1000000:
                    valores.append(v)
            except:
                pass
    
    datas = sorted(set(re.findall(r"(\d{2}/\d{2}/\d{4})", texto_completo)))
    
    keywords = {"pix", "ted", "valor", "comprovante", "transferencia", "pago", "receb", "remetente", "favorecido", "cpf/cnpj", "instituicao", "conta", "agencia"}
    encontradas = [kw.upper() for kw in keywords if kw in texto_completo.lower()]
    
    return {
        "sucesso": True,
        "arquivo": caminho.name,
        "dimensoes": f"{w}x{h}",
        "tamanho_bytes": caminho.stat().st_size,
        "num_blocos": len(textos),
        "confianca_media": round(sum(confs)/len(confs), 4) if confs else 0,
        "tempo_segundos": round(elapsed, 2),
        "texto": texto_completo,
        "valores": sorted(set(valores)),
        "valor_principal": sorted(set(valores))[0] if valores else None,
        "datas": datas,
        "palavras_chave": encontradas,
        "eh_comprovante": len(encontradas) >= 2,
        "blocos_altos": [b for b in blocos if b["conf"] > 0.8][:8]
    }


def main():
    base = Path(__file__).resolve().parent
    samples_dir = base / "samples" / "comprovantes"
    
    imagens = []
    for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp"]:
        imagens.extend(samples_dir.glob(ext))
    imagens = sorted(imagens)
    
    if not imagens:
        print("Nenhuma imagem encontrada!", flush=True)
        return
    
    # Carregar resultados parciais se existirem
    output = base / "resultado_final_otimizado.json"
    resultados = []
    if output.exists():
        try:
            with open(output, "r", encoding="utf-8") as f:
                resultados = json.load(f)
            ja_processados = {r["arquivo"] for r in resultados}
            print(f"Retomando execucao - {len(resultados)} ja processados", flush=True)
        except:
            ja_processados = set()
    else:
        ja_processados = set()
    
    print("=" * 70, flush=True)
    print(f"TESTE OCR FINAL - {len(imagens)} imagens | EasyOCR + Pillow", flush=True)
    print(f"Ja processados: {len(ja_processados)}", flush=True)
    print("=" * 70, flush=True)
    
    for idx, img_path in enumerate(imagens, 1):
        if img_path.name in ja_processados:
            print(f"\n  [{idx}/{len(imagens)}] {img_path.name} - ja processado, pulando", flush=True)
            continue
        
        print(f"\n{'-'*60}", flush=True)
        print(f"[{idx}/{len(imagens)}] {img_path.name}", flush=True)
        print(f"{'-'*60}", flush=True)
        
        try:
            r = processar_imagem(img_path)
            resultados.append(r)
            
            print(f"  OK {r['num_blocos']} blocos | Conf: {r['confianca_media']:.1%} | {r['tempo_segundos']:.1f}s", flush=True)
            if r["valores"]:
                print(f"  VALOR: {' | '.join(f'R$ {v:.2f}' for v in r['valores'])}", flush=True)
            if r["datas"]:
                print(f"  DATA: {', '.join(r['datas'])}", flush=True)
            if r["palavras_chave"]:
                print(f"  KEYWORDS: {' '.join(r['palavras_chave'][:5])}", flush=True)
            print(f"  STATUS: {'COMPROVANTE' if r['eh_comprovante'] else 'DESCONHECIDO'}", flush=True)
            
            # Salvar após cada imagem (nao perder progresso)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(resultados, f, ensure_ascii=False, indent=2, default=str)
            print(f"  Salvo em {output.name}", flush=True)
            
        except Exception as e:
            print(f"  ERRO: {e}", flush=True)
            import traceback
            traceback.print_exc()
            # Salvar mesmo com erro parcial
            with open(output, "w", encoding="utf-8") as f:
                json.dump(resultados, f, ensure_ascii=False, indent=2, default=str)
            break  # Parar para debug
    
    # RESUMO
    if resultados:
        print(f"\n\n{'='*70}", flush=True)
        print("RESUMO FINAL", flush=True)
        print(f"{'='*70}", flush=True)
        
        comprovantes = sum(1 for r in resultados if r["eh_comprovante"])
        com_valor = sum(1 for r in resultados if r["valor_principal"])
        total_blocos = sum(r["num_blocos"] for r in resultados)
        total_tempo = sum(r["tempo_segundos"] for r in resultados)
        
        print(f"\n{'ARQUIVO':<22} {'BLOCOS':<8} {'CONF':<8} {'VALOR':<12} {'STATUS'}", flush=True)
        print("-" * 65, flush=True)
        for r in resultados:
            nome = r["arquivo"][:20]
            blocos = str(r["num_blocos"])
            conf = f"{r['confianca_media']:.0%}"
            valor = f"R$ {r['valor_principal']:.2f}" if r["valor_principal"] else "-"
            status = "COMPROVANTE" if r["eh_comprovante"] else "?"
            print(f"{nome:<22} {blocos:<8} {conf:<8} {valor:<12} {status}", flush=True)
        
        print(f"\n{'='*50}", flush=True)
        print(f"  Total imagens: {len(resultados)}", flush=True)
        print(f"  Comprovantes: {comprovantes}/{len(resultados)}", flush=True)
        print(f"  Com valor: {com_valor}/{len(resultados)}", flush=True)
        print(f"  Total blocos: {total_blocos}", flush=True)
        print(f"  Tempo total: {total_tempo:.0f}s (media {total_tempo/len(resultados):.0f}s/img)", flush=True)
        print(f"{'='*50}", flush=True)
        print(f"\nResultados em: {output}", flush=True)

    # Limpar cache do reader
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()

if __name__ == "__main__":
    main()