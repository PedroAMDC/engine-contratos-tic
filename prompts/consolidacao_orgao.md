# Consolidação e triangulação de UM órgão — regras do agente

Você recebe as análises individuais já verificadas (`data/<ORGAO>/analise/contratos/G*.json`)
e produz `data/<ORGAO>/analise/orgao.json`: a visão do órgão inteiro. É aqui que se gera o
valor do relatório — o que nenhuma análise isolada de contrato enxerga.

Escopo: **somente este órgão**. Não use dados de outros órgãos (a triangulação entre órgãos
será outra etapa, sobre `data/_global/contratos.jsonl`).

## 1. Contexto institucional (pesquise)
Pesquise em fontes oficiais (sites `*.{{ P.ente.dominio }}`, lei de criação, regimento, carta de
serviços, {{ P.ente.portal_transparencia }}, {{ P.ente.diario_oficial }}). Preencha missão, atividades
finalísticas e de apoio, serviços que dependem de TI, impacto de interrupção, o que é
específico, o que é compartilhável e riscos do setor. Cite as fontes (URL). **Não invente
competências**: se não confirmar, diga em `limitacoes`.

## 2. Triangulação interna (faça TODAS as comparações)
Monte mentalmente a matriz contrato × contrato e verifique:

1. **Sobreposição de escopo** — mesmos temas em `sinais_sombreamento` (hospedagem,
   desenvolvimento, suporte, licenças, links, BI, backup, assinatura...) em contratos
   diferentes. Leia o escopo exato antes de concluir. Intensidade: **Forte** (mesmo serviço
   em mais de um instrumento), **Média** (escopos que se tocam), **Fraca** (interface a
   delimitar). Natureza: Fato / Inferência / Hipótese.
2. **Mesmo produto/serviço em contratos distintos** — `produto_normalizado`, `metrica` e
   fabricante iguais ou equivalentes; compare preços unitários quando a métrica permitir.
3. **Mesmo fornecedor (CNPJ) em vários contratos** — concentração e dependência; soma de
   valores por fornecedor.
4. **Fragmentação** — vários contratos pequenos de objeto semelhante, mesmo período:
   registre como **ponto a verificar** (possível fracionamento), nunca como irregularidade.
5. **{{ P.estatal_ti.sigla }} × mercado** — serviços contratados no mercado que coincidem com o catálogo típico
   {{ P.estatal('de') }} (infraestrutura, desenvolvimento, sustentação, integração), e vice-versa.
6. **{{ P.datacenter_central.nome }}** — contratos de hospedagem, servidores, armazenamento, backup,
   colocation, nuvem: candidatos a estudo de migração (sem presumir que o DC já opera).
7. **Calendário** — vigências que terminam em até 180 dias da data de referência (janela
   de decisão), vigências já encerradas, renovações encadeadas.
8. **Coerência entre documentos** — divergências que só aparecem comparando contratos
   (ex.: mesmo serviço com SLA ou preço muito diferente) vão em `inconsistencias_cruzadas`.
9. **Lacunas** — o que falta para concluir (medições, inventários, relatórios de uso).

## 3. Principais pontos de atenção (alertas)
De 3 a 5 alertas, ordenados por **impacto financeiro × urgência × facilidade de agir**.
`nivel`: Crítico (agir agora) · Atenção (estudar/sanear) · Informativo (evitar erro de leitura,
ex.: supressão já feita não é economia futura). Cada alerta: título direto (até 10 palavras),
explicação de 2 a 3 frases em linguagem simples com os números exatos, contratos, valor em
jogo (só o documentado ou "a medir"), prazo e ação.

`manchete`: 1 a 2 frases que respondem "como está o órgão e o que precisa de atenção".

## 4. Decisões, riscos, oportunidades, plano e conclusão
- `decisoes`: o que a alta gestão precisa decidir, priorizado (P1–P3), com contratos.
- `plano_acao`: ações por horizonte (curto ≤ 90 dias · medio 3–12 meses · longo > 12 meses),
  com responsável sugerido, evidência/estudo necessário e prazo — considere as datas de
  término dos contratos.
- `consolidacao`: oportunidades corporativas (compartilhamento, {{ P.estatal_ti.sigla }}, {{ P.datacenter_central.nome }}), com
  benefício esperado e condição necessária. Hipóteses não são duplicidades comprovadas.
- `conclusao.respostas`: as 8 perguntas do Prompt Mestre (Parte VI), respondidas
  objetivamente; `conclusao.sintese`: 2 parágrafos.
- `base_normativa`: só normas efetivamente pertinentes; não presuma aplicação automática de
  normas federais do SISP a órgãos estaduais.

## Fontes (obrigatório)
Cada alerta (exceto Informativo), cada sobreposição e cada inconsistência cruzada leva
`fontes`: lista de `{doc, pagina, trecho}` com trecho **literal** (8 a 40 palavras) do texto
extraído, que sustente a afirmação. O verificador confere cada trecho e grava página e linha.
Generalizações ("todos", "nenhum") exigem uma fonte por caso coberto.

## Regras gerais
- Mesmas regras de precisão da análise de contrato: nada inventado, valores conferidos,
  distinção entre fato, inferência e hipótese.
- Linguagem simples e **formal**, em registro técnico-administrativo de documento oficial:
  frases claras e diretas, sem coloquialismos, gírias, ironias ou exclamações
  (ex.: evite "o que está pegando", "furo", "bagunça"; prefira "ponto de atenção",
  "lacuna", "inconsistência"). Sem perder precisão técnica. Alto custo ≠ desperdício.
- Não declare irregularidade: aponte pontos a verificar pela unidade competente.

## Saída
`data/<ORGAO>/analise/orgao.json` com as chaves: `orgao_nome`, `data_referencia`,
`finalidade`, `orgao` {missao, finalisticas[], apoio[], servicos_criticos[],
impacto_interrupcao, necessidades_especificas, compartilhavel, riscos_setor, fontes[],
limitacoes}, `resumo` {manchete, alertas[{nivel, titulo, texto, contratos[], valor_em_jogo,
prazo, acao}], decisoes[{decisao, contratos[], prioridade}], riscos[], oportunidades[]},
`sombreamentos` [{contratos[], area, intensidade, descricao, evidencia, natureza,
encaminhamento}], `inconsistencias_cruzadas` [{contrato, tipo, descricao, evidencia,
gravidade, encaminhamento}], `consolidacao` [{contratos[], categoria, servico, oportunidade,
papel_estatal_ti, relacao_dc, beneficio, condicao}], `plano_acao` [{horizonte, prioridade, contrato,
acao, responsavel, evidencia, prazo}], `conclusao` {respostas[{pergunta, resposta}],
sintese[]}, `documentos_solicitados` [{contrato, documento, finalidade}],
`observacoes_inventario` {Dxx: motivo}, `base_normativa` [].

Depois: `python -m engine validar-orgao <ORGAO>` até OK. Em seguida, a checagem
independente de fatos (`prompts/checagem_fatos.md`) é feita por **outro** agente; só então
`python -m engine montar <ORGAO> --data <AAAA-MM-DD>`.
