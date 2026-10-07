"""SDC commercial desk — Solicitação / Cadastro / Venda Cap Giro (legado Paulo)."""

from __future__ import annotations

from datetime import UTC, date, datetime
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
from app.sdc_checklist_service import (
    ASSET_CATEGORY_LABELS,
    OPERATION_TYPE_LABELS,
    normalize_asset_category,
    normalize_operation_type,
    resolve_required_docs,
)
from app.network_service import PARTNER_NETWORK_ROLES
from app.services import money

DESK_ROLES = frozenset({
    Role.PLATFORM_ADMIN,
    Role.INTERNAL_STAFF,
    Role.MASTER_FRANCHISEE,
    Role.MANAGER,
    Role.PARTNER,
})

TIPOS_VEICULO = frozenset({
    "veiculo",
    "veiculo_leve",
    "veiculo_pesado",
    "maquina",
    "maquina_agricola",
    "carro",
    "caminhao",
    "maquina_rural",
})
TIPOS_IMOVEL = frozenset({
    "imovel",
    "imovel_urbano",
    "casa",
    "lote",
    "imovel_rural",
    "imovel_comercial",
    "apartamento",
})
IDADE_MAX = {
    "carro": 10,
    "caminhao": 15,
    "maquina_rural": 5,
    "veiculo_leve": 10,
    "veiculo_pesado": 15,
    "maquina": 5,
    "maquina_agricola": 5,
    "veiculo": 10,
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

UPLOAD_BATCH_INITIAL = "INITIAL"
UPLOAD_BATCH_PENDENCY = "PENDENCY"

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
    "imovel_urbano": "Imóvel urbano",
    "veiculo": "Veículo",
    "maquina_agricola": "Máquina agrícola",
}


def _item_asset_category(item: SdcSolicitation) -> str:
    if item.asset_category:
        return normalize_asset_category(item.asset_category)
    return normalize_asset_category(item.asset_type)


def _item_operation_type(item: SdcSolicitation) -> str:
    return normalize_operation_type(item.operation_type, item.person_type)


def sdc_required_docs(
    asset_type: str,
    person_type: str = "PF",
    *,
    db: Session | None = None,
    organization_id: str | None = None,
    operation_type: str | None = None,
    asset_category: str | None = None,
) -> list[dict]:
    category = normalize_asset_category(asset_category or asset_type)
    op = normalize_operation_type(operation_type, person_type)
    return resolve_required_docs(
        db,
        organization_id,
        asset_type=category,
        operation_type=op,
        person_type=person_type,
    )


def _load_status_log(item: SdcSolicitation) -> list[dict]:
    raw = item.status_log_json
    if not raw:
        return []
    try:
        parsed = json_loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def _save_status_log(item: SdcSolicitation, entries: list[dict]) -> None:
    item.status_log_json = json_dumps(entries, ensure_ascii=False)


def _load_pending_codes(item: SdcSolicitation) -> list[str]:
    raw = item.pending_doc_codes_json
    if not raw:
        return []
    try:
        parsed = json_loads(raw)
        if isinstance(parsed, list):
            return [str(c).strip().upper() for c in parsed if c]
    except (TypeError, ValueError):
        pass
    return []


def _save_pending_codes(item: SdcSolicitation, codes: list[str]) -> None:
    item.pending_doc_codes_json = json_dumps(codes, ensure_ascii=False) if codes else None


def _append_status_log(
    item: SdcSolicitation,
    user: User,
    *,
    status: str,
    notes: str | None = None,
    pending_doc_codes: list[str] | None = None,
) -> None:
    entries = _load_status_log(item)
    entries.append(
        {
            "at": datetime.now(UTC).isoformat(),
            "user_id": user.id,
            "user_name": (user.name or user.email or user.id),
            "status": status,
            "status_label": STATUS_LABELS.get(status, status),
            "notes": (notes or "").strip() or None,
            "pending_doc_codes": pending_doc_codes or [],
        }
    )
    _save_status_log(item, entries)


def assert_desk_access(user: User) -> None:
    if user.role not in DESK_ROLES:
        raise HTTPException(status_code=403, detail="Sem acesso à mesa comercial SDC")


