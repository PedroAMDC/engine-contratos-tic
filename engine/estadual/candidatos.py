"""Candidatos a redundância no Estado, calculados de forma determinística sobre a base.

Os agentes temáticos interpretam e verificam estes candidatos; nenhum número do relatório
estadual é escrito à mão. Saída: data/_global/candidatos.json
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import date, timedelta

from ..config import MACROCATEGORIAS
from ..perfil import P
from .base import GLOBAL, carregar_base

# funções em que várias plataformas concorrentes podem coexistir no Estado
FUNCOES = {
    "BI e painéis": ["qlik", "power bi", "tableau", "metabase", "looker"],
    "Escritório e colaboração": ["microsoft 365", "office 365", "office", "google workspace", "g-suite", "g suite"],
    "Simplificação e automação de processos": ["simplifica", "automação de processos", "bpm", "low-code", "low code", "workflow"],
    "Atendimento digital e chatbot": ["chatbot", "whatsapp", "atendimento digital", "assistente virtual"],
    "Assinatura eletrônica": ["assinatura eletrônica", "assinatura digital", "bry", "docusign", "clicksign"],
    "Antivírus e proteção de estações": ["kaspersky", "antivírus", "antivirus", "trend micro", "sophos", "eset", "symantec"],
    "Firewall e WAF": ["firewall", "waf", "fortinet", "fortigate", "palo alto", "checkpoint", "ntsec"],
    "Service desk": ["service desk", "glpi", "servicenow", "help desk", "central de serviços"],
    "CAD e BIM": ["autodesk", "autocad", "revit", "sketchup", "v-ray", "lumion", "bim"],
    "Design gráfico": ["adobe", "corel", "creative cloud"],
    "Pesquisa e consultoria em TIC": ["gartner", "idc", "forrester"],
    "Internet satelital": ["starlink", "satelital", "satélite"],
}


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _texto(c: dict) -> str:
    return " ".join([c.get("objeto") or "", " ".join(c["temas"]), " ".join(
        f"{it.get('produto_canonico') or ''} {it.get('descricao') or ''} {it.get('fabricante') or ''}" for it in c["itens"])]).lower()


def _resumo(c: dict) -> dict:
    return {k: c.get(k) for k in ("id", "orgao", "numero", "contratada", "sub", "objeto", "valor", "valor_anual", "vigencia_fim", "situacao", "estatal_ti")}


def calcular(data_ref: str | None = None) -> dict:
    base = carregar_base()
    ref = date.fromisoformat(data_ref) if data_ref else date.today()
    # contratos "vencidos nos documentos" quase sempre seguem ativos (aditivo não enviado):
    # entram em todas as análises, com a situação exibida para o leitor
    vigentes = base

    # ---------------- panorama
    tot = lambda cs: round(sum(c["valor"] or 0 for c in cs), 2)
    anual = lambda cs: round(sum(c["valor_anual"] or 0 for c in cs), 2)
    panorama = {
        "contratos": len(base), "vigentes": sum(c["situacao"] == "Vigente" for c in base),
        "vencidos_nos_documentos": sum(c["situacao"] == "Vencido nos documentos" for c in base),
        "orgaos": len({c["orgao"] for c in base}),
        "fornecedores": len({c["cnpj"] or c["contratada"] for c in base}),
        "valor_total": tot(base), "valor_anual": anual(base),
        "com_valor_anual": sum(1 for c in base if c["valor_anual"]),
        "estatal_ti": {"contratos": sum(c["estatal_ti_contratada"] for c in base),
                       "valor": tot([c for c in base if c["estatal_ti_contratada"]]),
                       "orgaos": len({c["orgao"] for c in base if c["estatal_ti_contratada"]}),
                       "pct": round(100 * tot([c for c in base if c["estatal_ti_contratada"]]) / (tot(base) or 1), 1)},
        "estatal_ti_envolvida": {"contratos": sum(c["estatal_ti"] for c in base), "valor": tot([c for c in base if c["estatal_ti"]]),
                                 "orgaos": len({c["orgao"] for c in base if c["estatal_ti"]})},
        "por_macro": {}, "orgao_x_macro": defaultdict(dict),
    }
    for macro, subs in MACROCATEGORIAS.items():
        cs = [c for c in base if c["macro"] == macro]
        panorama["por_macro"][macro] = {
            "contratos": len(cs), "orgaos": len({c["orgao"] for c in cs}), "valor": tot(cs), "valor_anual": anual(cs),
            "por_sub": {s: {"contratos": len(x), "orgaos": len({c["orgao"] for c in x}), "valor": tot(x), "valor_anual": anual(x)}
                        for s in subs if (x := [c for c in cs if c["sub"] == s])},
        }
        for c in cs:
            d = panorama["orgao_x_macro"][c["orgao"]]
            d[macro] = round(d.get(macro, 0) + (c["valor"] or 0), 2)
    panorama["orgao_x_macro"] = dict(panorama["orgao_x_macro"])

    # ---------------- produtos repetidos e dispersão de preço (mesma métrica e periodicidade)
    por_produto = defaultdict(list)
    for c in vigentes:
        for it in c["itens"]:
            if it.get("produto_canonico"):
                por_produto[(it["produto_canonico"], it.get("metrica"), it.get("periodicidade"))].append((c, it))
    produtos = []
    for (prod, met, per), lst in por_produto.items():
        orgaos = sorted({c["orgao"] for c, _ in lst})
        if len(orgaos) < 2:
            continue
        precos = [it["valor_unitario"] for _, it in lst if _num(it.get("valor_unitario"))]
        med = statistics.median(precos) if precos else None
        excesso = round(sum(max(0, it["valor_unitario"] - med) * it["quantidade"]
                            for _, it in lst if med and _num(it.get("valor_unitario")) and _num(it.get("quantidade"))), 2) if med else None
        produtos.append({
            "produto": prod, "metrica": met, "periodicidade": per, "orgaos": orgaos, "n_orgaos": len(orgaos),
            "itens": [{"contrato": c["id"], "orgao": c["orgao"], "contratada": c["contratada"], "quantidade": it.get("quantidade"),
                       "valor_unitario": it.get("valor_unitario"), "valor_total": it.get("valor_total"), "fonte": it.get("fonte")}
                      for c, it in lst],
            "preco_min": min(precos) if precos else None, "preco_mediano": med, "preco_max": max(precos) if precos else None,
            "dispersao": round(max(precos) / min(precos), 2) if precos and min(precos) > 0 else None,
            "excesso_sobre_mediana": excesso,
            "premissa_excesso": "Soma, item a item, de (preço unitário − mediana) × quantidade, só para preços acima da mediana, "
                                "mesma métrica e periodicidade. Indicativo; depende de comparabilidade das especificações.",
        })
    produtos.sort(key=lambda p: (-(p["excesso_sobre_mediana"] or 0), -p["n_orgaos"]))

    # ---------------- fornecedores em vários órgãos
    forn = defaultdict(list)
    for c in base:
        forn[c["cnpj"] or c["contratada"]].append(c)
    fornecedores = sorted(
        ({"cnpj": k, "nome": cs[0]["contratada"], "n_orgaos": len({c["orgao"] for c in cs}), "orgaos": sorted({c["orgao"] for c in cs}),
          "contratos": len(cs), "valor": tot(cs), "subs": sorted({c["sub"] for c in cs})}
         for k, cs in forn.items() if len({c["orgao"] for c in cs}) >= 2),
        key=lambda f: (-f["n_orgaos"], -f["valor"]))

    # ---------------- várias contratações do mesmo serviço no mesmo órgão
    mesmo_orgao = []
    agrup = defaultdict(list)
    for c in vigentes:
        agrup[(c["orgao"], c["sub"])].append(c)
    for (org, sub), cs in agrup.items():
        if len(cs) >= 2 and sub not in ("Suprimentos de informática", "Outros serviços de TIC", "Outras licenças", "Equipamentos e locação"):
            mesmo_orgao.append({"orgao": org, "sub": sub, "contratos": [_resumo(c) for c in cs], "valor": tot(cs)})
    mesmo_orgao.sort(key=lambda x: -x["valor"])

    # ---------------- plataformas concorrentes por função
    funcoes = {}
    for funcao, chaves in FUNCOES.items():
        achados = [c for c in vigentes if any(k in _texto(c) for k in chaves)]
        if not achados:
            continue
        por_plataforma = defaultdict(list)
        for c in achados:
            t = _texto(c)
            nomes = [k for k in chaves if k in t]
            por_plataforma[nomes[0]].append(_resumo(c))
        funcoes[funcao] = {"orgaos": sorted({c["orgao"] for c in achados}), "contratos": len(achados), "valor": tot(achados),
                           "por_plataforma": dict(por_plataforma)}

    # ---------------- desenvolvimento: preço por unidade de esforço
    dev = [c for c in vigentes if c.get("desenvolvimento")]
    por_metrica = defaultdict(list)
    for c in dev:
        d = c["desenvolvimento"]
        por_metrica[(d.get("metrica") or "?").upper()].append({**_resumo(c), "quantidade": d.get("quantidade"),
                                                               "valor_unitario": d.get("valor_unitario"),
                                                               "catalogo": d.get("catalogo_de_servicos"), "fonte": d.get("fonte")})
    desenvolvimento = {m: {"contratos": lst, "n_orgaos": len({x["orgao"] for x in lst}), "valor": round(sum(x["valor"] or 0 for x in lst), 2),
                           "preco_min": min((x["valor_unitario"] for x in lst if _num(x["valor_unitario"])), default=None),
                           "preco_max": max((x["valor_unitario"] for x in lst if _num(x["valor_unitario"])), default=None),
                           "sem_catalogo": sum(1 for x in lst if not x["catalogo"]),
                           "estatal_ti": sum(1 for x in lst if x["estatal_ti"])}
                       for m, lst in por_metrica.items()}

    # ---------------- nuvem e hospedagem (candidatos ao datacenter central do perfil)
    infra_subs = {"Nuvem pública", "Nuvem privada e hospedagem", "Data center e colocation", "Servidores, storage e backup"}
    nuvem = [dict(_resumo(c), **{"provedor": (c.get("nuvem") or {}).get("provedor"), "modelo": (c.get("nuvem") or {}).get("modelo"),
                                 "broker": (c.get("nuvem") or {}).get("broker")})
             for c in vigentes if c.get("nuvem") or c["sub"] in infra_subs]

    # ---------------- atas
    import re

    def chave_ata(ata: dict) -> str:
        """'016/2024', '016/2024/<GERENCIADOR>' e 'ARP nº 16/2024' são a mesma ata."""
        num = ata.get("numero") or ""
        m = re.search(r"(\d{1,4})\s*[/\-.]\s*(20\d{2})", num)
        ger = (ata.get("orgao_gerenciador") or "").upper().strip()
        if not ger:
            ger = next((g for g in P.atas.gerenciadores if g.upper() in num.upper()), "?")
        return f"{int(m[1]):03d}/{m[2]} ({ger})" if m else f"{num.strip()} ({ger})"

    atas = defaultdict(list)
    for c in base:
        if c.get("ata") and c["ata"].get("numero"):
            atas[chave_ata(c["ata"])].append(_resumo(c))
    atas_lst = sorted(({"ata": k, "orgaos": sorted({x["orgao"] for x in v}), "contratos": v, "valor": round(sum(x["valor"] or 0 for x in v), 2)}
                       for k, v in atas.items()), key=lambda a: -len(a["orgaos"]))
    subs_com_ata = defaultdict(set)
    for a in atas_lst:
        for x in a["contratos"]:
            subs_com_ata[x["sub"]].add(a["ata"])
    fora_de_ata = [_resumo(c) for c in vigentes if not c.get("ata") and c["sub"] in subs_com_ata]

    # ---------------- calendário
    def janela(c, meses):
        fim = c.get("vigencia_fim")
        return fim and ref <= date.fromisoformat(fim) <= ref + timedelta(days=30.44 * meses)
    calendario = {
        "vencem_6m": [_resumo(c) for c in base if janela(c, 6)],
        "vencem_12m": [_resumo(c) for c in base if janela(c, 12) and not janela(c, 6)],
        "vencem_24m": [_resumo(c) for c in base if janela(c, 24) and not janela(c, 12)],
        "vencidos_nos_documentos": [_resumo(c) for c in base if c["situacao"] == "Vencido nos documentos"],
    }

    resultado = {
        "data_referencia": ref.isoformat(), "panorama": panorama, "produtos_repetidos": produtos,
        "fornecedores_multiorgao": fornecedores, "mesmo_servico_mesmo_orgao": mesmo_orgao, "funcoes": funcoes,
        "desenvolvimento": desenvolvimento, "nuvem_e_hospedagem": nuvem, "atas": atas_lst,
        "fora_de_ata_em_subcategoria_com_ata": fora_de_ata, "calendario": calendario,
    }
    (GLOBAL / "candidatos.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado
