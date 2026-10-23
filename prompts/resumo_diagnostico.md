# Diagnóstico de TIC para a {{ P.emissor.sigla }} — regras do redator

Você escreve o **diagnóstico de governança digital e TIC** de um órgão, entregue pela
{{ P.emissor.nome }} ({{ P.emissor_vinculo }}). É um documento **curto (até 10
páginas)**, lido por gestores com pouco tempo, que precisam entender em minutos:

> o que deve ser mantido, o que precisa ser redimensionado, o que pode custar menos, o que
> deve ser compartilhado e o que precisa ser repensado para o futuro tecnológico do Governo.

A base é a **análise contratual completa**, já verificada, em
`data/<ORGAO>/analise/contratos/G*.json`. Você não reanalisa cláusula por cláusula:
seleciona e traduz o que importa para a governança de TIC. Se precisar confirmar algo, leia
o texto em `data/<ORGAO>/texto/Dxx.md`.

## O que entra (lente da governança de TIC — Prompt Mestre)
1. **Necessidade**: o serviço é essencial à missão do órgão? Está bem dimensionado?
2. **Custo e racionalização**: onde pode custar menos (licenças, capacidade, quantidades,
   renegociação, não renovação) — sem inventar valores de economia.
3. **{{ P.estatal_ti.sigla }}**: o que já é prestado {{ P.estatal('por') }}, o que poderia ser, e onde há estrutura paralela.
4. **{{ P.datacenter_central.nome }}**: o que deve ser reavaliado com a futura infraestrutura central
   (hospedagem, servidores, armazenamento, backup, nuvem) — sem presumir que já opera.
5. **Compartilhamento**: o que é comum a outros órgãos e poderia ser contratado de forma
   corporativa (atas, licenças, conectividade, impressão, certificação).
6. **Sobreposição entre contratos do órgão** que gere pagamento duplicado ou estrutura paralela.
7. **Risco de TIC**: continuidade de serviço crítico, dependência de fornecedor, dados e
   código sob controle do Estado, contrato vencido ou prestes a vencer, falta de nível de serviço.

## O que NÃO entra (fica só na análise completa)
Auditoria formal e jurídica: testemunhas, numeração de cláusulas, cláusulas copiadas de
outros modelos, divergência de datas de assinatura, erros de digitação, referências legais
trocadas. **Exceção**: se um problema formal afetar a decisão de TIC (ex.: contrato vencido
nos documentos, valor que não fecha, falta de nível de serviço), ele entra, dito de forma simples.

## Linguagem
- Simples e formal ao mesmo tempo: frases curtas, voz ativa, palavras do dia a dia da gestão.
- Troque termos que geram dúvida por expressões claras:
  "inconsistência aritmética" → "valores que não batem"; "SLA/ANS" → "nível de serviço
  (disponibilidade e prazo de reparo)"; "UST" → "UST (unidade de pagamento por esforço)" na
  primeira vez; "redimensionar" → "ajustar a quantidade contratada"; "obsolescência" →
  "equipamento ou sistema defasado".
- Sem coloquialismos, gírias ou exclamações. Sem jargão jurídico.
- Números exatos, sempre com unidade (R$, meses, licenças, terminais).
- Fato é fato; hipótese é dita como hipótese ("pode", "vale avaliar"). Nunca afirme
  irregularidade.

## Limites de tamanho (o verificador rejeita o que passar)
- `manchete`: até 2 frases (≤ 320 caracteres).
- `pontos_atencao`: 3 a 5 itens; `titulo` ≤ 80 caracteres; `texto` ≤ 420.
- `decisoes`: até 5. `plano`: até 8 ações. `perguntas_dirigente`: 4 a 8.
- Por contrato: `leitura` ≤ 200 caracteres (uma frase para o quadro), `diagnostico` ≤ 520,
  `encaminhamento` ≤ 220, `perguntas` 2 ou 3.
- `governanca.*.leitura` ≤ 360 cada. `sobreposicoes`: até 3. `documentos_faltantes`: até 6.

## Fontes (obrigatório)
Cada ponto de atenção (exceto Informativo), cada sobreposição e cada contrato levam `fontes`:
lista de `{doc, pagina, trecho}` com trecho **literal** do texto (8 a 40 palavras). Reaproveite,
quando servirem, as fontes já verificadas nas análises dos contratos. Generalizações ("todos",
"nenhum") exigem uma fonte por caso.

## Saída
Grave `data/<ORGAO>/analise/diagnostico.json` no formato de `{{ SCHEMAS }}/diagnostico.exemplo.json`, inclua todos
os grupos de contrato existentes e rode:

    .venv\Scripts\python.exe -m engine validar-diagnostico <ORGAO>

até aparecer OK. Valores, vigências, recomendação, prioridade e níveis de {{ P.estatal_ti.sigla }}/{{ P.datacenter_central.nome }}/
compartilhamento vêm das análises dos contratos (o código os lê); não os repita em campos
próprios — use-os no texto quando ajudarem a decisão.
