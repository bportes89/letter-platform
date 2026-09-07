"""Contratos pós-BANK: aceite obrigatório por perfil antes do escritório."""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.company_profile_service import company_profile
from app.flash_valid_lss_service import issue_stamp
from app.legal_manuals_service import MANUALS_ROOT, get_manual
from app.models import PartnerContractAcceptance, Role, User, UserContractAcceptance
from app.partner_contract_service import (
    build_partner_context,
    canonical_hash,
    contract_excerpt,
    fill_partner_contract_docx,
)
from app.storage_service import get_storage

CONTRACT_VERSIONS = {
    "parceiros": "LETTER_PARTNER_AGREEMENT_2026_V51.0_UNIVERSAL",
    "master-franqueado": "LETTER_MASTER_FRANCHISEE_2026_V1",
    "carta-contemplada-cliente": "LETTER_CLIENT_CARTA_2026_V1",
}

CONTRACT_TITLES = {
    "parceiros": "Contrato de Parceiro Comercial",
    "master-franqueado": "Contrato Master Franqueado",
    "carta-contemplada-cliente": "Contrato de Cliente — Carta Contemplada",
}

ROLE_CONTRACT_SLUG: dict[Role, str] = {
    Role.PARTNER: "parceiros",
    Role.QUOTA_SELLER: "parceiros",
    Role.MANAGER: "parceiros",
    Role.MASTER_FRANCHISEE: "master-franqueado",
    Role.CLIENT: "carta-contemplada-cliente",
}

CONTRACT_OPTIONAL_ROLES = frozenset({
    Role.PLATFORM_ADMIN,
    Role.INTERNAL_STAFF,
    Role.AUDITOR,
    Role.RETAIL_INVESTOR,
    Role.INSTITUTIONAL_FUND,
})

PJ_REQUIRED_SLUGS = frozenset({"parceiros", "master-franqueado"})


@dataclass
class _InviteStub:
    id: str
    organization_id: str
    email: str
    role: Role


