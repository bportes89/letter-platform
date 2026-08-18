"""LETTER_FINOPS_LEASE_EQUITY_ENGINE_2026_V1 — motor de crédito, antecipação e tokenização RWA."""

from decimal import Decimal, ROUND_HALF_UP

HUNDRED = Decimal("100")


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class EngineLeaseEquityLetter:
    taxa_desconto_antecipacao_mensal = Decimal("0.025")
    rentabilidade_investidor_pool = Decimal("0.016")
    recompensa_dono_imovel_base = Decimal("0.004")
    valor_nominal_unitario_token = Decimal("100.00")
    carencia_meses_minima = 6
    taxa_tapaf_nominal = Decimal("750.00")
    gatilho_captacao_minima_percent = Decimal("0.30")
    prazo_vigencia_meses = 36
    comissao_parceiro_pool_percent = Decimal("2")

    def _ltv_percent_for_type(self, tipo: str) -> Decimal:
        if tipo in {"URBANO_RESIDENCIAL", "URBANO_COMERCIAL"}:
            return Decimal("0.40")
        if tipo in {"LOTE_URBANO", "GALPAO"}:
            return Decimal("0.25")
        if tipo == "RURAL":
            return Decimal("0.20")
        raise ValueError("TIPOLOGIA_IMOVEL_INVALIDA_MESA_RISCO")

    def processar_matriz_credito_ltv(self, tipologia_imovel: str, valor_avaliacao: Decimal) -> dict:
        tipo = tipologia_imovel.upper()
        v_aval = money(Decimal(str(valor_avaliacao)))
        ltv_maximo_captacao = self._ltv_percent_for_type(tipo)
        valor_maximo_alavancado_pool = money(v_aval * ltv_maximo_captacao)
        aluguel_mensal_recorrente_dono = money(valor_maximo_alavancado_pool * self.recompensa_dono_imovel_base)
        custo_mensal_pool_investidores = money(valor_maximo_alavancado_pool * self.rentabilidade_investidor_pool)
        ganho_total_proprietario_prazo = money(aluguel_mensal_recorrente_dono * self.prazo_vigencia_meses)
        antecipacao = self.calcular_antecipacao_recebiveis_price(
            aluguel_mensal_recorrente_dono,
            parcelas_restantes=self.prazo_vigencia_meses,
            meses_vigencia_atual=self.carencia_meses_minima,
        )
        saque_total_antecipado = Decimal(antecipacao["valor_liquido_payout_vista"])
        comissao_parceiro = self.calcular_comissao_parceiro_antecipacao(saque_total_antecipado)
        return {
            "tipologia_processada": tipo,
            "valor_avaliacao_imovel": str(v_aval),
            "limite_teto_ltv_captacao": str(valor_maximo_alavancado_pool),
            "base_calculo_recompensa_dono": str(valor_maximo_alavancado_pool),
            "aluguel_mensal_recorrente_bruto_dono": str(aluguel_mensal_recorrente_dono),
            "ganho_total_proprietario_prazo": str(ganho_total_proprietario_prazo),
            "saque_total_antecipado_vp": str(saque_total_antecipado),
            "comissao_parceiro_pool": str(comissao_parceiro),
            "custo_mensal_remuneracao_pool_investidores": str(custo_mensal_pool_investidores),
            "custo_operacional_total_distribuido_mensal": str(
                money(aluguel_mensal_recorrente_dono + custo_mensal_pool_investidores)
            ),
            "ltv_percent": str(money(ltv_maximo_captacao * HUNDRED)),
            "taxa_proprietario_mensal_percent": str(money(self.recompensa_dono_imovel_base * HUNDRED)),
            "taxa_antecipacao_mensal_percent": str(money(self.taxa_desconto_antecipacao_mensal * HUNDRED)),
            "comissao_parceiro_percent": str(self.comissao_parceiro_pool_percent),
            "prazo_vigencia_meses": self.prazo_vigencia_meses,
        }

    def calcular_comissao_parceiro_antecipacao(self, valor_presente_antecipacao: Decimal) -> Decimal:
        base = money(Decimal(str(valor_presente_antecipacao)))
        return money(base * self.comissao_parceiro_pool_percent / HUNDRED)

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
        comissao_parceiro = self.calcular_comissao_parceiro_antecipacao(valor_presente_liquido_vista)
        return {
            "status_antecipacao": "LIBERADO_PARA_SAQUE_VISTA",
            "total_meses_antecipados": p_restantes,
            "taxa_desconto_aplicada_mes": str(i),
            "valor_bruto_futuro_total": str(valor_bruto_futuro),
            "valor_liquido_payout_vista": str(valor_presente_liquido_vista),
            "comissao_parceiro_pool": str(comissao_parceiro),
            "base_comissao_parceiro_mmn": str(valor_presente_liquido_vista),
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
