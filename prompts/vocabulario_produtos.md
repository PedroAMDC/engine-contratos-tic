# Vocabulário de produtos — regras do agente

Entrada: `data/_global/fatias/produtos_<macro>.json` (a tarefa informa a macrocategoria) —
cada nome de produto como foi escrito nas fichas dos contratos de TIC de todos os órgãos,
com ocorrências, órgãos, métricas, fabricantes e subcategorias.

Tarefa: agrupar nomes que designam **o mesmo produto ou serviço comparável** sob um nome
canônico, para que o Estado possa comparar quantidades e preços entre órgãos.

Regras:
1. Mesmo produto = mesmo fabricante, mesma edição/plano e mesma natureza (licença perpétua ≠
   assinatura; e-CPF A1 ≠ A3; link 100 Mbps ≠ 1 Gbps; página monocromática ≠ colorida;
   UST {{ P.estatal('de') }} ≠ UST de outro fornecedor). Na dúvida, **não agrupe**.
2. Nome canônico: fabricante + produto + edição, curto e estável (ex.: "Microsoft 365 E3",
   "Autodesk AEC Collection", "SketchUp Pro", "Starlink itinerante", "Certificado digital
   e-CPF A3", "Outsourcing de impressão — página monocromática A4", "UST {{ P.estatal_ti.sigla }}").
3. Corrija variações de grafia, caixa, siglas e ordem de palavras.
4. Todo nome de entrada aparece como chave exatamente uma vez (mesmo que mapeie para si).

Saída: `data/_global/vocabulario_<macro>.json`, objeto `{"nome como na ficha": "nome canônico", ...}`
(JSON válido; confira com `.venv\Scripts\python.exe -c "import json; json.load(open(r'<arquivo>', encoding='utf-8'))"`).
Não altere outros arquivos.
