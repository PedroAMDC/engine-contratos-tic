"""Diagnóstico de TIC para o emissor (até 10 páginas), montado sobre a análise completa.

Entradas: data/<ORGAO>/analise/diagnostico.json (redação) + contratos/G*.json (dados verificados).
Valores, vigências, recomendação, prioridade e níveis corporativos vêm sempre dos contratos.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .config import OUTPUT
from .inventario import carregar_manifest, dir_orgao
from .montar import OBJETIVO, Evidencias, carregar_contratos
from .perfil import P
from .relatorio import render

MAX_FICHAS = 10
PAGINAS_ALVO = 10


def montar_diagnostico(sigla: str, data_referencia: str | None = None, versao: str = "1.0", exigir_checagem: bool = True) -> dict:
    from .verificacao import checagem_aprovada, verificar_diagnostico

    base = dir_orgao(sigla)
    v = verificar_diagnostico(sigla)
    if not v["ok"]:
        raise SystemExit(f"Diagnóstico {P.emissor.sigla} inválido:\n  " + "\n  ".join(v["erros"]))
    if exigir_checagem:
        ok, motivo = checagem_aprovada(sigla, "checagem_diagnostico.json")
        if not ok:
            raise SystemExit(f"Checagem de fatos do diagnóstico {P.emissor.sigla} não aprovada: {motivo}")

    s = json.loads((base / "analise" / "diagnostico.json").read_text(encoding="utf-8"))
    manifest = carregar_manifest(sigla)
    nomes = {d["codigo"]: d for d in manifest["documentos"]}
    analises = {c["grupo"]: c for c in carregar_contratos(sigla)}
    orgao_nome = manifest.get("orgao_nome") or s.get("orgao_nome") or manifest["orgao"]
    orgao_path = base / "analise" / "orgao.json"
    if orgao_path.exists():
        orgao_nome = json.loads(orgao_path.read_text(encoding="utf-8")).get("orgao_nome", orgao_nome)
    ref = data_referencia or s.get("data_referencia") or date.today().isoformat()
    ev = Evidencias(nomes)

    alertas = []
    for p in s["pontos_atencao"]:
        alertas.append({**p, "acao": p["encaminhamento"],
                        "fontes_txt": [ev.ref(f, f"Ponto de atenção: {p['titulo']}") for f in p.get("fontes", [])]})

    contratos = []
    for item in s["contratos"]:
        c = analises[item["grupo"]]
        contratos.append({
            "grupo": c["grupo"],
            "numero": c["numero"],
            "contratada": c["contratada"],
            "categoria": c["categoria"],
            "objeto_resumido": c["objeto_resumido"],
            "valor_original": c.get("valor_original"),
            "valor_atualizado": c.get("valor_atualizado"),
            "valor_anual": c.get("valor_anual"),
            "vigencia_inicio": c.get("vigencia_inicio"),
            "vigencia_fim": c.get("vigencia_fim"),
            "necessidade": c["necessidade"],
            "recomendacao": c["recomendacao"],
            "prioridade": c["prioridade"],
            "corporativo": c["corporativo"],
            "leitura": item["leitura"],
            "diagnostico": item["diagnostico"],
            "encaminhamento": item["encaminhamento"],
            "perguntas": item["perguntas"],
            "fontes_txt": [ev.ref(f, f"{c['numero']}: ficha") for f in item.get("fontes", [])],
        })

    sobreposicoes = [
        {**x, "fontes_txt": [ev.ref(f, f"Sobreposição: {' × '.join(x['contratos'])}") for f in x.get("fontes", [])]}
        for x in s.get("sobreposicoes", [])
    ]

    # fichas: todas se couberem; senão prioridade alta e média, por valor
    ordem = sorted(contratos, key=lambda c: (c["valor_atualizado"] or c["valor_original"] or 0), reverse=True)
    if len(ordem) <= MAX_FICHAS:
        fichas, fora = ordem, []
    else:
        cand = [c for c in ordem if c["prioridade"] in ("P1", "P2")]
        fichas = cand[:MAX_FICHAS]
        fora = [c["numero"] for c in ordem if c not in fichas]

    dados = {
        "meta": {
            "modelo": False,
            "orgao_sigla": sigla,
            "orgao_nome": orgao_nome,
            "unidade_emissora": P.emissor_completo,
            "data_referencia": ref,
            "data_emissao": date.today().isoformat(),
            "versao": versao,
            "classificacao": P.relatorio.classificacao,
            "finalidade": s.get("finalidade", P.relatorio.finalidade),
            "objetivo": OBJETIVO,
        },
        "resumo": {"manchete": s["manchete"], "alertas": alertas, "decisoes": s.get("decisoes", [])},
        "contratos": contratos,
        "fichas_ids": [c["grupo"] for c in fichas],
        "fichas_fora": fora,
        "governanca": s.get("governanca", {}),
        "sobreposicoes": sobreposicoes,
        "plano": s.get("plano", []),
        "perguntas_dirigente": s.get("perguntas_dirigente", []),
        "documentos_faltantes": s.get("documentos_faltantes", []),
        "conclusao": s.get("conclusao", ""),
        "inventario": [d for d in manifest["documentos"]],
        "evidencias": ev.itens,
        "checagem": _checagem(base),
    }
    (base / "relatorio_diagnostico.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return dados


def _checagem(base: Path) -> dict | None:
    arq = base / "analise" / "checagem_diagnostico.json"
    if not arq.exists():
        return None
    c = json.loads(arq.read_text(encoding="utf-8"))
    afs = c.get("afirmacoes", [])
    return {"data": c.get("data"), "total": len(afs),
            "confirmadas": sum(a.get("status") == "Confirmado" for a in afs),
            "corrigidas": sum(bool(a.get("corrigido")) for a in afs)}


def gerar_pdf_diagnostico(sigla: str) -> tuple[Path, int]:
    import pymupdf

    dados = json.loads((dir_orgao(sigla) / "relatorio_diagnostico.json").read_text(encoding="utf-8"))
    nome = f"Diagnostico_TIC_{P.emissor.sigla}_{sigla}_{dados['meta']['data_referencia']}.pdf"
    pdf = render.pdf(dados, OUTPUT / sigla / nome, modelo="relatorio_diagnostico")
    paginas = pymupdf.open(pdf).page_count
    return pdf, paginas
