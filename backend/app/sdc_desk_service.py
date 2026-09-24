"""SDC commercial desk — Solicitação / Cadastro / Venda Cap Giro (legado Paulo)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from json import dumps as json_dumps
from json import loads as json_loads
from math import pow as math_pow

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.desk_solicitation_meta import desk_payload_extras, evaluation_json_with_meta, evaluation_meta
from app.document_service import persist_upload, purge_document, purge_document_links
from app.models import Document, Lead, Proposal, Quota, Role, SdcSolicitation, SdcSolicitationDocument, User
from app.network_service import PARTNER_NETWORK_ROLES
from app.services import money

DESK_ROLES = frozenset({
    Role.PLATFORM_ADMIN,
    Role.INTERNAL_STAFF,
    Role.MASTER_FRANCHISEE,
    Role.MANAGER,
    Role.PARTNER,
})

TIPOS_VEICULO = frozenset({"veiculo_leve", "veiculo_pesado", "maquina", "carro", "caminhao", "maquina_rural"})
TIPOS_IMOVEL = frozenset({"imovel", "casa", "lote", "imovel_rural", "imovel_comercial", "apartamento"})
IDADE_MAX = {
    "carro": 10,
    "caminhao": 15,
    "maquina_rural": 5,
    "veiculo_leve": 10,
    "veiculo_pesado": 15,
    "maquina": 5,
}
PORC_CREDITO_VEICULO = Decimal("0.50")
PORC_CREDITO_IMOVEL = Decimal("0.35")
VEICULO_PRAZO = 60
VEICULO_TAXA = Decimal("2.7")
IMOVEL_PRAZO = 180
IMOVEL_TAXA = Decimal("1.6")

STATUS_AWAITING_DOCS = "AWAITING_DOCS"
STATUS_UNDER_REVIEW = "UNDER_REVIEW"
STATUS_PENDING = "PENDING"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"
STATUS_CANCELLED = "CANCELLED"
STATUS_TERMINAL = frozenset({STATUS_APPROVED, STATUS_REJECTED, STATUS_CANCELLED})

STATUS_LABELS = {
    STATUS_AWAITING_DOCS: "Aguardando Documentação",
    STATUS_UNDER_REVIEW: "Em Análise",
    STATUS_PENDING: "Pendente",
    STATUS_APPROVED: "Aprovado",
    STATUS_REJECTED: "Reprovado",
    STATUS_CANCELLED: "Cancelado",
}

DOCS_CLIENT_BASE = [
    {"code": "RG_CPF", "label": "RG e CPF (ou CNH) — proponente"},
    {"code": "COMPROVANTE_RENDA", "label": "Comprovante de renda / faturamento (últimos 3 meses)"},
    {"code": "COMPROVANTE_ENDERECO", "label": "Comprovante de endereço do proponente"},
]
DOCS_PJ = [
    {"code": "CONTRATO_SOCIAL", "label": "Contrato social / alterações consolidadas (PJ)"},
    {"code": "QSA_REPRESENTANTES", "label": "QSA / procuração dos representantes legais (PJ)"},
]
DOCS_SDC_IMOVEL = [
    {"code": "MATRICULA_ENOTARIADO", "label": "Matrícula atualizada (e-notariado)"},
    {"code": "LAUDO_AVALIACAO", "label": "Laudo de avaliação do imóvel em garantia"},
    {"code": "IPTU_IPTUR", "label": "IPTU / carnê do imóvel (exercício vigente)"},
    {"code": "SERASA", "label": "Consulta Serasa / restrições cadastrais"},
    {"code": "BACEN", "label": "Consulta Bacen (SCR)"},
]
DOCS_SDC_VEHICLE = [
    {"code": "CRLV", "label": "CRLV (DETRAN — consulta prevalece)"},
    {"code": "FIPE_MOLICAR", "label": "Tabela FIPE ou Molicar"},
    {"code": "LAUDO_AVALIACAO", "label": "Laudo de avaliação do veículo"},
    {"code": "COMPROVANTE_QUITACAO", "label": "Comprovante de quitação / ausência de gravame"},
    {"code": "SERASA", "label": "Consulta Serasa / restrições cadastrais"},
    {"code": "BACEN", "label": "Consulta Bacen (SCR)"},
]
DOCS_SDC_MAQUINA = [
    {"code": "NOTA_FISCAL_MAQUINA", "label": "Nota fiscal / registro da máquina ou equipamento"},
    {"code": "LAUDO_AVALIACAO", "label": "Laudo de avaliação do equipamento"},
    {"code": "SERASA", "label": "Consulta Serasa / restrições cadastrais"},
    {"code": "BACEN", "label": "Consulta Bacen (SCR)"},
]

TIPOS_LABEL = {
    "imovel": "Imóvel",
    "casa": "Imóvel",
    "lote": "Imóvel",
    "imovel_rural": "Imóvel",
    "imovel_comercial": "Imóvel",
    "apartamento": "Imóvel",
    "veiculo_leve": "Veículo leve",
    "veiculo_pesado": "Veículo pesado",
    "maquina": "Máquina",
    "carro": "Veículo leve",
    "caminhao": "Veículo pesado",
    "maquina_rural": "Máquina",
}


def assert_desk_access(user: User) -> None:
    if user.role not in DESK_ROLES:
        raise HTTPException(status_code=403, detail="Sem acesso à mesa comercial SDC")


def sdc_required_docs(asset_type: str, person_type: str = "PF") -> list[dict]:
    """Checklist documental SDC por tipo de bem e PF/PJ (mesa comercial)."""
    tipo = (asset_type or "").strip().lower()
    pt = (person_type or "PF").strip().upper()
    rows: list[dict] = list(DOCS_CLIENT_BASE)
    if pt == "PJ":
        rows.extend(DOCS_PJ)
    if tipo in TIPOS_IMOVEL:
        rows.extend(DOCS_SDC_IMOVEL)
    elif tipo == "maquina":
        rows.extend(DOCS_SDC_MAQUINA)
    elif tipo in TIPOS_VEICULO:
        rows.extend(DOCS_SDC_VEHICLE)
    return rows


def _allowed_doc_types(asset_type: str, person_type: str) -> set[str]:
    codes = {d["code"] for d in sdc_required_docs(asset_type, person_type)}
    codes.add("SDC_SUPPORT")
    return codes


def _checklist_uploaded_codes(docs: list[SdcSolicitationDocument]) -> set[str]:
    return {d.doc_type for d in docs if d.doc_type}


def checklist_complete_for(item: SdcSolicitation, docs: list[SdcSolicitationDocument]) -> bool:
    required = {d["code"] for d in sdc_required_docs(item.asset_type, item.person_type)}
    uploaded = _checklist_uploaded_codes(docs)
    return required.issubset(uploaded)


def submit_documents(db: Session, user: User, item: SdcSolicitation) -> SdcSolicitation:
    """Parceiro transmite o pacote após anexar todos os itens obrigatórios do checklist."""
    assert_desk_access(user)
    if _is_admin(user):
        raise HTTPException(status_code=403, detail="Transmissão é ação do parceiro; admin altera status manualmente.")
    if item.status in STATUS_TERMINAL:
        raise HTTPException(status_code=422, detail="Solicitação encerrada — não é possível transmitir documentação.")
    if item.status != STATUS_AWAITING_DOCS:
        raise HTTPException(status_code=422, detail="Documentação já foi transmitida ou está em análise.")
    docs = list_documents(db, item.id)
    if not checklist_complete_for(item, docs):
        uploaded = _checklist_uploaded_codes(docs)
        missing = [d for d in sdc_required_docs(item.asset_type, item.person_type) if d["code"] not in uploaded]
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Anexe todos os documentos do checklist antes de transmitir.",
                "missing": missing,
            },
        )
    item.status = STATUS_UNDER_REVIEW
    db.flush()
    return item


def _dec(value) -> Decimal:
    return Decimal(str(value or 0))


def _installment_for(credito: Decimal, prazo: int, taxa: Decimal) -> Decimal:
    if credito <= 0 or prazo <= 0:
        return Decimal("0")
    i = taxa / Decimal("100")
    parcela = credito * i / (Decimal("1") - Decimal(str(math_pow(float(1 + i), -prazo))))
    return money(parcela)


def _simulation_row(credito: Decimal, prazo: int, taxa: Decimal) -> dict:
    return {
        "credito": str(money(credito)),
        "parcela_estimada": str(_installment_for(credito, prazo, taxa)),
        "prazo_meses": prazo,
        "taxa_juros_mensal": str(taxa.quantize(Decimal("0.01"))),
    }


def _apply_sdc_asset_totals(data: dict) -> dict:
    """Soma valores de properties_json (imóveis) ou vehicles_json (veículos) no asset_value."""
    merged = dict(data)
    props = merged.get("properties_json") or []
    if isinstance(props, list) and props:
        total = Decimal("0")
        for row in props:
            if isinstance(row, dict):
                total += _dec(row.get("property_value") or 0)
        if total > 0:
            merged["asset_value"] = str(money(total))
            merged["asset_type"] = "imovel"
    tipo = str(merged.get("asset_type") or "").strip().lower()
    vehicles = merged.get("vehicles_json") or []
    if isinstance(vehicles, list) and vehicles and tipo in TIPOS_VEICULO:
        total = Decimal("0")
        for row in vehicles:
            if isinstance(row, dict):
                total += _dec(row.get("vehicle_value") or row.get("asset_value") or 0)
        if total > 0:
            merged["asset_value"] = str(money(total))
    return merged


def evaluate_sdc_desk(data: dict) -> dict:
    data = _apply_sdc_asset_totals(dict(data))
    motivos: list[str] = []
    tipo_bem = str(data.get("asset_type") or data.get("tipo_bem") or "").strip().lower()
    is_veiculo = tipo_bem in TIPOS_VEICULO
    is_imovel = tipo_bem in TIPOS_IMOVEL
    if not tipo_bem or (not is_veiculo and not is_imovel):
        motivos.append("Tipo de bem inválido.")

    if not bool(data.get("asset_paid_off", data.get("bem_quitado", False))):
        motivos.append("O bem não está quitado.")
    if bool(data.get("asset_has_lien", data.get("bem_pendencia", False))):
        motivos.append("O bem possui pendência.")
    if not bool(data.get("docs_complete", data.get("documentacao_completa", False))):
        motivos.append("Documentação incompleta.")

    if is_veiculo:
        vehicles = data.get("vehicles_json") or []
        years: list[int] = []
        if isinstance(vehicles, list) and vehicles:
            for row in vehicles:
                if not isinstance(row, dict):
                    continue
                ano = int(row.get("year") or row.get("asset_year") or 0)
                if ano > 0:
                    years.append(ano)
        if not years:
            ano = int(data.get("asset_year") or data.get("ano_fabricacao") or 0)
            if ano > 0:
                years.append(ano)
        if not years:
            motivos.append("Informe o ano de fabricação de cada veículo.")
        else:
            limite = IDADE_MAX.get(tipo_bem, 0)
            for ano in years:
                idade = date.today().year - ano
                if idade > limite:
                    motivos.append(f"Veículo (ano {ano}) excede a idade máxima permitida ({limite} anos).")
                    break

    valor = _dec(data.get("asset_value") or data.get("valor_bens") or 0)
    if valor <= 0:
        motivos.append("Informe o valor total dos bens.")

    asset_type_key = str(data.get("asset_type") or data.get("tipo_bem") or "").strip().lower()
    person_type = str(data.get("person_type") or "PF").strip().upper()
    required_docs = sdc_required_docs(asset_type_key, person_type)

    if motivos:
        return {
            "viable": False,
            "motivos": motivos,
            "required_docs": required_docs,
            "credito_estimado": "0.00",
            "parcela_estimada": "0.00",
            "prazo_meses": 0,
            "taxa_juros_mensal": "0.00",
            "tipo_categoria": "",
            "message": "NÃO FOI POSSÍVEL SEGUIR COM A SUA OPERAÇÃO",
        }

    if is_veiculo:
        porc, prazo, taxa = PORC_CREDITO_VEICULO, VEICULO_PRAZO, VEICULO_TAXA
        categoria = "veiculo"
    else:
        porc, prazo, taxa = PORC_CREDITO_IMOVEL, IMOVEL_PRAZO, IMOVEL_TAXA
        categoria = "imovel"

    credito_max = money(valor * porc)
    sim_limite = _simulation_row(credito_max, prazo, taxa)

    requested_raw = data.get("requested_leverage_amount")
    requested = _dec(requested_raw) if requested_raw not in (None, "", 0) else Decimal("0")
    if requested > 0:
        requested = money(requested)
    requested_exceeds = requested > credito_max if requested > 0 else False
    sim_solicitada = None
    if requested > 0 and not requested_exceeds:
        sim_solicitada = _simulation_row(requested, prazo, taxa)

    message = "Operação viável"
    if requested_exceeds:
        message = (
            f"O valor solicitado ({money(requested)}) excede o limite máximo permitido "
            f"({credito_max}). Você pode prosseguir com o limite máximo."
        )

    return {
        "viable": True,
        "motivos": [],
        "required_docs": required_docs,
        "credito_estimado": str(credito_max),
        "limite_maximo_credito": str(credito_max),
        "credito_solicitado": str(requested) if requested > 0 else None,
        "requested_exceeds_limit": requested_exceeds,
        "excesso_sobre_limite": str(money(requested - credito_max)) if requested_exceeds else None,
        "simulacao_limite": sim_limite,
        "simulacao_solicitada": sim_solicitada,
        "show_choice": sim_solicitada is not None,
        "parcela_estimada": sim_limite["parcela_estimada"],
        "prazo_meses": prazo,
        "taxa_juros_mensal": str(taxa.quantize(Decimal("0.01"))),
        "tipo_categoria": categoria,
        "message": message,
    }


def _is_admin(user: User) -> bool:
    return user.role in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF, Role.MASTER_FRANCHISEE}


def _chain_user_ids(db: Session, user: User) -> list[str]:
    """Parceiro vê a própria cadeia (downline); admin não usa filtro."""
    from app.models import NetworkNode

    ids = {user.id}
    changed = True
    while changed:
        changed = False
        children = list(
            db.scalars(
                select(NetworkNode).where(
                    NetworkNode.organization_id == user.organization_id,
                    NetworkNode.sponsor_user_id.in_(list(ids)),
                    NetworkNode.tree_type == "SALES",
                )
            )
        )
        for child in children:
            if child.user_id not in ids:
                ids.add(child.user_id)
                changed = True
    return list(ids)


def list_solicitations(db: Session, user: User) -> list[SdcSolicitation]:
    assert_desk_access(user)
    q = select(SdcSolicitation).where(SdcSolicitation.organization_id == user.organization_id)
    if not _is_admin(user):
        chain = _chain_user_ids(db, user)
        q = q.where(SdcSolicitation.partner_user_id.in_(chain or [user.id]))
    return list(db.scalars(q.order_by(SdcSolicitation.created_at.desc())))


def list_documents(db: Session, solicitation_id: str) -> list[SdcSolicitationDocument]:
    return list(
        db.scalars(
            select(SdcSolicitationDocument)
            .where(SdcSolicitationDocument.solicitation_id == solicitation_id)
            .order_by(SdcSolicitationDocument.created_at.desc())
        )
    )


def get_solicitation(db: Session, user: User, solicitation_id: str) -> SdcSolicitation:
    assert_desk_access(user)
    item = db.scalar(
        select(SdcSolicitation).where(
            SdcSolicitation.id == solicitation_id,
            SdcSolicitation.organization_id == user.organization_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Solicitação SDC não encontrada")
    if not _is_admin(user) and item.partner_user_id not in _chain_user_ids(db, user):
        raise HTTPException(status_code=403, detail="Sem acesso a esta solicitação")
    return item


def _resolve_chosen_credit(payload: dict, result: dict) -> tuple[Decimal, dict]:
    """Retorna crédito escolhido e linha de simulação (parcela/prazo/taxa)."""
    limite = _dec(result.get("limite_maximo_credito") or result.get("credito_estimado"))
    chosen_raw = payload.get("chosen_credit_amount")
    if chosen_raw in (None, "", 0):
        row = result.get("simulacao_limite") or {}
        return limite, row
    chosen = money(_dec(chosen_raw))
    if chosen > limite:
        raise HTTPException(
            status_code=422,
            detail=f"Crédito escolhido ({chosen}) excede o limite máximo ({limite}).",
        )
    sim_sol = result.get("simulacao_solicitada")
    sim_lim = result.get("simulacao_limite") or {}
    if sim_sol and _dec(sim_sol.get("credito")) == chosen:
        return chosen, sim_sol
    if _dec(sim_lim.get("credito")) == chosen:
        return chosen, sim_lim
    prazo = int(result.get("prazo_meses") or sim_lim.get("prazo_meses") or 0)
    taxa = _dec(result.get("taxa_juros_mensal") or sim_lim.get("taxa_juros_mensal"))
    return chosen, _simulation_row(chosen, prazo, taxa)


def open_tapaf_checkout_for_solicitation(db: Session, user: User, item: SdcSolicitation) -> dict:
    """Cria proposta SD C + pauta pré-análise e retorna checkout TAPAF (R$ 1.500)."""
    from app.pre_analysis_service import generate_tapaf_checkout, get_or_create_pauta

    assert_desk_access(user)
    try:
        meta = json_loads(item.evaluation_json or "{}")
    except (TypeError, ValueError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}

    tapaf_meta = meta.get("tapaf") if isinstance(meta.get("tapaf"), dict) else {}
    proposal_id = tapaf_meta.get("proposal_id") or item.proposal_id

    if not proposal_id:
        lead = Lead(
            organization_id=user.organization_id,
            owner_id=item.partner_user_id or user.id,
            name=item.contact_name,
            phone=item.contact_phone or "00000000000",
            document=item.document,
            product_interest="SDC",
            status="QUALIFIED",
            source="SDC_DESK",
        )
        db.add(lead)
        db.flush()
        proposal = Proposal(
            organization_id=user.organization_id,
            lead_id=lead.id,
            product="SDC",
            requested_amount=item.credit_estimated,
            status="SUBMITTED",
            terms_json=json_dumps(
                {
                    "sdc_solicitation_id": item.id,
                    "asset_type": item.asset_type,
                    "asset_value": str(item.asset_value),
                    "channel": "SDC_DESK",
                    "tapaf_phase": True,
                },
                ensure_ascii=False,
            ),
            sale_channel="PARTNER_OFFICE",
            served_by_user_id=user.id,
            commission_originator_id=item.partner_user_id,
            created_by_user_id=user.id,
        )
        db.add(proposal)
        db.flush()
        proposal_id = proposal.id
        item.proposal_id = proposal_id
        tapaf_meta["proposal_id"] = proposal_id
        tapaf_meta["lead_id"] = lead.id
        meta["tapaf"] = tapaf_meta
        item.evaluation_json = json_dumps({**meta, "channel": meta.get("channel") or "SDC_DESK"}, ensure_ascii=False)

    proposal = db.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=500, detail="Proposta TAPAF não encontrada")

    pauta = get_or_create_pauta(db, user, proposal)
    if pauta.status == "PENDING_DOCUMENTS":
        pauta.status = "DOCUMENTS_OK"
    at = "VEHICLE" if item.asset_type in TIPOS_VEICULO else "REAL_ESTATE"
    pauta.asset_type = at
    db.flush()

    checkout = generate_tapaf_checkout(pauta)
    tapaf_meta["pauta_id"] = pauta.id
    tapaf_meta["pauta_code"] = pauta.pauta_code
    meta["tapaf"] = tapaf_meta
    item.evaluation_json = json_dumps({**meta, "channel": meta.get("channel") or "SDC_DESK"}, ensure_ascii=False)
    return {
        "proposal_id": proposal_id,
        "pauta_id": pauta.id,
        **checkout,
    }


def store_solicitation(db: Session, user: User, payload: dict) -> SdcSolicitation:
    assert_desk_access(user)
    payload = _apply_sdc_asset_totals(dict(payload))
    result = evaluate_sdc_desk(payload)
    if not result["viable"]:
        raise HTTPException(
            status_code=422,
            detail={"message": result["message"], "motivos": result["motivos"], "result": result},
        )
    credit_chosen, sim_row = _resolve_chosen_credit(payload, result)
    partner_id = user.id if user.role in PARTNER_NETWORK_ROLES or user.role == Role.PARTNER else payload.get("partner_user_id") or user.id
    if _is_admin(user) and payload.get("partner_user_id"):
        partner_id = payload["partner_user_id"]

    item = SdcSolicitation(
        organization_id=user.organization_id,
        partner_user_id=partner_id,
        created_by_id=user.id,
        status=STATUS_AWAITING_DOCS,
        contact_name=str(payload["contact_name"]).strip(),
        contact_email=str(payload["contact_email"]).strip().lower(),
        contact_phone=str(payload.get("contact_phone") or "").strip(),
        document=str(payload.get("document") or "").strip() or None,
        person_type=str(payload.get("person_type") or "PF").upper()[:2],
        address=str(payload.get("address") or "").strip() or None,
        occupation=str(payload.get("occupation") or "").strip() or None,
        income_value=money(_dec(payload.get("income_value") or 0)),
        asset_type=str(payload["asset_type"]).strip().lower(),
        asset_value=money(_dec(payload["asset_value"])),
        asset_year=int(payload["asset_year"]) if payload.get("asset_year") else None,
        asset_paid_off=bool(payload.get("asset_paid_off", True)),
        asset_has_lien=bool(payload.get("asset_has_lien", False)),
        docs_complete=bool(payload.get("docs_complete", True)),
        credit_estimated=money(_dec(credit_chosen)),
        installment_estimated=money(_dec(sim_row.get("parcela_estimada") or result["parcela_estimada"])),
        term_months=int(sim_row.get("prazo_meses") or result["prazo_meses"]),
        interest_rate_monthly=money(_dec(sim_row.get("taxa_juros_mensal") or result["taxa_juros_mensal"])),
        evaluation_json=evaluation_json_with_meta(
            {
                **result,
                "chosen_credit_amount": str(credit_chosen),
                **desk_payload_extras(
                    payload,
                    (
                        "requested_leverage_amount",
                        "property_registry",
                        "vehicle_plate",
                        "vehicle_renavam",
                        "vehicles_json",
                        "properties_json",
                        "asset_full_address",
                        "partners_json",
                    ),
                ),
            },
            channel="SDC_DESK",
            lead_id=str(payload.get("lead_id") or "").strip() or None,
        ),
    )
    db.add(item)
    db.flush()
    return item


def update_status(db: Session, user: User, item: SdcSolicitation, status: str, notes: str | None = None) -> SdcSolicitation:
    assert_desk_access(user)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Apenas operação LETTER altera o status do SDC")
    status = status.upper().strip()
    if status not in STATUS_LABELS:
        raise HTTPException(status_code=422, detail="Status inválido")
    if item.status in STATUS_TERMINAL and status != item.status:
        # allow admin override only from PENDING/UNDER_REVIEW typically; still allow change with notes
        pass
    item.status = status
    if notes is not None:
        item.status_notes = notes
    db.flush()
    return item


async def add_document(
    db: Session,
    user: User,
    item: SdcSolicitation,
    *,
    upload: UploadFile,
    doc_type: str,
    comment: str | None = None,
) -> SdcSolicitationDocument:
    assert_desk_access(user)
    if item.status in STATUS_TERMINAL and not _is_admin(user):
        raise HTTPException(status_code=422, detail="Esta solicitação já está encerrada e não aceita mais documentos.")
    if item.status == STATUS_APPROVED and not _is_admin(user):
        raise HTTPException(status_code=422, detail="SDC aprovado não aceita novos documentos do parceiro.")
    dtype = (doc_type or "SDC_SUPPORT").strip().upper()[:80]
    allowed = _allowed_doc_types(item.asset_type, item.person_type)
    if dtype not in allowed:
        raise HTTPException(status_code=422, detail=f"Tipo de documento inválido para este SDC. Use um item do checklist.")
    document = await persist_upload(upload, user, "sdc_solicitation", item.id, dtype)
    document.status = "CLEAN"
    db.add(document)
    db.flush()
    row = SdcSolicitationDocument(
        organization_id=user.organization_id,
        solicitation_id=item.id,
        document_id=document.id,
        doc_type=dtype,
        comment=(comment or None),
        uploaded_by_id=user.id,
    )
    db.add(row)
    db.flush()
    return row


def remove_document(db: Session, user: User, item: SdcSolicitation, link_id: str) -> None:
    assert_desk_access(user)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Apenas operação LETTER pode excluir documentos")
    row = db.scalar(
        select(SdcSolicitationDocument).where(
            SdcSolicitationDocument.id == link_id,
            SdcSolicitationDocument.solicitation_id == item.id,
            SdcSolicitationDocument.organization_id == user.organization_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    document = db.get(Document, row.document_id)
    db.delete(row)
    if document:
        purge_document_links(db, document.id)
        purge_document(db, document)
    db.flush()


def _document_link_view(db: Session, row: SdcSolicitationDocument) -> dict:
    document = db.get(Document, row.document_id)
    return {
        "id": row.id,
        "doc_type": row.doc_type,
        "comment": row.comment,
        "document_id": row.document_id,
        "filename": document.filename if document else None,
        "status": document.status if document else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def create_sale_from_sdc(
    db: Session,
    user: User,
    item: SdcSolicitation,
    *,
    quota_id: str,
) -> dict:
    assert_desk_access(user)
    if item.status != STATUS_APPROVED:
        raise HTTPException(status_code=422, detail="Só SDCs Aprovados podem gerar cadastro de venda")
    if item.quota_id:
        raise HTTPException(status_code=409, detail="Este SDC já possui venda vinculada")
    quota = db.scalar(
        select(Quota).where(Quota.id == quota_id, Quota.organization_id == user.organization_id)
    )
    if not quota:
        raise HTTPException(status_code=404, detail="Cota não encontrada")
    if quota.status not in {"AVAILABLE", "RESERVED"}:
        raise HTTPException(status_code=422, detail="Cota indisponível")

    if item.proposal_id:
        proposal = db.get(Proposal, item.proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposta vinculada não encontrada")
        proposal.requested_amount = item.credit_estimated
        lead_id = proposal.lead_id
    else:
        lead = Lead(
            organization_id=user.organization_id,
            owner_id=item.partner_user_id or user.id,
            name=item.contact_name,
            phone=item.contact_phone or "00000000000",
            document=item.document,
            product_interest="SDC",
            status="QUALIFIED",
            source="SDC_DESK",
        )
        db.add(lead)
        db.flush()
        lead_id = lead.id
        proposal = Proposal(
            organization_id=user.organization_id,
            lead_id=lead.id,
            product="SDC",
            requested_amount=item.credit_estimated,
            status="SUBMITTED",
            terms_json=json_dumps(
                {
                    "sdc_solicitation_id": item.id,
                    "quota_id": quota.id,
                    "asset_type": item.asset_type,
                    "asset_value": str(item.asset_value),
                    "channel": "SDC_DESK",
                },
                ensure_ascii=False,
            ),
            sale_channel="PARTNER_OFFICE",
            served_by_user_id=user.id,
            commission_originator_id=item.partner_user_id,
            created_by_user_id=user.id,
        )
        db.add(proposal)
        db.flush()
        item.proposal_id = proposal.id
    quota.status = "RESERVED"
    item.quota_id = quota.id
    db.flush()
    return {"proposal_id": proposal.id, "lead_id": lead_id, "quota_id": quota.id}


def solicitation_view(
    item: SdcSolicitation,
    docs: list[SdcSolicitationDocument] | None = None,
    db: Session | None = None,
) -> dict:
    doc_rows = docs or []
    uploaded = _checklist_uploaded_codes(doc_rows)
    required = sdc_required_docs(item.asset_type, item.person_type)
    complete = checklist_complete_for(item, doc_rows)
    return {
        "id": item.id,
        "status": item.status,
        "status_label": STATUS_LABELS.get(item.status, item.status),
        "status_notes": item.status_notes,
        "partner_user_id": item.partner_user_id,
        "contact_name": item.contact_name,
        "contact_email": item.contact_email,
        "contact_phone": item.contact_phone,
        "document": item.document,
        "person_type": item.person_type,
        "address": item.address,
        "occupation": item.occupation,
        "income_value": str(money(_dec(item.income_value))),
        "asset_type": item.asset_type,
        "asset_type_label": TIPOS_LABEL.get(item.asset_type, item.asset_type),
        "asset_value": str(money(_dec(item.asset_value))),
        "asset_year": item.asset_year,
        "asset_paid_off": item.asset_paid_off,
        "asset_has_lien": item.asset_has_lien,
        "docs_complete": item.docs_complete,
        "credit_estimated": str(money(_dec(item.credit_estimated))),
        "installment_estimated": str(money(_dec(item.installment_estimated))),
        "term_months": item.term_months,
        "interest_rate_monthly": str(money(_dec(item.interest_rate_monthly))),
        "proposal_id": item.proposal_id,
        "quota_id": item.quota_id,
        "required_docs": [{**d, "uploaded": d["code"] in uploaded} for d in required],
        "docs_checklist_complete": complete,
        "can_submit_documents": item.status == STATUS_AWAITING_DOCS and complete,
        "documents": [
            _document_link_view(db, d) if db else {
                "id": d.id,
                "doc_type": d.doc_type,
                "comment": d.comment,
                "document_id": d.document_id,
                "filename": None,
                "status": None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in doc_rows
        ],
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "can_create_sale": item.status == STATUS_APPROVED and not item.quota_id,
        **evaluation_meta(item.evaluation_json),
    }
