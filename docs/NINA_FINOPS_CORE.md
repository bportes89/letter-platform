# NINA FinOps Core — v0.23.0

O simulador recebe AVM, valor solicitado e IPCA projetado. Aplica LTV máximo de 40% e produz quatro cronogramas: Fundos Linear, Fundos Balão, Pool Linear e Pool Balão. Cada cronograma possui 36 registros com saldo inicial, parcela, juros, amortização, saldo de quitação e indicação de reajuste nas faturas 13 e 25.

O ambiente público é limitado por IP e retorna somente simulações. A área autenticada cria cotações de quitação ligadas ao contrato, memória de cálculo e usuário. A cotação registra hash, valor presente, desconto estimado e expiração em 60 minutos. Não gera Pix real.

As taxas e indexadores são parâmetros de simulação. Produção exige homologação contábil, fonte oficial do IPCA, política de arredondamento aprovada e conciliação com o BaaS.
