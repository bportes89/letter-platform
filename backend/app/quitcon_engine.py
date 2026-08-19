"""LETTER_FINOPS_QUITCON_ENGINE_2026_V1 — quitação consórcio, multas e tokenização RWA.

LTV assimétrico e remuneração 0,4% a.m. são exclusivos do Lease Equity.
"""

from decimal import Decimal, ROUND_HALF_UP

HUNDRED = Decimal("100")


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class EngineQuitConLetter:
    rentabilidade_investidor_pool = Decimal("0.016")
    valor_nominal_unitario_token = Decimal("100.00")
    taxa_tapaf_nominal = Decimal("1500.00")
    gatilho_captacao_minima_percent = Decimal("0.30")
    sla_dias_estimados = 45
    multa_percentual = Decimal("0.10")
    dias_inadimplencia_cancelamento = 15
    prazo_deposito_quitacao_horas_uteis = 48

    def processar_matriz_financeira(
        self,
        saldo_devedor_bruto: Decimal,
        valor_avaliacao_referencia: Decimal | None = None,
    ) -> dict:
        saldo = money(Decimal(str(saldo_devedor_bruto)))
        if saldo <= 0:
            raise ValueError("SALDO_DEVEDOR_INVALIDO")
        avaliacao = money(Decimal(str(valor_avaliacao_referencia))) if valor_avaliacao_referencia else saldo
        meta_captacao = saldo
        custo_mensal_pool = money(meta_captacao * self.rentabilidade_investidor_pool)
        return {
            "saldo_devedor_bruto": str(saldo),
            "valor_avaliacao_referencia": str(avaliacao),
            "meta_captacao_quitacao": str(meta_captacao),
            "custo_mensal_remuneracao_pool_investidores": str(custo_mensal_pool),
            "sla_dias_estimados": self.sla_dias_estimados,
            "ltv_assimetrico_aplicavel": False,
            "remuneracao_proprietario_aplicavel": False,
            "nota_produto": (
                "QuitCon: base financeira = saldo devedor bruto da cota. "
                "LTV assimétrico e remuneração 0,4% a.m. são exclusivos do Lease Equity."
            ),
        }

    def calcular_taxa_sucesso_escrow(self, saldo_devedor_bruto: Decimal) -> Decimal:
        return money(Decimal(str(saldo_devedor_bruto)) * self.multa_percentual)

    def calcular_multa_inadimplencia_cessionario(self, taxa_sucesso_escrow: Decimal) -> dict:
        retained = money(Decimal(str(taxa_sucesso_escrow)))
        return {
            "tipo": "INADIMPLENCIA_CESSIONARIO_POS_APROVACAO",
            "dias_atraso_minimo": self.dias_inadimplencia_cancelamento,
            "taxa_sucesso_escrow_retida_integralmente": str(retained),
            "multa_compensatoria_percent": str(money(self.multa_percentual * HUNDRED)),
            "observacao": "Taxa de sucesso de 10% retida em Escrow permanece integralmente com a LETTER SPE.",
        }

    def calcular_multa_desistencia_cedente(self, saldo_devedor_bruto: Decimal, custos_vistoria: Decimal = Decimal("0")) -> dict:
        base = money(Decimal(str(saldo_devedor_bruto)))
        multa = money(base * self.multa_percentual)
        return {
            "tipo": "DESISTENCIA_CEDENTE_POS_APROVACAO",
            "prazo_deposito_quitacao_horas_uteis": self.prazo_deposito_quitacao_horas_uteis,
            "saldo_devedor_bruto": str(base),
            "multa_10_porcento_negocio": str(multa),
            "reembolso_cessionario_custos_vistoria": str(money(Decimal(str(custos_vistoria)))),
            "total_penalidades_cedente": str(money(multa + money(custos_vistoria))),
        }

    def gerar_fracionamento_securitizado_rwa(self, valor_lastro: Decimal, contrato_id: str) -> dict:
        v_lastro = money(Decimal(str(valor_lastro)))
        total_tokens_emissao = int(v_lastro / self.valor_nominal_unitario_token)
        rendimento_por_token_mes = money(self.valor_nominal_unitario_token * self.rentabilidade_investidor_pool)
        return {
            "contrato_vinculado_rwa": contrato_id,
            "token_standard": "ERC-3643_COMPLIANT",
            "total_supply_tokens_mint": total_tokens_emissao,
            "valor_face_unitario_token_brl": str(self.valor_nominal_unitario_token),
            "rendimento_mensal_unitario_smart_contract": str(rendimento_por_token_mes),
            "payout_mensal_total_investidores_pool": str(money(Decimal(total_tokens_emissao) * rendimento_por_token_mes)),
        }