def _required_docs_for_item(db: Session | None, item: SdcSolicitation) -> list[dict]:
    return sdc_required_docs(
        item.asset_type,
        item.person_type,
        db=db,
        organization_id=item.organization_id,
        operation_type=item.operation_type,
        asset_category=_item_asset_category(item),
    )


def _allowed_doc_types(db: Session | None, item: SdcSolicitation) -> set[str]:
    codes = {d["code"] for d in _required_docs_for_item(db, item)}
    codes.add("SDC_SUPPORT")
    if item.status == STATUS_PENDING:
        pending = set(_load_pending_codes(item))
        if pending:
            return pending | {"SDC_SUPPORT"}
    return codes


def _checklist_uploaded_codes(
    docs: list[SdcSolicitationDocument],
    *,
    upload_batch: str | None = None,
) -> set[str]:
    out: set[str] = set()
    for d in docs:
        if not d.doc_type or d.doc_type == "SDC_SUPPORT":
            continue
        batch = (d.upload_batch or UPLOAD_BATCH_INITIAL).upper()
        if upload_batch and batch != upload_batch.upper():
            continue
        out.add(d.doc_type)
    return out


def _required_doc_codes(docs: list[dict]) -> set[str]:
    return {d["code"] for d in docs if d.get("required", True)}


def _active_required_codes(item: SdcSolicitation, db: Session | None) -> set[str]:
    if item.status == STATUS_PENDING:
        pending = _load_pending_codes(item)
        if pending:
            return set(pending)
    return _required_doc_codes(_required_docs_for_item(db, item))


def checklist_complete_for(
    item: SdcSolicitation,
    docs: list[SdcSolicitationDocument],
    db: Session | None = None,
) -> bool:
    if item.status == STATUS_PENDING and _load_pending_codes(item):
        required = _active_required_codes(item, db)
        uploaded = _checklist_uploaded_codes(docs, upload_batch=UPLOAD_BATCH_PENDENCY)
        return required.issubset(uploaded)
    required = _active_required_codes(item, db)
    uploaded = _checklist_uploaded_codes(docs, upload_batch=UPLOAD_BATCH_INITIAL)
    return required.issubset(uploaded)


def submit_documents(
    db: Session,
    user: User,
    item: SdcSolicitation,
    *,
    partner_observation: str | None = None,
) -> SdcSolicitation:
    """Parceiro transmite o pacote após anexar todos os itens obrigatórios do checklist."""
    assert_desk_access(user)
    if _is_letter_ops(user):
        raise HTTPException(status_code=403, detail="Transmissão é ação do parceiro; admin altera status manualmente.")
    if item.status in STATUS_TERMINAL:
        raise HTTPException(status_code=422, detail="Solicitação encerrada — não é possível transmitir documentação.")
    docs = list_documents(db, item.id)
    if item.status == STATUS_PENDING and _load_pending_codes(item):
        if not checklist_complete_for(item, docs, db):
            required = _load_pending_codes(item)
            uploaded = _checklist_uploaded_codes(docs, upload_batch=UPLOAD_BATCH_PENDENCY)
            missing_codes = [c for c in required if c not in uploaded]
            catalog = {d["code"]: d for d in _required_docs_for_item(db, item)}
            missing = [catalog.get(c, {"code": c, "label": c}) for c in missing_codes]
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Anexe todos os documentos pendentes antes de reenviar.",
                    "missing": missing,
                },
            )
        item.status = STATUS_UNDER_REVIEW
        _save_pending_codes(item, [])
        _append_status_log(item, user, status=STATUS_UNDER_REVIEW, notes="Documentação pendente reenviada pelo parceiro.")
        db.flush()
        return item
    if item.status != STATUS_AWAITING_DOCS:
        raise HTTPException(status_code=422, detail="Documentação já foi transmitida ou está em análise.")
    if not checklist_complete_for(item, docs, db):
        uploaded = _checklist_uploaded_codes(docs, upload_batch=UPLOAD_BATCH_INITIAL)
        missing = [
            d for d in _required_docs_for_item(db, item) if d.get("required", True) and d["code"] not in uploaded
        ]
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Anexe todos os documentos do checklist antes de transmitir.",
                "missing": missing,
            },
        )
    if partner_observation is not None:
        item.partner_observation = partner_observation.strip() or None
    item.status = STATUS_UNDER_REVIEW
    _append_status_log(item, user, status=STATUS_UNDER_REVIEW, notes="Documentação inicial transmitida pelo parceiro.")
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


