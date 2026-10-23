"""Renderiza o relatório de um órgão (JSON -> HTML -> PDF).

Os agregados (totais, contagens, distribuições, vencimentos) são calculados aqui,
de forma determinística, e nunca copiados do texto gerado pela análise.

Uso:
    python -m engine.relatorio.render <dados.json> <saida.pdf> [--html]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..perfil import P

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates" / "relatorio"

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "msedge",
    "google-chrome",
    "chromium",
]

# código oficial (prompt mestre) -> rótulo de leitura
RECOMENDACOES = {
    "MANTER": "Manter",
    "MANTER COM AJUSTES": "Manter com ajustes",
    "REDIMENSIONAR": "Redimensionar",
    "RENEGOCIAR": "Renegociar",
    "CONSOLIDAR": "Consolidar",
    f"AVALIAR ATENDIMENTO {P.estatal('por').upper()}": f"Avaliar atendimento {P.estatal('por')}",
    f"AVALIAR MIGRAÇÃO AO {P.datacenter_central.nome.upper()}": "Avaliar migração ao Data Center",
    "AVALIAR NÃO RENOVAÇÃO": "Avaliar não renovação",
    "REVISÃO PRIORITÁRIA": "Revisão prioritária",
    "DADOS INSUFICIENTES": "Dados insuficientes",
}

PRIORIDADES = {"P1": "Alta", "P2": "Média", "P3": "Baixa"}

# termos técnicos explicados no anexo, quando aparecem no relatório
GLOSSARIO = {
    "Apostilamento": "Registro simples no contrato para corrigir dados ou aplicar reajuste previsto, sem necessidade de termo aditivo.",
    "Termo aditivo": "Documento que altera o contrato: prazo, valor, quantidades ou cláusulas.",
    "Supressão": "Redução formal de quantidades ou valor do contrato, limitada a 25% pela Lei 14.133/2021.",
    "SaaS": "Software como serviço: o sistema roda na nuvem do fornecedor e é pago por assinatura.",
    "UST": "Unidade de Serviço Técnico: medida usada para pagar serviços de TI por esforço, como horas padronizadas.",
    "Fábrica de software": "Contrato para desenvolver e manter sistemas sob demanda, por ordens de serviço.",
    "SLA": "Nível de serviço acordado: disponibilidade, prazos de atendimento e penalidades.",
    "RPO": "Quanto de dados se aceita perder em uma falha (ex.: 24 h = último backup diário).",
    "RTO": "Tempo máximo para restabelecer o serviço após uma falha.",
    "vCPU": "Processador virtual: unidade de capacidade de processamento em nuvem.",
    "Nuvem privada": f"Infraestrutura virtualizada dedicada ao Estado, operada por um provedor (no caso, {P.estatal()}).",
    "ICP-Brasil": "Infraestrutura oficial de certificação digital, que dá validade jurídica a assinaturas eletrônicas.",
    "e-CPF": "Certificado digital de pessoa física, usado para assinar documentos e acessar sistemas.",
    "e-CNPJ": "Certificado digital de pessoa jurídica.",
    "Outsourcing": "Terceirização de um serviço completo (equipamento, manutenção e insumos).",
    "Franquia": "Quantidade mínima incluída no preço mensal (ex.: páginas impressas).",
    "Bilhetagem": "Relatório que registra o uso real, como páginas impressas por equipamento.",
    P.datacenter_central.nome: P.datacenter_central.descricao,
    P.estatal_ti.sigla: f"{P.estatal_ti.nome}, {P.estatal_ti.descricao}.",
    "LGPD": "Lei Geral de Proteção de Dados Pessoais (Lei 13.709/2018).",
    "Sombreamento": "Sobreposição de objeto ou escopo entre contratos, que pode levar a pagar duas vezes pelo mesmo serviço.",
}


# ---------------------------------------------------------------- formatação

def brl(valor, vazio="Não identificado"):
    if valor is None or valor == "":
        return vazio
    s = f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def brl_curto(valor):
    if valor is None:
        return "—"
    v = float(valor)
    for limite, sufixo in ((1e9, "bi"), (1e6, "mi"), (1e3, "mil")):
        if abs(v) >= limite:
            n = f"{v / limite:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"R$ {n} {sufixo}"
    return brl(v)


def parse_data(s):
    if not s:
        return None
    if isinstance(s, date):
        return s
    return datetime.strptime(s, "%Y-%m-%d").date()


def data_br(s, vazio="Não identificado"):
    d = parse_data(s)
    return d.strftime("%d/%m/%Y") if d else vazio


def pct(parte, todo):
    return 0 if not todo else round(100 * parte / todo, 1)


def slug(s):
    import unicodedata

    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")


# ---------------------------------------------------------------- agregados

def enriquecer(dados: dict) -> dict:
    ref = parse_data(dados["meta"]["data_referencia"])
    contratos = dados["contratos"]

    dados.setdefault("inconsistencias", [])
    dados.setdefault("sombreamentos", [])
    dados.setdefault("inventario", [])
    for i, c in enumerate(contratos, 1):
        c.setdefault("id", slug(c["numero"]))
        c["valor_referencia"] = c.get("valor_atualizado") or c.get("valor_original")
        fim = parse_data(c.get("vigencia_fim"))
        c["dias_para_fim"] = (fim - ref).days if fim else None

    ordenados = sorted(contratos, key=lambda c: c["valor_referencia"] or 0, reverse=True)
    for i, c in enumerate(ordenados, 1):
        c["ordem"] = i

    total = sum(c["valor_referencia"] or 0 for c in contratos)
    anual = sum(c.get("valor_anual") or 0 for c in contratos)
    sem_valor = [c["numero"] for c in contratos if not c["valor_referencia"]]

    por_cat = defaultdict(lambda: {"qtd": 0, "valor": 0.0})
    for c in contratos:
        por_cat[c["categoria"]]["qtd"] += 1
        por_cat[c["categoria"]]["valor"] += c["valor_referencia"] or 0
    categorias = sorted(
        ({"nome": k, **v, "pct": pct(v["valor"], total)} for k, v in por_cat.items()),
        key=lambda x: x["valor"],
        reverse=True,
    )

    prioridades = Counter(c["prioridade"] for c in contratos)
    recomendacoes = Counter(c["recomendacao"] for c in contratos)

    vencimentos = sorted(
        (c for c in contratos if c["dias_para_fim"] is not None),
        key=lambda c: c["dias_para_fim"],
    )

    # matriz simétrica de sombreamento: mantém a maior intensidade por par
    peso = {"Forte": 3, "Média": 2, "Fraca": 1}
    celulas, envolvidos = {}, []
    for s in dados.get("sombreamentos", []):
        for a in s["contratos"]:
            if a not in envolvidos:
                envolvidos.append(a)
            for b in s["contratos"]:
                if a == b:
                    continue
                atual = celulas.get(f"{a}|{b}")
                if not atual or peso[s["intensidade"]] > peso[atual]:
                    celulas[f"{a}|{b}"] = s["intensidade"]

    ordem_grav = {"Alta": 0, "Média": 1, "Baixa": 2}
    dados.get("inconsistencias", []).sort(key=lambda i: ordem_grav.get(i["gravidade"], 9))

    texto = json.dumps(dados, ensure_ascii=False).lower()
    glossario = [
        {"termo": t, "def": d} for t, d in sorted(GLOSSARIO.items()) if t.lower() in texto
    ]

    dados["calc"] = {
        "glossario": glossario,
        "max_valor": max((c["valor_referencia"] or 0 for c in contratos), default=0),
        "vencem_180": [c for c in vencimentos if 0 <= c["dias_para_fim"] <= 180],
        "vencidos": [c for c in vencimentos if c["dias_para_fim"] < 0],
        "com_anual": sum(1 for c in contratos if c.get("valor_anual")),
        "matriz": {"contratos": envolvidos, "celulas": celulas},
        "qtd_contratos": len(contratos),
        "qtd_documentos": len(dados.get("inventario", [])),
        "valor_total": total,
        "valor_anual": anual,
        "sem_valor": sem_valor,
        "categorias": categorias,
        "max_cat": max((c["valor"] for c in categorias), default=0),
        "prioridades": {p: prioridades.get(p, 0) for p in ("P1", "P2", "P3")},
        "recomendacoes": [
            {"nome": r, "qtd": recomendacoes[r]} for r in RECOMENDACOES if recomendacoes.get(r)
        ],
        "alertas_por_nivel": Counter(a["nivel"] for a in dados["resumo"]["alertas"]),
        "quadro": ordenados,
        "vencimentos": vencimentos,
        "inconsistencias_por_gravidade": Counter(
            i["gravidade"] for i in dados.get("inconsistencias", [])
        ),
        "data_emissao": dados["meta"].get("data_emissao") or date.today().isoformat(),
    }
    return dados


# ---------------------------------------------------------------- renderização

def html(dados: dict, modelo: str = "relatorio") -> str:
    pasta = TEMPLATE_DIR.parent / modelo
    env = Environment(
        loader=FileSystemLoader([pasta, TEMPLATE_DIR]),
        undefined=StrictUndefined,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters.update(
        brl=brl,
        brl_curto=brl_curto,
        data=data_br,
        slug=slug,
        rec_label=lambda r: RECOMENDACOES.get(r, r),
        prio_label=lambda p: PRIORIDADES.get(p, p),
    )
    env.globals.update(pct=pct, P=P)
    css = (TEMPLATE_DIR / "relatorio.css").read_text(encoding="utf-8")
    extra = pasta / "extra.css"
    if extra.exists() and pasta != TEMPLATE_DIR:
        css += "\n" + extra.read_text(encoding="utf-8")
    # o CSS também usa o perfil (rodapé com a sigla do emissor)
    css = env.from_string(css).render(P=P)
    return env.get_template("relatorio.html.j2").render(d=enriquecer(dados), css=css)


def navegador() -> str:
    for b in BROWSERS:
        if Path(b).exists() or shutil.which(b):
            return b
    raise RuntimeError("Nenhum Edge/Chrome encontrado para gerar o PDF.")


def pdf(dados: dict, saida: Path, manter_html: bool = False, modelo: str = "relatorio") -> Path:
    saida = Path(saida).resolve()
    saida.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        arq = Path(tmp) / "relatorio.html"
        arq.write_text(html(dados, modelo), encoding="utf-8")
        # logos da instituição (pasta do perfil)
        for nome in (P.relatorio.logo_faixa, P.relatorio.brasao):
            if P.asset(nome).exists():
                shutil.copy(P.asset(nome), Path(tmp) / nome)
        subprocess.run(
            [
                navegador(),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--user-data-dir={Path(tmp) / 'perfil'}",
                f"--print-to-pdf={saida}",
                arq.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
        if manter_html:
            shutil.copy(arq, saida.with_suffix(".html"))
    return saida


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dados", type=Path)
    p.add_argument("saida", type=Path)
    p.add_argument("--html", action="store_true", help="salva também o HTML intermediário")
    a = p.parse_args(argv)
    dados = json.loads(a.dados.read_text(encoding="utf-8"))
    print(pdf(dados, a.saida, a.html))


if __name__ == "__main__":
    sys.exit(main())
