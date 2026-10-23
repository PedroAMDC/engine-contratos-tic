"""Etapa 3 — agrupa os documentos de um órgão por contrato.

Heurística determinística (número do contrato no nome do arquivo e nas primeiras
páginas + tipo do documento). O resultado em data/<ORGAO>/grupos.json é revisado
pelo orquestrador antes da análise, e pode ser editado à mão.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict

from .inventario import carregar_manifest, dir_orgao

NUM = re.compile(
    r"(?:contrato|termo\s+de\s+ades[aã]o|instrumento\s+contratual|\bctr\.?|\bi\.?c\.?(?=\s*n?[º°o.]*\s*\d))"
    r"\s*(?:administrativo|adm\.?)?\s*(?:de\s+\w+\s+)?n?\s*[º°o.]*\s*[:\-]?\s*(\d{1,5})\s*[/\-.]\s*(20\d{2}|\d{2})\b",
    re.I,
)
TIPOS = [
    ("Aditivo", r"termo\s+aditivo|\baditivo\b|\d+\s*[º°o]\s*ta\b"),
    ("Apostilamento", r"apostilamento|termo\s+de\s+apostila"),
    ("Termo de referência", r"termo\s+de\s+refer[eê]ncia|\btr\b"),
    ("Nota de empenho", r"nota\s+de\s+empenho|\bempenho\b"),
    ("Ordem de serviço", r"ordem\s+de\s+servi[cç]o|\bos\s*n"),
    ("Ata de registro de preços", r"ata\s+de\s+registro"),
    ("Proposta", r"\bproposta\b"),
    ("Publicação", r"\bextrato\b"),
]
TITULO_CONTRATO = re.compile(r"contrato\s+(administrativo|adm\.?)?\s*n", re.I)


def _tipo(texto: str, inicio_documento: bool = False) -> str:
    if inicio_documento:
        # no texto da 1ª página, o título vence menções incidentais (ex.: "DOE 22/07/2011")
        cabeca = texto[:700]
        for nome, padrao in TIPOS[:2]:
            if re.search(padrao, cabeca, re.I):
                return nome
        if TITULO_CONTRATO.search(cabeca):
            return "Contrato"
        texto = cabeca
    for nome, padrao in TIPOS:
        if re.search(padrao, texto, re.I):
            return nome
    return "Contrato"


def _numero(texto: str) -> str | None:
    m = NUM.search(texto)
    if not m:
        return None
    n, ano = int(m[1]), m[2]
    ano = ano if len(ano) == 4 else f"20{ano}"
    return f"{n:03d}/{ano}"


def agrupar(sigla: str) -> list[dict]:
    base = dir_orgao(sigla)
    manifest = carregar_manifest(sigla)
    grupos: dict[str, list] = defaultdict(list)
    soltos = []

    for d in manifest["documentos"]:
        if d.get("status") != "baixado" or d.get("duplicata_de"):
            continue
        inicio = ""
        arq = base / "texto" / f"{d['codigo']}.json"
        if arq.exists():
            pags = json.loads(arq.read_text(encoding="utf-8")).get("paginas", [])
            inicio = " ".join(p["texto"] for p in pags[:2])[:4000]
        tipo = _tipo(d["nome"])
        if tipo == "Contrato":
            tipo = _tipo(inicio, inicio_documento=True)
        numero = _numero(d["nome"].replace("-", "/", 1)) or _numero(inicio)
        reg = {"codigo": d["codigo"], "nome": d["nome"], "tipo": tipo}
        if numero:
            grupos[numero].append(reg)
        else:
            soltos.append(reg)

    saida = []
    for i, (numero, docs) in enumerate(sorted(grupos.items(), key=lambda x: (x[0][-4:], x[0])), 1):
        saida.append({"grupo": f"G{i:02d}", "numero_provavel": numero, "documentos": docs, "confirmado": False})
    for reg in soltos:
        saida.append({"grupo": f"G{len(saida) + 1:02d}", "numero_provavel": None, "documentos": [reg], "confirmado": False})

    (base / "grupos.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    return saida
