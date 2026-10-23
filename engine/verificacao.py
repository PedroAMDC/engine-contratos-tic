"""Etapa 4 — verificação automática da análise de um contrato.

Erros (bloqueiam): formato, valores fora das listas fixas, citações que não existem
no texto extraído, dados pessoais no JSON.
Avisos (examinar): contas que não fecham, citações encontradas só aproximadamente
ou em página vizinha (a página é corrigida automaticamente).
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from functools import lru_cache

from rapidfuzz import fuzz

from .config import CATEGORIAS
from .inventario import dir_orgao
from .perfil import P
from .relatorio.render import RECOMENDACOES

NECESSIDADE = {"Essencial", "Necessário", "Complementar", "Justificativa insuficiente"}
PRIORIDADE = {"P1", "P2", "P3"}
CONFIANCA = {"Alto", "Médio", "Baixo"}
POTENCIAL = {"Alto", "Médio", "Baixo", "Indeterminado"}
NIVEL_CORP = {"Alto", "Médio", "Baixo", "Não determinado"}
NATUREZA = {"Fato", "Inferência", "Hipótese"}
GRAVIDADE = {"Alta", "Média", "Baixa"}
PERIODICIDADE = {"mensal", "anual", "único", "global", None}

OBRIGATORIOS = [
    "grupo", "documentos", "numero", "contratada", "categoria", "objeto_resumido", "objeto",
    "valor_original", "vigencia_inicio", "vigencia_fim", "necessidade", "recomendacao",
    "prioridade", "confianca", "potencial_economia", "veredito", "o_que_fazer", "missao",
    "diagnostico", "questionamentos", "racionalizacao", "corporativo", "inconsistencias",
    "itens", "fontes_campos",
]

CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")


def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[|*#_`>\-–—•·“”\"'«»]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


class _Pagina:
    """Texto normalizado de uma página com o mapa de linhas.

    Linhas = linhas não vazias do texto extraído da página, na ordem em que aparecem
    (em PDFs com texto, correspondem às linhas impressas; em páginas com OCR, a
    parágrafos). Linhas de tabelas detectadas vêm depois e são marcadas como tabela.
    """

    def __init__(self, texto: str, tabelas: list[str]):
        self.inicios, self.linhas, partes, pos = [], [], [], 0
        brutas = [(l, False) for l in texto.splitlines()] + [(l, True) for t in tabelas for l in t.splitlines()]
        n = 0
        for linha, de_tabela in brutas:
            norm = normalizar(linha)
            if not norm:
                continue
            if not de_tabela:
                n += 1
            self.inicios.append(pos)
            self.linhas.append("tabela" if de_tabela else n)
            partes.append(norm)
            pos += len(norm) + 1
        self.texto = " ".join(partes)

    def linhas_de(self, ini: int, fim: int) -> tuple:
        from bisect import bisect_right

        a = self.linhas[max(0, bisect_right(self.inicios, ini) - 1)] if self.linhas else None
        b = self.linhas[max(0, bisect_right(self.inicios, max(ini, fim - 1)) - 1)] if self.linhas else None
        return a, b


@lru_cache(maxsize=256)
def _paginas(sigla: str, doc: str) -> dict[int, _Pagina]:
    arq = dir_orgao(sigla) / "texto" / f"{doc}.json"
    if not arq.exists():
        return {}
    dados = json.loads(arq.read_text(encoding="utf-8"))
    return {
        p["n"]: _Pagina(p["texto"] + ("\n" + p["texto_imagem"] if p.get("texto_imagem") else ""), p.get("tabelas", []))
        for p in dados.get("paginas", [])
    }


def localizar(sigla: str, doc: str, pagina: int, trecho: str) -> tuple[str, int | None, int, tuple]:
    """Retorna (situação, página, nota, (linha_ini, linha_fim)). situação: exato | aproximado | ausente."""
    paginas = _paginas(sigla, doc)
    alvo = normalizar(trecho)
    if not paginas or len(alvo) < 15:
        return "ausente", None, 0, (None, None)
    ordem = [pagina] + [p for p in (pagina - 1, pagina + 1) if p in paginas] + [p for p in paginas if abs(p - pagina) > 1]
    melhor = ("ausente", None, 0, (None, None))
    for p in ordem:
        pg = paginas.get(p)
        if not pg or not pg.texto:
            continue
        i = pg.texto.find(alvo)
        if i >= 0:
            return "exato", p, 100, pg.linhas_de(i, i + len(alvo))
        al = fuzz.partial_ratio_alignment(alvo, pg.texto)
        nota = int(al.score) if al else 0
        if nota > melhor[2]:
            melhor = ("aproximado" if nota >= 88 else "ausente", p, nota, pg.linhas_de(al.dest_start, al.dest_end))
    return melhor


def conferir_fonte(sigla: str, onde: str, f: dict, docs: set | None, obrigatoria: bool, erros: list, avisos: list) -> None:
    """Confere uma citação {doc, pagina, trecho}, corrige página e grava as linhas."""
    doc, pag, trecho = f.get("doc"), f.get("pagina"), f.get("trecho") or ""
    if docs is not None and doc not in docs:
        erros.append(f"{onde}: documento {doc} não pertence ao grupo {sorted(docs)}")
        return
    if not isinstance(pag, int):
        erros.append(f"{onde}: página deve ser inteiro")
        return
    sit, achou, nota, (l1, l2) = localizar(sigla, doc, pag, trecho)
    if sit in ("exato", "aproximado") and achou is not None:
        if achou != pag:
            f["pagina"] = achou
            avisos.append(f"{onde}: trecho está na p. {achou}, não na p. {pag} (corrigido)")
        if sit == "aproximado":
            avisos.append(f"{onde}: trecho encontrado só aproximadamente ({nota}%) em {doc} p. {achou}")
        f["linha_ini"], f["linha_fim"] = l1, l2
        f["conferido"] = sit
        return
    f.pop("conferido", None)
    msg = f"{onde}: trecho não encontrado em {doc} (melhor {nota}%): \"{trecho[:80]}\""
    (erros if obrigatoria else avisos).append(msg)


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _data(x):
    if x is None:
        return True
    try:
        date.fromisoformat(x)
        return True
    except Exception:
        return False


def verificar(sigla: str, grupo: str) -> dict:
    arq = dir_orgao(sigla) / "analise" / "contratos" / f"{grupo}.json"
    erros, avisos = [], []
    try:
        c = json.loads(arq.read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "erros": [f"JSON inválido ou ausente: {e}"], "avisos": []}

    for k in OBRIGATORIOS:
        if k not in c:
            erros.append(f"campo obrigatório ausente: {k}")
    if erros:
        return {"ok": False, "erros": erros, "avisos": avisos}

    # listas fixas
    checks = [
        ("categoria", c["categoria"], set(CATEGORIAS)),
        ("recomendacao", c["recomendacao"], set(RECOMENDACOES)),
        ("necessidade", c["necessidade"], NECESSIDADE),
        ("prioridade", c["prioridade"], PRIORIDADE),
        ("confianca", c["confianca"], CONFIANCA),
        ("potencial_economia", c["potencial_economia"], POTENCIAL),
    ]
    for chave in ("compartilhamento", "estatal_ti", "datacenter"):
        checks.append((f"corporativo.{chave}.nivel", c["corporativo"].get(chave, {}).get("nivel"), NIVEL_CORP))
    for i, d in enumerate(c["diagnostico"]):
        checks.append((f"diagnostico[{i}].natureza", d.get("natureza"), NATUREZA))
    for i, d in enumerate(c["inconsistencias"]):
        checks.append((f"inconsistencias[{i}].gravidade", d.get("gravidade"), GRAVIDADE))
    for nome, valor, permitidos in checks:
        if valor not in permitidos:
            erros.append(f"{nome} = {valor!r} fora da lista: {sorted(p for p in permitidos if p)}")

    for k in ("vigencia_inicio", "vigencia_fim"):
        if not _data(c.get(k)):
            erros.append(f"{k} deve ser AAAA-MM-DD ou null")
    for k in ("valor_original", "valor_atualizado", "valor_mensal", "valor_anual"):
        if c.get(k) is not None and not _num(c[k]):
            erros.append(f"{k} deve ser número ou null")

    # forma do texto para leitura rápida
    if len(c["veredito"]) > 420:
        erros.append("veredito longo demais (máx. ~2 frases)")
    if not 2 <= len(c["o_que_fazer"]) <= 4:
        erros.append("o_que_fazer deve ter de 2 a 4 ações")
    if not 3 <= len(c["questionamentos"]) <= 6:
        erros.append("questionamentos deve ter de 3 a 6 perguntas")
    if len(c["diagnostico"]) < 3:
        erros.append("diagnostico precisa de pelo menos 3 itens")

    # dados pessoais
    if CPF.search(json.dumps(c, ensure_ascii=False)):
        erros.append("o JSON contém um CPF completo: remova dados pessoais")

    # citações
    docs = set(c["documentos"])
    citacoes = []
    for i, d in enumerate(c["diagnostico"]):
        if d.get("natureza") == "Fato":
            if not d.get("fonte"):
                erros.append(f"diagnostico[{i}] é Fato sem fonte")
            else:
                citacoes.append((f"diagnostico[{i}]", d["fonte"], True))
        elif d.get("fonte"):
            citacoes.append((f"diagnostico[{i}]", d["fonte"], False))
    for i, d in enumerate(c["inconsistencias"]):
        if not d.get("fonte"):
            erros.append(f"inconsistencias[{i}] sem fonte")
        else:
            citacoes.append((f"inconsistencias[{i}]", d["fonte"], True))
    for k, f in (c.get("fontes_campos") or {}).items():
        if f:
            citacoes.append((f"fontes_campos.{k}", f, True))
    for i, it in enumerate(c["itens"]):
        if it.get("fonte"):
            citacoes.append((f"itens[{i}]", it["fonte"], False))
    for i, s in enumerate(c.get("sinais_sombreamento", [])):
        if s.get("fonte"):
            citacoes.append((f"sinais_sombreamento[{i}]", s["fonte"], False))

    for onde, f, obrigatoria in citacoes:
        conferir_fonte(sigla, onde, f, docs, obrigatoria, erros, avisos)

    # contas
    soma, completos = 0.0, True
    for i, it in enumerate(c["itens"]):
        q, u, t = it.get("quantidade"), it.get("valor_unitario"), it.get("valor_total")
        if it.get("periodicidade") not in PERIODICIDADE:
            erros.append(f"itens[{i}].periodicidade inválida")
        if _num(t):
            soma += t
        else:
            completos = False
        if _num(q) and _num(u) and _num(t):
            produto = q * u
            if abs(produto - t) > max(0.05, 0.002 * t):
                multiplos = [m for m in (12, 24, 36, 48, 60) if abs(produto * m - t) <= max(0.05, 0.002 * t)]
                if multiplos:
                    avisos.append(f"itens[{i}]: q × unitário × {multiplos[0]} meses = total (confira a periodicidade)")
                else:
                    avisos.append(f"itens[{i}]: {q} × {u:,.2f} = {produto:,.2f}, mas o total é {t:,.2f}")
    vo = c.get("valor_original")
    if completos and c["itens"] and _num(vo) and abs(soma - vo) > max(0.05, 0.002 * vo):
        avisos.append(f"soma dos itens ({soma:,.2f}) ≠ valor_original ({vo:,.2f})")
    if _num(c.get("valor_mensal")) and _num(vo):
        ini, fim = c.get("vigencia_inicio"), c.get("vigencia_fim")
        if ini and fim:
            meses = round((date.fromisoformat(fim) - date.fromisoformat(ini)).days / 30.44)
            if meses and abs(c["valor_mensal"] * meses - vo) > 0.01 * vo:
                avisos.append(f"mensal × {meses} meses de vigência = {c['valor_mensal'] * meses:,.2f}, valor_original = {vo:,.2f}")

    # grava páginas corrigidas e linhas localizadas
    arq.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    res = {"ok": not erros, "erros": erros, "avisos": avisos}
    arq.with_suffix(".verificacao.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def verificar_orgao(sigla: str) -> dict:
    """Confere as fontes da consolidação (alertas, sobreposições, inconsistências cruzadas)."""
    from .inventario import carregar_manifest

    arq = dir_orgao(sigla) / "analise" / "orgao.json"
    erros, avisos = [], []
    try:
        o = json.loads(arq.read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "erros": [f"orgao.json inválido ou ausente: {e}"], "avisos": []}
    docs = {d["codigo"] for d in carregar_manifest(sigla)["documentos"]}

    blocos = [
        ("alertas", o.get("resumo", {}).get("alertas", []), lambda x: x.get("nivel") != "Informativo"),
        ("sombreamentos", o.get("sombreamentos", []), lambda x: True),
        ("inconsistencias_cruzadas", o.get("inconsistencias_cruzadas", []), lambda x: True),
    ]
    for nome, itens, exige in blocos:
        for i, it in enumerate(itens):
            fontes = it.get("fontes") or []
            if exige(it) and not fontes:
                erros.append(f"{nome}[{i}] sem fontes (lista de {{doc, pagina, trecho}})")
            for j, f in enumerate(fontes):
                conferir_fonte(sigla, f"{nome}[{i}].fontes[{j}]", f, docs, True, erros, avisos)

    arq.write_text(json.dumps(o, ensure_ascii=False, indent=2), encoding="utf-8")
    res = {"ok": not erros, "erros": erros, "avisos": avisos}
    arq.with_name("orgao.verificacao.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


LIMITES_DIAGNOSTICO = {
    "manchete": 320, "pontos_atencao.titulo": 80, "pontos_atencao.texto": 420,
    "contratos.leitura": 200, "contratos.diagnostico": 520, "contratos.encaminhamento": 220,
    "governanca.leitura": 360,
}


def verificar_diagnostico(sigla: str) -> dict:
    """Diagnóstico resumido do órgão: tamanho, cobertura dos contratos e fontes."""
    from .inventario import carregar_manifest

    base = dir_orgao(sigla) / "analise"
    arq = base / "diagnostico.json"
    erros, avisos = [], []
    try:
        s = json.loads(arq.read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "erros": [f"diagnostico.json inválido ou ausente: {e}"], "avisos": []}
    docs = {d["codigo"] for d in carregar_manifest(sigla)["documentos"]}
    grupos = {p.stem for p in (base / "contratos").glob("G*.json") if not p.name.endswith(".verificacao.json")}

    def limite(chave, texto, onde):
        if texto and len(texto) > LIMITES_DIAGNOSTICO[chave]:
            erros.append(f"{onde}: {len(texto)} caracteres (máx. {LIMITES_DIAGNOSTICO[chave]})")

    limite("manchete", s.get("manchete", ""), "manchete")
    pa = s.get("pontos_atencao", [])
    if not 3 <= len(pa) <= 5:
        erros.append("pontos_atencao deve ter de 3 a 5 itens")
    for i, p in enumerate(pa):
        limite("pontos_atencao.titulo", p.get("titulo", ""), f"pontos_atencao[{i}].titulo")
        limite("pontos_atencao.texto", p.get("texto", ""), f"pontos_atencao[{i}].texto")
        if p.get("nivel") not in ("Crítico", "Atenção", "Informativo"):
            erros.append(f"pontos_atencao[{i}].nivel inválido")
        if p.get("nivel") != "Informativo" and not p.get("fontes"):
            erros.append(f"pontos_atencao[{i}] sem fontes")
    for chave, maximo in (("decisoes", 5), ("plano", 8), ("sobreposicoes", 3), ("documentos_faltantes", 6)):
        if len(s.get(chave, [])) > maximo:
            erros.append(f"{chave}: no máximo {maximo} itens")
    if not 4 <= len(s.get("perguntas_dirigente", [])) <= 8:
        erros.append("perguntas_dirigente deve ter de 4 a 8 perguntas")
    for k in ("estatal_ti", "datacenter", "compartilhamento"):
        limite("governanca.leitura", s.get("governanca", {}).get(k, {}).get("leitura", ""), f"governanca.{k}")

    vistos = set()
    for i, c in enumerate(s.get("contratos", [])):
        g = c.get("grupo")
        vistos.add(g)
        if g not in grupos:
            erros.append(f"contratos[{i}]: grupo {g} não existe na análise")
        for campo in ("leitura", "diagnostico", "encaminhamento"):
            limite(f"contratos.{campo}", c.get(campo, ""), f"contratos[{i}].{campo}")
        if not 2 <= len(c.get("perguntas", [])) <= 3:
            erros.append(f"contratos[{i}]: 2 ou 3 perguntas")
        if not c.get("fontes"):
            erros.append(f"contratos[{i}] sem fontes")
    for g in sorted(grupos - vistos):
        erros.append(f"contrato {g} não aparece no diagnóstico")

    blocos = [("pontos_atencao", pa), ("sobreposicoes", s.get("sobreposicoes", [])), ("contratos", s.get("contratos", []))]
    for nome, itens in blocos:
        for i, it in enumerate(itens):
            for j, f in enumerate(it.get("fontes") or []):
                conferir_fonte(sigla, f"{nome}[{i}].fontes[{j}]", f, docs, True, erros, avisos)
    if CPF.search(json.dumps(s, ensure_ascii=False)):
        erros.append("o JSON contém um CPF completo: remova dados pessoais")

    arq.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    res = {"ok": not erros, "erros": erros, "avisos": avisos}
    (base / "diagnostico.verificacao.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def checagem_aprovada(sigla: str, nome: str = "checagem.json") -> tuple[bool, str]:
    """A checagem independente de fatos precisa existir e estar aprovada."""
    arq = dir_orgao(sigla) / "analise" / nome
    if not arq.exists():
        return False, f"{nome} ausente: rode a checagem de fatos (prompts/checagem_fatos.md)"
    c = json.loads(arq.read_text(encoding="utf-8"))
    pend = [x for x in c.get("afirmacoes", []) if x.get("status") in ("Não confirmado", "Parcial") and not x.get("corrigido")]
    if pend:
        return False, f"{len(pend)} afirmação(ões) não confirmadas e não corrigidas na checagem"
    return bool(c.get("aprovado")), "ok" if c.get("aprovado") else "checagem não aprovada"


# ---------------------------------------------------------------- fichas (análise estadual)

SITUACOES = {"Vigente", "Vencido nos documentos", "Indeterminada"}
PAPEIS_ESTATAL = {"Contratada", "Intermediária", "Integradora", "Nenhum"}
OBRIGATORIOS_FICHA = [
    "orgao_pasta", "orgao_contratante", "grupos", "documentos", "numero", "contratada",
    "macrocategoria", "subcategoria", "objeto_resumido", "valor_original", "vigencia_inicio",
    "vigencia_fim", "situacao", "estatal_ti", "itens", "temas", "fontes_campos",
]


def verificar_ficha(sigla: str, grupo: str) -> dict:
    from .config import MACROCATEGORIAS

    arq = dir_orgao(sigla) / "fichas" / f"{grupo}.json"
    erros, avisos = [], []
    try:
        c = json.loads(arq.read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "erros": [f"JSON inválido ou ausente: {e}"], "avisos": []}
    for k in OBRIGATORIOS_FICHA:
        if k not in c:
            erros.append(f"campo obrigatório ausente: {k}")
    if erros:
        return {"ok": False, "erros": erros, "avisos": avisos}

    macro, sub = c["macrocategoria"], c["subcategoria"]
    if macro not in MACROCATEGORIAS:
        erros.append(f"macrocategoria {macro!r} fora da lista: {list(MACROCATEGORIAS)}")
    elif sub not in MACROCATEGORIAS[macro]:
        erros.append(f"subcategoria {sub!r} não pertence a {macro!r}: {MACROCATEGORIAS[macro]}")
    if c["situacao"] not in SITUACOES:
        erros.append(f"situacao {c['situacao']!r} fora da lista: {sorted(SITUACOES)}")
    if (c.get("estatal_ti") or {}).get("papel") not in PAPEIS_ESTATAL:
        erros.append(f"estatal_ti.papel fora da lista: {sorted(PAPEIS_ESTATAL)}")
    for k in ("vigencia_inicio", "vigencia_fim"):
        if not _data(c.get(k)):
            erros.append(f"{k} deve ser AAAA-MM-DD ou null")
    for k in ("valor_original", "valor_atualizado", "valor_anual"):
        if c.get(k) is not None and not _num(c[k]):
            erros.append(f"{k} deve ser número ou null")
    if CPF.search(json.dumps(c, ensure_ascii=False)):
        erros.append("o JSON contém um CPF completo: remova dados pessoais")

    docs = set(c["documentos"])
    fc = c.get("fontes_campos") or {}
    for campo in ("contratada", "objeto"):
        if not fc.get(campo):
            erros.append(f"fontes_campos.{campo} obrigatório")
    for campo in ("valor_original", "vigencia_fim"):
        if c.get(campo) is not None and not fc.get(campo):
            erros.append(f"fontes_campos.{campo} obrigatório quando {campo} é informado")
    for k, f in fc.items():
        if f:
            conferir_fonte(sigla, f"fontes_campos.{k}", f, docs, True, erros, avisos)

    soma, completos = 0.0, True
    for i, it in enumerate(c["itens"]):
        if it.get("periodicidade") not in PERIODICIDADE:
            erros.append(f"itens[{i}].periodicidade inválida")
        if _num(it.get("valor_unitario")) and not it.get("fonte"):
            erros.append(f"itens[{i}] tem preço sem fonte")
        if it.get("fonte"):
            conferir_fonte(sigla, f"itens[{i}]", it["fonte"], docs, True, erros, avisos)
        q, u, t = it.get("quantidade"), it.get("valor_unitario"), it.get("valor_total")
        if _num(t):
            soma += t
        else:
            completos = False
        if _num(q) and _num(u) and _num(t) and abs(q * u - t) > max(0.05, 0.002 * t):
            mult = [m for m in (12, 24, 36, 48, 60) if abs(q * u * m - t) <= max(0.05, 0.002 * t)]
            avisos.append(f"itens[{i}]: q × unitário" + (f" × {mult[0]} meses" if mult else "") +
                          (" = total (confira a periodicidade)" if mult else f" = {q * u:,.2f} ≠ total {t:,.2f}"))
    vo = c.get("valor_original")
    if completos and c["itens"] and _num(vo) and abs(soma - vo) > max(0.05, 0.002 * vo):
        avisos.append(f"soma dos itens ({soma:,.2f}) ≠ valor_original ({vo:,.2f})")
    for bloco in ("desenvolvimento", "nuvem"):
        if c.get(bloco) and c[bloco].get("fonte"):
            conferir_fonte(sigla, f"{bloco}.fonte", c[bloco]["fonte"], docs, True, erros, avisos)

    arq.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    res = {"ok": not erros, "erros": erros, "avisos": avisos}
    arq.with_suffix(".verificacao.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


# ---------------------------------------------------------------- temas estaduais

TIPOS_ACHADO = {"Redundância comprovada", "Sobreposição provável", "Dispersão de preço", "Fragmentação",
                f"Estrutura paralela {P.estatal('a')}", "Oportunidade de ata corporativa",
                f"Candidato ao {P.datacenter_central.nome}",
                "Lacuna de governança"}
NIVEIS3 = {"Alto", "Médio", "Baixo"}
CONF3 = {"Alta", "Média", "Baixa"}


def verificar_tema(n: str) -> dict:
    from .config import DATA

    arq = DATA / "_global" / "temas" / f"{n}.json"
    erros, avisos = [], []
    try:
        t = json.loads(arq.read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "erros": [f"JSON inválido ou ausente: {e}"], "avisos": []}
    base = {json.loads(l)["id"]: json.loads(l) for l in (DATA / "_global" / "base.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}

    achados = t.get("achados", [])
    if not 4 <= len(achados) <= 10:
        erros.append("o tema deve ter de 4 a 10 achados")
    for k in t.get("contratos_quadro", []):
        if k not in base:
            erros.append(f"contratos_quadro: {k} não existe na base")
    for i, a in enumerate(achados):
        onde = f"achados[{i}] ({a.get('id')})"
        if a.get("tipo") not in TIPOS_ACHADO:
            erros.append(f"{onde}: tipo fora da lista {sorted(TIPOS_ACHADO)}")
        if a.get("potencial") not in NIVEIS3 or a.get("confianca") not in CONF3:
            erros.append(f"{onde}: potencial (Alto/Médio/Baixo) e confianca (Alta/Média/Baixa) obrigatórios")
        if len(a.get("titulo", "")) > 90:
            erros.append(f"{onde}: título acima de 90 caracteres")
        faltam = [k for k in a.get("contratos", []) if k not in base]
        if faltam:
            erros.append(f"{onde}: contratos inexistentes na base: {faltam}")
        if not a.get("contratos"):
            erros.append(f"{onde}: sem contratos")
        eco = a.get("economia") or {}
        if eco.get("tipo") not in ("calculada", "estimada", "não estimada"):
            erros.append(f"{onde}: economia.tipo inválido")
        if eco.get("tipo") in ("calculada", "estimada") and (not _num(eco.get("valor")) or not eco.get("premissa")):
            erros.append(f"{onde}: economia {eco.get('tipo')} exige valor numérico e premissa")
        if eco.get("tipo") == "calculada" and not eco.get("base_calculo"):
            erros.append(f"{onde}: economia calculada exige base_calculo")
        evs = a.get("evidencias") or []
        if not evs:
            erros.append(f"{onde}: sem evidências")
        for j, ev in enumerate(evs):
            c = base.get(ev.get("contrato"))
            if not c:
                erros.append(f"{onde}.evidencias[{j}]: contrato {ev.get('contrato')} não existe")
                continue
            pasta = ev["contrato"].rsplit("-", 1)[0]
            conferir_fonte(pasta, f"{onde}.evidencias[{j}]", ev, set(c["documentos"]), True, erros, avisos)
        if a.get("tipo") == "Redundância comprovada" and len({base[k]["orgao"] for k in a.get("contratos", []) if k in base}) < 2 \
                and len(a.get("contratos", [])) < 2:
            erros.append(f"{onde}: redundância comprovada exige ao menos dois contratos")

    _verificar_centrais(t, erros)
    arq.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
    res = {"ok": not erros, "erros": erros, "avisos": avisos}
    arq.with_suffix(".verificacao.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def verificar_resumo_estadual() -> dict:
    from .config import DATA

    g = DATA / "_global"
    erros, avisos = [], []
    try:
        r = json.loads((g / "estadual.json").read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "erros": [f"estadual.json inválido ou ausente: {e}"], "avisos": []}
    ids = set()
    for arq in sorted((g / "temas").glob("[1-6].json")):
        ids |= {a["id"] for a in json.loads(arq.read_text(encoding="utf-8")).get("achados", [])}
    if len(r.get("manchete", "")) > 380:
        erros.append("manchete acima de 380 caracteres")
    if not 3 <= len(r.get("mensagens_chave", [])) <= 5:
        erros.append("mensagens_chave: de 3 a 5")
    top = r.get("top_oportunidades", [])
    if not 5 <= len(top) <= 10:
        erros.append("top_oportunidades: de 5 a 10")
    for x in top:
        if x.get("achado") not in ids:
            erros.append(f"top_oportunidades: achado {x.get('achado')} inexistente")
    for t in r.get("temas", []):
        for a in t.get("achados_destaque", []):
            if a not in ids:
                erros.append(f"tema {t.get('n')}: achado {a} inexistente")
        if len(t.get("achados_destaque", [])) > 6:
            erros.append(f"tema {t.get('n')}: no máximo 6 achados em destaque")
    if len(r.get("plano", [])) > 12:
        erros.append("plano: no máximo 12 ações")
    for p in r.get("plano", []):
        if p.get("horizonte") not in ("curto", "medio", "longo"):
            erros.append(f"plano: horizonte inválido em {p.get('acao', '')[:40]}")
    if CPF.search(json.dumps(r, ensure_ascii=False)):
        erros.append("contém CPF")
    res = {"ok": not erros, "erros": erros, "avisos": avisos}
    (g / "estadual.verificacao.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def _verificar_centrais(t: dict, erros: list) -> None:
    for a in t.get("achados", []):
        cen = a.get("contratos_centrais")
        if cen is None:
            continue
        if not cen:
            erros.append(f"{a.get('id')}: contratos_centrais vazio")
        fora = [k for k in cen if k not in a.get("contratos", [])]
        if fora:
            erros.append(f"{a.get('id')}: contratos_centrais fora de contratos: {fora}")
