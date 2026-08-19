"""LETTER_FINOPS_QUITCON_ENGINE_2026_V1 — motor de crédito, antecipação, multas e tokenização RWA."""

from decimal import Decimal, ROUND_HALF_UP

HUNDRED = Decimal("100")


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class EngineQuitConLetter:
    taxa_desconto_antecipacao_mensal = Decimal("0.025")
    rentabilidade_investidor_pool = Decimal("0.016")
    recompensa_dono_imovel_base = Decimal("0.004")
    valor_nominal_unitario_token = Decimal("100.00")
    carencia_meses_minima = 6
    taxa_tapaf_nominal = Decimal("1500.00")
    gatilho_captacao_minima_percent = Decimal("0.30")
    prazo_vigencia_meses = 36
    sla_dias_estimados = 45
    multa_percentual = Decimal("0.10")
    dias_inadimplencia_cancelamento = 15
    prazo_deposito_quitacao_horas_uteis = 48

    def processar_matriz_credito_ltv(self, tipologia_imovel: str, valor_avaliacao: Decimal) -> dict:
        tipo = tipologia_imovel.upper()
        v_aval = money(Decimal(str(valor_avaliacao)))
        if tipo in {"URBANO_RESIDENCIAL", "URBANO_COMERCIAL"}:
            ltv_maximo_captacao = Decimal("0.60")
            base_calculo_recompensa = Decimal("0.40")
        elif tipo in {"LOTE_URBANO", "GALPAO"}:
            ltv_maximo_captacao = Decimal("0.40")
            base_calculo_recompensa = Decimal("0.25")
        elif tipo == "RURAL":
            ltv_maximo_captacao = Decimal("0.30")
            base_calculo_recompensa = Decimal("0.20")
        else:
            raise ValueError("TIPOLOGIA_IMOVEL_INVALIDA_MESA_RISCO")
        valor_maximo_alavancado_pool = money(v_aval * ltv_maximo_captacao)
        base_recompensa_liquida_dono = money(v_aval * base_calculo_recompensa)
        aluguel_mensal_recorrente_dono = money(base_recompensa_liquida_dono * self.recompensa_dono_imovel_base)
        custo_mensal_pool_investidores = money(valor_maximo_alavancado_pool * self.rentabilidade_investidor_pool)
        ganho_total_proprietario_prazo = money(aluguel_mensal_recorrente_dono * self.prazo_vigencia_meses)
        antecipacao = self.calcular_antecipacao_recebiveis_price(
            aluguel_mensal_recorrente_dono,
            parcelas_restantes=self.prazo_vigencia_meses,
            meses_vigencia_atual=self.carencia_meses_minima,
        )
        return {
            "tipologia_processada": tipo,
            "valor_avaliacao_imovel": str(v_aval),
            "limite_teto_ltv_captacao": str(valor_maximo_alavancado_pool),
            "base_calculo_recompensa_dono": str(base_recompensa_liquida_dono),
            "aluguel_mensal_recorrente_bruto_dono": str(aluguel_mensal_recorrente_dono),
            "ganho_total_proprietario_prazo": str(ganho_total_proprietario_prazo),
            "saque_total_antecipado_vp": antecipacao["valor_liquido_payout_vista"],
            "custo_mensal_remuneracao_pool_investidores": str(custo_mensal_pool_investidores),
            "custo_operacional_total_distribuido_mensal": str(
                money(aluguel_mensal_recorrente_dono + custo_mensal_pool_investidores)
            ),
            "ltv_percent": str(money(ltv_maximo_captacao * HUNDRED)),
            "base_recompensa_percent": str(money(base_calculo_recompensa * HUNDRED)),
            "taxa_proprietario_mensal_percent": str(money(self.recompensa_dono_imovel_base * HUNDRED)),
            "sla_dias_estimados": self.sla_dias_estimados,
            "prazo_vigencia_meses": self.prazo_vigencia_meses,
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

    def calcular_antecipacao_recebiveis_price(
        self,
        aluguel_mensal_dono: Decimal,
        parcelas_restantes: int = 36,
        meses_vigencia_atual: int = 6,
    ) -> dict:
        p_restantes = int(parcelas_restantes)
        v_mensal = money(Decimal(str(aluguel_mensal_dono)))
        vigencia = int(meses_vigencia_atual)
        i = self.taxa_desconto_antecipacao_mensal
        if vigencia < self.carencia_meses_minima:
            return {
                "status_antecipacao": "ANTECIPACAO_BLOQUEADA_CARENCIA_MINIMA",
                "meses_faltantes_para_liberacao": self.carencia_meses_minima - vigencia,
                "valor_liquido_payout": "0.00",
                "valor_liquido_payout_vista": "0.00",
            }
        one_plus_i = Decimal("1") + i
        fator_desconto_price = (Decimal("1") - one_plus_i ** (-p_restantes)) / i
        valor_presente_liquido_vista = money(v_mensal * fator_desconto_price)
        valor_bruto_futuro = money(v_mensal * p_restantes)
        return {
            "status_antecipacao": "LIBERADO_PARA_SAQUE_VISTA",
            "total_meses_antecipados": p_restantes,
            "taxa_desconto_aplicada_mes": str(i),
            "valor_bruto_futuro_total": str(valor_bruto_futuro),
            "valor_liquido_payout_vista": str(valor_presente_liquido_vista),
            "retencao_spread_desconto_spe": str(money(valor_bruto_futuro - valor_presente_liquido_vista)),
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
