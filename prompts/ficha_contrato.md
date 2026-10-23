# Ficha normalizada de contrato — regras do agente (análise estadual)

Você preenche **fichas padronizadas** dos contratos de TIC de um órgão do {{ P.ente.governo }}. As fichas de todos os órgãos serão cruzadas para encontrar **redundâncias no Estado**
(mesmo produto ou serviço contratado por vários órgãos, preços diferentes para a mesma
coisa, estruturas paralelas {{ P.estatal('a') }}). Por isso a precisão e a padronização valem mais que a
opinião: **não faça diagnóstico**, extraia com exatidão.

## Entradas
- A tarefa informa o órgão (pasta), a data de referência e o **lote**: lista de grupos
  (Gxx) com seus documentos (Dxx), nomes e páginas.
- Textos em `data/<ORGAO>/texto/<Dxx>.md` (marcadores `[Dxx · p. N]`; blocos
  `conteúdo em imagem — OCR` vêm de tabelas em imagem). Leia **todos** os documentos do lote,
  inteiros.
- Lista fechada de macro e subcategorias: `engine/config.py` (MACROCATEGORIAS).
- Formato: `{{ SCHEMAS }}/ficha.exemplo.json` (os campos `*_exemplo` só mostram o formato).

## 1. Confirme o agrupamento
Os grupos vieram de uma heurística e podem errar. Antes de preencher:
- **Uma ficha por contrato**: contrato + seus aditivos, apostilamentos e anexos. Se dois
  grupos do lote forem o mesmo contrato, faça **uma** ficha listando os dois em `grupos`.
- **Cópias** do mesmo documento: use uma e registre a outra em `observacoes_documentos`.
- Documento que **não é contrato** (planilha, lista consolidada, nota de empenho isolada,
  ordem de serviço sem contrato, publicação): não gera ficha; registre no arquivo de lote
  (seção Saída) com o motivo. Se for o único documento sobre um contrato, gere a ficha com
  o que houver e diga isso em `observacoes_documentos`.
- `orgao_contratante`: quem **assinou** como contratante (ex.: pasta do órgão A com contrato
  assinado pelo órgão B → `ORG-B`). Isso evita contar o mesmo contrato duas vezes no Estado.

## 2. Regras de precisão (inegociáveis)
1. Não invente números, datas, nomes ou produtos. Sem informação: `null`.
2. Valor **original** ≠ **atualizado** (após aditivos). Aditivo não é contrato novo.
3. `valor_anual` só quando informado ou calculável sem premissa duvidosa; explique em
   `base_valor_anual`.
4. `situacao`: compare `vigencia_fim` (considerando prorrogações nos aditivos recebidos) com a
   data de referência: `Vigente`, `Vencido nos documentos` ou `Indeterminada`.
5. **Fontes literais**: `fontes_campos` (contratada, objeto, valor_original, vigencia_fim) e
   cada item com preço levam `{doc, pagina, trecho}`; o trecho é cópia **literal** (8 a 40
   palavras) do texto daquela página. O verificador confere e rejeita o que não achar.
6. Não reproduza CPF, RG ou dados pessoais.

## 3. Itens (o coração da comparação entre órgãos)
Uma linha por item da planilha de preços (inclusive de aditivos que mudem quantidade/preço):
- `produto`: nome de mercado **estável e comparável** — fabricante + produto + edição, sem
  enfeites. Ex.: "Microsoft 365 E3", "Autodesk AEC Collection", "Adobe Creative Cloud",
  "Starlink itinerante", "Link de internet dedicado 100 Mbps", "UST {{ P.estatal_ti.sigla }}", "Outsourcing de
  impressão — página monocromática A4", "Certificado digital e-CPF A3".
- `metrica` explícita (licença/ano, usuário/mês, terminal/mês, UST, PF, página, Mbps/mês,
  unidade); `periodicidade` (mensal | anual | único | global).
- Quantidade, unitário e total exatamente como no documento.

## 4. Blocos específicos (preencha quando couber; senão `null`)
- `desenvolvimento`: fábricas de software, sustentação, ordens de serviço por esforço —
  métrica (UST/PF/HST/horas), quantidade total, preço unitário, se há catálogo de serviços,
  sistemas-alvo citados.
- `nuvem`: hospedagem, nuvem pública/privada, colocation, backup em nuvem — provedor (diga se
  é via {{ P.estatal_ti.sigla }}), modelo, broker (sim/não), capacidade contratada.
- `estatal_ti`: se {{ P.estatal() }} é contratada, intermediária (revende serviço de terceiro) ou integradora.

## 5. Classificação e temas
- `macrocategoria` e `subcategoria`: exatamente da lista fechada; use o objeto principal.
  "Plataforma de simplificação", automação de processos, low-code, chatbot e atendimento
  digital → "Desenvolvimento e sistemas / Plataformas digitais e automação".
- `temas`: etiquetas que ajudem o cruzamento, preferindo esta lista: nuvem, hospedagem,
  data center, backup, fábrica de software, sustentação, BI, simplificação, automação de
  processos, chatbot, IA, Microsoft 365, Google Workspace, Adobe, Autodesk, CAD, antivírus,
  firewall/WAF, banco de dados, link de internet,{% if P.estatal_ti.rede_governo %} {{ P.estatal_ti.rede_governo }},{% endif %} Starlink, telefonia fixa,
  telefonia móvel, impressão, service desk, certificação digital, assinatura eletrônica,
  consultoria/pesquisa, digitalização, treinamento, suprimentos. Crie outra só se necessário.

## Saída
- Uma ficha por contrato em `data/<ORGAO>/fichas/<Gxx>.json`, com o nome do **primeiro**
  grupo do contrato.
- Um resumo do lote em `data/<ORGAO>/fichas/_lote_<n>.json`:
  `{"lote": n, "fichas": ["G01", ...], "sem_ficha": [{"grupo": "G09", "motivo": "..."}]}`.
- Rode `.venv\Scripts\python.exe -m engine fichas-validar <ORGAO> <G01> <G02> ...` até
  todas saírem OK. Avisos de conta: corrija se for erro seu; se o documento tiver o erro,
  registre em `observacoes_documentos`.
- Não altere outros arquivos. Não mencione IA ou ferramentas nos textos.
