# NINA Asset — execução patrimonial controlada

## Escopo da v0.19.0

O subsistema conecta inadimplência Flash Credit, operação, evidências, documentos e preparação de leilão. A automação calcula prazos e organiza a fila operacional; decisões com efeito jurídico ou financeiro permanecem bloqueadas.

| Marco | Ação do sistema | Controle |
|---|---|---|
| H+1 a H+5 | Janela de alertas amigáveis | Simulação de e-mail e WhatsApp |
| H+6 | Solicitação de trava preventiva | Aprovação, sem bloqueio BaaS real |
| H+16 | Preparação de notificação extrajudicial | Aprovação e provedor cartorial pendente |
| H+30 | Relógio de caducidade | Aviso informativo, sem efeito automático |
| H+61 | Revisão de caducidade e leilão | Dupla aprovação e legal hold |

## Entidades

- `NinaDistressCase`: estado consolidado do caso, AVM, preços e gates.
- `NinaDistressEvent`: timeline idempotente com hash de evidência.
- `NinaCriticalApproval`: decisão individual por gate e aprovador.
- `NinaLegalDocument`: minuta versionada com conteúdo e hash SHA-256.

## Gates críticos

`CASH_HOLD` e `CARTORIO_NOTICE` exigem uma aprovação. `CADUCITY` e `AUCTION_PUBLICATION` exigem duas pessoas distintas. Todas as operações de aplicação de gate exigem step-up de autenticação.

Mesmo após as aprovações, a v0.19.0 grava estados como `SIMULATED_HOLD`, `APPROVED_FOR_SANDBOX` e `SANDBOX_READY`. O campo `legal_hold` permanece ativo.

## Precificação sandbox

- Preço inicial: 80% do AVM informado.
- Redução padrão: R$ 500,00 por execução diária.
- Piso: 50% do AVM.
- A rotina não atua em lotes produtivos nem movimenta recursos.

## Documentos

O sistema gera minutas PDF de notificação extrajudicial, notificação de desocupação, edital e ata. Todos os arquivos exibem aviso de ausência de efeito jurídico/registral, versão e hash de integridade.

## Pendências para produção

- Parecer jurídico sobre retrovenda, consolidação, leilão, posse, edital e título registral.
- Templates aprovados e dados oficiais da SPE.
- Integração com RTD/e-Notariado ou prestador homologado.
- BaaS/escrow oficial e regras autorizadas de bloqueio e split.
- AVM homologado, documentos do imóvel, fotos S3 e cadeia de custódia.
- Processo humano de exceção, suspensão, recurso e recuperação do pagamento.
