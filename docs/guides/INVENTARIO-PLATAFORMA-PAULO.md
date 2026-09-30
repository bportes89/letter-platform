# LETTER Platform — Inventário de módulos e status

**Versão:** 0.24.0  
**Data:** 16/09/2026  
**Empresa:** LETTER FRANQUEADORA LTDA · CNPJ 57.255.607/0001-30  
**Produção:** https://plataformaletter.com.br  
**API:** https://letter-api-fobc.onrender.com  

Documento para apresentação ao cliente (Paulo) e equipe LETTER.  
Legenda de status:

| Status | Significado |
|--------|-------------|
| **Pronto** | Funcional em produção para operação diária |
| **Parcial** | Estrutura e telas prontas; depende de homologação, integração real ou ajuste fino |
| **Pendente** | Planejado ou stand-by; não priorizado no momento |
| **N/A** | Não aplicável nesta fase |

---

## 1. Resumo executivo

A LETTER Platform v0.24.0 é uma plataforma fintech modular para:

- Marketplace de cotas contempladas  
- Crédito estruturado (SDC, Flash Capital, QuitCon)  
- Conta digital e pagamentos (BaaS Asaas)  
- Rede de parceiros e comissões (MMN)  
- Investimentos (Flash Invest), leilões, LSS e automações NINA  

**Prioridade operacional atual (acordada):**

1. Marketplace, SDC, Flash Capital  
2. QuitCon, Flash Invest, SaaS LSS, TAPAF  
3. Lease Equity — **stand-by**

**Infraestrutura:** Frontend Vercel · API Render · Banco Neon (PostgreSQL) · Integração Asaas (subcontas BaaS em homologação).

---

## 2. Site público (sem login)

| Recurso | Rota | Status | Observações |
|---------|------|--------|-------------|
| Home institucional | `/` | **Pronto** | Simuladores Flash/SDC, Nina, leilão vitrine, manuais |
| Login | `/login` | **Pronto** | MFA opcional |
| Cadastro cliente | `/cadastro` | **Pronto** | Auto-cadastro |
| Abertura conta digital | `/cadastro/conta` | **Parcial** | Redireciona ao BANK; KYC Asaas em homologação |
| Cadastro fornecedor | `/cadastro-fornecedor` | **Pronto** | |
| Vender minha cota | `/vender-minha-cota` | **Pronto** | Fluxo público + compliance admin |
| Simulador QuitCon | `/simulador/quitcon` | **Pronto** | |
| Convite / contrato | `/convite`, `/contrato` | **Pronto** | Aceite de convites e contratos |
| Recuperação de acesso | `/recuperar-senha`, `/recuperar-email` | **Pronto** | |
| Selo Asaas (BaaS) | Rodapé | **Pronto** | Conformidade playbook Asaas |

---

## 3. BANK — Conta digital e financeiro

| Módulo | Rota | Status | Funcionalidades | Pendências |
|--------|------|--------|-----------------|------------|
| **Carteira LETTER** | `/modules/my-wallet` | **Parcial** | Subconta Asaas, saldo, extrato, Pix, boleto, wizard RG/selfie, dados bancários (461 - Asaas) | Homologação BaaS; KYC PF sem onboardingUrl em alguns casos |
| **Flash Invest** | `/modules/flash-invest` | **Parcial** | Oportunidades, reservas, checkout Asaas, mútuo/tokens | Tokenização completa em fase 2 |
| **Painel de gestão BANK** | `/modules/bank-control` | **Pronto** | Visão consolidada interna | |
| **Pagamentos e escrow** | `/modules/payments` | **Parcial** | Criar subconta, fila KYC, escrow on/off, transferências admin, sync docs, repair API keys | Escrow taxa Asaas; produção financeira sob flag |
| **Ledger e saldos** | `/modules/wallet` | **Pronto** | Dupla entrada, saldos, extratos | |
| **Cobrança** | `/modules/collections` | **Parcial** | Faturas, régua, cobrança ad-hoc, LSS SaaS | Canais reais de cobrança |

---

## 4. PLATAFORMA — Marketplace e cotas

