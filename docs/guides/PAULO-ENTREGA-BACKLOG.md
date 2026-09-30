# Backlog de entrega — requisitos Paulo Stutz × LETTER

**Fonte:** WhatsApp + prints legado (admin categorias, liberações, robô, bank, extratos).  
**Legenda:** ✅ feito no código · 🟡 parcial · ❌ pendente · 📋 operação/homologação (dados em prod)

---

## Fase A — Marketplace / cartas contempladas (prioridade Paulo)

| ID | Entrega | Status | Notas |
|----|---------|--------|-------|
| A1 | Categorias de cotas (CRUD + ativo/ordem) | ✅ | `/modules/quota-categories` |
| A2 | Subcategorias (pai/filho) + import legado SQL | ✅ | `import-legacy` |
| A3 | Administradoras: liberações categoria/sub + ano máx. | ✅ | UI alienações |
| A4 | Mesmas regras em Venda Direta Manual + Robô + chat | ✅ | Filtros `venda_direta_filters`; robô com parceiro/markup; manual lista alienações/bancos |
| A5 | Robô: **2 opções crédito + 2 entrada** (réguas 10/20/5) | ✅ backend | UI chat enriquecida (A5b) |
| A5b | Cards opção: admin, tipo, parcelas “Nx … mais …”, vencimento | ✅ | Chat (cards na escolha) + admin robô |
| A6 | Vídeo explicativo no fluxo do robô/chat | ✅ | `chat_robo_video_url` + embed YouTube/Vimeo |
| A7 | Boleto entrada no fluxo | ✅ | Passo chat + Inter |
| A8 | Contrato: aceite chat + ZapSign **após pagamento entrada** | ✅ código | Alinhar expectativa Paulo vs ordem legado |
| A9 | E-mails personalizados (CMS + import texts) | ✅ | Slugs `email-marketplace-*`; `POST /cms/texts/ensure-marketplace-emails` + import legado |
| A10 | Contrato HTML editável (org-settings / CMS) | ✅ | Jurídico + homologação |
| A11 | `% plataforma` (x_settings) na liberação comissão | ✅ | Fallback `platform_commission_percent` |
| A12 | Import dados prod (categorias, texts, admins, cotas) | 📋 | Dump/ETL no Render |

---

## Fase B — Bank legado (stand-by Asaas)

| ID | Entrega | Status |
|----|---------|--------|
| B1 | Manter nome **Bank** sem wizard abertura conta / KYC Asaas | ✅ | `bank_display_mode` default **legacy**; UI «BANK · Meus ganhos» |
| B2 | Parceiro: **Meus ganhos** (disponível, total, sacar) | ✅ | `/wallet/me/legacy-earnings` (+ total sacado, saque pendente) |
| B3 | Parceiro: **extrato** linha a linha (comissão/saque) | ✅ | `/wallet/me/legacy-statement` + status PT + filtro |
| B4 | Parceiro: solicitação de saque | ✅ | `POST/GET /wallet/me/legacy-withdrawals`, PIX pré-preenchido |
| B5 | Saque bloqueado até **NF aprovada** (validador notas) | ✅ | Hold fiscal + gate saque legado |
| B6 | Admin: extrato **fornecedor** | ✅ | Aba + ledger `/marketplace/extrato/supplier-ledger` |
| B7 | Admin: extrato **parceiro/franquia** | ✅ | Aba parceiros + `scope=partner` |
| B8 | Admin: extrato **plataforma** (líquido após repasses) | ✅ | Resumo + por venda (`platform_net`) |
| B9 | Admin: fila **saques** fornecedor + parceiro | ✅ | Fornecedores + menu «Saques parceiros» |

---

## Fase C — Qualificação / gratificação

| ID | Entrega | Status |
|----|---------|--------|
| C1 | Qualificação SDC + apuração + import legado | ✅ |
| C2 | Gratificação parceiros **marketplace** (menu legado) | ❌ | Escopo: confirmar se = SDC ou rede MMN |
| C3 | Apuração vendas parceiros diretos (plataforma) | ❌ |

---

## Fase D — Produto / infra (fora do espelho PHP imediato)

| ID | Entrega | Status |
|----|---------|--------|
| D1 | Homologação BaaS Asaas produção | 📋 |
| D2 | Cláusulas jurídicas Asaas nos termos | 📋 |
| D3 | App mobile iOS/Android | ❌ |
| D4 | Categorias: reordenar estilo legado (setas) | ❌ | Hoje `sort_order` numérico |

---

## Ordem de implementação (dev)

1. **A5b + A6** — chat robô (cards + vídeo)  
2. **A11** — comissão plataforma na liberação  
3. **A9** — e-mails documento fornecedor/plataforma  
4. **B1–B9** — modo Bank legado + extratos admin  
5. **C2–C3** — após alinhamento escopo gratificação  
6. **D4** — UX categorias  

---

## Critérios de aceite (homologação com Paulo)

- [ ] Import categorias/subcategorias iguais ao menu legado  
- [ ] 1 administradora com liberações como no print (Carro 15 anos, Imóvel sem restrição, …)  
- [ ] Simulação chat: 4 opções (2 crédito + 2 entrada) com parcelas detalhadas  
- [x] Vídeo explicativo visível no fluxo (configurar URL em Configurações gerais)  
- [ ] Compra teste: boleto → pagamento → ZapSign → conclusão → e-mails  
- [ ] Parceiro vê ganhos/extrato/saque (modo legado)  
- [ ] Admin vê extratos 3 perfis + saques  

*Atualizado conforme commits na branch `main`.*
