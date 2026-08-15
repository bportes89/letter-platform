# Eventos FinOps e SDC — v0.23.0

O inbox aceita os oito eventos documentados com HMAC-SHA256, tolerância temporal e idempotência. Reutilizar o mesmo `event_id` com outro payload é conflito; assinatura alterada é rejeitada.

Eventos de cobrança, notificação, caducidade, timeout SDC, liquidação Bullet, MMN e payout biométrico geram registros e decisões sandbox. Nenhum deles congela conta externa, transfere Pix, estorna capital, consolida imóvel ou publica leilão sozinho.

Para o SDC, a prévia calcula juros simples de 2,5% a.m. proporcionais a 45 ou 90 dias. No MMN, 50% vão ao Master e os outros 50% são normalizados nos pesos 35/7/5/3. Isso corrige a inconsistência do payload-fonte, que distribuía somente R$ 3.000 de uma verba de R$ 4.000. Todos os resultados permanecem `PENDING_FISCAL` e `PREVIEW_ONLY_NO_FUNDS`.