| Módulo | Rota | Status | Funcionalidades | Pendências |
|--------|------|--------|-----------------|------------|
| **Marketplace (esteiras)** | `/modules/marketplace` | **Pronto** | Esteira comercial, chat, cotas, boletos | |
| **Cadastros** | `/modules/cadastros` | **Pronto** | Novos, negociação, incompleto, concluído, cancelados | |
| **Venda Direta Robô** | `/modules/venda-direta-robo` | **Pronto** | Automação venda direta | |
| **Venda Direta Manual** | `/modules/venda-direta-manual` | **Pronto** | Operação manual | |
| **Minhas compras** | `/modules/minhas-compras` | **Pronto** | Visão cliente | |
| **Fornecedores** | `/modules/fornecedores` | **Pronto** | Cadastro, markup, sync estoque | |
| **Portal fornecedor** | `/portal-fornecedor` | **Pronto** | Login, envio cotas, saldo/saque | |
| **FAQ do chat** | `/modules/chat-faq` | **Pronto** | Base conhecimento chat | |
| **Inventário (admin)** | `/modules/inventory` | **Pronto** | Estoque, reservas, locks | |
| **Compliance vender cota** | `/modules/vender-cota` | **Pronto** | Fila ofertas + aprovação | |
| **Chat marketplace** | (dentro marketplace) | **Pronto** | Fluxo comercial, ref parceiro, ZapSign, e-mails | |
| **Comissões marketplace** | (automático) | **Pronto** | Bolo rachado, markup parceiro, propagador cliente | |
| **Sync cotas fornecedor** | Cron 30 min | **Pronto** | JSON/HTML scrape fornecedores | |

---

## 5. PLATAFORMA — Produtos de crédito

| Módulo | Rota | Status | Funcionalidades | Pendências |
|--------|------|--------|-----------------|------------|
| **Propostas e simulações** | `/modules/proposals` | **Pronto** | Price, Bullet, memória de cálculo | |
| **SDC — Capital de Giro** | `/modules/sdc` | **Pronto** | Mesa desk, simulação, pool investidor, DETRAN, docs admin | |
| **Flash Capital** | `/modules/flash-capital` | **Pronto** | Mesa desk, FinOps V3, recibos, pré-análise, TAPAF | |
| **QuitCon** | `/modules/quitcon` | **Pronto** | Mesa desk, simulador, multas/SLA, integração SDC | |
| **SaaS LSS** | `/modules/lss` | **Parcial** | Assinatura, aceite, cobrança Asaas | Homologação recorrência |
| **Leilão** | `/modules/leilao` | **Parcial** | Vitrine, lances, gated content | Liquidação financeira real |
| **Lease Equity** | `/modules/lease-equity` | **Pendente** | Código existe | **Stand-by** no menu |

---

## 6. PLATAFORMA — Ferramentas e fundação

| Módulo | Rota | Status | Funcionalidades | Pendências |
|--------|------|--------|-----------------|------------|
| **Identidade e organizações** | `/modules/identity` | **Pronto** | Usuários, filiais, convites e-mail, KYC, **admin permissões granulares** | Editar permissões de admin existente (só criar) |
| **RBAC e segurança** | `/modules/rbac` | **Pronto** | Papéis, MFA, sessões, auditoria | |
| **CRM e originação** | `/modules/crm` | **Pronto** | Leads, funil, parceiros | |
| **Administradoras** | `/modules/administrators` | **Parcial** | Cadastro, regras BACEN/SCR | Sync regras automático |
| **NINA Engine** | `/modules/nina` | **Parcial** | Underwriting, políticas, contingência | Provedores externos reais |
| **Imóveis estruturados** | `/modules/structured-properties` | **Parcial** | LTV 40%, payout fases | Operação real |
| **Contratos e documentos** | `/modules/contracts` | **Parcial** | Templates, PDF, ZapSign | Cláusula Asaas nos termos |
| **Manuais e contratos** | `/modules/legal-manuals` | **Pronto** | Manuais PDF por produto | |
| **Rede e comissões (MMN)** | `/modules/mmn` | **Pronto** | Árvore 5 níveis, regras, link indicação, repasses | NFS-e real |
| **TaxTech** | `/modules/taxtech` | **Parcial** | NFS-e mock, elegibilidade | Provedor municipal |
| **Comunicações** | `/modules/communications` | **Parcial** | Templates, e-mail | WhatsApp oficial |
| **BI e relatórios** | `/modules/reports` | **Pronto** | Funil, carteira, CSV | Data warehouse |
| **Operações** | `/modules/operations` | **Pronto** | Jobs, métricas, readiness | Worker separado |
| **Backoffice** | `/modules/admin` | **Pronto** | KYC central, configurações | |

---

## 7. Portais por perfil

