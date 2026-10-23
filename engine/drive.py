"""Acesso às pastas públicas do Google Drive (link "qualquer pessoa com o link").

O conector MCP do Drive não lista o conteúdo de pastas compartilhadas por link,
então a listagem usa a visualização pública `embeddedfolderview` e o download
usa o endpoint público de arquivos.
"""

from __future__ import annotations

import html
import re
import time
import unicodedata
import urllib.request
from dataclasses import dataclass
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (engine-contratos)"}

_HREF = re.compile(r'<a href="([^"]+)"')
_ICONE = re.compile(r'<div class="flip-entry-list-icon"><img src="([^"]*)"')
_TITULO = re.compile(r'<div class="flip-entry-title">(.*?)</div>', re.S)

GOOGLE_EXPORT = {
    "application/vnd.google-apps.document": ("https://docs.google.com/document/d/{id}/export?format=pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": ("https://docs.google.com/spreadsheets/d/{id}/export?format=xlsx", ".xlsx"),
    "application/vnd.google-apps.presentation": ("https://docs.google.com/presentation/d/{id}/export/pdf", ".pdf"),
}


@dataclass
class Item:
    id: str
    nome: str
    pasta: bool
    mime: str
    caminho: str  # caminho relativo dentro da pasta do órgão, ex.: "2025/Aditivos"


def _get(url: str, tentativas: int = 4) -> bytes:
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception:
            if i == tentativas - 1:
                raise
            time.sleep(2 * (i + 1))
    raise RuntimeError("inalcançável")


def listar(pasta_id: str) -> list[Item]:
    """Itens diretos de uma pasta pública."""
    pagina = _get(f"https://drive.google.com/embeddedfolderview?id={pasta_id}").decode("utf-8", "replace")
    itens = []
    for bloco in pagina.split('<div class="flip-entry" id="entry-')[1:]:
        id_ = bloco.split('"', 1)[0]
        href = html.unescape((_HREF.search(bloco) or [None, ""])[1])
        icone = _ICONE.search(bloco)
        mime = icone[1].split("/type/", 1)[1] if icone and "/type/" in icone[1] else ""
        titulo = html.unescape((_TITULO.search(bloco) or [None, id_])[1]).strip()
        pasta = "/folders/" in href or 'aria-label="Folder"' in bloco
        itens.append(Item(id_, titulo, pasta, "application/vnd.google-apps.folder" if pasta else mime, ""))
    return itens


def listar_recursivo(pasta_id: str, caminho: str = "") -> list[Item]:
    """Todos os arquivos abaixo de uma pasta, em qualquer profundidade."""
    saida = []
    for it in listar(pasta_id):
        if it.pasta:
            sub = f"{caminho}/{it.nome}" if caminho else it.nome
            saida.extend(listar_recursivo(it.id, sub))
        else:
            it.caminho = caminho
            saida.append(it)
    return saida


def baixar(item: Item, destino_dir: Path) -> Path:
    """Baixa um arquivo público (exporta formatos nativos do Google para PDF/XLSX)."""
    destino_dir.mkdir(parents=True, exist_ok=True)
    if item.mime in GOOGLE_EXPORT:
        modelo, ext = GOOGLE_EXPORT[item.mime]
        url, nome = modelo.format(id=item.id), Path(item.nome).stem + ext
    else:
        url = f"https://drive.usercontent.google.com/download?id={item.id}&export=download&confirm=t"
        nome = item.nome
    dados = _get(url)
    if dados[:15].lstrip().lower().startswith((b"<!doctype html", b"<html")):
        raise RuntimeError(f"Download de {item.nome} retornou HTML (sem permissão ou link inválido).")
    alvo = destino_dir / nome_seguro(com_extensao(nome, dados[:8], item.mime))
    alvo.write_bytes(dados)
    return alvo


EXTENSOES = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".odt", ".jpg", ".jpeg", ".png",
             ".tif", ".tiff", ".bmp", ".html", ".txt", ".zip", ".rar"}
MIME_EXT = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


def com_extensao(nome: str, cabecalho: bytes, mime: str = "") -> str:
    """Acrescenta a extensão quando o arquivo no Drive não a tem no nome (identifica pelo conteúdo)."""
    if Path(nome).suffix.lower() in EXTENSOES:
        return nome
    if cabecalho.startswith(b"%PDF"):
        return nome + ".pdf"
    if cabecalho.startswith(b"\xff\xd8"):
        return nome + ".jpg"
    if cabecalho.startswith(b"\x89PNG"):
        return nome + ".png"
    return nome + MIME_EXT.get(mime, "")


def nome_seguro(nome: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nome).strip(" .")


def normalizar(s: str) -> str:
    """Chave de comparação de nomes de órgãos: sem acento, espaço ou pontuação."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def pastas_orgaos() -> dict[str, Item]:
    from .config import PASTA_CONTRATOS

    return {normalizar(i.nome): i for i in listar(PASTA_CONTRATOS) if i.pasta}


# ---------------------------------------------------------------- origem local (Drive para desktop)
# Quando o link público não está disponível, a pasta compartilhada com a conta é lida pelo
# Google Drive para desktop (G:). O id do item passa a ser o caminho relativo.

NATIVOS_GOOGLE = {".gdoc", ".gsheet", ".gslides", ".gdraw", ".gform", ".gmap", ".gsite"}


def pastas_orgaos_local(raiz: Path) -> dict[str, Path]:
    return {normalizar(p.name): p for p in raiz.iterdir() if p.is_dir()}


def listar_local(pasta: Path) -> list[Item]:
    itens = []
    for arq in sorted(pasta.rglob("*")):
        if not arq.is_file() or arq.name.lower() == "desktop.ini":
            continue
        rel = arq.relative_to(pasta)
        caminho = "/".join(rel.parts[:-1])
        itens.append(Item(f"local:{rel.as_posix()}", arq.name, False, arq.suffix.lower(), caminho))
    return itens


def copiar_local(pasta: Path, item: Item, destino_dir: Path) -> Path:
    import shutil

    origem = pasta / item.id.split(":", 1)[1]
    if origem.suffix.lower() in NATIVOS_GOOGLE:
        raise RuntimeError("documento nativo do Google (Docs/Sheets): exporte como PDF no Drive para análise")
    destino_dir.mkdir(parents=True, exist_ok=True)
    with open(origem, "rb") as f:
        cab = f.read(8)
    alvo = destino_dir / nome_seguro(com_extensao(item.nome, cab))
    shutil.copy2(origem, alvo)
    return alvo
