# Revisão de um tema após a verificação adversarial — regras

Você recebe um tema do resumo estadual (`data/_global/temas/<n>.json`) e os vereditos dos
revisores céticos de cada achado (`data/_global/vereditos/<n>.json`: lista de
`{achado, revisor, refutado, motivo, ajuste_sugerido, tipo_correto}`).

Para cada achado:
- **Refutado pelos dois revisores** → exclua o achado (ou transforme em hipótese de baixo
  potencial e confiança, se o núcleo ainda se sustentar com outra redação — diga por quê).
- **Refutado por um** → leia o motivo e confira nos documentos: se procede, corrija o texto,
  o tipo, os contratos ou a economia; se não procede, mantenha e registre por quê.
- **Ajustes sugeridos** pertinentes → aplique.
- Mantenha de 4 a 10 achados; não crie achados novos sem evidência.

Registre em `data/_global/temas/<n>.revisao.json`: `{achado: {decisao: "mantido|corrigido|rebaixado|excluído", motivo}}`.
Depois rode `.venv\Scripts\python.exe -m engine estadual-validar tema <n>` até OK.
Não altere outros arquivos e não mencione IA ou ferramentas nos textos.