| Portal | Rota | Perfil | Status |
|--------|------|--------|--------|
| Operação | `/operacao` | Admin / staff | **Pronto** |
| Parceiro | `/parceiro` | Parceiro comercial | **Pronto** |
| Cliente | `/cliente` | Cliente final | **Pronto** |
| Investidor | `/investidor` | Investidor retail | **Pronto** |
| Fundo | `/fundo` | Fundo institucional | **Pronto** |
| Autenticação 2FA | `/seguranca` | Todos | **Pronto** |

---

## 8. Perfis de acesso (RBAC)

| Papel | Descrição | Acesso |
|-------|-----------|--------|
| PLATFORM_ADMIN | Operação LETTER | Total |
| INTERNAL_STAFF | Staff interno | Configurável por permissões granulares |
| MASTER_FRANCHISEE | Franqueadora | Produtos + rede |
| MANAGER | Gestão regional | Produtos + rede (limitado) |
| PARTNER | Parceiro comercial | Marketplace, propostas, produtos |
| CLIENT | Cliente final | Compras, propostas, carteira |
| QUOTA_SELLER | Vendedor de cotas | Marketplace, cadastros |
| RETAIL_INVESTOR | Investidor | Flash Invest, leilão |
| INSTITUTIONAL_FUND | Fundo | Investimentos |
| AUDITOR | Auditoria | Leitura restrita |

**Permissões granulares (set/2026):** Acesso Total Sim/Não + checkboxes por grupo (Administradores, Cadastros, SDC, Flash, BANK, etc.) — catálogo com 6 grupos.

---

## 9. Integrações externas

| Integração | Status | Uso na LETTER |
|------------|--------|---------------|
| **Asaas (BaaS)** | **Parcial** | Subcontas, Pix, boleto, escrow, split MMN, checkout investimento, webhooks |
| **ZapSign** | **Parcial** | Assinatura contratos marketplace e geral |
| **InfoSimples** | **Parcial** | DETRAN e consultas cadastrais |
| **Resend / SMTP** | **Pronto** | Convites, transacionais marketplace e BANK |
| **Neon (PostgreSQL)** | **Pronto** | Banco de produção |
| **Vercel** | **Pronto** | Frontend |
| **Render** | **Pronto** | API + crons |

---

## 10. Entregas recentes (set/2026)

| Entrega | Descrição |
|---------|-----------|
| Permissões granulares admin | Criar admin com Acesso Total ou permissões por módulo |
| Documentos admin | Anexar, baixar e excluir em SDC, Flash, QuitCon, Marketplace, KYC subcontas |
| KYC BANK | Wizard RG/selfie embutido na carteira |
| Selo Asaas BaaS | Rodapé site + área logada |
| Dados bancários | Nome Asaas restaurado (461 - Asaas IP S.A.) |
| Transferências admin | Pix terceiros e transferência entre subcontas |
| Marketplace | Comissões bolo rachado, portal fornecedor, sync cotas |
| E-mails | Convites, boleto, pagamento, carteira LETTER-branded |

---

## 11. Pendências e homologações em andamento

| Item | Prioridade | Responsável / ação |
|------|------------|-------------------|
| Homologação BaaS Asaas (subcontas produção) | Alta | Formulário + selo + playbook (em andamento) |
| Cláusula contratual Asaas nos termos | Alta | Jurídico |
| Selo Asaas em telas de subconta/contrato | Média | Dev (além do rodapé) |
| KYC PF sem onboardingUrl Asaas | Média | Limitação Asaas; wizard LETTER como fallback |
| Editar permissões admin existente | Baixa | UI pendente |
| Lease Equity | Baixa | Stand-by até nova ordem |
| Transações financeiras reais (`FINANCIAL_TRANSACTIONS_ENABLED`) | Alta | Após homologação BaaS |
| App mobile (iOS / Android) | Média | **Alinhado com o cliente**; ainda não desenvolvido — hoje a entrega é web responsiva |

---

## 12. Contagem de módulos

| Categoria | Quantidade |
|-----------|------------|
| Módulos API (`/modules`) | 24 |
| Produtos comerciais (rotas frontend) | 12+ |
| Páginas públicas | 10+ |
| Portais por perfil | 6 |
| Migrations banco | 50+ |
| Perfis RBAC | 10 |

---

## 13. Como gerar PDF deste documento

1. Abra este arquivo no VS Code / Cursor e use **Markdown: Export (PDF)** ou  
2. Copie para Google Docs / Word e exporte PDF, ou  
3. No GitHub: visualizar o `.md` e imprimir (Ctrl+P → Salvar como PDF).

---

*Documento gerado a partir do estado do repositório `letter-platform` branch `main` em 16/09/2026.*
