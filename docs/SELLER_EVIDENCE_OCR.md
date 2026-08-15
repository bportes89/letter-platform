# Lastros do vendedor e OCR cruzado — v0.21.0

## Gate anterior ao cronômetro de 24 horas

A janela do comprador só pode começar depois de quatro controles:

1. upload do extrato oficial da cota;
2. upload do documento/e-mail com protocolo da administradora;
3. upload do termo de cessão;
4. OCR conforme e aprovação humana com step-up.

O motor verifica o termo `CONTEMPLADA`, extrai o protocolo, confronta CPF/CNPJ das partes e identifica indícios textuais de assinatura, reconhecimento ou ICP-Brasil. Os arquivos permanecem no serviço de documentos com SHA-256 e quarentena. Os textos OCR e os documentos completos não são gravados na tabela de auditoria; são persistidos somente os resultados, documentos mascarados, referências e hash do snapshot.

## Estados

- `PENDING_OCR`
- `OCR_PASSED_PENDING_REVIEW`
- `REJECTED_DIVERGENT`
- `APPROVED`
- `REJECTED_MANUAL`

OCR é ferramenta de triagem, não “fé pública”, validação cartorial ou prova definitiva. Divergências impedem aprovação. Mesmo com OCR conforme, a revisão humana é obrigatória.

## Comunicações

A aprovação dos lastros permite iniciar a janela de 24 horas e os jobs já existentes de aviso imediato, H+12 e H+22. Os canais previstos são Super App, WhatsApp e e-mail. Os templates produtivos dependem de fornecedor homologado, consentimentos e parecer jurídico.

