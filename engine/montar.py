"""Etapa 6 — monta o relatório do órgão a partir das análises e gera o PDF.

Entradas: data/<ORGAO>/analise/contratos/G*.json (um por contrato) e
data/<ORGAO>/analise/orgao.json (consolidação). Também atualiza o índice global
data/_global/contratos.jsonl, base da futura triangulação entre órgãos.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .config import DATA, OUTPUT
from .inventario import carregar_manifest, dir_orgao
from .perfil import P
from .relatorio import render

OBJETIVO = (
    "Diagnosticar, com base nos documentos contratuais recebidos, se os recursos destinados à "
    "tecnologia estão sendo empregados de forma necessária, proporcional, eficiente e alinhada ao "
    f"ecossistema tecnológico do {P.ente.governo}, apontando sobreposições entre contratos, "
    "inconsistências documentais e oportunidades de racionalização."
)


def _local(f: dict) -> str:
    """'D02 · p. 4, l. 12–14' (linhas do texto da página; 'tabela' quando o trecho está numa tabela)."""
    s = f"{f['doc']} · p. {f['pagina']}"
    a, b = f.get("linha_ini"), f.get("linha_fim")
    if a == "tabela" or b == "tabela":
        s += ", tabela"
    elif a:
        s += f", l. {a}" + (f"–{b}" if b and b != a else "")
    return s


class Evidencias:
    """Numera cada citação (E001, E002...) e monta o anexo de evidências."""

    def __init__(self, nomes: dict):
        self.nomes, self.itens, self._chave = nomes, [], {}

    def ref(self, f: dict | None, uso: str) -> str | None:
        if not f or not f.get("trecho"):
            return _local(f) if f else None
        chave = (f["doc"], f["pagina"], f["trecho"].strip())
        if chave not in self._chave:
            eid = f"E{len(self.itens) + 1:03d}"
            self._chave[chave] = eid
            self.itens.append({
                "id": eid, "doc": f["doc"], "documento": self.nomes.get(f["doc"], {}).get("nome", ""),
                "local": _local(f), "trecho": f["trecho"].strip(), "usos": [],
                "conferido": f.get("conferido", "—"),
            })
        item = self.itens[int(self._chave[chave][1:]) - 1]
        if uso not in item["usos"]:
            item["usos"].append(uso)
        return f"{item['id']} · {item['local']}"


def carregar_contratos(sigla: str) -> list[dict]:
    pasta = dir_orgao(sigla) / "analise" / "contratos"
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(pasta.glob("G*.json"))
        if not p.name.endswith(".verificacao.json")
    ]


def montar(sigla: str, data_referencia: str | None = None, versao: str = "1.0", exigir_checagem: bool = True) -> dict:
    from .verificacao import checagem_aprovada, verificar_orgao

    base = dir_orgao(sigla)
    vo = verificar_orgao(sigla)
    if not vo["ok"]:
        raise SystemExit("Consolidação com fontes inválidas:\n  " + "\n  ".join(vo["erros"]))
    if exigir_checagem:
        ok, motivo = checagem_aprovada(sigla)
        if not ok:
            raise SystemExit(f"Checagem de fatos não aprovada: {motivo}")
    manifest = carregar_manifest(sigla)
    orgao = json.loads((base / "analise" / "orgao.json").read_text(encoding="utf-8"))
    contratos = carregar_contratos(sigla)
    nomes = {d["codigo"]: d for d in manifest["documentos"]}
    grupos = json.loads((base / "grupos.json").read_text(encoding="utf-8"))
    tipo_doc = {d["codigo"]: d["tipo"] for g in grupos for d in g["documentos"]}
    grupo_num = {c["grupo"]: c["numero"] for c in contratos}
    doc_contrato = {d: c["numero"] for c in contratos for d in c["documentos"]}

    pendentes = [c["grupo"] for c in contratos if not json.loads(
        (base / "analise" / "contratos" / f"{c['grupo']}.verificacao.json").read_text(encoding="utf-8")
    ).get("ok")] if contratos else []
    if pendentes:
        raise SystemExit(f"Contratos sem verificação OK: {pendentes}. Rode `validar` e corrija.")

    ref = data_referencia or orgao.get("data_referencia") or date.today().isoformat()
    ev = Evidencias(nomes)

    # consolidação primeiro: as referências dos alertas aparecem no início do anexo
    resumo = orgao["resumo"]
    for a in resumo.get("alertas", []):
        a["fontes_txt"] = [ev.ref(f, f"Alerta: {a['titulo']}") for f in a.get("fontes", [])]
    sombreamentos = []
    for s in orgao.get("sombreamentos", []):
        refs = [ev.ref(f, f"Sobreposição: {' × '.join(s['contratos'])}") for f in s.get("fontes", [])]
        sombreamentos.append({**s, "evidencia": "; ".join(refs) if refs else s.get("evidencia", "")})

    cts, incs, solicitados = [], [], []
    for c in contratos:
        for campo, f in (c.get("fontes_campos") or {}).items():
            ev.ref(f, f"{c['numero']}: {campo.replace('_', ' ')}")
        cts.append({
            "numero": c["numero"],
            "contratada": c["contratada"],
            "cnpj": c.get("cnpj"),
            "categoria": c["categoria"],
            "objeto_resumido": c["objeto_resumido"],
            "objeto": c["objeto"],
            "valor_original": c.get("valor_original"),
            "valor_atualizado": c.get("valor_atualizado"),
            "valor_mensal": c.get("valor_mensal"),
            "valor_anual": c.get("valor_anual"),
            "vigencia_inicio": c.get("vigencia_inicio"),
            "vigencia_fim": c.get("vigencia_fim"),
            "prazo": c.get("prazo") or "não informado",
            "prorrogacao": c.get("prorrogacao") or "não informada",
            "quantitativos": c.get("quantitativos") or ["não identificados"],
            "sla": c.get("sla") or "Não identificado no documento.",
            "condicoes_alteracao": c.get("condicoes_alteracao") or "Não identificadas no documento.",
            "documentos": [
                {"arquivo": f"{d} · {nomes[d]['nome']}", "tipo": tipo_doc.get(d, "—"),
                 "paginas": nomes[d].get("extracao", {}).get("paginas", "—")}
                for d in c["documentos"]
            ],
            "necessidade": c["necessidade"],
            "recomendacao": c["recomendacao"],
            "prioridade": c["prioridade"],
            "confianca": c["confianca"],
            "potencial_economia": c["potencial_economia"],
            "veredito": c["veredito"],
            "o_que_fazer": c["o_que_fazer"],
            "missao": c["missao"],
            "diagnostico": [
                {"natureza": d["natureza"], "texto": d["texto"],
                 "fonte": ev.ref(d.get("fonte"), f"{c['numero']}: análise ({d['natureza'].lower()})")}
                for d in c["diagnostico"]
            ],
            "questionamentos": c["questionamentos"],
            "racionalizacao": c["racionalizacao"],
            "corporativo": c["corporativo"],
        })
        for i in c["inconsistencias"]:
            incs.append({
                "contrato": c["numero"], "tipo": i["tipo"], "descricao": i["descricao"],
                "evidencia": ev.ref(i.get("fonte"), f"{c['numero']}: inconsistência ({i['tipo']})"),
                "trecho": (i.get("fonte") or {}).get("trecho"),
                "gravidade": i["gravidade"], "encaminhamento": i["encaminhamento"],
            })
        for s in c.get("documentos_faltantes", []):
            solicitados.append({"contrato": c["numero"], **s})

    for i in orgao.get("inconsistencias_cruzadas", []):
        refs = [ev.ref(f, f"Inconsistência cruzada: {i['tipo']}") for f in i.get("fontes", [])]
        incs.append({**i, "evidencia": "; ".join(refs) if refs else i.get("evidencia", ""), "trecho": None})
    solicitados.extend(orgao.get("documentos_solicitados", []))

    inventario = []
    for d in manifest["documentos"]:
        ext = d.get("extracao", {})
        if d.get("duplicata_de"):
            situacao, obs = "Duplicata", f"igual a {d['duplicata_de']}"
        elif d.get("status") != "baixado":
            situacao, obs = "Erro no download", d.get("erro", "")[:80]
        elif ext.get("status") not in (None, "ok"):
            situacao, obs = "Não lido", ext.get("status")
        elif d["codigo"] in doc_contrato:
            situacao = "Analisado"
            obs = f"{ext.get('ocr')} p. com OCR" if ext.get("ocr") else None
        else:
            situacao, obs = "Não contratual", orgao.get("observacoes_inventario", {}).get(d["codigo"])
        inventario.append({
            "codigo": d["codigo"],
            "arquivo": (f"{d['caminho_drive']}/" if d.get("caminho_drive") else "") + d["nome"],
            "contrato": doc_contrato.get(d["codigo"]),
            "tipo": tipo_doc.get(d["codigo"], "—"),
            "paginas": ext.get("paginas", "—"),
            "situacao": situacao,
            "obs": obs,
        })

    rel = {
        "meta": {
            "modelo": False,
            "orgao_sigla": sigla,
            "orgao_nome": orgao["orgao_nome"],
            "unidade_emissora": P.emissor_completo,
            "data_referencia": ref,
            "data_emissao": date.today().isoformat(),
            "versao": versao,
            "classificacao": P.relatorio.classificacao,
            "finalidade": orgao.get("finalidade", P.relatorio.finalidade),
            "objetivo": OBJETIVO,
        },
        "orgao": orgao["orgao"],
        "resumo": resumo,
        "contratos": cts,
        "sombreamentos": sombreamentos,
        "evidencias": ev.itens,
        "checagem": _resumo_checagem(base),
        "inconsistencias": incs,
        "consolidacao": orgao.get("consolidacao", []),
        "plano_acao": orgao.get("plano_acao", []),
        "conclusao": orgao["conclusao"],
        "inventario": inventario,
        "documentos_solicitados": solicitados,
        "base_normativa": orgao.get("base_normativa", []),
    }
    (base / "relatorio.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    _indice_global(sigla, contratos)
    return rel


def _resumo_checagem(base: Path) -> dict | None:
    arq = base / "analise" / "checagem.json"
    if not arq.exists():
        return None
    c = json.loads(arq.read_text(encoding="utf-8"))
    afs = c.get("afirmacoes", [])
    return {
        "data": c.get("data"),
        "total": len(afs),
        "confirmadas": sum(a.get("status") == "Confirmado" for a in afs),
        "corrigidas": sum(bool(a.get("corrigido")) for a in afs),
        "removidas": sum(a.get("status") == "Removido" for a in afs),
    }


def _indice_global(sigla: str, contratos: list[dict]) -> None:
    arq = DATA / "_global" / "contratos.jsonl"
    arq.parent.mkdir(parents=True, exist_ok=True)
    linhas = []
    if arq.exists():
        linhas = [l for l in arq.read_text(encoding="utf-8").splitlines() if l and json.loads(l)["orgao"] != sigla]
    for c in contratos:
        linhas.append(json.dumps({
            "orgao": sigla,
            "numero": c["numero"],
            "contratada": c["contratada"],
            "cnpj": c.get("cnpj"),
            "categoria": c["categoria"],
            "objeto_resumido": c["objeto_resumido"],
            "valor_original": c.get("valor_original"),
            "valor_atualizado": c.get("valor_atualizado"),
            "valor_anual": c.get("valor_anual"),
            "vigencia_inicio": c.get("vigencia_inicio"),
            "vigencia_fim": c.get("vigencia_fim"),
            "itens": [{k: it.get(k) for k in ("produto_normalizado", "fabricante", "metrica", "quantidade",
                                               "valor_unitario", "valor_total", "periodicidade")} for it in c["itens"]],
            "temas": sorted({s["tema"] for s in c.get("sinais_sombreamento", [])}),
            "recomendacao": c["recomendacao"],
            "prioridade": c["prioridade"],
        }, ensure_ascii=False))
    arq.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def gerar_pdf(sigla: str) -> Path:
    rel = json.loads((dir_orgao(sigla) / "relatorio.json").read_text(encoding="utf-8"))
    nome = f"Diagnostico_Contratos_TIC_{sigla}_{rel['meta']['data_referencia']}.pdf"
    return render.pdf(rel, OUTPUT / sigla / nome)
