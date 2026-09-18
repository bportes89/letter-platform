# Checklist — Documento (155) Paulo

Legenda: **OK** implementado em código · **Parcial** depende de dados/homologação · **Ops** configuração Asaas/terceiros · **Stand-by** fora de escopo acordado

## Site e login
| Item | Status |
|------|--------|
| Layout mobile site público | **OK** (CSS responsivo; validar no celular) |
| 2FA por e-mail no login (sem depender só do submenu MFA) | **OK** (`LETTER_LOGIN_EMAIL_OTP`) |
| Submenu MFA TOTP | **OK** opcional em `/seguranca` |

## BANK
| Item | Status |
|------|--------|
| Anexo docs/selfie KYC PF | **Parcial** — PF via link oficial Asaas (limite API) |
| Pix: validar chave, recebedor, comprovante, extrato | **OK** · **Ops** homologação Pix Asaas |
| Boleto cobrança + pagamento de contas visíveis | **OK** (bloqueio até KYC) |
| Enviar dinheiro duplicado | **OK** (CSS) |
| Over/ganhos taxas Asaas | **Parcial** — painel quando há eventos com custo |
| Flash Invest — painel operacional | **OK** (resumo + links) |

## Marketplace
| Item | Status |
|------|--------|
| Esteiras sem números fixos / ano só veículo | **OK** |
| Validação CPF/e-mail/telefone + CEP | **OK** |
| Venda direta robô — cadastros salvos | **OK** |
| Venda direta manual — cotas + multi-cota + gate Bacen | **OK** |
| Cadastros só do parceiro | **OK** (filtro `owner_id`) |
| Cadastros pipelines (concluído/negociação…) | **OK** (cadastro_service) |
| Inventário Nina pendente (admin/API) | **OK** auto-approve ingest |
| FAQ chat — usabilidade | **OK** (texto introdutório) |
| Fornecedores | Ver `docs/MARKETPLACE.md` |

## Propostas
| Item | Status |
|------|--------|
| Campos sem valores salvos | **OK** |
| Flash IPCA no fundo | **OK** |
| Texto de orientação | **OK** |

## SDC / Flash / QuitCon
| Item | Status |
|------|--------|
| SDC — matrícula, placa, alavancagem, endereço, sócios | **OK** |
| SDC — docs por operação | **OK** (painel por solicitação) |
| Flash — R$, matrícula, quitação gravame, IPCA fundo | **OK** |
| TAPAF / OCR / Valid-Stamp upload | **Parcial** — módulos FinOps/Pré-análise (fluxo interno) |
| QuitCon — multi cota, bem alienado, tipos bem, sócios | **OK** |
| QuitCon — token inválido | **OK** (refresh JWT) |
| Sócios em todos os produtos | **OK** SDC, Flash, QuitCon |

## SaaS LSS / Leilão / Lease Equity
| Item | Status |
|------|--------|
| LSS outbound leads | **Parcial** — produto configurável; campanhas reais = Ops |
| Leilão | Sem mudança (cliente não testou) |
| Lease Equity | **Stand-by** |

## Não resolvível só com código
- Homologação BaaS Asaas (Pix, subcontas, limites sandbox)
- Integrações Nina externas (ONR, Serasa, etc.) — checklists em `docs/`