MAX_PROPERTY_DEBT_PCT = Decimal("0.30")
DEBT_SFI = "SFI"
DEBT_SFH = "SFH"
DEBT_HIPOTECA = "HIPOTECA"
DEBT_DEMAIS_FINANCEIRAS = "DEMAIS_FINANCEIRAS"
DEBT_NAO_FINANCEIRAS = "NAO_FINANCEIRAS"
SDC_FLASH_DEBT_TYPES = frozenset({DEBT_HIPOTECA, DEBT_DEMAIS_FINANCEIRAS})
SDC_SDC_DEBT_TYPES = frozenset({DEBT_SFI, DEBT_SFH})


def _build_flash_handoff_from_sdc(data: dict) -> dict:
    return {
        "source": "SDC_DESK",
        "saved_at": datetime.now(UTC).isoformat(),
        "contact_name": str(data.get("contact_name") or "").strip(),
        "contact_email": str(data.get("contact_email") or "").strip(),
        "contact_phone": str(data.get("contact_phone") or "").strip(),
        "document": str(data.get("document") or "").strip(),
        "person_type": str(data.get("person_type") or "PF").strip().upper(),
        "address": str(data.get("address") or "").strip(),
        "occupation": str(data.get("occupation") or "").strip(),
        "income_value": str(data.get("income_value") or "0"),
        "requested_amount": str(data.get("requested_leverage_amount") or data.get("requested_amount") or ""),
        "properties": data.get("properties_json") if isinstance(data.get("properties_json"), list) else [],
        "partners_json": data.get("partners_json") if isinstance(data.get("partners_json"), list) else [],
    }


def _sdc_credit_restrictions(data: dict) -> list[str]:
    motivos: list[str] = []
    if bool(data.get("client_has_credit_restriction")):
        motivos.append("Cliente com restrição creditícia — indicado Flash Capital.")
    person = str(data.get("person_type") or "PF").strip().upper()
    if person == "PJ" and bool(data.get("company_has_credit_restriction")):
        motivos.append("Empresa (PJ) com restrição creditícia — indicado Flash Capital.")
    partners = data.get("partners_json") or []
    if isinstance(partners, list):
        for idx, row in enumerate(partners, start=1):
            if isinstance(row, dict) and bool(row.get("has_credit_restriction")):
                motivos.append(f"Sócio {idx} com restrição creditícia — indicado Flash Capital.")
                break
    return motivos


def _sdc_property_debt_analysis(data: dict) -> tuple[list[str], bool, bool]:
    """Retorna (motivos, redirect_flash, profile_blocked)."""
    props = data.get("properties_json") or []
    if not isinstance(props, list) or not props:
        return [], False, False
    motivos: list[str] = []
    redirect_flash = False
    profile_blocked = False
    for idx, row in enumerate(props, start=1):
        if not isinstance(row, dict):
            continue
        label = f"Imóvel {idx}"
        paid_off = row.get("is_paid_off")
        if paid_off is None:
            motivos.append(f"{label}: informe se o imóvel está quitado.")
            continue
        if bool(paid_off):
            continue
        debt_type = str(row.get("debt_type") or "").strip().upper()
        property_value = _dec(row.get("property_value") or 0)
        payoff = _dec(row.get("debt_payoff_value") or 0)
        if payoff <= 0:
            motivos.append(f"{label}: informe o valor de quitação do bem.")
            continue
        if not debt_type:
            motivos.append(f"{label}: selecione o tipo de dívida na matrícula.")
            continue
        if debt_type == DEBT_NAO_FINANCEIRAS:
            profile_blocked = True
            motivos.append(f"{label}: dívidas não financeiras — sem perfil para o produto.")
            continue
        if property_value <= 0:
            motivos.append(f"{label}: informe o valor do imóvel para validar a dívida.")
            continue
        ratio = payoff / property_value
        if ratio > MAX_PROPERTY_DEBT_PCT:
            profile_blocked = True
            motivos.append(
                f"{label}: quitação superior a 30% do valor do bem — sem perfil para o produto."
            )
            continue
        if debt_type in SDC_FLASH_DEBT_TYPES:
            redirect_flash = True
            motivos.append(
                f"{label}: hipoteca ou demais dívidas financeiras — perfil Flash Capital (não SDC)."
            )
        elif debt_type not in SDC_SDC_DEBT_TYPES:
            motivos.append(f"{label}: tipo de dívida inválido.")
    return motivos, redirect_flash, profile_blocked


