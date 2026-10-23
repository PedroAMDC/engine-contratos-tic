"""Configuração central da engine.

Identificadores do Drive e caminhos locais ficam no arquivo .env (fora do git).
Copie .env.exemplo para .env e preencha.
"""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DATA = RAIZ / "data"
OUTPUT = RAIZ / "output"
PROMPTS = RAIZ / "prompts"
SCHEMAS = RAIZ / "schemas"


def _carregar_env(arq: Path) -> None:
    """Lê CHAVE=valor do .env sem sobrescrever variáveis já definidas no ambiente."""
    if not arq.exists():
        return
    for linha in arq.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        k, v = linha.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_carregar_env(RAIZ / ".env")

# Google Drive (pastas compartilhadas)
PASTA_CONTRATOS = os.environ.get("PASTA_CONTRATOS", "")  # pasta com uma subpasta por órgão
PASTA_RELATORIOS = os.environ.get("PASTA_RELATORIOS", "")  # pasta de destino dos relatórios
PLANILHA_ORGAOS = os.environ.get("PLANILHA_ORGAOS", "")  # planilha de controle dos órgãos
SUBPASTA_RELATORIOS = os.environ.get("SUBPASTA_RELATORIOS", "3_CONTRATOS_TIC")

# Pastas sincronizadas pelo Google Drive para desktop (acesso autenticado)
DRIVE_CONTRATOS_LOCAL = Path(os.environ.get("DRIVE_CONTRATOS_LOCAL", RAIZ / "contratos"))
DRIVE_RELATORIOS_LOCAL = Path(os.environ.get("DRIVE_RELATORIOS_LOCAL", OUTPUT / "publicados"))

# Taxonomia estadual: macrocategoria -> subcategorias (lista fechada, base da triangulação)
MACROCATEGORIAS = {
    "Infraestrutura e nuvem": [
        "Nuvem pública",
        "Nuvem privada e hospedagem",
        "Data center e colocation",
        "Servidores, storage e backup",
        "Equipamentos e locação",
    ],
    "Conectividade": [
        "Link de internet e rede de dados",
        "Internet satelital",
        "Telefonia fixa",
        "Telefonia móvel e dados móveis",
        "Rede local e Wi-Fi",
    ],
    "Desenvolvimento e sistemas": [
        "Fábrica de software e sustentação",
        "Sistema finalístico",
        "Sistema administrativo",
        "BI e dados",
        "Plataformas digitais e automação",
        "Inteligência artificial",
    ],
    "Licenciamento e plataformas": [
        "Escritório e colaboração",
        "Design, engenharia e CAD",
        "Segurança da informação (software)",
        "Banco de dados e infraestrutura de software",
        "Outras licenças",
    ],
    "Serviços de TIC": [
        "Outsourcing de impressão",
        "Service desk e suporte técnico",
        "Certificação digital e assinatura eletrônica",
        "Consultoria e pesquisa",
        "Digitalização e gestão documental",
        "Segurança gerenciada",
        "Treinamento",
        "Suprimentos de informática",
        "Outros serviços de TIC",
    ],
}

# Taxonomia fixa de categorias (análise por órgão)
CATEGORIAS = [
    "Infraestrutura e hospedagem",
    "Nuvem pública",
    "Conectividade e telecomunicações",
    "Segurança da informação",
    "Licenciamento de software",
    "Sistemas finalísticos",
    "Sistemas administrativos",
    "Desenvolvimento e sustentação de software",
    "Suporte técnico e service desk",
    "Outsourcing de impressão",
    "Equipamentos e locação",
    "Certificação digital",
    "Consultoria e pesquisa em TIC",
    "Gestão documental e digitalização",
    "Inteligência artificial",
    "Outros serviços de TIC",
]
