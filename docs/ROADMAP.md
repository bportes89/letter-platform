# Roadmap de desenvolvimento

O projeto completo será evoluído dentro desta mesma pasta.

## Fundação — iniciada nesta entrega

- Monorepo backend/frontend.
- FastAPI, banco e configuração por ambiente.
- Usuários, organizações, autenticação e RBAC.
- CORS e Swagger.
- Leads, administradoras, cotas, propostas, operações, ledger e auditoria.
- Validador NINA para categoria e administradora.
- Catálogo navegável dos 18 módulos.
- Painel web responsivo e dados de demonstração.
- Trava explícita de transações financeiras.
- Testes iniciais de API e regras críticas.

## Domínio operacional — entregue na v0.2.0

- Alembic e esquema compatível com PostgreSQL.
- CRUD operacional de leads, cotas e propostas.
- Telas reais de CRM, inventário e propostas.
- Reserva de cotas, expiração por TTL e liberação controlada.
- Memória de cálculo versionada para marketplace.
- Contrato vinculado ao cálculo, hash de integridade e aceite com evidência.
- Ledger de dupla entrada com referência idempotente.

## Documentos e operação financeira simulada — entregue na v0.3.0

- Contratos em PDF com hash e versão financeira.
- Upload validado e armazenado em quarentena.
- Scanner e assinatura por adaptadores mock substituíveis.
- Plano de contas e saldos derivados do ledger.
- Simulador de escrow com webhooks idempotentes.
- Payout bloqueado e liberado após duas aprovações distintas.
- Telas de contratos, wallet e pagamentos.

## Identidade avançada e compliance — entregue na v0.4.0

- Organizações, filiais, regiões, convites e administração de usuários.
- MFA, recuperação de senha, sessões e step-up para ações críticas.
- Rotação de refresh token e revogação de sessões.
- Esteira KYC/KYB com adaptador mock e decisão auditável.
- Telas de identidade, segurança e compliance.

## Motores SDC e Flash Credit — entregue na v0.5.0

- Memória de cálculo persistente e versionada por proposta.
- SDC com juros simples de 4,5% a.m. e vencimento Bullet.
- Split SDC de 2,5% para investidores e 2% de spread LETTER.
- Taxa de Start de 3% para imóveis e 5% para veículos, incluindo marcos.
- Fee SDC de 10% e comissão de captação de 1%.
- Flash Credit Retail com Tabela Price de 36 ou 60 meses.
- Parcela Balloon obrigatória no mês 36 para o plano de 60 meses.
- Flash Credit institucional a 14% a.a. + IPCA informado na simulação.
- Taxa de gestão de 0,5% a.a., fee da plataforma de 10% e provisão de ITBI de 3%.
- Trava de LTV máximo de 40% e tela operacional para os dois produtos.

## MMN e funding simulado — entregue na v0.6.0

- Árvore comercial e de captação com cinco níveis.
- Matrizes de comissão versionadas por produto.
- Wallet de comissões, Hold Fiscal e privacidade anti-bypass.
- Oportunidades de funding, reservas, posições e resgates simulados.

## Cobrança e conciliação — entregue na v0.7.0

- Faturas e parcelas derivadas dos contratos SDC/Flash Credit.
- Régua de cobrança, inadimplência, mora e caducidade.
- Importação de arquivos e webhooks de conciliação.
- Fila operacional de divergências e baixa manual auditável.

## Leilões e recuperação de ativos — entregue na v0.8.0

- Cadastro de ativos recuperados, lotes, documentos e trilha de custódia.
- Conteúdo restrito por habilitação, aceite e perfil de investidor.
- Lances idempotentes, extensão automática e regras de preço.
- Liquidação simulada com waterfall, comissão e baixa da inadimplência.

## TaxTech e comunicações — entregue na v0.9.0

- Evidências fiscais, NFS-e por adaptador e fila de exceções.
- Fechamento mensal de comissões e payout fiscalmente habilitado.
- Templates versionados de WhatsApp, e-mail e notificações internas.
- Consentimento, opt-out, preferências de canal e histórico de entrega.

