"""Etapa 2 — extração de texto, página a página, com rastreio de fonte.

Estratégia híbrida, para equilibrar qualidade e tempo em CPU:
- Páginas com camada de texto: PyMuPDF (instantâneo) + detecção de tabelas.
- Páginas digitalizadas (sem texto): docling com OCR, só nesses trechos.
- DOCX/XLSX/imagens: docling.

Resultado por documento em data/<ORGAO>/texto/<codigo>.json e .md (este com
marcadores "[D01 · p. 3]" para os agentes citarem a fonte). Há cache global por
hash do arquivo: o mesmo PDF nunca é processado duas vezes, nem entre órgãos.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .config import DATA
from .inventario import carregar_manifest, dir_orgao

CACHE = DATA / "_cache" / "extracao"
MIN_CHARS = 200          # abaixo disso, a página é tratada como digitalizada
VERSAO = 1               # mude para invalidar o cache após alterar a extração

_conversores: dict = {}


def _docling(ocr: bool):
    """Conversor docling reutilizado dentro do processo (carregar modelos é caro)."""
    if ocr in _conversores:
        return _conversores[ocr]
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions()
    opts.do_ocr = ocr
    opts.do_table_structure = True
    if ocr:
        opts.ocr_options.force_full_page_ocr = True
    conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
    _conversores[ocr] = conv
    return conv


OCR_BLOCO = 8  # páginas por chamada de OCR: limita a memória em digitalizações grandes


def _faixas(paginas: list[int], bloco: int = OCR_BLOCO) -> list[tuple[int, int]]:
    """[1,2,3,7,8] -> [(1,3),(7,8)], com no máximo `bloco` páginas por faixa."""
    faixas = []
    for p in sorted(paginas):
        if faixas and p == faixas[-1][1] + 1 and faixas[-1][1] - faixas[-1][0] + 1 < bloco:
            faixas[-1] = (faixas[-1][0], p)
        else:
            faixas.append((p, p))
    return faixas


def pagina_ilegivel(texto: str, tem_imagem: bool) -> bool:
    """Camada de texto que não serve: fonte com codificação quebrada (caracteres de controle)
    ou só o carimbo da assinatura eletrônica sobre um contrato digitalizado."""
    import re

    if not texto:
        return tem_imagem
    legiveis = sum(1 for ch in texto if ch.isalnum() or ch.isspace() or ch in ".,;:/-()%$ºª°'\"")
    if legiveis / len(texto) < 0.85:
        return True
    unicas = len({w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]{3,}", texto)})
    return tem_imagem and unicas < 40 and "assinad" in texto.lower()


def _pdf(caminho: Path) -> list[dict]:
    import pymupdf

    doc = pymupdf.open(caminho)
    paginas, ocr = [], []
    for i, pg in enumerate(doc, 1):
        texto = pg.get_text("text").strip()
        imagens = bool(pg.get_images())
        if (len(texto) < MIN_CHARS and imagens) or pagina_ilegivel(texto, imagens):
            ocr.append(i)
            paginas.append({"n": i, "metodo": "ocr", "texto": "", "tabelas": []})
            continue
        tabelas = []
        try:
            for t in pg.find_tables().tables:
                md = t.to_markdown().strip()
                if md.count("\n") >= 2:
                    tabelas.append(md)
        except Exception:
            pass
        paginas.append({"n": i, "metodo": "texto", "texto": texto, "tabelas": tabelas})

    if ocr:
        conv = _docling(ocr=True)
        for a, b in _faixas(ocr):
            res = conv.convert(str(caminho), page_range=(a, b)).document
            for n in range(a, b + 1):
                pag = paginas[n - 1]
                pag["texto"] = res.export_to_markdown(page_no=n).strip()
                pag["tabelas"] = [
                    t.export_to_markdown(doc=res) for t in res.tables
                    if t.prov and t.prov[0].page_no == n
                ]
    return paginas


def _outro(caminho: Path) -> list[dict]:
    """DOCX, XLSX, imagens: um bloco único (sem paginação confiável)."""
    imagem = caminho.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
    res = _docling(ocr=imagem).convert(str(caminho)).document
    return [{
        "n": 1,
        "metodo": "ocr" if imagem else "docling",
        "texto": res.export_to_markdown().strip(),
        "tabelas": [t.export_to_markdown(doc=res) for t in res.tables],
    }]


SUPORTADOS = {".pdf", ".docx", ".xlsx", ".pptx", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".html"}


def extrair_arquivo(caminho: str, sha: str) -> dict:
    cache = CACHE / f"{sha}.json"
    if cache.exists():
        dados = json.loads(cache.read_text(encoding="utf-8"))
        if dados.get("versao") == VERSAO:
            return dados | {"cache": True}

    t0 = time.time()
    arq = Path(caminho)
    ext = arq.suffix.lower()
    if ext not in SUPORTADOS:
        return {"versao": VERSAO, "status": "nao_suportado", "paginas": [], "segundos": 0}
    try:
        paginas = _pdf(arq) if ext == ".pdf" else _outro(arq)
        status = "ok"
    except Exception as e:
        return {"versao": VERSAO, "status": "erro", "erro": f"{type(e).__name__}: {e}", "paginas": [], "segundos": round(time.time() - t0, 1)}

    vazias = [p["n"] for p in paginas if len(p["texto"]) < 40]
    dados = {
        "versao": VERSAO,
        "status": status,
        "paginas": paginas,
        "n_paginas": len(paginas),
        "paginas_ocr": sum(p["metodo"] == "ocr" for p in paginas),
        "paginas_vazias": vazias,
        "segundos": round(time.time() - t0, 1),
    }
    CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return dados


def _markdown(codigo: str, nome: str, dados: dict) -> str:
    partes = [f"# [{codigo}] {nome}\n"]
    for p in dados["paginas"]:
        partes.append(f"\n\n===== [{codigo} · p. {p['n']}] ({p['metodo']}) =====\n\n{p['texto']}")
        if p.get("texto_imagem"):
            partes.append(f"\n\n[{codigo} · p. {p['n']} · conteúdo em imagem — OCR]\n{p['texto_imagem']}")
        for i, t in enumerate(p["tabelas"], 1):
            partes.append(f"\n\n[{codigo} · p. {p['n']} · tabela {i}]\n{t}")
    return "".join(partes)


def _init_worker(threads: int):
    for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[v] = str(threads)
    try:
        import torch

        torch.set_num_threads(threads)
    except Exception:
        pass


def extrair_orgao(sigla: str, workers: int = 4, threads: int = 4, log=print) -> dict:
    base = dir_orgao(sigla)
    manifest = carregar_manifest(sigla)
    saida = base / "texto"
    saida.mkdir(parents=True, exist_ok=True)

    pendentes = [d for d in manifest["documentos"] if d.get("status") == "baixado" and not d.get("duplicata_de")]
    # maiores primeiro: melhor balanceamento entre processos
    pendentes.sort(key=lambda d: d.get("bytes", 0), reverse=True)

    from concurrent.futures.process import BrokenProcessPool

    resumo = {}

    def registra(d, dados):
        (saida / f"{d['codigo']}.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        if dados["status"] == "ok":
            (saida / f"{d['codigo']}.md").write_text(_markdown(d["codigo"], d["nome"], dados), encoding="utf-8")
        resumo[d["codigo"]] = {
            "status": dados["status"],
            "paginas": dados.get("n_paginas", 0),
            "ocr": dados.get("paginas_ocr", 0),
            "vazias": len(dados.get("paginas_vazias", [])),
            "segundos": dados.get("segundos", 0),
            "cache": dados.get("cache", False),
        }
        log(f"  {d['codigo']} {dados['status']:13s} {resumo[d['codigo']]['paginas']:3d} p. "
            f"({resumo[d['codigo']]['ocr']} OCR) {resumo[d['codigo']]['segundos']:6.1f}s  {d['nome'][:60]}")

    # se um processo morrer (ex.: falta de memória numa digitalização grande), o pool inteiro
    # quebra; refazemos só o que faltou, com menos processos, até chegar a 1
    fila, n = pendentes, workers
    while fila:
        falhas = []
        try:
            with ProcessPoolExecutor(max_workers=n, initializer=_init_worker, initargs=(threads,)) as ex:
                futuros = {ex.submit(extrair_arquivo, str(base / d["arquivo_local"]), d["sha256"]): d for d in fila}
                for f in as_completed(futuros):
                    d = futuros[f]
                    try:
                        registra(d, f.result())
                    except BrokenProcessPool:
                        falhas.append(d)
        except BrokenProcessPool:
            falhas = [d for d in fila if d["codigo"] not in resumo]
        if not falhas:
            break
        if n == 1:
            for d in falhas:
                registra(d, {"versao": VERSAO, "status": "erro", "erro": "processo encerrado (provável falta de memória)",
                             "paginas": [], "segundos": 0})
            break
        n = max(1, n // 2)
        log(f"  {len(falhas)} documento(s) interrompidos; repetindo com {n} processo(s)")
        fila = falhas

    for d in manifest["documentos"]:
        if d["codigo"] in resumo:
            d["extracao"] = resumo[d["codigo"]]
    from .inventario import salvar_manifest

    salvar_manifest(sigla, manifest)
    return resumo


# ---------------------------------------------------------------- OCR complementar
# Páginas que já têm texto digital mas também trazem imagem grande (tabela de preços ou
# nível de serviço colado como figura). O OCR só é incorporado se trouxer conteúdo novo:
# timbres e marcas d'água repetem o que já está no texto e são descartados.

def _palavras(s: str) -> set[str]:
    import re
    import unicodedata

    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return {w for w in re.findall(r"[a-z0-9][a-z0-9.,/-]{3,}", s)}


def _ocr_paginas(caminho: str, paginas: list[int]) -> dict:
    """OCR de páginas específicas (processo filho). Retorna {n: (texto, tabelas)}."""
    conv = _docling(ocr=True)
    saida = {}
    for a, b in _faixas(paginas):
        res = conv.convert(caminho, page_range=(a, b)).document
        for n in range(a, b + 1):
            saida[n] = (
                res.export_to_markdown(page_no=n).strip(),
                [t.export_to_markdown(doc=res) for t in res.tables if t.prov and t.prov[0].page_no == n],
            )
    return saida


def paginas_mistas(caminho: Path, dados: dict, limiar: float) -> list[int]:
    import pymupdf

    doc = pymupdf.open(caminho)
    alvo = []
    for p in dados["paginas"]:
        if p["metodo"] != "texto" or "ocr_complementar" in p:
            continue
        pg = doc[p["n"] - 1]
        area = pg.rect.width * pg.rect.height
        coberta = sum(
            max(0, (r & pg.rect).width) * max(0, (r & pg.rect).height)
            for img in pg.get_images(full=True)
            for r in pg.get_image_rects(img[0])
        )
        if area and coberta / area >= limiar:
            alvo.append(p["n"])
    return alvo


def complementar_ocr(sigla: str, limiar: float = 0.25, min_novas: int = 25,
                     workers: int = 3, threads: int = 4, log=print) -> dict:
    base = dir_orgao(sigla)
    manifest = carregar_manifest(sigla)
    tarefas = []
    for d in manifest["documentos"]:
        if d.get("duplicata_de") or not d.get("arquivo_local", "").lower().endswith(".pdf"):
            continue
        arq_txt = base / "texto" / f"{d['codigo']}.json"
        dados = json.loads(arq_txt.read_text(encoding="utf-8"))
        if dados.get("status") != "ok":
            continue
        pags = paginas_mistas(base / d["arquivo_local"], dados, limiar)
        if pags:
            tarefas.append((d, dados, pags))

    resumo = {"documentos": len(tarefas), "paginas": sum(len(t[2]) for t in tarefas), "incorporadas": 0}
    if not tarefas:
        return resumo
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, initargs=(threads,)) as ex:
        futuros = {ex.submit(_ocr_paginas, str(base / d["arquivo_local"]), pags): (d, dados, pags)
                   for d, dados, pags in tarefas}
        for f in as_completed(futuros):
            d, dados, pags = futuros[f]
            try:
                resultado = f.result()
            except Exception as e:
                log(f"  {d['codigo']}: OCR complementar falhou ({type(e).__name__})")
                continue
            por_n = {p["n"]: p for p in dados["paginas"]}
            for n, (texto, tabelas) in resultado.items():
                p = por_n[n]
                novas = _palavras(texto) - _palavras(p["texto"] + " ".join(p.get("tabelas", [])))
                if len(novas) >= min_novas:
                    p["texto_imagem"] = texto
                    p["tabelas"] = p.get("tabelas", []) + tabelas
                    p["ocr_complementar"] = "incorporado"
                    resumo["incorporadas"] += 1
                else:
                    p["ocr_complementar"] = "sem_conteudo_novo"
            (base / "texto" / f"{d['codigo']}.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
            (base / "texto" / f"{d['codigo']}.md").write_text(_markdown(d["codigo"], d["nome"], dados), encoding="utf-8")
            cache = CACHE / f"{d['sha256']}.json"
            if cache.exists():
                cache.write_text(json.dumps({k: v for k, v in dados.items() if k != "cache"}, ensure_ascii=False), encoding="utf-8")
            log(f"  {d['codigo']}: {len(pags)} p. verificadas, "
                f"{sum(1 for n in pags if por_n[n].get('ocr_complementar') == 'incorporado')} com conteúdo novo")
    return resumo


def reprocessar_ilegiveis(sigla: str, workers: int = 3, threads: int = 4, log=print) -> list[str]:
    """Refaz com OCR as páginas tratadas como texto que são ilegíveis (ver pagina_ilegivel)."""
    import pymupdf

    base = dir_orgao(sigla)
    manifest = carregar_manifest(sigla)
    tarefas = []
    for d in manifest["documentos"]:
        if d.get("duplicata_de") or not d.get("arquivo_local", "").lower().endswith(".pdf"):
            continue
        arq_txt = base / "texto" / f"{d['codigo']}.json"
        dados = json.loads(arq_txt.read_text(encoding="utf-8"))
        if dados.get("status") != "ok":
            continue
        doc = pymupdf.open(base / d["arquivo_local"])
        ruins = [p["n"] for p in dados["paginas"]
                 if p["metodo"] == "texto" and pagina_ilegivel(p["texto"], bool(doc[p["n"] - 1].get_images()))]
        if ruins:
            tarefas.append((d, dados, ruins))
    alterados = []
    if not tarefas:
        return alterados
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, initargs=(threads,)) as ex:
        futuros = {ex.submit(_ocr_paginas, str(base / d["arquivo_local"]), ruins): (d, dados, ruins) for d, dados, ruins in tarefas}
        for f in as_completed(futuros):
            d, dados, ruins = futuros[f]
            try:
                res = f.result()
            except Exception as e:
                log(f"  {d['codigo']}: reprocessamento falhou ({type(e).__name__})")
                continue
            por_n = {p["n"]: p for p in dados["paginas"]}
            for n, (texto, tabelas) in res.items():
                p = por_n[n]
                p.update({"metodo": "ocr", "texto": texto, "tabelas": tabelas, "reprocessada": "texto ilegível"})
                p.pop("texto_imagem", None)
            dados["paginas_ocr"] = sum(p["metodo"] == "ocr" for p in dados["paginas"])
            (base / "texto" / f"{d['codigo']}.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
            (base / "texto" / f"{d['codigo']}.md").write_text(_markdown(d["codigo"], d["nome"], dados), encoding="utf-8")
            cache = CACHE / f"{d['sha256']}.json"
            cache.write_text(json.dumps({k: v for k, v in dados.items() if k != "cache"}, ensure_ascii=False), encoding="utf-8")
            alterados.append(d["codigo"])
            log(f"  {d['codigo']}: {len(ruins)} páginas refeitas com OCR")
    return alterados
