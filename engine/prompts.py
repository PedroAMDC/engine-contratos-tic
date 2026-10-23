"""Gera os prompts e schemas com os nomes da instituição.

Os arquivos de prompts/*.md e schemas/*.json são modelos Jinja2 com o perfil `P` e o caminho
`SCHEMAS` (onde ficam os schemas gerados). A saída vai para data/_prompts/, que é o que os
agentes devem ler.
"""

from __future__ import annotations

from jinja2 import Environment, StrictUndefined

from .config import DATA, PROMPTS, SCHEMAS
from .perfil import P

DESTINO = DATA / "_prompts"
SCHEMAS_REL = "data/_prompts/schemas"


def gerar_prompts() -> int:
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True, autoescape=False)
    variaveis = {"P": P, "SCHEMAS": SCHEMAS_REL}
    n = 0
    for origem, destino in ((PROMPTS, DESTINO), (SCHEMAS, DESTINO / "schemas")):
        padrao = "*.md" if origem == PROMPTS else "*.json"
        destino.mkdir(parents=True, exist_ok=True)
        for arq in sorted(origem.glob(padrao)):
            texto = env.from_string(arq.read_text(encoding="utf-8")).render(**variaveis)
            (destino / arq.name).write_text(texto, encoding="utf-8", newline="")
            n += 1
    return n
