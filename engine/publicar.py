"""Etapa 7 — publica o PDF na pasta do órgão em RELATÓRIOS/3_CONTRATOS_TIC.

Usa a pasta sincronizada pelo Google Drive para desktop. A confirmação de que o
arquivo chegou ao Drive é feita pelo orquestrador via MCP (search_files).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .config import DRIVE_RELATORIOS_LOCAL


def publicar(sigla: str, pdf: Path) -> Path:
    if not DRIVE_RELATORIOS_LOCAL.exists():
        raise SystemExit(
            f"Pasta do Drive não encontrada em {DRIVE_RELATORIOS_LOCAL}. "
            "Abra o Google Drive para desktop com a conta que tem acesso à pasta e confira DRIVE_RELATORIOS_LOCAL no .env."
        )
    destino = DRIVE_RELATORIOS_LOCAL / sigla
    destino.mkdir(exist_ok=True)
    alvo = destino / pdf.name
    shutil.copy2(pdf, alvo)
    return alvo
