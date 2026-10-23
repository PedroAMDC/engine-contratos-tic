"""Divide os grupos de todos os órgãos em lotes para os agentes de ficha.

Regras: um lote nunca mistura órgãos; até LIMITE páginas; grupo acima de SOZINHO páginas vai
sozinho; grupos com o mesmo número provável ficam juntos (o agente pode uni-los).
"""

from __future__ import annotations

import json
from itertools import groupby

from ..config import DATA

LIMITE = 120
SOZINHO = 70


def _paginas_grupo(grupo: dict, docs: dict) -> int:
    return sum(docs.get(d["codigo"], 0) for d in grupo["documentos"])


def montar_lotes(orgaos: list[str] | None = None) -> list[dict]:
    pastas = sorted(p for p in DATA.iterdir() if (p / "grupos.json").exists() and not p.name.startswith("_"))
    if orgaos:
        pastas = [p for p in pastas if p.name in {o.upper() for o in orgaos}]

    lotes = []
    for pasta in pastas:
        org = pasta.name
        manifest = json.loads((pasta / "manifest.json").read_text(encoding="utf-8"))
        docs = {d["codigo"]: d.get("extracao", {}).get("paginas", 0)
                for d in manifest["documentos"] if not d.get("duplicata_de")}
        grupos = json.loads((pasta / "grupos.json").read_text(encoding="utf-8"))
        for g in grupos:
            g["paginas"] = _paginas_grupo(g, docs)
            for d in g["documentos"]:
                d["paginas"] = docs.get(d["codigo"], 0)

        # blocos indivisíveis: grupos com o mesmo número provável
        chave = lambda g: g["numero_provavel"] or f"~{g['grupo']}"
        blocos = [list(v) for _, v in groupby(sorted(grupos, key=chave), key=chave)]

        atual, pags, n = [], 0, 1

        def fecha():
            nonlocal atual, pags, n
            if atual:
                lotes.append({"id": f"{org}-L{n:02d}", "orgao": org, "paginas": pags, "grupos": atual})
                n += 1
                atual, pags = [], 0

        for bloco in blocos:
            p = sum(g["paginas"] for g in bloco)
            if p > SOZINHO:
                fecha()
                atual, pags = list(bloco), p
                fecha()
                continue
            if pags + p > LIMITE:
                fecha()
            atual.extend(bloco)
            pags += p
        fecha()

    destino = DATA / "_global" / "lotes.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(lotes, ensure_ascii=False, indent=2), encoding="utf-8")
    return lotes
