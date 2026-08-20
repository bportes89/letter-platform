"""LETTER_FINOPS_QUITCON_ENGINE_2026_V1 — quitação consórcio (doc252/doc253).

LTV assimétrico e remuneração 0,4% a.m. são exclusivos do Lease Equity.
"""

from decimal import Decimal, ROUND_HALF_UP
import re
import unicodedata

HUNDRED = Decimal("100")


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _normalize_admin_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text.lower())


class EngineQuitConLetter:
    rentabilidade_investidor_pool = Decimal("0.016")
    valor_nominal_unitario_token = Decimal("100.00")
    taxa_tapaf_nominal = Decimal("1500.00")
    gatilho_captacao_minima_percent = Decimal("0.30")
    sla_dias_estimados = 45
    multa_percentual = Decimal("0.10")
    taxa_intermediacao_percent = Decimal("0.03")
    taxa_servico_operacional_percent = Decimal("0.02")
    taxa_plataforma_cessionario_percent = Decimal("0.05")
    dias_inadimplencia_cancelamento = 15
    prazo_deposito_quitacao_horas_uteis = 48
    taxa_desconto_projecao_mensal = Decimal("0.01")
    prazos_projecao_meses = (6, 12, 18, 24, 36, 48)
    administradoras_whitelist = (
        "ancora",
        "hs",
        "embracon",
        "ademicon",
        "tradicao",
        "recon",
        "groscon",
        "roma",
        "reserva",
    )
    nota_compliance_projecao = (
        "Os valores exibidos na tabela abaixo são estimados. As parcelas e o saldo devedor de consórcios "
        "sofrem reajustes periódicos com base nos índices de correção das próprias administradoras "
        "(como INCC ou IPCA), alterando o valor final de quitação."
    )
    modal_quitcon_titulo = "Como funciona a Quitação Inteligente QuitCon?"
    modal_quitcon_corpo = (
        "Nós aplicamos um desconto financeiro de 1% ao mês sobre o prazo que resta para encerrar o seu "
        "contrato, trazendo a sua dívida a valor presente.\n\n"
        "A plataforma encontra um investidor de Capital de Giro para assumir o pagamento das suas parcelas "
        "restantes no consórcio. A LETTER cuida de toda a burocracia de transferência de titularidade e "
        "substituição da garantia junto à administradora.\n\n"
        "Resultado: Você quita o seu contrato à vista com um super desconto e libera o seu imóvel ou veículo "
        "da alienação sem precisar desembolsar o valor bruto total."
    )

    def calcular_valor_quitcon_vp(self, saldo_devedor: Decimal, meses: int) -> Decimal:
        sb = money(Decimal(str(saldo_devedor)))
        n = max(int(meses), 0)
        i = self.taxa_desconto_projecao_mensal
        return money(sb / (Decimal("1") + i * Decimal(str(n))))

    def gerar_tabela_projecao_quitcon(self, saldo_devedor_simulado: Decimal) -> dict:
        sb = money(Decimal(str(saldo_devedor_simulado)))
        linhas: list[dict] = []
        tabela: dict[str, dict] = {}
        for n in self.prazos_projecao_meses:
            vp = self.calcular_valor_quitcon_vp(sb, n)
            row = {
                "prazo_meses": n,
                "valor_bruto_referencia": str(sb),
                "valor_quitcon_estimado_vp": str(vp),
                "desconto_financeiro_obtido": str(money(sb - vp)),
                "status_operacao": f"Estimativa com desconto de {n}%",
                "nota_compliance": "VALOR_ESTIMADO_SUJEITO_A_REAJUSTES_DA_ADMINISTRADORA",
            }
            linhas.append(row)
            tabela[f"quitacao_{n}_meses"] = row
        return {
            "saldo_devedor_referencia": str(sb),
            "taxa_desconto_mensal": str(self.taxa_desconto_projecao_mensal),
            "formula": "VP = SB / (1 + i * n)",
            "nota_compliance_rodape": self.nota_compliance_projecao,
            "linhas": linhas,
            "tabela": tabela,
        }

    def gerar_integracao_sdc_quitcon(
        self,
        saldo_devedor_simulado: Decimal,
        meses_restantes: int | None = None,
    ) -> dict:
        sb = money(Decimal(str(saldo_devedor_simulado)))
        meses = int(meses_restantes) if meses_restantes is not None else max(self.prazos_projecao_meses)
        vp_vista = self.calcular_valor_quitcon_vp(sb, meses)
        return {
            "card": {
                "saldo_devedor_atual": str(sb),
                "quitacao_vista_quitcon_vp": str(vp_vista),
                "meses_restantes_referencia": meses,
                "taxa_desconto_mensal_percent": str(money(self.taxa_desconto_projecao_mensal * HUNDRED)),
                "modal": {
                    "titulo": self.modal_quitcon_titulo,
                    "corpo": self.modal_quitcon_corpo,
                },
            },
            "projecao_temporal": self.gerar_tabela_projecao_quitcon(sb),
        }

    def administradora_permitida(self, administrator_name: str) -> bool:
        key = _normalize_admin_key(administrator_name)
        if not key:
            return False
        return any(token in key or key in token for token in self.administradoras_whitelist)

    def validar_elegibilidade_cedente(
        self,
        *,
        contemplada: bool,
        bem_faturado: bool,
        parcelas_em_dia: bool,
        administrator_name: str | None = None,
    ) -> dict:
        blockers: list[str] = []
        if not contemplada:
            blockers.append("COTA_NAO_CONTEMPLADA")
        if not bem_faturado:
            blockers.append("BEM_NAO_FATURADO")
        if not parcelas_em_dia:
            blockers.append("PARCELAS_EM_ATRASO")
        if administrator_name and not self.administradora_permitida(administrator_name):
            blockers.append("ADMINISTRADORA_FORA_WHITELIST")
        return {
            "elegivel": len(blockers) == 0,
            "blockers": blockers,
            "criterios_doc253": {
                "contemplada_obrigatoria": True,
                "bem_faturado_obrigatorio": True,
                "parcelas_em_dia_obrigatorio": True,
            },
            "administradoras_whitelist": list(self.administradoras_whitelist),
        }

    def simular_quitcon_doc253(
        self,
        saldo_devedor_bruto: Decimal,
        meses_restantes: int,
        *,
        operational_service: bool = False,
        administrator_name: str | None = None,
        contemplada: bool = True,
        bem_faturado: bool = True,
        parcelas_em_dia: bool = True,
    ) -> dict:
        sb = money(Decimal(str(saldo_devedor_bruto)))
        meses = max(int(meses_restantes), 0)
        vp = self.calcular_valor_quitcon_vp(sb, meses)
        taxa_intermediacao = money(sb * self.taxa_intermediacao_percent)
        valor_liquido_antes_servico = money(vp - taxa_intermediacao)
        taxa_servico = (
            money(valor_liquido_antes_servico * self.taxa_servico_operacional_percent)
            if operational_service
            else money(Decimal("0"))
        )
        valor_liquido_cedente = money(valor_liquido_antes_servico - taxa_servico)
        taxa_plataforma_cessionario = money(vp * self.taxa_plataforma_cessionario_percent)
        capital_giro_liquido = money(vp - taxa_plataforma_cessionario)
        taxa_sucesso_escrow = self.calcular_taxa_sucesso_escrow(vp)
        elegibilidade = self.validar_elegibilidade_cedente(
            contemplada=contemplada,
            bem_faturado=bem_faturado,
            parcelas_em_dia=parcelas_em_dia,
            administrator_name=administrator_name,
        )
        return {
            "doc_version": "LETTER_QUITCON_PRODUTO_2026_DOC253",
            "saldo_devedor_bruto": str(sb),
            "meses_restantes": meses,
            "valor_presente_quitacao": str(vp),
            "formula_deflacionamento": "VP = SB / (1 + 0.01 * n)",
            "elegibilidade": elegibilidade,
            "cedente": {
                "quitacao_vista_vp": str(vp),
                "taxa_intermediacao_3_porcento": str(taxa_intermediacao),
                "taxa_servico_operacional_2_porcento": str(taxa_servico),
                "servico_operacional_contratado": operational_service,
                "valor_liquido_estimado_cedente": str(valor_liquido_cedente),
                "prazo_deposito_pos_aprovacao_horas_uteis": self.prazo_deposito_quitacao_horas_uteis,
            },
            "cessionario": {
                "valor_assumido_deflacionado": str(vp),
                "taxa_plataforma_5_porcento": str(taxa_plataforma_cessionario),
                "capital_giro_liquido_estimado": str(capital_giro_liquido),
                "tapaf_nominal": str(self.taxa_tapaf_nominal),
                "taxa_sucesso_escrow_10_porcento": str(taxa_sucesso_escrow),
                "taxa_sucesso_reembolsavel_se_reprovado_adm": True,
            },
            "compliance": {
                "sla_dias_estimados": self.sla_dias_estimados,
                "multa_inadimplencia_cessionario_dias": self.dias_inadimplencia_cancelamento,
                "multa_desistencia_cedente_percent": str(money(self.multa_percentual * HUNDRED)),
                "nota_parcelas_pos_aprovacao": (
                    "Tomador assume parcelas mensais a partir da aprovação da administradora, "
                    "mesmo antes da conclusão da transferência."
                ),
            },
            "projecao_temporal": self.gerar_tabela_projecao_quitcon(sb),
        }

    def processar_matriz_financeira(
        self,
        saldo_devedor_bruto: Decimal,
        valor_avaliacao_referencia: Decimal | None = None,
        meses_restantes: int | None = None,
        operational_service: bool = False,
    ) -> dict:
        saldo = money(Decimal(str(saldo_devedor_bruto)))
        if saldo <= 0:
            raise ValueError("SALDO_DEVEDOR_INVALIDO")
        avaliacao = money(Decimal(str(valor_avaliacao_referencia))) if valor_avaliacao_referencia else saldo
        meses = int(meses_restantes) if meses_restantes is not None else max(self.prazos_projecao_meses)
        simulacao = self.simular_quitcon_doc253(saldo, meses, operational_service=operational_service)
        vp = Decimal(simulacao["valor_presente_quitacao"])
        meta_captacao = money(vp)
        custo_mensal_pool = money(meta_captacao * self.rentabilidade_investidor_pool)
        return {
            "saldo_devedor_bruto": str(saldo),
            "valor_avaliacao_referencia": str(avaliacao),
            "valor_presente_quitacao": simulacao["valor_presente_quitacao"],
            "meses_restantes": meses,
            "meta_captacao_quitacao": str(meta_captacao),
            "custo_mensal_remuneracao_pool_investidores": str(custo_mensal_pool),
            "taxa_intermediacao_3_porcento": simulacao["cedente"]["taxa_intermediacao_3_porcento"],
            "taxa_servico_operacional_2_porcento": simulacao["cedente"]["taxa_servico_operacional_2_porcento"],
            "taxa_plataforma_cessionario_5_porcento": simulacao["cessionario"]["taxa_plataforma_5_porcento"],
            "capital_giro_liquido_cessionario": simulacao["cessionario"]["capital_giro_liquido_estimado"],
            "taxa_sucesso_escrow_10_porcento": simulacao["cessionario"]["taxa_sucesso_escrow_10_porcento"],
            "sla_dias_estimados": self.sla_dias_estimados,
            "ltv_assimetrico_aplicavel": False,
            "remuneracao_proprietario_aplicavel": False,
            "doc_version": "LETTER_QUITCON_PRODUTO_2026_DOC253",
            "nota_produto": (
                "QuitCon doc253: VP com 1% a.m., taxas 3%/2%/5%/10%, whitelist de administradoras."
            ),
        }

    def calcular_taxa_sucesso_escrow(self, valor_liberado: Decimal) -> Decimal:
        """10% sobre o valor liberado (VP deflacionado) — doc253."""
        return money(Decimal(str(valor_liberado)) * self.multa_percentual)

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
