# Rede MMN e Funding — v0.6.0

## Árvores independentes

A plataforma mantém duas árvores por organização:

- `SALES`: originação comercial.
- `CAPITAL`: captação de capital.

Cada usuário possui no máximo um nó em cada árvore. O patrocinador precisa existir anteriormente na mesma árvore.

## Matriz de cinco níveis

Cada regra é versionada por produto e tipo de comissão. A verba total é calculada sobre a base configurada e distribuída assim:

1. Nível 1: 50%.
2. Nível 2: 20%.
3. Nível 3: 15%.
4. Nível 4: 10%.
5. Nível 5: 5%.

Uma nova versão desativa a anterior sem alterar comissões históricas. Referências idempotentes impedem provisionamento duplicado.

## Privacidade e Hold Fiscal

- Parceiros visualizam apenas totais agregados dos cinco níveis inferiores.
- Nomes, e-mails, leads e propostas da rede inferior não são retornados.
- Cada beneficiário visualiza somente suas comissões.
- Comissões nascem como `PENDING_FISCAL`.
- A evidência fiscal simulada gera hash e libera as comissões para `AVAILABLE`.
- Integração real de NFS-e e parser fiscal permanece pendente.

## Funding simulado

- Backoffice publica oportunidades de varejo ou institucionais.
- A oportunidade define meta, mínimo e referência de retorno.
- Somente `RETAIL_INVESTOR` ou `INSTITUTIONAL_FUND` pode reservar.
- Reservas não podem ultrapassar a capacidade disponível.
- A confirmação simulada cria uma posição e atualiza o capital confirmado.
- Ao atingir a meta, a oportunidade muda para `FUNDED`.

Nenhum aporte, token, rendimento ou resgate real é executado nesta versão.
