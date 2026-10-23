# engine-contratos

Engine de análise de contratos de Tecnologia da Informação e Comunicação (TIC) de órgãos
públicos. Lê os contratos enviados pelos órgãos (PDFs, digitais ou escaneados), extrai uma
ficha padronizada de cada contrato, cruza os dados de todos os órgãos e produz relatórios
em PDF e planilhas Excel.

O trabalho de leitura e interpretação é feito por agentes de IA, coordenados em paralelo.
O código cuida do que precisa ser exato: extração de texto, OCR, agrupamento dos documentos,
cálculos, verificação das citações e montagem dos relatórios.

## Produtos

- **Diagnóstico por órgão** (até 10 páginas): visão dos contratos de TIC de um órgão, com
  vencimentos, valores e pontos de atenção.
- **Resumo executivo estadual** (até 50 páginas): redundâncias e oportunidades de
  consolidação entre órgãos (infraestrutura e nuvem, conectividade, desenvolvimento,
  licenças e serviços).
- **Base de contratos** (Excel): todos os contratos, itens, fornecedores, produtos,
  contratos de desenvolvimento e de nuvem, com a fonte de cada campo.
- **Mapa preliminar da infraestrutura de dados** (Excel): onde ficam os dados de cada órgão
  e quanto custa, segundo os contratos.

## Como garante que os números são fiéis aos documentos

1. **Citação literal com página e linha.** Toda informação extraída traz o trecho do
   documento de onde saiu. O código procura o trecho no texto (com tolerância a erros de
   OCR) e rejeita a ficha se não encontrar.
2. **Números calculados pelo código.** Totais, preços unitários, medianas e dispersões são
   calculados a partir da base, nunca escritos pelos agentes.
3. **Listas fechadas.** Categorias, tipos de achado e situações vêm de listas fixas
   ([engine/config.py](engine/config.py)).
4. **Verificação adversarial.** Cada achado de impacto alto ou médio é contestado por dois
   agentes independentes; o que for refutado cai ou é rebaixado.
5. **Checagem final independente** das afirmações do relatório antes de gerar o PDF.

## Fluxo

```
inventario → extrair (texto + OCR) → agrupar (documentos por contrato)
  → fichas (agentes) → fichas-validar
  → base → candidatos (cálculos de redundância) → temas (agentes) → verificação
  → estadual-montar → PDF + Excel
```

Principais comandos (`python -m engine <comando> <órgão>`):

| Comando | O que faz |
|---|---|
| `preparar` | inventário, extração e agrupamento de um órgão |
| `ocr-complementar`, `reprocessar` | OCR em imagens dentro de páginas com texto e em páginas ilegíveis |
| `fichas-validar` | verifica as fichas de um órgão (citações, contas, listas) |
| `base`, `candidatos` | consolida a base estadual e calcula os candidatos a redundância |
| `estadual-validar` | verifica um tema (`<n>`) ou o resumo (`resumo`) |
| `estadual-montar` | monta o resumo executivo estadual |
| `infra-mapa` | gera o mapa de infraestrutura de dados |
| `montar`, `publicar` | monta e publica o diagnóstico de um órgão |
| `status` | situação de cada etapa |

A metodologia de cada agente está em [prompts/](prompts/) e o formato esperado das respostas
em [schemas/](schemas/). Os dois são modelos com variáveis do perfil da instituição:
`python -m engine prompts` gera a versão final em `data/_prompts/`, que é a que os agentes leem.

## Perfil da instituição

Nenhum nome de instituição fica fixo no código, nos modelos de relatório ou nos prompts. Emissor,
órgão central de TIC, ente federativo, empresa pública de TIC, data center corporativo, órgãos
gerenciadores de atas, classificação e logos vêm de `perfil.toml`:

- `instituicao/` — perfil real, com logos (fora do git);
- `instituicao.exemplo/` — perfil fictício, usado quando não há perfil real.

Para adaptar a outro governo, copie `instituicao.exemplo/` para `instituicao/` e troque os valores
e as logos. A variável de ambiente `INSTITUICAO_DIR` aponta para outra pasta, se preciso.

## Instalação

Requisitos: Python 3.11+, Microsoft Edge (gera os PDFs) e Google Drive para desktop, se os
contratos estiverem no Drive.

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.exemplo .env   # preencha os IDs e caminhos do Drive
xcopy /E /I instituicao.exemplo instituicao   # troque nomes e logos
```

## Dados

Contratos, textos extraídos, fichas e relatórios ficam em `data/` e `output/`, que **não**
vão para o repositório. O repositório contém só o código, os prompts, os modelos de
relatório e exemplos com dados fictícios.
