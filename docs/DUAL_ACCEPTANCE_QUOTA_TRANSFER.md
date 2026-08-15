# Duplo aceite da carta contemplada — v0.20.0

## Objetivo

Separar dois momentos que não podem compartilhar o mesmo checkbox ou evidência:

1. **CHECKOUT_INITIAL** — contrato completo e aceite inicial no fim do checkout, antes do Pix ou boleto.
2. **TRANSFER_RELEASE** — confirmação crítica após a administradora informar a transferência, quando o comprador verifica a titularidade e autoriza o repasse.

Cada texto possui tipo, versão, corpo, SHA-256, estado de revisão jurídica e vigência. Somente uma versão `APPROVED` e ativa pode receber aceites.

## Esteira implementada

1. O comprador lê o contrato e marca duas confirmações explícitas no checkout.
2. O aceite registra usuário, data/hora, IP, agente do navegador, versão e hashes.
3. Um operador informa o protocolo de transferência e o sistema abre a janela exata de 24 horas.
4. Jobs idempotentes avisam imediatamente, após 12 horas e quando faltarem 2 horas, pelos canais Super App, WhatsApp e e-mail.
5. O comprador acessa o portal oficial da administradora e retorna à LETTER.
6. A confirmação crítica exige login realizado, cota em nome do comprador e autorização expressa de repasse. A referência biométrica é opcional; nenhuma imagem biométrica é armazenada neste módulo.
7. Payout vinculado à carta só passa pelo gate quando a verificação está `BUYER_CONFIRMED` e `payout_unlocked=true`. Aprovações financeiras e step-up continuam obrigatórios.

## Estados e bloqueios

- `AUDIT_WINDOW_OPEN`: saldo bloqueado.
- `BUYER_CONFIRMED`: segundo aceite registrado; gate documental liberado.
- `EXPIRED_REVIEW`: prazo expirado; saldo bloqueado para revisão manual.
- `DISPUTED`: contestação aberta; saldo bloqueado.

Não existe liberação automática por silêncio. A prontidão sempre informa `automatic_release_on_silence=false`.

## Segurança jurídica

Aceite tácito, prazo decadencial, quitação irrestrita, eleição de foro e exclusões de responsabilidade presentes na fonte não são considerados automaticamente válidos. Os textos ficam configuráveis e só podem ser ativados por aprovação jurídica com step-up e auditoria. O sistema não declara “fé pública” nem biometria quando não houver evidência de fornecedor homologado.

## Endpoints principais

- `POST /acceptance-templates`
- `POST /acceptance-templates/{id}/approve`
- `POST /contracts/{id}/checkout-acceptance`
- `POST /contracts/{id}/transfer-verification`
- `POST /transfer-verifications/{id}/confirm-release`
- `POST /transfer-verifications/{id}/dispute`
- `GET /transfer-verifications/{id}/release-readiness`
