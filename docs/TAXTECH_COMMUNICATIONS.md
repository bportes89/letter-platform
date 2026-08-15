# TaxTech e comunicações

## TaxTech

A v0.9.0 registra documentos fiscais simulados com número, competência, hash, valor bruto e imposto. O fechamento mensal compara as comissões geradas com a cobertura documental de cada beneficiário, calcula o payout elegível e abre exceções para valores sem NFS-e suficiente.

O mesmo fechamento é idempotente por organização e competência. Resoluções de exceção exigem step-up e permanecem auditadas. A emissão atual é mock: produção depende de integração municipal ou provedor fiscal, certificados, regras tributárias validadas e processo contábil homologado.

## Comunicações

Templates de WhatsApp, e-mail e mensagem interna são versionados. Uma nova versão desativa a anterior para novos envios sem apagar o histórico. Cada contato mantém preferência por canal, origem e evidência do consentimento.

Campanhas de marketing exigem opt-in; qualquer opt-out bloqueia novos envios no canal. A chave idempotente evita mensagens duplicadas em retries. O adaptador mock permite enfileirar e confirmar a entrega sem consumir serviço externo.

## Gate de produção

WhatsApp e e-mail reais exigem provedores oficiais, templates homologados, gestão de credenciais, assinatura de webhooks, política de retry, limites de frequência, base legal, retenção, atendimento a direitos do titular e monitoramento de reputação. NFS-e e payout dependem de validação contábil, fiscal e jurídica.
