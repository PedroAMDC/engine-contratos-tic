"""Perfil da instituição: nomes, siglas e logos usados nos relatórios, planilhas e prompts.

A engine não tem nomes de instituição fixos no código. Tudo vem do arquivo perfil.toml da
pasta da instituição:

- `instituicao/` (local, fora do git), se existir;
- senão, a pasta indicada na variável de ambiente INSTITUICAO_DIR;
- senão, `instituicao.exemplo/` (dados fictícios, versionado).

Uso no código: `from .perfil import P` e depois `P.emissor.sigla`, `P.estatal("de")` etc.
Nos modelos Jinja e nos prompts, o perfil está disponível como `P`.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from types import SimpleNamespace

from .config import RAIZ

# contrações de preposição + artigo, por gênero do nome
_CONTRACOES = {
    "f": {"": "a", "a": "à", "de": "da", "em": "na", "por": "pela", "com": "com a"},
    "m": {"": "o", "a": "ao", "de": "do", "em": "no", "por": "pelo", "com": "com o"},
}


def pasta() -> Path:
    if os.environ.get("INSTITUICAO_DIR"):
        return Path(os.environ["INSTITUICAO_DIR"]).resolve()
    local = RAIZ / "instituicao"
    return local if (local / "perfil.toml").exists() else RAIZ / "instituicao.exemplo"


def _ns(x):
    if isinstance(x, dict):
        return SimpleNamespace(**{k: _ns(v) for k, v in x.items()})
    if isinstance(x, list):
        return [_ns(v) for v in x]
    return x


class Perfil(SimpleNamespace):
    """Perfil carregado do TOML, com atalhos para frases com artigo."""

    def _com(self, ent, prep: str) -> str:
        return f"{_CONTRACOES[ent.genero][prep]} {ent.sigla}"

    def estatal(self, prep: str = "") -> str:
        """Empresa pública de TIC com artigo: estatal('de') -> 'da <sigla>'."""
        return self._com(self.estatal_ti, prep)

    def central(self, prep: str = "") -> str:
        """Órgão central de TIC com artigo: central('a') -> 'à <sigla>'."""
        return self._com(self.orgao_central, prep)

    def emissor_com(self, prep: str = "") -> str:
        """Nome do emissor com artigo: emissor_com('por') -> 'pela <nome>'."""
        return f"{_CONTRACOES[self.emissor.genero][prep]} {self.emissor.nome}"

    @property
    def emissor_completo(self) -> str:
        """'<nome do emissor> — <sigla>'."""
        return f"{self.emissor.nome} — {self.emissor.sigla}"

    @property
    def emissor_vinculo(self) -> str:
        """'<emissor>/<órgão central>-<ente>'."""
        return f"{self.emissor.sigla}/{self.orgao_central.sigla}-{self.ente.sigla}"

    def asset(self, nome: str) -> Path:
        return self.dir / nome


def carregar(dir_: Path | None = None) -> Perfil:
    d = dir_ or pasta()
    dados = tomllib.loads((d / "perfil.toml").read_text(encoding="utf-8"))
    p = Perfil(**{k: _ns(v) for k, v in dados.items()})
    p.dir = d
    return p


P = carregar()
