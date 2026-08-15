# Arquitetura da LETTER

## Decisão principal

A plataforma começa como **monólito modular**. Há um único backend implantável, mas os domínios permanecem separados em módulos. Isso reduz custo operacional e permite que um desenvolvedor mantenha a solução sem a sobrecarga prematura de microsserviços.

## Camadas

1. **Interfaces**: painel Next.js e, futuramente, aplicativo mobile.
2. **API**: FastAPI com contratos OpenAPI, autenticação, validação e idempotência.
3. **Domínio**: regras de marketplace, SDC, Flash Credit, funding, rede, fiscal e leilões.
4. **Persistência**: PostgreSQL em produção; SQLite apenas no desenvolvimento inicial.
5. **Integrações**: adaptadores para BaaS/escrow, KYC, assinatura, bureaus, WhatsApp e documentos.
6. **Jobs**: filas para webhooks, notificações, consultas, documentos e reconciliação.

## Princípios obrigatórios

- Multiempresa e deny-by-default.
- Ledger financeiro de dupla entrada.
- Idempotência em todo evento financeiro.
- LLM/NINA não movimenta dinheiro nem calcula saldos.
- Operações críticas exigem step-up e dupla aprovação.
- Fornecedores externos nunca vazam para o domínio; todos entram por interfaces/adaptadores.
- Fórmulas financeiras são versionadas e testadas por exemplos canônicos.

## Estado dos adaptadores

Os endpoints de payout permanecem bloqueados enquanto `LETTER_FINANCIAL_TRANSACTIONS_ENABLED=false`. Essa é uma trava intencional para impedir que uma integração simulada seja confundida com fluxo financeiro real.
