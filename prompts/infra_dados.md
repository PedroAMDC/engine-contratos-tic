# Mapa da infraestrutura de dados — regras do agente

Levantamento{% if P.relatorio.demandante_mapa %} pedido pela {{ P.relatorio.demandante_mapa }}{% endif %}: **onde estão fisicamente os dados
de cada órgão e quanto custa manter essa infraestrutura**. Você trabalha sobre contratos já
fichados e extrai, de cada contrato do lote, os **ambientes** de armazenamento e processamento
de dados que ele paga ou descreve. Não detalhe sistemas nem licenças de software.

## Entradas
- Lista de contratos do lote (ids `PASTA-Gxx`) informada na tarefa.
- Ficha de cada contrato: `data/<PASTA>/fichas/<Gxx>.json` (documentos, objeto, itens, valores).
- Textos: `data/<PASTA>/texto/Dxx.md`. Procure (Grep) termos como data center, datacenter,
  hospedagem, nuvem, colocation, sala-cofre, servidor, storage, armazenamento, backup,
  endereço, localizado, instalações, firewall, link, energia, climatização, cabeamento,
  e leia o contexto das páginas relevantes (especificações e termo de referência).

## O que registrar por contrato (`data/<PASTA>/infra/<Gxx>.json`, formato `{{ SCHEMAS }}/infra.exemplo.json`)
- `ambientes`: um item por local/ambiente onde dados do órgão ficam ou são processados:
  - `tipo`: Datacenter {{ P.estatal('de') }} · Outro datacenter governamental · Nuvem pública ·
    Nuvem privada de terceiros · Colocation · Ambiente próprio do órgão · Não identificado.
  - `provedor` ({{ P.estatal_ti.sigla }}, Oracle via {{ P.estatal_ti.sigla }}, AWS, Azure, Google, empresa de colocation...),
    `local` (descrição: "datacenter {{ P.estatal('de') }} em {{ P.ente.capital }}", "região AWS São Paulo"...),
    `endereco` (só se constar do documento), `componentes` (lista: hospedagem, servidores,
    armazenamento, backup, processamento, banco de dados, firewall, conectividade, energia,
    climatização, cabeamento, monitoramento, outro).
  - `custo_mensal`, `custo_anual` do que este contrato paga por esse ambiente (só se
    documentado ou calculável; senão `null`) e `base_custo` (explique o cálculo).
  - `fonte`: `{doc, pagina, trecho}` literal que sustente tipo/local.
- `pagador`: órgão que paga o contrato (pode diferir da pasta).
- `relevante`: `false` se o contrato não envolve ambiente de dados (ex.: link de internet
  puro, impressora) — nesse caso `ambientes` pode ficar vazio, mas registre componentes de
  conectividade/firewall que sirvam a um ambiente, se houver.
- `lacunas`: o que o órgão ainda precisa informar (endereço, rateio, infraestrutura própria,
  energia/climatização) que o contrato não responde.

## Regras
- Nada inventado: sem evidência de local, use "Não identificado".
- Dados pessoais (CPF, nomes de servidores): não reproduza.
- Rode `.venv\Scripts\python.exe -m engine infra-validar <PASTA> <Gxx> ...` até OK.
- Não altere outros arquivos; não mencione IA ou ferramentas.
