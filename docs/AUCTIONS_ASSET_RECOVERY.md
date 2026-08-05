# Leilões e recuperação de ativos

## Escopo da v0.8.0

O módulo cobre a jornada simulada entre um ativo elegível para recuperação e sua liquidação: registro de custódia, criação do lote, habilitação, acesso controlado aos documentos, lances idempotentes, encerramento e waterfall.

## Ativos e custódia

Cada ativo registra tipo, descrição pública, avaliação, saldo da dívida, custos de recuperação e referência única de custódia. O vínculo com inadimplência é opcional na sandbox, mas, quando utilizado, exige caso elegível à caducidade.

Documentos sensíveis, matrícula e endereço permanecem em conteúdo restrito. Participantes comuns só acessam esses dados após aceite expresso dos termos; administradores mantêm acesso operacional auditável.

## Lotes e lances

- O preço de reserva deve ser igual ou superior ao preço inicial.
- Cada lance respeita o maior valor vigente acrescido do incremento mínimo.
- A chave de idempotência impede a duplicação causada por retry de rede.
- Lances dentro da janela final prorrogam o encerramento pelo período configurado.
- Somente investidores de varejo ou fundos institucionais habilitados podem participar.

## Waterfall de liquidação

Quando o preço de reserva é atingido, o maior lance válido origina a liquidação simulada nesta ordem:

1. custos de recuperação;
2. fee da plataforma;
3. pagamento do saldo da dívida;
4. saldo remanescente destinado ao proprietário.

O resultado é persistido e a execução repetida devolve a mesma liquidação. Casos de inadimplência vinculados recebem o status de liquidados ou parcialmente recuperados.

## Limites da sandbox

O botão de liquidação é um mock protegido por step-up. A solução não transfere propriedade, não movimenta dinheiro real e não executa garantia. Produção exige edital e contratos homologados, laudos e custódia documental, política de habilitação, integração com escrow/BaaS, assinatura dos eventos, proteção contra concorrência de lances, observabilidade, pentest e aprovação jurídica.
