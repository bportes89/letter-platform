"""LETTER_FINOPS_QUITCON_ENGINE_2026_V1 — motor LTV, multas e tokenização RWA (sem remuneração 0,4% — exclusiva Lease Equity)."""

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

    def processar_matriz_credito_ltv(self, tipologia_imovel: str, valor_avaliacao: Decimal) -> dict:
        tipo = tipologia_imovel.upper()
        v_aval = money(Decimal(str(valor_avaliacao)))
        if tipo in {"URBANO_RESIDENCIAL", "URBANO_COMERCIAL"}:
            ltv_maximo_captacao = Decimal("0.60")
        elif tipo in {"LOTE_URBANO", "GALPAO"}:
            ltv_maximo_captacao = Decimal("0.40")
        elif tipo == "RURAL":
            ltv_maximo_captacao = Decimal("0.30")
        else:
            raise ValueError("TIPOLOGIA_IMOVEL_INVALIDA_MESA_RISCO")
        valor_maximo_alavancado_pool = money(v_aval * ltv_maximo_captacao)
        custo_mensal_pool_investidores = money(valor_maximo_alavancado_pool * self.rentabilidade_investidor_pool)
        return {
            "tipologia_processada": tipo,
            "valor_avaliacao_imovel": str(v_aval),
            "limite_teto_ltv_captacao": str(valor_maximo_alavancado_pool),
            "custo_mensal_remuneracao_pool_investidores": str(custo_mensal_pool_investidores),
            "ltv_percent": str(money(ltv_maximo_captacao * HUNDRED)),
            "sla_dias_estimados": self.sla_dias_estimados,
            "remuneracao_proprietario_aplicavel": False,
            "nota_produto": "Remuneração 0,4% a.m. é exclusiva do Lease Equity — QuitCon não possui payout recorrente ao proprietário.",
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

    def gerar_fracionamento_securitizado_rwa(self, valor_alavancado_ltv: Decimal, contrato_id: str) -> dict:
        v_alavancado = money(Decimal(str(valor_alavancado_ltv)))
        total_tokens_emissao = int(v_alavancado / self.valor_nominal_unitario_token)
        rendimento_por_token_mes = money(self.valor_nominal_unitario_token * self.rentabilidade_investidor_pool)
        return {
            "contrato_vinculado_rwa": contrato_id,
            "token_standard": "ERC-3643_COMPLIANT",
            "total_supply_tokens_mint": total_tokens_emissao,
            "valor_face_unitario_token_brl": str(self.valor_nominal_unitario_token),
            "rendimento_mensal_unitario_smart_contract": str(rendimento_por_token_mes),
            "payout_mensal_total_investidores_pool": str(money(Decimal(total_tokens_emissao) * rendimento_por_token_mes)),
        }
