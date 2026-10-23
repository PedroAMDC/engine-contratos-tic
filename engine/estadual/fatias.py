"""Fatias da base e dos candidatos por tema e do vocabulário por macrocategoria.

Os arquivos completos são grandes demais para um agente ler inteiros; cada agente recebe
só o recorte do seu tema, em formato compacto, e consulta fichas e textos quando precisar.
"""

from __future__ import annotations

import json

from ..config import MACROCATEGORIAS
from .base import GLOBAL, carregar_base, slug_macro
from .temas import TEMAS


def _compacto(c: dict, itens: bool = True) -> dict:
    d = {k: c.get(k) for k in ("id", "orgao", "numero", "contratada", "cnpj", "estatal_ti", "estatal_ti_papel", "sub", "objeto",
                               "valor", "valor_anual", "vigencia_fim", "situacao", "temas")}
    if c.get("ata"):
        d["ata"] = f"{c['ata'].get('numero')} ({c['ata'].get('orgao_gerenciador')})"
    if itens:
        d["itens"] = [{k: it.get(k) for k in ("produto_canonico", "metrica", "periodicidade", "quantidade", "valor_unitario", "valor_total")}
                      for it in c["itens"]]
        if c.get("desenvolvimento"):
            d["desenvolvimento"] = {k: c["desenvolvimento"].get(k) for k in ("metrica", "quantidade", "valor_unitario", "catalogo_de_servicos", "sistemas_alvo")}
        if c.get("nuvem"):
            d["nuvem"] = {k: c["nuvem"].get(k) for k in ("provedor", "modelo", "broker", "capacidade")}
    return d


def gerar() -> dict:
    base = carregar_base()
    cand = json.loads((GLOBAL / "candidatos.json").read_text(encoding="utf-8"))
    pasta = GLOBAL / "fatias"
    pasta.mkdir(parents=True, exist_ok=True)
    tamanhos = {}
    for n, t in TEMAS.items():
        if t["macros"]:
            cs = [c for c in base if c["macro"] in t["macros"]]
            linhas = [_compacto(c) for c in cs]
        else:  # tema transversal: todos os contratos, sem itens
            cs = base
            linhas = [_compacto(c, itens=False) for c in cs]
        ids = {c["id"] for c in cs}
        (pasta / f"base_{n}.jsonl").write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in linhas) + "\n", encoding="utf-8")

        def dentro(lista, campo="id"):
            return [x for x in lista if x.get(campo) in ids]

        recorte = {
            "panorama": {k: v for k, v in cand["panorama"].items() if k != "orgao_x_macro"} | (
                {"por_macro": {m: cand["panorama"]["por_macro"][m] for m in t["macros"]}} if t["macros"] else {}),
            "produtos_repetidos": [p for p in cand["produtos_repetidos"] if any(i["contrato"] in ids for i in p["itens"])],
            "fornecedores_multiorgao": cand["fornecedores_multiorgao"] if not t["macros"] else
                [f for f in cand["fornecedores_multiorgao"] if set(f["subs"]) & {s for m in t["macros"] for s in MACROCATEGORIAS[m]}],
            "mesmo_servico_mesmo_orgao": [x for x in cand["mesmo_servico_mesmo_orgao"] if any(c["id"] in ids for c in x["contratos"])],
            "funcoes": {k: v for k, v in cand["funcoes"].items()
                        if any(c["id"] in ids for lst in v["por_plataforma"].values() for c in lst)},
            "desenvolvimento": cand["desenvolvimento"] if n == "2" else {},
            "nuvem_e_hospedagem": dentro(cand["nuvem_e_hospedagem"]),
            "atas": [a for a in cand["atas"] if any(c["id"] in ids for c in a["contratos"])],
            "fora_de_ata_em_subcategoria_com_ata": dentro(cand["fora_de_ata_em_subcategoria_com_ata"]),
            "calendario": {k: dentro(v) for k, v in cand["calendario"].items()},
        }
        if not t["macros"]:  # transversal: produtos, funções e nuvem já são tratados nos temas 1–5
            recorte["produtos_repetidos"] = []
            recorte["mesmo_servico_mesmo_orgao"] = []
            recorte["nuvem_e_hospedagem"] = []
            recorte["funcoes"] = {k: {"orgaos": v["orgaos"], "contratos": v["contratos"], "valor": v["valor"]} for k, v in cand["funcoes"].items()}
        arq = pasta / f"candidatos_{n}.json"
        arq.write_text(json.dumps(recorte, ensure_ascii=False, indent=1), encoding="utf-8")
        tamanhos[n] = (len(linhas), round((pasta / f"base_{n}.jsonl").stat().st_size / 1024), round(arq.stat().st_size / 1024))
    return tamanhos


def fatias_vocabulario() -> dict:
    produtos = json.loads((GLOBAL / "produtos_distintos.json").read_text(encoding="utf-8"))
    pasta = GLOBAL / "fatias"
    pasta.mkdir(parents=True, exist_ok=True)
    saida = {}
    for macro, subs in MACROCATEGORIAS.items():
        lst = [p for p in produtos if set(p["subcategorias"]) & set(subs)]
        nome = slug_macro(macro)
        (pasta / f"produtos_{nome}.json").write_text(json.dumps(lst, ensure_ascii=False, indent=1), encoding="utf-8")
        saida[nome] = len(lst)
    return saida
