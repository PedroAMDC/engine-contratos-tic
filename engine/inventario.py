"""Etapa 1 — inventário e download de todos os arquivos de um órgão.

Gera data/<ORGAO>/manifest.json com um registro por arquivo. Cada arquivo
recebe um código curto (D01, D02...) usado nas citações de fonte.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from . import drive
from .config import DATA


def dir_orgao(sigla: str) -> Path:
    return DATA / drive.normalizar(sigla)


def carregar_manifest(sigla: str) -> dict:
    arq = dir_orgao(sigla) / "manifest.json"
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}


def salvar_manifest(sigla: str, manifest: dict) -> None:
    arq = dir_orgao(sigla) / "manifest.json"
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def inventariar(sigla: str, forcar: bool = False) -> dict:
    from .config import DRIVE_CONTRATOS_LOCAL

    chave = drive.normalizar(sigla)
    local_ok = DRIVE_CONTRATOS_LOCAL.exists()
    if local_ok:  # acesso autenticado pelo Drive para desktop
        pastas_l = drive.pastas_orgaos_local(DRIVE_CONTRATOS_LOCAL)
        if chave not in pastas_l:
            raise SystemExit(f"Pasta do órgão '{sigla}' não encontrada. Disponíveis: {', '.join(sorted(pastas_l))}")
        pasta_local = pastas_l[chave]
        nome_pasta, id_pasta = pasta_local.name, f"local:{pasta_local.name}"
        itens = drive.listar_local(pasta_local)
        baixar = lambda it, destino: drive.copiar_local(pasta_local, it, destino)
    else:  # link público
        pastas = drive.pastas_orgaos()
        if chave not in pastas:
            raise SystemExit(f"Pasta do órgão '{sigla}' não encontrada. Disponíveis: {', '.join(sorted(pastas))}")
        pasta = pastas[chave]
        nome_pasta, id_pasta = pasta.nome, pasta.id
        itens = drive.listar_recursivo(pasta.id)
        baixar = drive.baixar

    base = dir_orgao(sigla)
    antes = carregar_manifest(sigla).get("documentos", [])
    anterior = {d["drive_id"]: d for d in antes}
    # mesmo arquivo identificado pela posição na pasta (permite trocar de origem web ↔ local)
    por_caminho = {(d.get("caminho_drive", ""), d["nome"]): d for d in antes}
    itens.sort(key=lambda i: (i.caminho.lower(), i.nome.lower()))

    docs = []
    for n, it in enumerate(itens, 1):
        reg = anterior.get(it.id) or por_caminho.get((it.caminho, it.nome))
        # só reaproveita o que foi baixado com sucesso; falhas anteriores são baixadas de novo
        local = base / reg["arquivo_local"] if reg and reg.get("status") == "baixado" else None
        if local and local.exists() and not forcar:
            # arquivos baixados sem extensão no nome (ocorre em alguns órgãos) recebem a extensão pelo conteúdo
            with open(local, "rb") as f:
                novo = local.with_name(drive.com_extensao(local.name, f.read(8), reg.get("mime", "")))
            if novo != local:
                local.rename(novo)
                reg["arquivo_local"] = novo.relative_to(base).as_posix()
            reg["codigo"] = f"D{n:02d}"
            docs.append(reg)
            continue
        destino = base / "raw" / Path(*[drive.nome_seguro(p) for p in it.caminho.split("/") if p])
        try:
            arq = baixar(it, destino)
            docs.append({
                "codigo": f"D{n:02d}",
                "drive_id": it.id,
                "nome": it.nome,
                "caminho_drive": it.caminho,
                "mime": it.mime,
                "arquivo_local": arq.relative_to(base).as_posix(),
                "bytes": arq.stat().st_size,
                "sha256": sha256(arq),
                "status": "baixado",
            })
        except Exception as e:  # registra e segue: nenhum arquivo some do inventário
            docs.append({
                "codigo": f"D{n:02d}", "drive_id": it.id, "nome": it.nome,
                "caminho_drive": it.caminho, "mime": it.mime, "status": "erro_download", "erro": str(e),
            })

    # o mesmo arquivo pode estar duplicado em pastas diferentes
    por_hash: dict[str, str] = {}
    for d in docs:
        h = d.get("sha256")
        if h and h in por_hash:
            d["duplicata_de"] = por_hash[h]
        elif h:
            por_hash[h] = d["codigo"]

    manifest = {
        "orgao": nome_pasta.strip(),
        "sigla": sigla,
        "pasta_drive": id_pasta,
        "atualizado_em": datetime.now().isoformat(timespec="seconds"),
        "documentos": docs,
    }
    salvar_manifest(sigla, manifest)
    return manifest
