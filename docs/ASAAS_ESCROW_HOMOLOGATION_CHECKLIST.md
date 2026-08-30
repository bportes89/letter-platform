# Checklist de homologação — Integração Asaas (Conta Escrow / Subcontas)

**Projeto:** LETTER Platform  
**Escopo:** Abertura de conta Escrow e subcontas Asaas direto pela plataforma (fluxo 1 clique)  
**Ambiente inicial:** Sandbox (homologação) → Produção (go-live)  
**Responsável LETTER (engenharia):** ___________________________  
**Responsável cliente (financeiro/compliance):** ___________________________  
**Data:** ___ / ___ / ______

---

## 1. Objetivo

Este checklist reúne o que o **cliente LETTER** precisa providenciar junto ao **Asaas** para habilitarmos na plataforma o fluxo de:

- criação/gestão de **subcontas**;
- configuração de **Conta Escrow** (retenção de valores);
- recebimento de **webhooks** de confirmação;
- migração controlada para **produção**.

Sem estes itens, a integração permanece em modo **sandbox/mock** na plataforma.

---

## 2. Documentação oficial Asaas (referência)

| Recurso | URL |
|--------|-----|
| Portal de desenvolvedores | https://docs.asaas.com |
| Ambiente Sandbox | https://docs.asaas.com/docs/sandbox |
| Chaves de API | https://docs.asaas.com/docs/chaves-de-api |
| Autenticação | https://docs.asaas.com/docs/autenticação |
| Guia Conta Escrow (subcontas) | https://docs.asaas.com/docs/habilitando-a-conta-escrow-para-as-subcontas |
| API — configurar Escrow da subconta | https://docs.asaas.com/reference/salvar-ou-atualizar-configuracao-da-conta-escrow-para-a-subconta |
| API — configuração padrão Escrow | https://docs.asaas.com/reference/criar-configuracao-padrao-da-conta-escrow-para-todas-as-subcontas |
| Conta Sandbox (cadastro) | https://sandbox.asaas.com |
| Suporte integrações Asaas | integracoes@asaas.com.br |

**URLs base da API**

| Ambiente | Base URL |
|----------|----------|
| Sandbox | `https://api-sandbox.asaas.com/v3` |
| Produção | `https://api.asaas.com/v3` |

---

## 3. Checklist — Sandbox (obrigatório para iniciar desenvolvimento)

### 3.1 Conta e acesso

- [ ] Conta **Sandbox** criada em https://sandbox.asaas.com (independente da conta de produção)
- [ ] Usuário **administrador** com acesso ao menu **Integrações**
- [ ] API Key Sandbox gerada e armazenada em cofre seguro (ex.: 1Password, Azure Key Vault, variável Render criptografada)
- [ ] API Key **não** compartilhada por WhatsApp, e-mail corporativo aberto ou chat sem criptografia
- [ ] Confirmação de que a chave é do ambiente **Sandbox** (prefixo típico `$aact_hmlg_...`)

### 3.2 Produto Escrow / Subcontas

- [ ] Confirmado com Asaas se a **Conta Escrow** está habilitada na conta principal (Sandbox)
- [ ] Confirmado se o modelo LETTER usará **subcontas** (white label / split) ou apenas conta principal
- [ ] Definido **quem paga a mensalidade** da Conta Escrow (`isFeePayer`: conta principal vs subconta)
- [ ] Definido **período de retenção** padrão (`daysToExpire` em dias) alinhado ao jurídico/ops
- [ ] Definidos fluxos que usarão Escrow (ex.: taxa sucesso QuitCon 10%, TAPAF, quitação cedente, Flash Capital pool)

### 3.3 Dados para configuração na LETTER

Preencher e enviar ao time de engenharia (canal seguro):

| Campo | Valor |
|-------|-------|
| Razão social titular Asaas | |
| CNPJ titular | |
| E-mail administrador Asaas | |
| Ambiente | **Produção** (chave `$aact_prod_*`) |
| API Key (referência — não colar aqui se documento for compartilhado) | Ver cofre seguro → `LETTER_ASAAS_API_KEY` |
| Wallet ID | `LETTER_ASAAS_WALLET_ID` |
| Base URL Produção | `LETTER_ASAAS_BASE_URL=https://api.asaas.com/v3` |
| Eventos webhook desejados | |
| `daysToExpire` padrão | ___ dias |
| `isFeePayer` padrão | Principal / Subconta |
| IP(s) de origem (se Asaas exigir allowlist) | |

