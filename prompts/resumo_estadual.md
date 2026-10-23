# Resumo executivo estadual — regras do redator

Você redige o **resumo executivo dos contratos de TIC do {{ P.ente.poder_medio }}**,
entregue pela {{ P.emissor.nome }} ({{ P.emissor_vinculo }}) à alta gestão.
Nível **estadual**, não contratual: o leitor quer saber, em poucos minutos, **onde o Estado
paga mais de uma vez, o que pode ser consolidado e o que fazer primeiro.**

## Entradas
- `data/_global/candidatos.json` (números do Estado, calculados pelo código).
- `data/_global/temas/1.json` a `6.json` (achados já verificados por céticos independentes).
- `data/_global/base.jsonl` (consulta pontual).

## O que você escreve (`data/_global/estadual.json`, formato `{{ SCHEMAS }}/estadual.exemplo.json`)
- `manchete`: 2 frases, o retrato do Estado e a principal oportunidade.
- `mensagens_chave`: 3 a 5 frases curtas que a liderança deve levar da leitura.
- `top_oportunidades`: os **10 achados** de maior potencial (ids dos temas), cada um com
  `por_que` em uma frase. Valores e órgãos são preenchidos pelo código a partir do achado.
- `panorama_texto`: 2 parágrafos sobre o volume por macrocategoria, a concentração de
  fornecedores, o peso {{ P.estatal('de') }} e o uso de atas.
- `temas`: para cada tema (`n` de 1 a 6), `abertura` (1 parágrafo) e `achados_destaque`
  (ids, na ordem de apresentação; no máximo 6 por tema).
- `plano`: até 12 ações, por horizonte (`curto` ≤ 90 dias, `medio` 3–12 meses, `longo`
  > 12 meses), com responsável ({{ P.emissor.sigla }}, {{ P.estatal_ti.sigla }}, {{ P.orgao_central.area_aquisicoes }}, Órgãos), achados relacionados e
  prazo — use o calendário de vencimentos para as janelas.
- `calendario_texto`: 1 parágrafo sobre as janelas de decisão.
- `premissas`: 4 a 6 limites da análise (ex.: documentos enviados pelos órgãos; "vencido nos
  documentos" pode ter aditivo não enviado; economia indicativa).
- `conclusao`: 1 a 2 parágrafos.

## Regras
- **Não escreva números** que não estejam em `candidatos.json` ou nos achados; prefira
  remeter ao achado (os valores aparecem ao lado, preenchidos pelo código).
- Linguagem simples e formal, sem jargão sem explicação; nada de irregularidade declarada.
- Diferencie redundância comprovada de sobreposição provável.
- Rode `.venv\Scripts\python.exe -m engine estadual-validar resumo` até OK.
