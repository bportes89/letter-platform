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

- Investidores: `principal × 2,5% × meses`.
- Spread LETTER: `principal × 2,0% × meses`.

### Origem `FUND`

- Todo o spread (4,5% × meses) permanece no fundo; spread da plataforma = 0%.

Exemplo canônico pool: R$ 800.000 por 12 meses gera R$ 432.000 de juros, sendo R$ 240.000 para investidores e R$ 192.000 de spread LETTER.

## Flash Capital — `flash-capital-v1` / `flash-capital-v2`

> Nomenclatura comercial **Flash Capital** (identificador interno preservado: `FLASH_CREDIT`).

Regras comuns:

- LTV máximo: 40% do valor do bem.
- Provisão de ITBI e emolumentos: 3% do principal.
- Fee de estruturação: 7% do principal.
- Payout líquido simulado: principal menos provisão e fee.

### Origem `RETAIL` (pool)

- Taxa Price: 2,5% ao mês.
- Split mensal sobre juros: 1,6% para investidores do pool e 0,9% para a plataforma.
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

## Gates de produção

- Parâmetros devem ser formalmente aprovados pelo jurídico e pela contabilidade.
- Índices econômicos devem vir de fonte oficial, sem entrada manual em produção.
- Escrow, Pix, conciliação e payout dependem de fornecedor BaaS homologado.
- Alterações futuras criam nova versão de fórmula; memórias anteriores não são reescritas.