### 3.4 Webhooks (Sandbox)

- [ ] URL de webhook de homologação registrada no painel Asaas
- [ ] Secret/token de assinatura webhook definido (se aplicável)
- [ ] Teste de recebimento de evento simulado (pagamento confirmado, transferência, etc.)
- [ ] Política de **idempotência** acordada (mesmo `event_id` não processa duas vezes)

### 3.5 Validação técnica mínima (Sandbox)

- [ ] Criar subconta via API (se aplicável)
- [ ] Habilitar Escrow na subconta: `POST /v3/accounts/{id}/escrow`
- [ ] Simular cobrança / pagamento fictício
- [ ] Confirmar retenção e liberação conforme `daysToExpire`
- [ ] Validar logs e conciliação interna LETTER

---

## 4. Checklist — Produção (go-live)

Somente após **100% dos testes Sandbox** e aprovações internas.

### 4.1 Contrato e compliance

- [ ] Contrato comercial Asaas assinado (conta produção)
- [ ] Conta Escrow e subcontas **habilitadas em produção**
- [ ] Parecer jurídico sobre retenção Escrow, devolução 100% (ex.: reprovação ADM QuitCon) e multas contratuais
- [ ] Parecer compliance / PLD sobre fluxo de subcontas e titularidade dos recursos
- [ ] Política de KYC/KYB alinhada ao onboarding Asaas

### 4.2 Credenciais e segurança

- [ ] API Key **Produção** gerada (usuário admin, menu Integrações)
- [ ] Chave produção armazenada apenas em cofre / variáveis de ambiente produção (Render)
- [ ] Rotação de chaves documentada (quem gera, quem revoga, periodicidade)
- [ ] Webhook produção com HTTPS e allowlist de IPs (se exigido)
- [ ] Monitoramento de falhas, circuit breaker e alertas operacionais

### 4.3 Gate de go-live LETTER (interno)

- [ ] Adaptador oficial Asaas implementado e certificado no módulo **Operações → Adaptadores**
- [ ] Certificação 8/8 controles + 4 aprovações (Segurança, Jurídico, Compliance, Operações)
- [ ] Flag `financial_transactions_enabled` liberada apenas após gate
- [ ] Runbook de incidentes (Asaas indisponível, webhook atrasado, divergência de saldo)
- [ ] Plano de rollback (voltar para mock / bloquear novas aberturas)

---

## 5. Decisões de negócio a fechar (cliente)

| # | Decisão | Opções | Decisão tomada |
|---|---------|--------|----------------|
| 1 | Modelo de conta | Subconta por operação / por cliente PJ / conta única | |
| 2 | Prazo Escrow padrão (`daysToExpire`) | ___ dias | |
| 3 | Quem paga taxa Escrow | Conta LETTER / Subconta / Tomador | |
| 4 | Produtos que usam Escrow na v1 | QuitCon / Flash / SDC / Leilão / Todos | |
| 5 | Liberação manual vs automática | Automática após prazo / Manual por ops | |

---

## 6. Entregáveis do time LETTER após recebimento dos itens

1. Adaptador `AsaasEscrowAdapter` (create_account, escrow config, webhooks)
2. Botão **“Abrir conta Escrow”** (1 clique) no Deal Room / módulo financeiro
3. Substituição do provider `MOCK` por `ASAAS` nas contas escrow reais
4. Conciliação BaaS/escrow no painel de Operações
5. Evidências de homologação Sandbox documentadas
6. Go-live produção somente após checklist seção 4

---

## 7. Contatos

| Papel | Contato |
|-------|---------|
| Suporte integrações Asaas | integracoes@asaas.com.br |
| Engenharia LETTER | ___________________________ |
| Financeiro / Tesouraria cliente | ___________________________ |
| Jurídico / Compliance cliente | ___________________________ |

---

## 8. Assinaturas de ciência

**Cliente LETTER — Financeiro / Tesouraria**

Nome: ___________________________  
Cargo: ___________________________  
Data: ___ / ___ / ______  
Assinatura: ___________________________

**Cliente LETTER — Compliance / Jurídico**

Nome: ___________________________  
Cargo: ___________________________  
Data: ___ / ___ / ______  
Assinatura: ___________________________

**LETTER — Engenharia / Produto**

Nome: ___________________________  
Cargo: ___________________________  
Data: ___ / ___ / ______  
Assinatura: ___________________________

---

*Documento gerado para homologação da integração Asaas Escrow — LETTER Platform v0.24+*