def _clean_doc(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _template_path(slug: str) -> Path:
    item = get_manual(slug)
    path = MANUALS_ROOT / item["filename"]
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Template de contrato indisponível no servidor.")
    return path


def _fill_contract_docx(slug: str, context: dict[str, str]) -> bytes:
    if slug == "parceiros":
        return fill_partner_contract_docx(context)
    source = _template_path(slug)
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


def _store_contract(content: bytes, organization_id: str, user_id: str, slug: str) -> tuple[str, str]:
    digest = hashlib.sha256(content).hexdigest()
    relative = Path(organization_id) / "user-contracts" / datetime.now(UTC).strftime("%Y/%m") / f"{user_id}-{slug}-{uuid4().hex}.docx"
    get_storage().put(str(relative), content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    return str(relative), digest


def accepted_template_slugs(db: Session, user: User) -> set[str]:
    slugs = set(
        db.scalars(
            select(PartnerContractAcceptance.template_slug).where(PartnerContractAcceptance.user_id == user.id)
        )
    )
    slugs.update(
        db.scalars(
            select(UserContractAcceptance.template_slug).where(UserContractAcceptance.user_id == user.id)
        )
    )
    return {slug for slug in slugs if slug}


def required_contract_slug(user: User) -> str | None:
    if user.role in CONTRACT_OPTIONAL_ROLES:
        return None
    return ROLE_CONTRACT_SLUG.get(user.role)


def user_contract_completed(db: Session, user: User) -> bool:
    slug = required_contract_slug(user)
    if not slug:
        return True
    return slug in accepted_template_slugs(db, user)


def contract_status_view(db: Session, user: User) -> dict:
    slug = required_contract_slug(user)
    if not slug:
        return {
            "required": False,
            "completed": True,
            "template_slug": None,
            "template_title": None,
            "template_version": None,
            "contract_excerpt": None,
            "requires_pj_fields": False,
        }
    completed = slug in accepted_template_slugs(db, user)
    return {
        "required": True,
        "completed": completed,
        "template_slug": slug,
        "template_title": CONTRACT_TITLES.get(slug, slug),
        "template_version": CONTRACT_VERSIONS.get(slug, "1.0"),
        "contract_excerpt": contract_excerpt() if slug == "parceiros" else _generic_excerpt(slug),
        "requires_pj_fields": slug in PJ_REQUIRED_SLUGS,
    }


def _generic_excerpt(slug: str, max_chars: int = 4200) -> str:
    with zipfile.ZipFile(_template_path(slug)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    text = re.sub(r"<[^>]+>", " ", xml)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _invite_stub(user: User) -> _InviteStub:
    return _InviteStub(
        id=user.id,
        organization_id=user.organization_id,
        email=user.email,
        role=user.role,
    )


def _build_context(
    user: User,
    slug: str,
    *,
    evidence_hash: str,
    accepted_at: datetime,
    company_name: str,
    company_cnpj: str,
    company_address: str,
    company_city: str,
    company_state: str,
    representative_name: str,
    representative_document: str,
) -> dict[str, str]:
    profile = company_profile()
    signed_at = accepted_at.astimezone(UTC)
    holding_address = profile["footer_line"]
    if slug == "parceiros":
        invite = _InviteStub(
            id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            role=user.role,
        )
        return build_partner_context(
            invite=invite,  # type: ignore[arg-type]
            representative_name=representative_name,
            representative_document=representative_document,
            company_name=company_name,
            company_cnpj=company_cnpj,
            company_address=company_address,
            company_city=company_city,
            company_state=company_state,
            evidence_hash=evidence_hash,
            accepted_at=accepted_at,
        )
    partner_address = " — ".join(part for part in (company_address.strip(), company_city.strip(), company_state.strip()) if part)
    return {
        "CNPJ_da_Holding": profile["cnpj"],
        "Endereço _Completo": holding_address,
        "Endereço": partner_address or holding_address,
        "Razão Social da Empresa PJ do Parceiro": company_name.strip() or user.name,
        "Razão Social do Parceiro": company_name.strip() or user.name,
        "Nome do Cliente": user.name,
        "CPF do Cliente": representative_document.strip() or (user.document or ""),
        "E-mail do Cliente": user.email,
        "E-mail do Parceiro": user.email,
        "Telefone": (user.phone or "").strip(),
        "Data_de_Assinatura_D+0": signed_at.strftime("%d/%m/%Y"),
        "Horario_Servidor_Unix": str(int(signed_at.timestamp())),
        "Assinatura Digital via Logs SHA-256": evidence_hash,
        "Representante Legal": representative_name.strip() or user.name,
        "CPF Representante": representative_document.strip() or (user.document or ""),
        "Perfil Comercial": user.role.value if hasattr(user.role, "value") else str(user.role),
    }


def validate_accept_payload(
    user: User,
    slug: str,
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
    if slug in PJ_REQUIRED_SLUGS:
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
            raise HTTPException(status_code=422, detail="CNPJ inválido")
    if slug == "carta-contemplada-cliente":
        if not (user.document or "").strip():
            raise HTTPException(status_code=422, detail="CPF obrigatório no cadastro para assinar o contrato.")
        if len(_clean_doc(phone or user.phone or "")) < 10:
            raise HTTPException(status_code=422, detail="Telefone celular obrigatório.")
    phone_digits = _clean_doc(phone or "")
    if slug in PJ_REQUIRED_SLUGS and len(phone_digits) < 10:
        raise HTTPException(status_code=422, detail="Telefone celular inválido")
    if not all([terms_accepted, scroll_completed, (verification_reference or "").strip()]):
        raise HTTPException(status_code=422, detail="Leitura do contrato, aceite expresso e referência de verificação são obrigatórios.")


def record_user_contract_acceptance(
    db: Session,
    user: User,
    *,
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
) -> UserContractAcceptance:
    slug = required_contract_slug(user)
    if not slug:
        raise HTTPException(status_code=422, detail="Perfil não exige contrato na plataforma.")
    if slug in accepted_template_slugs(db, user):
        existing = db.scalar(
            select(UserContractAcceptance).where(
                UserContractAcceptance.user_id == user.id,
                UserContractAcceptance.template_slug == slug,
            )
        )
        if existing:
            return existing

    now = datetime.now(UTC)
    evidence = {
        "template_slug": slug,
        "template_version": CONTRACT_VERSIONS.get(slug, "1.0"),
        "user_id": user.id,
        "email": user.email,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "company_name": company_name.strip(),
        "company_cnpj_masked": company_cnpj.strip(),
        "representative_name": representative_name.strip(),
        "representative_document_masked": (representative_document or "")[:3] + "***",
        "verification_reference": verification_reference,
        "scroll_completed": True,
        "terms_accepted": True,
        "accepted_at": now.isoformat(),
        "ip_address": ip_address,
        "user_agent": user_agent,
        "source": "POST_BANK_ONBOARDING",
    }
    evidence_hash = canonical_hash(evidence)
    context = _build_context(
        user,
        slug,
        evidence_hash=evidence_hash,
        accepted_at=now,
        company_name=company_name or user.name,
        company_cnpj=company_cnpj or "",
        company_address=company_address or "",
        company_city=company_city or "",
        company_state=company_state or "",
        representative_name=representative_name or user.name,
        representative_document=representative_document or user.document or "",
    )
    document = _fill_contract_docx(slug, context)
    storage_key, document_sha256 = _store_contract(document, user.organization_id, user.id, slug)
    evidence["document_sha256"] = document_sha256
    evidence["storage_key"] = storage_key
    item = UserContractAcceptance(
        organization_id=user.organization_id,
        user_id=user.id,
        template_slug=slug,
        template_version=CONTRACT_VERSIONS.get(slug, "1.0"),
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
        entity_type="user_contract_acceptance",
        entity_id=item.id,
        purpose="PLATFORM_CONTRACT_ACCEPTANCE",
        payload=evidence,
    )
    return item


def preview_contract_bytes(db: Session, user: User) -> tuple[bytes, str]:
    slug = required_contract_slug(user)
    if not slug:
        raise HTTPException(status_code=422, detail="Perfil não exige contrato.")
    now = datetime.now(UTC)
    placeholder_hash = canonical_hash({"preview": True, "user_id": user.id, "at": now.isoformat()})
    context = _build_context(
        user,
        slug,
        evidence_hash=placeholder_hash,
        accepted_at=now,
        company_name=user.company_name or user.name,
        company_cnpj=user.company_cnpj or "00000000000000",
        company_address=user.company_address or "[Endereço]",
        company_city=user.company_city or "[Cidade]",
        company_state=user.company_state or "[UF]",
        representative_name=user.name,
        representative_document=user.document or "[CPF]",
    )
    filename = f"contrato-{slug}-preview.docx"
    return _fill_contract_docx(slug, context), filename
