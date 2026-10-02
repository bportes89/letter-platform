"""Cobrança comercial da plataforma via Banco Inter (visão unificada).

O cliente trata o Inter como a API de **qualquer cobrança** na LETTER:
entrada de carta contemplada (marketplace), TAPAF (pré-análise, QuitCon, Lease Equity),
assinatura SaaS (LSS) e, em seguida, cobranças avulsas do módulo Collections.

Emissão compartilhada: ``inter_cobranca_helpers.issue_inter_charge``.
Confirmação de pagamento: ``POST /api/v1/webhooks/inter`` → ``inter_webhook_service.handle_inter_webhook``.

Fora deste escopo (proposital): Bank legado / conta digital parceiro (Asaas), split MMN,
Flash Invest — fluxos BaaS distintos do boleto/PIX de cobrança LETTER.
"""

from __future__ import annotations

from enum import StrEnum

from app.inter_common import inter_configured


class InterPlatformChargeKind(StrEnum):
    MARKETPLACE_ENTRADA = "MARKETPLACE_ENTRADA"
    TAPAF_PRE_ANALYSIS = "TAPAF_PRE_ANALYSIS"
    TAPAF_QUITCON = "TAPAF_QUITCON"
    TAPAF_LEASE_EQUITY = "TAPAF_LEASE_EQUITY"
    LSS_SAAS_MONTHLY = "LSS_SAAS_MONTHLY"
    AD_HOC = "AD_HOC"


# Ordem de resolução no webhook (codigoSolicitacao → entidade de negócio).
INTER_WEBHOOK_RESOLUTION_ORDER: tuple[InterPlatformChargeKind, ...] = (
    InterPlatformChargeKind.MARKETPLACE_ENTRADA,
    InterPlatformChargeKind.TAPAF_PRE_ANALYSIS,
    InterPlatformChargeKind.LSS_SAAS_MONTHLY,
    InterPlatformChargeKind.TAPAF_QUITCON,
    InterPlatformChargeKind.TAPAF_LEASE_EQUITY,
    # InterPlatformChargeKind.AD_HOC — a implementar
)


def platform_charges_use_inter() -> bool:
    """True quando cobranças comerciais devem ir ao Inter (credenciais + cert mTLS)."""
    return inter_configured()
