"""Contrato de parceiro: preenchimento automático e aceite no onboarding."""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.company_profile_service import company_profile
from app.flash_valid_lss_service import issue_stamp
from app.identity_service import as_utc, token_hash
from app.legal_manuals_service import MANUALS_ROOT, get_manual
from app.models import PartnerContractAcceptance, User, UserInvitation
from app.network_service import PARTNER_NETWORK_ROLES
from app.storage_service import get_storage

TEMPLATE_SLUG = "parceiros"
TEMPLATE_VERSION = "LETTER_PARTNER_AGREEMENT_2026_V51.0_UNIVERSAL"
TEMPLATE_FILENAME = "parceiros.docx"


def canonical_hash(value: dict | str) -> str:
    raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _clean_doc(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _format_cnpj(value: str) -> str:
    digits = _clean_doc(value)
    if len(digits) != 14:
        return value.strip()
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def _template_path() -> Path:
    item = get_manual(TEMPLATE_SLUG)
    path = MANUALS_ROOT / item["filename"]
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Template de contrato de parceiro indisponível no servidor.")
    return path


def contract_excerpt(max_chars: int = 4200) -> str:
    with zipfile.ZipFile(_template_path()) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    text = re.sub(r"<[^>]+>", " ", xml)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def build_partner_context(
    *,
    invite: UserInvitation,
    representative_name: str,
    representative_document: str,
    company_name: str,
    company_cnpj: str,
    company_address: str,
    company_city: str,
    company_state: str,
    evidence_hash: str,
    accepted_at: datetime,
) -> dict[str, str]:
    profile = company_profile()
    holding_address = " — ".join(
        part for part in (profile["address_line"], profile["district"], profile["city_state"], f"CEP {profile['postal_code']}" if profile["postal_code"] else "") if part
    )
    partner_address = " — ".join(part for part in (company_address.strip(), company_city.strip(), company_state.strip()) if part)
    signed_at = accepted_at.astimezone(UTC)
    return {
        "CNPJ_da_Holding": profile["cnpj"],
        "Endereço _Completo": holding_address,
        "Endereço": partner_address,
        "Razão Social da Empresa PJ do Parceiro": company_name.strip(),
        "Razão Social do Parceiro": company_name.strip(),
        "CNPJ_do_Parceiro": _format_cnpj(company_cnpj),
        "Cidade_do_Parceiro": company_city.strip(),
        "UF": company_state.strip().upper()[:2],
        "Data_de_Assinatura_D+0": signed_at.strftime("%d/%m/%Y"),
        "Horario_Servidor_Unix": str(int(signed_at.timestamp())),
        "Assinatura Digital via Logs SHA-256": evidence_hash,
        "Representante Legal": representative_name.strip(),
        "CPF Representante": representative_document.strip(),
        "E-mail do Parceiro": invite.email,
        "Perfil Comercial": invite.role.value if hasattr(invite.role, "value") else str(invite.role),
    }


def fill_partner_contract_docx(context: dict[str, str]) -> bytes:
    source = _template_path()
    buffer = io.BytesIO()
    with zipfile.ZipFile(source, "r") as reader, zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as writer:
        for item in reader.infolist():
            data = reader.read(item.filename)
            if item.filename == "word/document.xml":
                xml = data.decode("utf-8")
                for token, value in context.items():
                    safe = _xml_escape(value)
                    xml = xml.replace(f"[{token}]", safe)
                    xml = xml.replace(token, safe)
                data = xml.encode("utf-8")
            writer.writestr(item, data)
    return buffer.getvalue()


def store_partner_contract(content: bytes, organization_id: str, invitation_id: str) -> tuple[str, str]:
    digest = hashlib.sha256(content).hexdigest()
    relative = Path(organization_id) / "partner-contracts" / datetime.now(UTC).strftime("%Y/%m") / f"{invitation_id}-{uuid4().hex}.docx"
    get_storage().put(str(relative), content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    return str(relative), digest


def get_pending_invitation(db: Session, raw_token: str) -> UserInvitation:
    invite = db.scalar(select(UserInvitation).where(UserInvitation.token_hash == token_hash(raw_token), UserInvitation.status == "PENDING"))
    if not invite or as_utc(invite.expires_at) <= datetime.now(UTC):
        raise HTTPException(status_code=422, detail="Convite inválido ou expirado")
    return invite


def preview_invitation(db: Session, raw_token: str) -> dict:
    invite = get_pending_invitation(db, raw_token)
    inviter = db.get(User, invite.invited_by_id)
    profile = company_profile()
    return {
        "email": invite.email,
        "role": invite.role,
        "expires_at": invite.expires_at,
        "contract_required": bool(invite.partner_contract_required),
        "contract_title": "Contrato de Parceiro Comercial",
        "contract_version": TEMPLATE_VERSION,
        "contract_excerpt": contract_excerpt(),
        "inviter_name": inviter.name if inviter else None,
        "company_legal_name": profile["legal_name"],
        "company_cnpj": profile["cnpj"],
    }


def preview_contract_bytes(db: Session, raw_token: str) -> bytes:
    invite = get_pending_invitation(db, raw_token)
    profile = company_profile()
    now = datetime.now(UTC)
    placeholder_hash = canonical_hash({"preview": True, "invitation_id": invite.id, "at": now.isoformat()})
    context = build_partner_context(
        invite=invite,
        representative_name="[Representante Legal]",
        representative_document="[CPF]",
        company_name="[Razão Social do Parceiro]",
        company_cnpj="00000000000000",
        company_address="[Endereço]",
        company_city="[Cidade]",
        company_state="[UF]",
        evidence_hash=placeholder_hash,
        accepted_at=now,
    )
    context["CNPJ_da_Holding"] = profile["cnpj"]
    context["Endereço _Completo"] = profile["footer_line"]
    return fill_partner_contract_docx(context)


def record_partner_contract_acceptance(
    db: Session,
    *,
    invite: UserInvitation,
    user: User,
    company_name: str,
    company_cnpj: str,
    company_address: str,
    company_city: str,
    company_state: str,
    representative_name: str,
    representative_document: str,
    verification_reference: str,
    ip_address: str | None,
    user_agent: str | None,
) -> PartnerContractAcceptance:
    now = datetime.now(UTC)
    evidence = {
        "template_slug": TEMPLATE_SLUG,
        "template_version": TEMPLATE_VERSION,
        "invitation_id": invite.id,
        "email": invite.email,
        "role": invite.role.value if hasattr(invite.role, "value") else str(invite.role),
        "company_name": company_name.strip(),
        "company_cnpj_masked": _format_cnpj(company_cnpj),
        "representative_name": representative_name.strip(),
        "representative_document_masked": representative_document.strip()[:3] + "***",
        "verification_reference": verification_reference,
        "scroll_completed": True,
        "terms_accepted": True,
        "accepted_at": now.isoformat(),
        "ip_address": ip_address,
        "user_agent": user_agent,
    }
    evidence_hash = canonical_hash(evidence)
    context = build_partner_context(
        invite=invite,
        representative_name=representative_name,
        representative_document=representative_document,
        company_name=company_name,
        company_cnpj=company_cnpj,
        company_address=company_address,
        company_city=company_city,
        company_state=company_state,
        evidence_hash=evidence_hash,
        accepted_at=now,
    )
    document = fill_partner_contract_docx(context)
    storage_key, document_sha256 = store_partner_contract(document, invite.organization_id, invite.id)
    evidence["document_sha256"] = document_sha256
    evidence["storage_key"] = storage_key
    item = PartnerContractAcceptance(
        organization_id=invite.organization_id,
        invitation_id=invite.id,
        user_id=user.id,
        template_slug=TEMPLATE_SLUG,
        template_version=TEMPLATE_VERSION,
        storage_key=storage_key,
        document_sha256=document_sha256,
        evidence_json=json.dumps(evidence, ensure_ascii=False, sort_keys=True),
        evidence_hash=evidence_hash,
        ip_address=ip_address,
        user_agent=user_agent,
        accepted_at=now,
    )
    db.add(item)
    db.flush()
    issue_stamp(
        db,
        user,
        entity_type="partner_contract_acceptance",
        entity_id=item.id,
        purpose="PARTNER_CONTRACT_ACCEPTANCE",
        payload=evidence,
    )
    return item


def validate_partner_contract_payload(
    invite: UserInvitation,
    *,
    company_name: str | None,
    company_cnpj: str | None,
    company_address: str | None,
    company_city: str | None,
    company_state: str | None,
    phone: str | None,
    terms_accepted: bool,
    scroll_completed: bool,
    verification_reference: str | None,
) -> None:
    if not invite.partner_contract_required:
        return
    if invite.role not in PARTNER_NETWORK_ROLES:
        raise HTTPException(status_code=422, detail="Convite não exige contrato de parceiro")
    missing = [
        label
        for label, value in (
            ("Razão social", company_name),
            ("CNPJ", company_cnpj),
            ("Endereço", company_address),
            ("Cidade", company_city),
            ("UF", company_state),
            ("Telefone celular", phone),
        )
        if not (value or "").strip()
    ]
    if missing:
        raise HTTPException(status_code=422, detail=f"Campos obrigatórios do contrato: {', '.join(missing)}")
    if len(_clean_doc(company_cnpj or "")) != 14:
        raise HTTPException(status_code=422, detail="CNPJ do parceiro inválido")
    phone_digits = _clean_doc(phone or "")
    if len(phone_digits) < 10:
        raise HTTPException(status_code=422, detail="Telefone celular inválido")
    if not all([terms_accepted, scroll_completed, (verification_reference or "").strip()]):
        raise HTTPException(status_code=422, detail="Leitura do contrato, aceite expresso e referência de verificação são obrigatórios")


def get_user_partner_contract(db: Session, user: User) -> PartnerContractAcceptance | None:
    return db.scalar(select(PartnerContractAcceptance).where(PartnerContractAcceptance.user_id == user.id))


def read_user_partner_contract_bytes(db: Session, user: User) -> tuple[bytes, str]:
    item = get_user_partner_contract(db, user)
    if not item:
        raise HTTPException(status_code=404, detail="Contrato de parceiro não encontrado para este usuário.")
    content = get_storage().get(item.storage_key)
    filename = f"contrato-parceiro-{item.template_slug}.docx"
    return content, filename
