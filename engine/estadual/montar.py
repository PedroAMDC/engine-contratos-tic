"""Monta o resumo executivo estadual (PDF ≤ 50 páginas).

Textos: data/_global/estadual.json (redator) e temas/*.json (achados verificados).
Números: sempre recalculados aqui a partir da base e dos candidatos.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from ..config import DATA, OUTPUT
from ..perfil import P
from ..relatorio import render
from .base import carregar_base
from .temas import TEMAS

G = DATA / "_global"
PAGINAS_ALVO = 50


def _ler(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _contrato(c: dict) -> dict:
    return {k: c.get(k) for k in ("id", "orgao", "numero", "contratada", "sub", "objeto", "valor", "valor_anual",
                                  "vigencia_fim", "situacao", "estatal_ti")}


def montar_estadual(data_ref: str, versao: str = "1.0", exigir_checagem: bool = True) -> dict:
    from ..verificacao import checagem_aprovada, verificar_resumo_estadual, verificar_tema

    for n in TEMAS:
        r = verificar_tema(n)
        if not r["ok"]:
            raise SystemExit(f"Tema {n} com erros: {r['erros'][:3]}")
    r = verificar_resumo_estadual()
    if not r["ok"]:
        raise SystemExit(f"Resumo estadual com erros: {r['erros'][:3]}")
    if exigir_checagem:
        arq = G / "checagem_estadual.json"
        if not arq.exists() or not _ler(arq).get("aprovado"):
            raise SystemExit("Checagem de fatos estadual ausente ou não aprovada.")

    base = {c["id"]: c for c in carregar_base()}
    cand = _ler(G / "candidatos.json")
    texto = _ler(G / "estadual.json")

    achados = {}
    temas = []
    for n, meta in TEMAS.items():
        t = _ler(G / "temas" / f"{n}.json")
        lista = []
        for a in t["achados"]:
            todos = [base[k] for k in a["contratos"] if k in base]
            # valores e órgãos contam só os contratos centrais (objeto do achado), não os de referência
            cs = [base[k] for k in (a.get("contratos_centrais") or a["contratos"]) if k in base]
            e = {
                **a, "tema_n": n, "tema": meta["nome"],
                "orgaos": sorted({c["orgao"] for c in cs}),
                "n_contratos": len(cs),
                "n_referencia": len(todos) - len(cs),
                "valor_envolvido": round(sum(c["valor"] or 0 for c in cs), 2),
                "valor_anual_envolvido": round(sum(c["valor_anual"] or 0 for c in cs), 2),
                "contratos_det": [_contrato(c) for c in todos],
                "evid_txt": [f"{ev['contrato']} · {ev['doc']} p. {ev['pagina']}" for ev in a.get("evidencias", [])],
            }
            achados[a["id"]] = e
            lista.append(e)
        cab = next((x for x in texto["temas"] if str(x["n"]) == n), {})
        destaque = [achados[i] for i in cab.get("achados_destaque", []) if i in achados] or lista[:6]
        produtos = [p for p in cand["produtos_repetidos"]
                    if meta["macros"] and any(base.get(it["contrato"], {}).get("macro") in meta["macros"] for it in p["itens"])][:8]
        macro = [cand["panorama"]["por_macro"][m] | {"nome": m} for m in meta["macros"]]
        temas.append({
            "n": n, "nome": meta["nome"], "abertura": cab.get("abertura", ""), "diagnostico": t.get("diagnostico", ""),
            "achados": destaque, "outros": [a for a in lista if a not in destaque],
            "quadro": [_contrato(base[k]) for k in t.get("contratos_quadro", []) if k in base][:14],
            "produtos": produtos, "macro": macro,
        })

    top = [achados[x["achado"]] | {"por_que": x["por_que"]} for x in texto["top_oportunidades"] if x["achado"] in achados]
    def soma_eco(tipo):
        return round(sum(a["economia"]["valor"] for a in achados.values()
                         if a["economia"]["tipo"] == tipo and isinstance(a["economia"].get("valor"), (int, float))), 2)

    economia_calc, economia_est = soma_eco("calculada"), soma_eco("estimada")
    n_medir = sum(1 for a in achados.values() if a["economia"]["tipo"] == "não estimada")
    from .mapa_infra import resumo_mapa

    mapa = resumo_mapa()

    dados = {
        "meta": {"orgao_sigla": P.ente.sigla, "orgao_nome": P.ente.poder, "unidade_emissora": P.emissor_completo,
                 "data_referencia": data_ref, "data_emissao": date.today().isoformat(), "versao": versao,
                 "classificacao": P.relatorio.classificacao, "finalidade": "Resumo executivo para a alta gestão"},
        "resumo": {"alertas": []}, "contratos": [],
        "est": {**texto, "temas": temas, "top": top, "panorama": cand["panorama"], "calendario": cand["calendario"],
                "fornecedores": cand["fornecedores_multiorgao"][:15], "atas": cand["atas"][:10],
                "economia_calculada": economia_calc, "economia_estimada": economia_est, "achados_a_medir": n_medir,
                "n_achados": len(achados), "mapa": mapa,
                "checagem": _ler(G / "checagem_estadual.json") if (G / "checagem_estadual.json").exists() else None},
    }
    (G / "relatorio_estadual.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return dados


def gerar_pdf_estadual() -> tuple[Path, int]:
    import pymupdf

    dados = _ler(G / "relatorio_estadual.json")
    pdf = render.pdf(dados, OUTPUT / "ESTADUAL" / f"Resumo_Executivo_TIC_{P.ente.sigla}_{dados['meta']['data_referencia']}.pdf",
                     modelo="relatorio_estadual")
    return pdf, pymupdf.open(pdf).page_count