## NINA avançada e BI — entregue na v0.10.0

- Underwriting configurável, score, fila de decisão e explicabilidade.
- Ranking de combinações e contingência por indisponibilidade.
- Indicadores de funil, carteira, inadimplência, funding e receita.
- Relatórios exportáveis e trilha executiva de risco.

## Hardening para homologação — entregue na v0.11.0

- Jobs assíncronos, retries, observabilidade e alertas operacionais.
- Testes de concorrência, carga, segurança e isolamento multi-tenant.
- Configuração PostgreSQL de produção e storage compatível com S3.
- Adaptadores homologáveis para fornecedores externos.

## Integração e implantação controlada — entregue na v0.12.0

- PostgreSQL gerenciado, storage S3 e segredos por ambiente.
- Worker separado e agendamento recorrente dos jobs.
- OpenTelemetry, logs estruturados e alertas.
- Pipeline CI/CD, staging e checklist formal de homologação.

## Suíte de qualidade e segurança — entregue na v0.13.0

- Rate limiting, proteção contra brute force e quotas por tenant.
- Testes de carga e concorrência para lances, pagamentos e jobs.
- Backup/restore automatizado e testes de desastre.
- Matriz de evidências para homologação funcional e segurança.

## Integrações homologáveis — entregue na v0.14.0

- Contratos de adaptadores, circuit breaker e sandbox por fornecedor.
- Webhooks assinados com replay protection.
- BaaS/escrow, KYC, assinatura, WhatsApp e NFS-e por configuração.
- Painel de saúde, latência e incidentes dos provedores.

## Conectores reais e gestão de incidentes — entregue na v0.15.0

- Adaptadores HTTP reais por contrato, com allowlist e rotação de credenciais.
- Homologação assistida de BaaS/escrow, KYC, assinatura, WhatsApp e NFS-e.
- Gestão de incidentes, SLAs, alertas e runbooks por fornecedor.
- DLQ operacional com reprocessamento em lote e reconciliação automática.

## Onboarding dos fornecedores contratados — infraestrutura entregue na v0.16.0

- Adaptadores específicos conforme contratos e documentação técnica dos fornecedores escolhidos.
- Cofre de segredos gerenciado, mTLS quando exigido e rotação automatizada.
- Conciliação ponta a ponta com arquivos e webhooks reais de BaaS/escrow.
- Evidências de homologação por fornecedor, pentest e simulado de incidentes.

## Adaptadores específicos sandbox — entregue na v0.17.0

- Contratos executáveis e catálogo de capacidades para BaaS/escrow, KYC, assinatura, comunicações e NFS-e.
- Registry/factory substituível por fornecedor, com simulações determinísticas em sandbox.
- Idempotência, hash de entrada, identificadores externos e histórico de execução auditável.
- Bancada de testes de adaptadores no painel operacional.
- Bloqueio explícito de produção enquanto não houver adaptador oficial registrado.

## Certificação e go-live controlado — entregue na v0.18.0

- Matriz automatizada de conformidade por integração e relatório com hash SHA-256.
- Aprovações independentes de Segurança, Jurídico, Compliance e Operações.
- Gate de go-live auditável com lista objetiva de bloqueadores.
- Histórico de certificações, decisões e revisões de aprovação.
- Painel operacional para executar certificação e acompanhar pendências.

## NINA Asset e execução patrimonial controlada — entregue na v0.19.0

- Casos de distress vinculados à inadimplência Flash Credit e operação original.
- Régua auditável H+1, H+6, H+16, H+30 e H+61 com eventos idempotentes.
- Gates de bloqueio de caixa, notificação cartorial, caducidade e publicação de leilão.
- Dupla aprovação para caducidade e publicação, sempre com step-up.
- Minutas de notificação, desocupação, edital e ata com PDF e hash SHA-256.
- Precificação sandbox em 80% do AVM, redução parametrizada e piso de 50%.
- Legal hold permanente enquanto não houver validação jurídica e integrações oficiais.

