"""Linha de comando da engine.

    python -m engine inventario <ORGAO> [--forcar]
    python -m engine extrair    <ORGAO> [--workers 4 --threads 4]
    python -m engine agrupar    <ORGAO>
    python -m engine validar    <ORGAO> [GRUPO ...]
    python -m engine validar-orgao <ORGAO>
    python -m engine montar     <ORGAO> [--data AAAA-MM-DD] [--versao 1.0] [--sem-checagem]
    python -m engine publicar   <ORGAO>
    python -m engine status     <ORGAO>
    python -m engine prompts
"""

import argparse
import json
import sys


def main(argv=None):
    p = argparse.ArgumentParser(prog="engine", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("comando", choices=["inventario", "extrair", "agrupar", "preparar", "ocr-complementar", "reprocessar", "fichas-validar", "lotes", "base", "candidatos", "estadual-validar", "estadual-montar", "infra-lotes", "infra-validar", "infra-mapa", "validar", "validar-orgao", "validar-diagnostico", "montar", "publicar", "status", "prompts"])
    p.add_argument("--tipo", choices=["diagnostico", "completo"], default="diagnostico", help="montar/publicar: diagnóstico resumido (padrão) ou análise completa")
    p.add_argument("orgao", nargs="?", default="", help="sigla do órgão (em `preparar`, lista separada por vírgula)")
    p.add_argument("grupos", nargs="*")
    p.add_argument("--forcar", action="store_true")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--data")
    p.add_argument("--versao", default="1.0")
    p.add_argument("--sem-checagem", action="store_true", help="rascunho: monta sem a checagem independente de fatos")
    a = p.parse_args(argv)
    if a.comando == "prompts":
        from .prompts import gerar_prompts

        n = gerar_prompts()
        print(f"{n} arquivo(s) gerado(s) em data/_prompts")
        return 0
    if not a.orgao:
        p.error("informe a sigla do órgão")
    sigla = a.orgao.upper() if a.comando not in ("preparar", "ocr-complementar", "reprocessar", "lotes", "base", "candidatos", "estadual-validar", "estadual-montar", "infra-lotes", "infra-mapa") else a.orgao

    if a.comando == "reprocessar":
        from datetime import datetime

        from .config import DATA
        from .extracao import reprocessar_ilegiveis

        saida = {}
        for s in [x.strip() for x in a.orgao.split(",") if x.strip()]:
            saida[s] = reprocessar_ilegiveis(s, a.workers, a.threads, log=lambda *_: None)
            print(f"{datetime.now():%H:%M:%S}  {s}: {len(saida[s])} documento(s) reprocessado(s) {saida[s]}", flush=True)
        (DATA / "_global" / "reprocessados.json").write_text(json.dumps(saida, ensure_ascii=False), encoding="utf-8")
        return 0

    if a.comando == "ocr-complementar":
        from datetime import datetime

        from .config import DATA
        from .extracao import complementar_ocr

        log = DATA / "_logs" / "ocr_complementar.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        for s in [x.strip() for x in a.orgao.split(",") if x.strip()]:
            try:
                r = complementar_ocr(s, workers=a.workers, threads=a.threads, log=lambda *_: None)
                msg = f"{s}: {r['paginas']} páginas verificadas em {r['documentos']} documentos; {r['incorporadas']} com conteúdo novo"
            except Exception as e:
                msg = f"{s}: FALHOU — {type(e).__name__}: {e}"
            linha = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
            print(linha, flush=True)
            with open(log, "a", encoding="utf-8") as f:
                f.write(linha + "\n")
        return 0

    if a.comando == "inventario":
        from .inventario import inventariar

        m = inventariar(sigla, a.forcar)
        for d in m["documentos"]:
            print(d["codigo"], d["status"], d.get("caminho_drive", ""), "|", d["nome"], d.get("duplicata_de", ""))

    elif a.comando == "extrair":
        from .extracao import extrair_orgao

        r = extrair_orgao(sigla, a.workers, a.threads)
        print(f"{len(r)} documentos, {sum(x['paginas'] for x in r.values())} páginas, "
              f"{sum(x['ocr'] for x in r.values())} com OCR")

    elif a.comando == "preparar":
        # lote determinístico: inventário + extração + agrupamento, um órgão após o outro
        import traceback
        from datetime import datetime

        from .agrupamento import agrupar
        from .config import DATA
        from .extracao import extrair_orgao
        from .inventario import inventariar

        log = DATA / "_logs" / "preparar.log"
        log.parent.mkdir(parents=True, exist_ok=True)

        def registra(msg):
            linha = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
            print(linha, flush=True)
            with open(log, "a", encoding="utf-8") as f:
                f.write(linha + "\n")

        for s in [x.strip() for x in a.orgao.split(",") if x.strip()]:
            try:
                registra(f"{s}: inventário")
                m = inventariar(s, a.forcar)
                registra(f"{s}: {len(m['documentos'])} arquivos; extração")
                r = extrair_orgao(s, a.workers, a.threads, log=lambda *_: None)
                registra(f"{s}: {sum(x['paginas'] for x in r.values())} páginas, {sum(x['ocr'] for x in r.values())} com OCR; agrupamento")
                g = agrupar(s)
                registra(f"{s}: PRONTO — {len(g)} grupos")
            except BaseException as e:  # um órgão com problema não para o lote
                registra(f"{s}: FALHOU — {type(e).__name__}: {e}")
                with open(log, "a", encoding="utf-8") as f:
                    f.write(traceback.format_exc() + "\n")

    elif a.comando == "agrupar":
        from .agrupamento import agrupar

        for g in agrupar(sigla):
            print(g["grupo"], g["numero_provavel"], [f"{d['codigo']}:{d['tipo']}" for d in g["documentos"]])

    elif a.comando == "validar":
        from .inventario import dir_orgao
        from .verificacao import verificar

        grupos = a.grupos or sorted(
            f.stem for f in (dir_orgao(sigla) / "analise" / "contratos").glob("G*.json")
            if not f.name.endswith(".verificacao.json")
        )
        falhou = False
        for g in grupos:
            r = verificar(sigla, g)
            print(f"{g}: {'OK' if r['ok'] else 'ERROS'}")
            for e in r["erros"]:
                print("  ERRO ", e)
            for w in r["avisos"]:
                print("  AVISO", w)
            falhou |= not r["ok"]
        return 1 if falhou else 0

    elif a.comando == "fichas-validar":
        from .inventario import dir_orgao
        from .verificacao import verificar_ficha

        grupos = a.grupos or sorted(
            f.stem for f in (dir_orgao(sigla) / "fichas").glob("G*.json") if not f.name.endswith(".verificacao.json")
        )
        falhou = False
        for g in grupos:
            r = verificar_ficha(sigla, g)
            print(f"{g}: {'OK' if r['ok'] else 'ERROS'}")
            for e in r["erros"]:
                print("  ERRO ", e)
            for w in r["avisos"]:
                print("  AVISO", w)
            falhou |= not r["ok"]
        return 1 if falhou else 0

    elif a.comando == "base":
        from .estadual.base import consolidar, planilha, produtos_distintos

        print(produtos_distintos())
        base = consolidar()
        print(f"{len(base)} contratos de {len({c['orgao'] for c in base})} órgãos")
        print(planilha(base))
        return 0

    elif a.comando == "candidatos":
        from .estadual.candidatos import calcular

        r = calcular(a.data)
        from .estadual.fatias import fatias_vocabulario, gerar

        print("fatias por tema (contratos, KB base, KB candidatos):", gerar())
        print("fatias de vocabulário:", fatias_vocabulario())
        p = r["panorama"]
        print(f"{p['contratos']} contratos · R$ {p['valor_total']:,.2f} · {len(r['produtos_repetidos'])} produtos em 2+ órgãos · "
              f"{len(r['fornecedores_multiorgao'])} fornecedores em 2+ órgãos · {len(r['funcoes'])} funções com plataformas")
        return 0

    elif a.comando == "estadual-validar":
        # uso: estadual-validar tema <n>
        from .verificacao import verificar_resumo_estadual, verificar_tema

        if a.orgao.lower() == "resumo":
            r = verificar_resumo_estadual()
            print(f"estadual.json: {'OK' if r['ok'] else 'ERROS'}")
            for e in r["erros"]:
                print("  ERRO ", e)
            return 0 if r["ok"] else 1
        if a.orgao.lower() != "tema" or not a.grupos:
            raise SystemExit("uso: python -m engine estadual-validar tema <n> | resumo")
        falhou = False
        for n in a.grupos:
            r = verificar_tema(n)
            print(f"tema {n}: {'OK' if r['ok'] else 'ERROS'}")
            for e in r["erros"]:
                print("  ERRO ", e)
            for w in r["avisos"]:
                print("  AVISO", w)
            falhou |= not r["ok"]
        return 1 if falhou else 0

    elif a.comando == "estadual-montar":
        from .estadual.montar import PAGINAS_ALVO, gerar_pdf_estadual, montar_estadual

        montar_estadual(a.data or __import__("datetime").date.today().isoformat(), a.versao, exigir_checagem=not a.sem_checagem)
        pdf, n = gerar_pdf_estadual()
        print(pdf)
        print(f"{n} páginas" + ("" if n <= PAGINAS_ALVO else f" — ACIMA DO ALVO DE {PAGINAS_ALVO}"))
        return 0

    elif a.comando == "infra-lotes":
        from .estadual.mapa_infra import selecionar

        l = selecionar()
        print(f"{len(l)} lotes, {sum(len(x['contratos']) for x in l)} contratos")
        return 0

    elif a.comando == "infra-validar":
        from .estadual.mapa_infra import verificar_infra

        falhou = False
        for g in a.grupos:
            r = verificar_infra(sigla, g)
            print(f"{g}: {'OK' if r['ok'] else 'ERROS'}")
            for e in r["erros"]:
                print("  ERRO ", e)
            for w in r["avisos"]:
                print("  AVISO", w)
            falhou |= not r["ok"]
        return 1 if falhou else 0

    elif a.comando == "infra-mapa":
        from .estadual.mapa_infra import montar_mapa

        print(montar_mapa())
        return 0

    elif a.comando == "lotes":
        from .estadual.lotes import montar_lotes

        lotes = montar_lotes([x.strip() for x in a.orgao.split(",") if x.strip()] if a.orgao != "TODOS" else None)
        print(f"{len(lotes)} lotes, {sum(l['paginas'] for l in lotes)} páginas")
        return 0

    elif a.comando == "validar-orgao":
        from .verificacao import checagem_aprovada, verificar_orgao

        r = verificar_orgao(sigla)
        print(f"orgao.json: {'OK' if r['ok'] else 'ERROS'}")
        for e in r["erros"]:
            print("  ERRO ", e)
        for w in r["avisos"]:
            print("  AVISO", w)
        ok, motivo = checagem_aprovada(sigla)
        print(f"checagem de fatos: {'APROVADA' if ok else motivo}")
        return 0 if r["ok"] else 1

    elif a.comando == "validar-diagnostico":
        from .verificacao import checagem_aprovada, verificar_diagnostico

        r = verificar_diagnostico(sigla)
        print(f"diagnostico.json: {'OK' if r['ok'] else 'ERROS'}")
        for e in r["erros"]:
            print("  ERRO ", e)
        for w in r["avisos"]:
            print("  AVISO", w)
        ok, motivo = checagem_aprovada(sigla, "checagem_diagnostico.json")
        print(f"checagem de fatos: {'APROVADA' if ok else motivo}")
        return 0 if r["ok"] else 1

    elif a.comando == "montar":
        if a.tipo == "completo":
            from .montar import gerar_pdf, montar

            montar(sigla, a.data, a.versao, exigir_checagem=not a.sem_checagem)
            print(gerar_pdf(sigla))
        else:
            from .montar_diagnostico import PAGINAS_ALVO, gerar_pdf_diagnostico, montar_diagnostico

            montar_diagnostico(sigla, a.data, a.versao, exigir_checagem=not a.sem_checagem)
            pdf, paginas = gerar_pdf_diagnostico(sigla)
            print(pdf)
            print(f"{paginas} páginas" + ("" if paginas <= PAGINAS_ALVO else f" — ACIMA DO ALVO DE {PAGINAS_ALVO}"))

    elif a.comando == "publicar":
        from .config import OUTPUT
        from .perfil import P
        from .publicar import publicar

        prefixo = f"Diagnostico_TIC_{P.emissor.sigla}_" if a.tipo == "diagnostico" else "Diagnostico_Contratos_TIC_"
        pdfs = sorted((OUTPUT / sigla).glob(f"{prefixo}*.pdf"), key=lambda f: f.stat().st_mtime)
        if not pdfs:
            raise SystemExit("Nenhum PDF gerado para este órgão. Rode `montar` antes.")
        print(publicar(sigla, pdfs[-1]))

    elif a.comando == "status":
        from .inventario import carregar_manifest

        m = carregar_manifest(sigla)
        print(json.dumps({d["codigo"]: d.get("extracao", d["status"]) for d in m.get("documentos", [])}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