def _sdc_profile_block_response(
    data: dict,
    *,
    motivos: list[str],
    required_docs: list[dict],
    redirect_flash: bool,
    profile_blocked: bool,
) -> dict:
    message = "NÃO FOI POSSÍVEL SEGUIR COM A SUA OPERAÇÃO"
    if redirect_flash and not profile_blocked:
        message = "Cliente com perfil Flash Capital — utilize a esteira Flash Capital."
    payload = {
        "viable": False,
        "motivos": motivos,
        "required_docs": required_docs,
        "credito_estimado": "0.00",
        "parcela_estimada": "0.00",
        "prazo_meses": 0,
        "taxa_juros_mensal": "0.00",
        "tipo_categoria": "",
        "message": message,
        "redirect_flash": redirect_flash and not profile_blocked,
        "profile_blocked": profile_blocked,
    }
    if redirect_flash and not profile_blocked:
        payload["flash_handoff"] = _build_flash_handoff_from_sdc(data)
    return payload


def evaluate_sdc_desk(data: dict) -> dict:
    data = _apply_sdc_asset_totals(dict(data))
    motivos: list[str] = []
    tipo_bem = str(data.get("asset_type") or data.get("tipo_bem") or "").strip().lower()
    is_veiculo = tipo_bem in TIPOS_VEICULO
    is_imovel = tipo_bem in TIPOS_IMOVEL
    if not tipo_bem or (not is_veiculo and not is_imovel):
        motivos.append("Tipo de bem inválido.")

    asset_type_key = str(data.get("asset_type") or data.get("tipo_bem") or data.get("asset_category") or "").strip().lower()
    person_type = str(data.get("person_type") or "PF").strip().upper()
    operation_type = data.get("operation_type")
    asset_category = data.get("asset_category") or asset_type_key
    required_docs = sdc_required_docs(
        asset_type_key,
        person_type,
        operation_type=operation_type,
        asset_category=asset_category,
    )

    restriction_motivos = _sdc_credit_restrictions(data)
    debt_motivos, debt_redirect, debt_blocked = _sdc_property_debt_analysis(data) if is_imovel else ([], False, False)
    if restriction_motivos:
        return _sdc_profile_block_response(
            data,
            motivos=restriction_motivos,
            required_docs=required_docs,
            redirect_flash=True,
            profile_blocked=False,
        )
    if debt_blocked:
        return _sdc_profile_block_response(
            data,
            motivos=debt_motivos,
            required_docs=required_docs,
            redirect_flash=False,
            profile_blocked=True,
        )
    if debt_redirect:
        return _sdc_profile_block_response(
            data,
            motivos=debt_motivos,
            required_docs=required_docs,
            redirect_flash=True,
            profile_blocked=False,
        )
    motivos.extend([m for m in debt_motivos if "informe" in m.lower() or "selecione" in m.lower() or "inválido" in m.lower()])

    props = data.get("properties_json") or []
    has_property_debt_fields = isinstance(props, list) and any(isinstance(p, dict) and p.get("is_paid_off") is not None for p in props)
    if not has_property_debt_fields:
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
            "redirect_flash": False,
            "profile_blocked": False,
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
        "redirect_flash": False,
        "profile_blocked": False,
    }


def _is_admin(user: User) -> bool:
    return user.role in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF, Role.MASTER_FRANCHISEE}


