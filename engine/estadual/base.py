"""Base estadual: consolida as fichas de todos os órgãos.

- Deduplica o mesmo contrato guardado em pastas de órgãos diferentes (ex.: contrato de uma
  secretaria guardado também na pasta de um órgão vinculado), pela chave número + CNPJ da contratada.
- Normaliza fornecedor (CNPJ) e produto (vocabulário em data/_global/vocabulario.json).
- Gera data/_global/base.jsonl e a planilha output/ESTADUAL/Base_Contratos_TIC_<ENTE>.xlsx.
Todos os números do relatório estadual saem daqui (nunca de texto escrito por agente).
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from ..config import DATA, OUTPUT
from ..perfil import P

GLOBAL = DATA / "_global"


def so_digitos(s) -> str:
    return re.sub(r"\D", "", s or "")


def chave_contrato(f: dict) -> str:
    """Número (sequencial + ano) + CNPJ: identifica o mesmo contrato em pastas diferentes."""
    m = re.search(r"(\d{1,5})\s*[/\-.]\s*(20\d{2})", f.get("numero") or "")
    num = f"{int(m[1])}/{m[2]}" if m else (f.get("numero") or "").strip().lower()
    return f"{num}|{so_digitos(f.get('cnpj'))}|{(f.get('orgao_contratante') or '').upper()}"


def slug_macro(macro: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", macro).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def vocabulario() -> dict:
    """Une os vocabulários por macrocategoria (vocabulario_<macro>.json) e o geral, se houver."""
    voc = {}
    for arq in sorted(GLOBAL.glob("vocabulario*.json")):
        voc.update(json.loads(arq.read_text(encoding="utf-8")))
    return voc


def carregar_fichas() -> list[dict]:
    fichas = []
    for arq in sorted(DATA.glob("*/fichas/G*.json")):
        if arq.name.endswith(".verificacao.json"):
            continue
        ver = arq.with_suffix(".verificacao.json")
        if not ver.exists() or not json.loads(ver.read_text(encoding="utf-8")).get("ok"):
            continue  # só entram fichas aprovadas no verificador
        f = json.loads(arq.read_text(encoding="utf-8"))
        f["_pasta"] = arq.parent.parent.name
        f["_grupo"] = arq.stem
        fichas.append(f)
    return fichas


def consolidar() -> list[dict]:
    voc = vocabulario()
    fichas = carregar_fichas()

    por_chave: dict[str, list[dict]] = defaultdict(list)
    for f in fichas:
        por_chave[chave_contrato(f)].append(f)

    nomes_por_cnpj: dict[str, Counter] = defaultdict(Counter)
    for f in fichas:
        nomes_por_cnpj[so_digitos(f.get("cnpj"))][(f.get("contratada") or "").strip()] += 1

    base = []
    for _, grupo in por_chave.items():
        # prefere a ficha da pasta do próprio órgão contratante
        grupo.sort(key=lambda f: (f["_pasta"] != (f.get("orgao_contratante") or "").upper(), f["_pasta"]))
        f = grupo[0]
        cnpj = so_digitos(f.get("cnpj"))
        # a empresa pública de TIC é reconhecida também pela razão social (há fichas com CNPJ
        # digitado errado ou ausente)
        if re.search(P.estatal_ti.padrao_nome, f.get("contratada") or "", re.I):
            cnpj = P.estatal_ti.cnpj
        nome = nomes_por_cnpj[cnpj].most_common(1)[0][0] if cnpj else f.get("contratada")
        valor = f.get("valor_atualizado") or f.get("valor_original")
        itens = []
        for it in f.get("itens", []):
            prod = (it.get("produto") or "").strip()
            itens.append({**it, "produto_canonico": voc.get(prod, prod)})
        base.append({
            "id": f"{f['_pasta']}-{f['_grupo']}",
            "orgao": (f.get("orgao_contratante") or f["_pasta"]).upper(),
            "pastas": sorted({g["_pasta"] for g in grupo}),
            "numero": f.get("numero"),
            "contratada": nome,
            "cnpj": cnpj or None,
            "estatal_ti": bool((f.get("estatal_ti") or {}).get("envolvida")) or cnpj == P.estatal_ti.cnpj,
            "estatal_ti_contratada": cnpj == P.estatal_ti.cnpj,
            "estatal_ti_papel": (f.get("estatal_ti") or {}).get("papel"),
            "modalidade": f.get("modalidade"),
            "ata": f.get("ata"),
            "macro": f["macrocategoria"],
            "sub": f["subcategoria"],
            "objeto": f.get("objeto_resumido"),
            "valor_original": f.get("valor_original"),
            "valor_atualizado": f.get("valor_atualizado"),
            "valor": valor,
            "valor_anual": f.get("valor_anual"),
            "vigencia_inicio": f.get("vigencia_inicio"),
            "vigencia_fim": f.get("vigencia_fim"),
            "situacao": f.get("situacao"),
            "itens": itens,
            "desenvolvimento": f.get("desenvolvimento"),
            "nuvem": f.get("nuvem"),
            "temas": sorted({t.strip().lower() for t in f.get("temas", []) if t}),
            "fontes": f.get("fontes_campos", {}),
            "documentos": f.get("documentos", []),
        })
    base.sort(key=lambda c: (c["macro"], c["sub"], c["orgao"], -(c["valor"] or 0)))
    GLOBAL.mkdir(parents=True, exist_ok=True)
    (GLOBAL / "base.jsonl").write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in base) + "\n", encoding="utf-8")
    return base


def produtos_distintos() -> Path:
    """Lista os nomes de produto como aparecem nas fichas, para o agente de vocabulário."""
    cont = defaultdict(lambda: {"n": 0, "orgaos": set(), "metricas": set(), "fabricantes": set(), "subs": set()})
    for f in carregar_fichas():
        for it in f.get("itens", []):
            p = (it.get("produto") or "").strip()
            if not p:
                continue
            c = cont[p]
            c["n"] += 1
            c["orgaos"].add((f.get("orgao_contratante") or f["_pasta"]).upper())
            c["metricas"].add(it.get("metrica") or "")
            c["fabricantes"].add(it.get("fabricante") or "")
            c["subs"].add(f["subcategoria"])
    lista = sorted(({"produto": p, "ocorrencias": v["n"], "orgaos": sorted(v["orgaos"]), "metricas": sorted(v["metricas"]),
                     "fabricantes": sorted(v["fabricantes"]), "subcategorias": sorted(v["subs"])} for p, v in cont.items()),
                   key=lambda x: (x["subcategorias"], x["produto"].lower()))
    arq = GLOBAL / "produtos_distintos.json"
    GLOBAL.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    return arq


def carregar_base() -> list[dict]:
    arq = GLOBAL / "base.jsonl"
    return [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------------------------------------------------------------- planilha

def planilha(base: list[dict], destino: Path | None = None) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    destino = destino or OUTPUT / "ESTADUAL" / f"Base_Contratos_TIC_{P.ente.sigla}.xlsx"
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    cab = PatternFill("solid", fgColor="0F2A4A")

    def aba(titulo, colunas, linhas, moeda=()):
        ws = wb.create_sheet(titulo)
        ws.append(colunas)
        for c in ws[1]:
            c.font, c.fill, c.alignment = Font(bold=True, color="FFFFFF"), cab, Alignment(wrap_text=True, vertical="center")
        for l in linhas:
            ws.append(l)
        for i, col in enumerate(colunas, 1):
            letra = get_column_letter(i)
            ws.column_dimensions[letra].width = min(60, max(12, len(col) + 2))
            if col in moeda:
                for cel in ws[letra][1:]:
                    cel.number_format = '"R$" #,##0.00'
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        return ws

    wb.remove(wb.active)
    aba("Contratos",
        ["ID", "Órgão", "Pastas", "Número", "Contratada", "CNPJ", P.estatal_ti.sigla, "Macrocategoria", "Subcategoria",
         "Objeto", "Modalidade", "Ata", "Valor original", "Valor atualizado", "Valor anual", "Início", "Fim", "Situação", "Temas"],
        [[c["id"], c["orgao"], ", ".join(c["pastas"]), c["numero"], c["contratada"], c["cnpj"], "Sim" if c["estatal_ti"] else "Não",
          c["macro"], c["sub"], c["objeto"], c["modalidade"],
          f"{c['ata'].get('numero')} ({c['ata'].get('orgao_gerenciador')})" if c.get("ata") else None,
          c["valor_original"], c["valor_atualizado"], c["valor_anual"], c["vigencia_inicio"], c["vigencia_fim"],
          c["situacao"], ", ".join(c["temas"])] for c in base],
        moeda=("Valor original", "Valor atualizado", "Valor anual"))
    aba("Itens",
        ["ID contrato", "Órgão", "Subcategoria", "Produto (canônico)", "Produto (como no contrato)", "Fabricante",
         "Métrica", "Periodicidade", "Quantidade", "Valor unitário", "Valor total", "Fonte"],
        [[c["id"], c["orgao"], c["sub"], it.get("produto_canonico"), it.get("produto"), it.get("fabricante"),
          it.get("metrica"), it.get("periodicidade"), it.get("quantidade"), it.get("valor_unitario"), it.get("valor_total"),
          f"{it['fonte']['doc']} p.{it['fonte']['pagina']}" if it.get("fonte") else None]
         for c in base for it in c["itens"]],
        moeda=("Valor unitário", "Valor total"))

    forn = defaultdict(lambda: {"nome": "", "orgaos": set(), "contratos": 0, "valor": 0.0})
    for c in base:
        k = c["cnpj"] or c["contratada"]
        forn[k]["nome"] = c["contratada"]
        forn[k]["orgaos"].add(c["orgao"])
        forn[k]["contratos"] += 1
        forn[k]["valor"] += c["valor"] or 0
    aba("Fornecedores", ["CNPJ", "Fornecedor", "Nº de órgãos", "Órgãos", "Nº de contratos", "Valor somado"],
        sorted(([k, v["nome"], len(v["orgaos"]), ", ".join(sorted(v["orgaos"])), v["contratos"], v["valor"]]
                for k, v in forn.items()), key=lambda r: (-r[2], -r[5])),
        moeda=("Valor somado",))

    prod = defaultdict(list)
    for c in base:
        for it in c["itens"]:
            if it.get("produto_canonico"):
                prod[(it["produto_canonico"], it.get("metrica"))].append((c["orgao"], it))
    linhas = []
    for (p, met), lst in prod.items():
        precos = [it["valor_unitario"] for _, it in lst if isinstance(it.get("valor_unitario"), (int, float))]
        linhas.append([p, met, len({o for o, _ in lst}), ", ".join(sorted({o for o, _ in lst})), len(lst),
                       min(precos) if precos else None, statistics.median(precos) if precos else None,
                       max(precos) if precos else None])
    aba("Produtos", ["Produto", "Métrica", "Nº de órgãos", "Órgãos", "Nº de itens", "Preço mínimo", "Preço mediano", "Preço máximo"],
        sorted(linhas, key=lambda r: (-r[2], r[0])), moeda=("Preço mínimo", "Preço mediano", "Preço máximo"))

    aba("Desenvolvimento", ["ID contrato", "Órgão", "Contratada", P.estatal_ti.sigla, "Métrica", "Quantidade", "Valor unitário",
                            "Catálogo", "Sistemas-alvo", "Valor do contrato", "Fim"],
        [[c["id"], c["orgao"], c["contratada"], "Sim" if c["estatal_ti"] else "Não", d.get("metrica"), d.get("quantidade"),
          d.get("valor_unitario"), "Sim" if d.get("catalogo_de_servicos") else "Não", ", ".join(d.get("sistemas_alvo") or []),
          c["valor"], c["vigencia_fim"]] for c in base if (d := c.get("desenvolvimento"))],
        moeda=("Valor unitário", "Valor do contrato"))
    aba("Nuvem", ["ID contrato", "Órgão", "Contratada", "Provedor", "Modelo", "Broker", "Capacidade", "Valor do contrato", "Fim"],
        [[c["id"], c["orgao"], c["contratada"], n.get("provedor"), n.get("modelo"), "Sim" if n.get("broker") else "Não",
          n.get("capacidade"), c["valor"], c["vigencia_fim"]] for c in base if (n := c.get("nuvem"))],
        moeda=("Valor do contrato",))
    ws = wb.create_sheet("Sobre", 0)
    ws.append([f"Base de contratos de TIC do {P.ente.poder_medio}"])
    ws["A1"].font = Font(bold=True, size=14, color="0F2A4A")
    for l in [f"Gerada em {date.today():%d/%m/%Y} {P.emissor_com('por')} — {P.emissor_vinculo}.",
              f"{len(base)} contratos de {len({c['orgao'] for c in base})} órgãos, extraídos dos documentos enviados pelos órgãos.",
              "Valores conforme os documentos recebidos; 'Vencido nos documentos' indica ausência de aditivo de prorrogação no material enviado.",
              "Coluna Fonte: código do documento e página (ver inventário de cada órgão)."]:
        ws.append([l])
    ws.column_dimensions["A"].width = 120
    wb.save(destino)
    return destino