## Duplo aceite e gate de transferência — entregue na v0.20.0

- Aceite inicial separado no checkout e confirmação crítica após transferência.
- Templates jurídicos versionados, aprovação por step-up e evidência SHA-256.
- Janela de 24 horas com avisos imediato, H+12 e H+22.
- Expiração, silêncio e contestação preservam o lock para revisão manual.
- Payout de carta vinculado à verificação confirmada.

## Lastros OCR e imóveis estruturados — entregue na v0.21.0

- Três lastros do vendedor, OCR cruzado e aprovação humana antes do timer de 24h.
- Onboarding com garantia limpa, interveniente quitante e construção não averbada.
- LTV máximo de 40%, payout em duas fases e janela de averbação de 90 dias.
- Minuta PDF para requerimento cartorial, eventos imutáveis e jobs de lembrete.
- Expiração mantém legal hold; nenhuma perda ou movimentação automática.

## Flash Credit v2, Valid-Stamp e LSS — entregue na v0.22.0

- Tomador Flash Credit restrito a PJ, proprietário terceiro com liveness/consentimento e conferência de QSA.
- Política versionada de LTV, taxas, degraus de leilão e fee, com aprovação reforçada.
- Valid-Stamp como registro de evidência HMAC-SHA256 encadeado e verificável.
- LSS com termos versionados, aprovação jurídica, clickwrap e rateio apenas demonstrativo.
- Produção financeira e coleta indiscriminada de fontes permanecem bloqueadas.

## NINA FinOps Core — entregue na v0.23.0

- Simulador Flash Credit com Fundos/Pool e Linear/Balão.
- Tabela Price de 36 meses, IPCA projetado nas faturas 13 e 25 e última parcela reconciliada.
- Curva pública de quitação do mês 6 ao 36 e cotação autenticada com validade de 60 minutos.
- Inbox de eventos HMAC, tolerância temporal, idempotência e rejeição de payload divergente.
- Eventos Flash/SDC convertidos em decisões seguras sem movimentação financeira automática.
- Prévia Bullet 45/90 dias e MMN conservando 100% da verba sob hold fiscal.

## Roteamento fiduciário NINA — entregue na v0.24.0

- Política versionada com limites de população, renda per capita e TAPAF.
- Negativação/veto pode rotear para Flash Credit somente com garantia imobiliária.
- Hipoteca bancária, Home Equity e financiamento ativo são classificações aceitas para análise.
- Bloqueio judicial, penhora, arresto, sequestro e embargo fiscal bloqueiam a pauta.
- Bifurcação Fundos/Pool usa os limites ativos e registra memória de decisão.
- Comitê com step-up emite Valid-Stamp de evidência, mantendo payout não autorizado e vistoria física obrigatória.
- Política de fontes bloqueia scraping massivo e enriquecimento sem base legal.

## Próxima evolução — fornecedores oficiais

- Seleção nominal dos fornecedores de BaaS/escrow, KYC, assinatura, WhatsApp e NFS-e.
- Implementação dos contratos específicos após recebimento das documentações e credenciais sandbox.
- Testes ponta a ponta nos ambientes oficiais e assinatura das evidências de aceite.
- Pentest independente, aprovação jurídica e decisão formal de go-live.

## Fornecedores e conciliação

- Adaptadores reais de KYC/KYB, assinatura, storage e antivírus.
- Homologação da conciliação por arquivos/webhooks com fornecedores reais.
- Aprovação formal das regras e templates jurídicos.

## Integrações homologadas

- BaaS/escrow.
- KYC/KYB e biometria.
- Assinatura eletrônica.
- WhatsApp Business oficial.
- AVM, FIPE/Molicar, cartórios e fontes autorizadas.

## Produtos avançados

- SDC completo.
- Flash Credit institucional.
- MMN/TaxTech.
- Funding de varejo após compliance.
- Leilões e aplicativo mobile.

## Gate de produção

Nenhuma operação financeira será habilitada sem fornecedor contratado, regras jurídicas aprovadas, conciliação testada, pentest e plano de incidentes.