def _is_letter_ops(user: User) -> bool:
    return user.role in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF}


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
    """Cria proposta SDC + pauta pré-análise (cobrança TAPAF após aceite do tomador)."""
    from app.pre_analysis_service import get_or_create_pauta

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

    tapaf_meta["pauta_id"] = pauta.id
    tapaf_meta["pauta_code"] = pauta.pauta_code
    meta["tapaf"] = tapaf_meta
    item.evaluation_json = json_dumps({**meta, "channel": meta.get("channel") or "SDC_DESK"}, ensure_ascii=False)
    return {
        "proposal_id": proposal_id,
        "pauta_id": pauta.id,
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

    asset_type_key = str(payload["asset_type"]).strip().lower()
    asset_category = normalize_asset_category(payload.get("asset_category") or asset_type_key)
    operation_type = normalize_operation_type(payload.get("operation_type"), payload.get("person_type"))

    item = SdcSolicitation(
        organization_id=user.organization_id,
        partner_user_id=partner_id,
        created_by_id=user.id,
        status=STATUS_AWAITING_DOCS,
        asset_category=asset_category,
        operation_type=operation_type,
        partner_observation=(str(payload.get("partner_observation") or "").strip() or None),
        contact_name=str(payload["contact_name"]).strip(),
        contact_email=str(payload["contact_email"]).strip().lower(),
        contact_phone=str(payload.get("contact_phone") or "").strip(),
        document=str(payload.get("document") or "").strip() or None,
        person_type=str(payload.get("person_type") or "PF").upper()[:2],
        address=str(payload.get("address") or "").strip() or None,
        occupation=str(payload.get("occupation") or "").strip() or None,
        income_value=money(_dec(payload.get("income_value") or 0)),
        asset_type=asset_type_key,
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


def update_status(
    db: Session,
    user: User,
    item: SdcSolicitation,
    status: str,
    notes: str | None = None,
    *,
    pending_doc_codes: list[str] | None = None,
) -> SdcSolicitation:
    assert_desk_access(user)
    if not _is_letter_ops(user):
        raise HTTPException(status_code=403, detail="Apenas operação LETTER altera o status do SDC")
    status = status.upper().strip()
    if status not in STATUS_LABELS:
        raise HTTPException(status_code=422, detail="Status inválido")
    if status == STATUS_PENDING:
        codes = [str(c).strip().upper() for c in (pending_doc_codes or []) if c]
        if not codes:
            raise HTTPException(
                status_code=422,
                detail="Ao pendenciar, informe quais itens do checklist devem ser reenviados.",
            )
        allowed = {d["code"] for d in _required_docs_for_item(db, item)}
        invalid = [c for c in codes if c not in allowed]
        if invalid:
            raise HTTPException(status_code=422, detail=f"Itens inválidos no checklist: {', '.join(invalid)}")
        _save_pending_codes(item, codes)
    elif status != STATUS_PENDING:
        if status != item.status or not _load_pending_codes(item):
            _save_pending_codes(item, [])
    item.status = status
    if notes is not None:
        item.status_notes = notes
    _append_status_log(
        item,
        user,
        status=status,
        notes=notes,
        pending_doc_codes=_load_pending_codes(item) if status == STATUS_PENDING else [],
    )
    db.flush()
    return item


def update_partner_observation(db: Session, user: User, item: SdcSolicitation, observation: str | None) -> SdcSolicitation:
    assert_desk_access(user)
    if _is_letter_ops(user):
        raise HTTPException(status_code=403, detail="Observação do parceiro é preenchida pelo parceiro.")
    if item.status in STATUS_TERMINAL:
        raise HTTPException(status_code=422, detail="Solicitação encerrada.")
    item.partner_observation = (observation or "").strip() or None
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
    upload_batch: str | None = None,
) -> SdcSolicitationDocument:
    assert_desk_access(user)
    if item.status in STATUS_TERMINAL and not _is_admin(user):
        raise HTTPException(status_code=422, detail="Esta solicitação já está encerrada e não aceita mais documentos.")
    if item.status == STATUS_APPROVED and not _is_admin(user):
        raise HTTPException(status_code=422, detail="SDC aprovado não aceita novos documentos do parceiro.")
    dtype = (doc_type or "SDC_SUPPORT").strip().upper()[:80]
    allowed = _allowed_doc_types(db, item)
    if dtype not in allowed:
        raise HTTPException(status_code=422, detail=f"Tipo de documento inválido para este SDC. Use um item do checklist.")
    batch = (upload_batch or "").strip().upper() or UPLOAD_BATCH_INITIAL
    if item.status == STATUS_PENDING and _load_pending_codes(item):
        if dtype != "SDC_SUPPORT" and dtype not in _load_pending_codes(item):
            raise HTTPException(status_code=422, detail="Anexe somente os documentos indicados na pendência.")
        batch = UPLOAD_BATCH_PENDENCY
    elif item.status != STATUS_AWAITING_DOCS and not _is_admin(user):
        raise HTTPException(status_code=422, detail="Novos anexos do checklist só na fase de documentação ou pendência.")
    if batch not in {UPLOAD_BATCH_INITIAL, UPLOAD_BATCH_PENDENCY}:
        batch = UPLOAD_BATCH_INITIAL
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
        upload_batch=batch,
    )
    db.add(row)
    db.flush()
    return row


