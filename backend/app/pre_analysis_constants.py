"""LETTER_DOCUMENT_OCR_PRE_ANALYSIS_ENGINE_2026_V6 — manifesto e textos regulatórios."""

TAPAF_MANIFESTO_HTML = """
<h3>TERMO DE MANIFESTO DE FLUXO, DECLARAÇÃO DE CIÊNCIA E PACTO DE NÃO REEMBOLSO DA TAPAF</h3>
<p>Por meio deste manifesto eletrônico de clique ativo e em conformidade com as diretrizes de simetria jurídica
e liberdade econômica entre agentes empresariais (Artigos 111, 421 e 421-A do Código Civil Brasileiro),
o <strong>PRETENDENTE PROPONENTE</strong> declara, para todos os fins de direito,
<strong>TOTAL CONCORDÂNCIA, INTEGRAL ANUÊNCIA E ACEITE IRREVOGÁVEL</strong> às presentes cláusulas de custeio de análise técnica:</p>
<ol>
<li><strong>Da Finalidade dos Recursos Aportados:</strong> O proponente declara ciência de que o valor de
<strong>R$ 1.500,00 (mil e quinhentos reais)</strong> correspondente à TAPAF constituirá uma provisão de fundos
destinada estritamente a cobrir despesas cartorárias, consultas automatizadas perante a ONR e laudo de engenharia AVM.
A taxa possui natureza de emolumento indenitário e <strong>não configura</strong> taxa de juros, comissão,
entrada de cota ou promessa de aprovação de pauta.</li>
<li><strong>Da Cláusula Coativa de Não Reembolso por Incompatibilidade:</strong> O proponente ratifica que,
por tratar-se de verba consumida de forma imediata na contratação de peritos e certidões estatais em D+0,
<strong>o valor da TAPAF não é reembolsável, estornável ou sujeito a chargeback</strong>.
Caso a Nina Engine ou o comitê reprovem a operação na Fase 3 por omissão de restrições, estouro de idade
do veículo ou insuficiência de lastro, o valor será retido para amortização dos custos operacionais despendidos.</li>
</ol>
""".strip()

TAPAF_CHECKBOX_01 = (
    "DECLARO QUE TENHO TOTAL CIÊNCIA DE QUE A TAPAF SE DESTINA DE FORMA EXCLUSIVA AO CUSTEIO DE "
    "EMOLUMENTOS CARTORÁRIOS E LAUDOS TÉCNICOS E NÃO CONSTITUI QUALQUER GARANTIA, PROMESSA OU "
    "VÍNCULO DE APROVAÇÃO FINANCEIRA DE OPERAÇÃO."
)

TAPAF_CHECKBOX_02 = (
    "ESTOU DE ACORDO DE QUE POR TRATAR-SE DE REPASSE DIRETO PARA ATOS DE AUDITORIA E VISTORIAS "
    "FÍSICAS TERCEIRIZADAS JÁ INICIADAS, O VALOR DA TAPAF NÃO É REEMBOLSÁVEL EM CASO DE "
    "REPROVAÇÃO PATRIMONIAL OU CADASTRAL POR CULPA, RESTRIÇÃO OU OMISSÃO DE DADOS OCULTOS "
    "PELO PROPONENTE SÓCIO OU PJ."
)

TAPAF_TOOLTIP = (
    "O que é a TAPAF? A Taxa de Análise e Processamento de Ativos Fiduciários no valor fixo de "
    "R$ 1.500,00 é um emolumento mandatório e não reembolsável, destinado a custear despesas "
    "cartorárias, varreduras automatizadas perante a Receita e a ONR, e laudo técnico AVM do bem colateralizado."
)

REQUIRED_DOCUMENT_CODES = [
    "EXTRATO_BANCARIO_6M",
    "PGDAS_DRE",
    "DECORE_CRC",
    "MATRICULA_OU_CRLV",
    "LAUDO_AVM",
]

DOCUMENT_LABELS = {
    "EXTRATO_BANCARIO_6M": "Extratos bancários — últimos 6 meses",
    "PGDAS_DRE": "PGDAS / DRE / Balanço",
    "DECORE_CRC": "DECORE eletrônica com selo CRC",
    "MATRICULA_OU_CRLV": "Matrícula ou CRLV",
    "LAUDO_AVM": "Laudo técnico AVM",
}
