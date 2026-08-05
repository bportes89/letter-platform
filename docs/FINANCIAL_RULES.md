# Regras financeiras canônicas — v0.5.0

As regras abaixo reproduzem as premissas recebidas na documentação da LETTER. Elas são executáveis e testadas, mas permanecem em modo de simulação até homologação jurídica, contábil e regulatória.

## SDC — `sdc-bullet-v1`

- O conjunto de cotas deve ter a mesma categoria e administradora.
- O crédito combinado deve estar dentro de ±10% do valor solicitado.
- Juros simples: `principal × 4,5% × meses`.
- Investidores: `principal × 2,5% × meses`.
- Spread LETTER: `principal × 2,0% × meses`.
- Amortização: principal e juros no vencimento Bullet.
- Taxa de Start: 3% para imóvel e 5% para veículo.
- Para imóvel, o primeiro marco é limitado a R$ 1.500 e o restante vai para o segundo marco.
- Fee de intermediação: 10% do crédito bruto.
- Comissão de captação: 1% do capital.

Exemplo canônico: R$ 800.000 por 12 meses gera R$ 432.000 de juros, sendo R$ 240.000 para investidores e R$ 192.000 de spread LETTER.

## Flash Credit — `flash-credit-v1`

Regras comuns:

- LTV máximo: 40% do valor do bem.
- Provisão de ITBI e emolumentos: 3% do principal.
- Fee de estruturação: 7% do principal.
- Payout líquido simulado: principal menos provisão e fee.

### Fonte `RETAIL`

- Taxa Price: 2,5% ao mês.
- Prazo de 36 meses: parcelas Price até a liquidação.
- Prazo de 60 meses: parcelas calculadas para 60 meses e saldo devedor liquidado como Balloon Payment no mês 36.
- Referências do split: 1,6% para investidores e 0,9% de spread LETTER.

### Fonte `INSTITUTIONAL`

- Taxa anual da simulação: 14% + IPCA informado.
- Juros calculados pro rata pelo prazo em meses.
- Parcelas lineares para a memória de cálculo inicial.
- Taxa de gestão: 0,5% ao ano sobre o principal, pro rata pelo prazo.

## Gates de produção

- Parâmetros devem ser formalmente aprovados pelo jurídico e pela contabilidade.
- Índices econômicos devem vir de fonte oficial, sem entrada manual em produção.
- Escrow, Pix, conciliação e payout dependem de fornecedor BaaS homologado.
- Alterações futuras criam nova versão de fórmula; memórias anteriores não são reescritas.