def remove_document(db: Session, user: User, item: SdcSolicitation, link_id: str) -> None:
    assert_desk_access(user)
    if not _is_letter_ops(user):
        if item.status in STATUS_TERMINAL:
            raise HTTPException(status_code=403, detail="Solicitação encerrada — não é possível excluir documentos.")
        if item.status not in {STATUS_AWAITING_DOCS, STATUS_PENDING}:
            raise HTTPException(status_code=403, detail="Exclusão de documentos só na fase de envio de documentação.")
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


def _pauta_for_sdc_solicitation(db: Session, item: SdcSolicitation):
    from app.models import PreAnalysisPauta
    from app.pre_analysis_service import get_or_create_pauta

    try:
        meta = json_loads(item.evaluation_json or "{}")
    except (TypeError, ValueError):
        meta = {}
    tapaf_meta = meta.get("tapaf") if isinstance(meta.get("tapaf"), dict) else {}
    proposal_id = tapaf_meta.get("proposal_id") or item.proposal_id
    if not proposal_id:
        return None
    proposal = db.get(Proposal, proposal_id)
    if not proposal:
        return None
    pauta_id = tapaf_meta.get("pauta_id")
    if pauta_id:
        row = db.get(PreAnalysisPauta, pauta_id)
        if row:
            return row
    partner = db.get(User, item.partner_user_id) if item.partner_user_id else None
    if not partner:
        partner = db.scalar(
            select(User).where(
                User.organization_id == item.organization_id,
                User.role == Role.PLATFORM_ADMIN,
            )
        )
    if not partner:
        return None
    return get_or_create_pauta(db, partner, proposal)


def _tapaf_manifest_preview_ui() -> dict:
    from app.pre_analysis_constants import TAPAF_CHECKBOX_01, TAPAF_CHECKBOX_02, TAPAF_MANIFESTO_HTML, TAPAF_TOOLTIP

    return {
        "valor_nominal_taxa": "1500.00",
        "texto_explicativo_tooltip_interrogacao": TAPAF_TOOLTIP,
        "checkbox_obrigatorio_01": TAPAF_CHECKBOX_01,
        "checkbox_obrigatorio_02": TAPAF_CHECKBOX_02,
        "manifesto_html": TAPAF_MANIFESTO_HTML,
        "botao_habilitado": False,
        "checkout_url": None,
    }


