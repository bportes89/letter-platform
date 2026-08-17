# Regras financeiras canônicas — v0.24.1

As regras abaixo reproduzem as premissas recebidas na documentação da LETTER. Elas são executáveis e testadas, mas permanecem em modo de simulação até homologação jurídica, contábil e regulatória.

## SDC — `sdc-bullet-v1` (pool) e `sdc-bullet-v2` (fundo)

- O conjunto de cotas deve ter a mesma categoria e administradora.
- O crédito combinado deve estar dentro de ±10% do valor solicitado.
- Juros simples: `principal × 4,5% × meses`.
- Amortização: principal e juros no vencimento Bullet.
- Taxa de Start: 3% para imóvel e 5% para veículo.
- Para imóvel, o primeiro marco é limitado a R$ 1.500 e o restante vai para o segundo marco.
- Fee de intermediação: 10% do crédito bruto.
- Comissão de captação: 1% do capital.

### Origem `POOL`

- Taxa total travada: **4,5% a.m.** (juros simples).
- Repasse padrão investidores: **2,5%**; spread plataforma: **2,0%**.
- **Faixa automática** (`pool_investment_amount`): até R$ 100.000 → **1,6% a.m.**; a partir de R$ 100.000 → **2,0% a.m.** (spread plataforma ajusta automaticamente).
- **Campanha:** `pool_investor_rate_percent` sobrescreve a faixa automática (até 4,5%).
- **Fiscal:** rentabilidade do investidor pool registrada como `EXEMPT_NOT_WITHHELD` (livre de retenção na origem, política LETTER).

### Origem `FUND`

- Todo o spread (4,5% × meses) permanece no fundo; spread da plataforma = 0%.

Exemplo canônico pool: R$ 800.000 por 12 meses gera R$ 432.000 de juros, sendo R$ 240.000 para investidores e R$ 192.000 de spread LETTER.

## Flash Capital — `flash-capital-v1` / `flash-capital-v2` / `flash-capital-v3`

> Nomenclatura comercial **Flash Capital** (identificador interno preservado: `FLASH_CREDIT`).

Regras comuns (v3):

- LTV máximo: 40% do valor do bem.
- **Valor nominal (principal):** montante alavancado sobre o bem (ex.: imóvel R$ 1M → principal R$ 400.000).
- **Fee da plataforma:** 10% do principal (configurável via política `intermediation_fee_percent`).
- **Provisão ITBI e emolumentos:** 3% do principal.
- **Payout líquido ao cliente:** `principal − fee plataforma − ITBI`.
- **Juros (Price / fundo):** calculados sobre o **valor nominal (principal)**, não sobre o líquido.
- **Comissão da rede (MMN):** base de cálculo = **payout líquido** (`partner_commission_base`).

Exemplo canônico (imóvel R$ 1.000.000, LTV 40%):

```
400.000 − 40.000 (fee 10%) − 12.000 (ITBI 3%) = 348.000 líquido ao cliente
Comissão parceiros: sobre R$ 348.000
Juros: sobre R$ 400.000 (nominal)
```

### Origem `RETAIL` (pool)

- Taxa Price travada: **2,5% ao mês**.
- Repasse padrão investidores: **1,6%**; spread plataforma: **0,9%**.
- **Faixa automática** (`pool_investment_amount`): até R$ 100.000 → **1,6% a.m.**; a partir de R$ 100.000 → **2,0% a.m.** (spread plataforma ajusta automaticamente).
- **Campanha:** `pool_investor_rate_percent` sobrescreve a faixa automática (até 2,5%).
- **Fiscal:** rentabilidade do investidor pool registrada como `EXEMPT_NOT_WITHHELD` (livre de retenção na origem, política LETTER).
- Amortização (fundo comum) reduz saldo devedor e é segregada em conta de investimento da plataforma para ressarcimento ao investidor no encerramento.
- Prazo de 60 meses: parcelas Price e saldo liquidado como Balloon Payment no mês 36.

### Origem `INSTITUTIONAL` (fundo)

- Taxa anual: 14% + IPCA informado, com reajuste anual da parcela nos meses 13 e 25.
- Juros calculados pro rata pelo prazo em meses.
- Taxa de gestão: 0,5% ao ano sobre o principal, pro rata pelo prazo.

## Valid-Stamp — lastros obrigatórios Flash Capital

Antes de emitir selo para partes/evidência Flash Capital, o payload deve incluir hashes dos documentos:

### Imóvel (`REAL_ESTATE`)

- Matrícula atualizada emitida no e-notariado
- Laudo de avaliação
- Consulta Serasa
- Consulta Bacen

### Veículo (`VEHICLE`)

- Tabela FIPE ou Molicar (quando não houver FIPE, ex.: ônibus)
- Laudo de avaliação
- Consulta Serasa
- Consulta Bacen
- CRLV (referência; **consulta DETRAN prevalece**)

## SDC veículo — restrições impeditivas

No pagamento TAPAF / emissão Valid-Stamp (`SDC_VEHICLE_COLLATERAL`), consulta obrigatória ao DETRAN (ou provedor homologado):

- Bloqueio judicial
- Alienação fiduciária ativa (CRLV pode estar desatualizado)
- Restrição de transferência por incentivo fiscal (prazo no CRLV)

Veículos leve, pesado ou máquina com restrição **não seguem** a operação.

## Gates de produção

- Parâmetros devem ser formalmente aprovados pelo jurídico e pela contabilidade.
- Índices econômicos devem vir de fonte oficial, sem entrada manual em produção.
- Escrow, Pix, conciliação e payout dependem de fornecedor BaaS homologado.
- Alterações futuras criam nova versão de fórmula; memórias anteriores não são reescritas.