def public_client_tapaf_view(db: Session, solicitation_id: str, token: str) -> dict:
    from app.inter_cobranca_helpers import verify_sdc_tapaf_client_token
    from app.pre_analysis_service import generate_tapaf_checkout

    if not verify_sdc_tapaf_client_token(solicitation_id, token):
        raise HTTPException(status_code=403, detail="Link TAPAF inválido ou expirado.")
    item = db.get(SdcSolicitation, solicitation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    pauta = _pauta_for_sdc_solicitation(db, item)
    if not pauta:
        raise HTTPException(status_code=409, detail="TAPAF ainda não disponível para esta solicitação.")
    accepted = pauta.status in {"TAPAF_CHECKOUT_ACCEPTED", "TAPAF_PAID"}
    if accepted:
        checkout = generate_tapaf_checkout(pauta)
        ui = checkout.get("interface_checkout_tapaf") or {}
    else:
        ui = _tapaf_manifest_preview_ui()
    return {
        "contact_name": item.contact_name,
        "solicitation_id": item.id,
        "pauta_status": pauta.status,
        "interface_checkout_tapaf": ui,
        "checkout_accepted": accepted,
        "checkout_paid": pauta.status == "TAPAF_PAID",
    }


def public_client_tapaf_accept(
    db: Session,
    solicitation_id: str,
    token: str,
    *,
    scroll_completed: bool,
    checkbox_1: bool,
    checkbox_2: bool,
) -> dict:
    from app.inter_cobranca_helpers import verify_sdc_tapaf_client_token
    from app.pre_analysis_service import accept_tapaf_checkout, generate_tapaf_checkout

    if not verify_sdc_tapaf_client_token(solicitation_id, token):
        raise HTTPException(status_code=403, detail="Link TAPAF inválido ou expirado.")
    item = db.get(SdcSolicitation, solicitation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    pauta = _pauta_for_sdc_solicitation(db, item)
    if not pauta:
        raise HTTPException(status_code=409, detail="TAPAF indisponível.")
    actor = db.get(User, item.partner_user_id) if item.partner_user_id else None
    if not actor:
        actor = db.scalar(
            select(User).where(
                User.organization_id == item.organization_id,
                User.role == Role.PLATFORM_ADMIN,
            )
        )
    if not actor:
        raise HTTPException(status_code=500, detail="Não foi possível registrar o aceite TAPAF.")
    asset = "VEHICLE" if item.asset_type in TIPOS_VEICULO else "REAL_ESTATE"
    accept_tapaf_checkout(
        db,
        actor,
        pauta,
        scroll_completed=scroll_completed,
        checkbox_1=checkbox_1,
        checkbox_2=checkbox_2,
        asset_type=asset,
    )
    db.flush()
    checkout = generate_tapaf_checkout(pauta)
    return {
        "status": "OK",
        "interface_checkout_tapaf": checkout.get("interface_checkout_tapaf") or {},
        "pauta_status": pauta.status,
    }


def _document_link_view(db: Session, row: SdcSolicitationDocument) -> dict:
    document = db.get(Document, row.document_id)
    return {
        "id": row.id,
        "doc_type": row.doc_type,
        "comment": row.comment,
        "upload_batch": row.upload_batch or UPLOAD_BATCH_INITIAL,
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
    lead = db.get(Lead, lead_id) if lead_id else None
    from app.product_contract_flow_service import emit_sdc_cap_giro_contract_and_zapsign

    zapsign = emit_sdc_cap_giro_contract_and_zapsign(db, user, item, proposal, lead)
    return {
        "proposal_id": proposal.id,
        "lead_id": lead_id,
        "quota_id": quota.id,
        "contract_zapsign": zapsign,
    }


def solicitation_view(
    item: SdcSolicitation,
    docs: list[SdcSolicitationDocument] | None = None,
    db: Session | None = None,
) -> dict:
    doc_rows = docs or []
    pending_codes = _load_pending_codes(item)
    initial_uploaded = _checklist_uploaded_codes(doc_rows, upload_batch=UPLOAD_BATCH_INITIAL)
    pendency_uploaded = _checklist_uploaded_codes(doc_rows, upload_batch=UPLOAD_BATCH_PENDENCY)
    required = _required_docs_for_item(db, item) if db else sdc_required_docs(
        item.asset_type,
        item.person_type,
        operation_type=item.operation_type,
        asset_category=_item_asset_category(item),
    )
    if item.status == STATUS_PENDING and pending_codes:
        uploaded = pendency_uploaded
        required_rows = [d for d in required if d["code"] in pending_codes]
    else:
        uploaded = initial_uploaded
        required_rows = required
    complete = checklist_complete_for(item, doc_rows, db)
    can_submit = False
    if item.status == STATUS_AWAITING_DOCS:
        can_submit = complete
    elif item.status == STATUS_PENDING and pending_codes:
        can_submit = complete
    asset_cat = _item_asset_category(item)
    op = _item_operation_type(item)
    return {
        "id": item.id,
        "status": item.status,
        "status_label": STATUS_LABELS.get(item.status, item.status),
        "status_notes": item.status_notes,
        "status_log": _load_status_log(item),
        "pending_doc_codes": pending_codes,
        "partner_observation": item.partner_observation,
        "asset_category": asset_cat,
        "asset_category_label": ASSET_CATEGORY_LABELS.get(asset_cat, asset_cat),
        "operation_type": op,
        "operation_type_label": OPERATION_TYPE_LABELS.get(op, op),
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
        "required_docs": [{**d, "uploaded": d["code"] in uploaded} for d in required_rows],
        "full_required_docs": [{**d, "uploaded": d["code"] in initial_uploaded} for d in required],
        "docs_checklist_complete": complete,
        "can_submit_documents": can_submit,
        "awaiting_pendency_upload": item.status == STATUS_PENDING and bool(pending_codes),
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
