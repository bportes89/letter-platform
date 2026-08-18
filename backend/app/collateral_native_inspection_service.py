"""Vistoria fotográfica nativa anti-fraude — Lease Equity, SDC e Flash Capital."""

import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CollateralNativeInspection, Contract, LeaseEquityPauta, Proposal, User
from app.storage_service import get_storage


NATIVE_INSPECTION_PRODUCTS = frozenset({"SDC", "FLASH_CREDIT", "LEASE_EQUITY"})
MIN_NATIVE_PHOTOS = 3


def validate_native_photos(photos: list[dict]) -> None:
    if len(photos) < MIN_NATIVE_PHOTOS:
        raise HTTPException(status_code=422, detail=f"Mínimo de {MIN_NATIVE_PHOTOS} fotos nativas com EXIF obrigatório")
    for photo in photos:
        if photo.get("source") == "GALLERY":
            raise HTTPException(status_code=422, detail="Upload da galeria bloqueado — use câmera nativa")
        if not photo.get("exif_timestamp_unix") or photo.get("gps_latitude") is None or photo.get("gps_longitude") is None:
            raise HTTPException(status_code=422, detail="Foto deve conter timestamp Unix e GPS no EXIF")


def inspection_vault_key(product: str, entity_id: str) -> str:
    return f"collateral-inspections/{product.lower()}/{entity_id}/native_vistoria_manifest.json"


def upsert_native_inspection(
    db: Session,
    user: User,
    *,
    product: str,
    proposal_id: str,
    photos: list[dict],
    contract_id: str | None = None,
    lease_equity_pauta_id: str | None = None,
) -> CollateralNativeInspection:
    product = product.upper()
    if product not in NATIVE_INSPECTION_PRODUCTS:
        raise HTTPException(status_code=422, detail="Produto sem vistoria nativa homologada")
    validate_native_photos(photos)
    entity_id = contract_id or lease_equity_pauta_id or proposal_id
    key = inspection_vault_key(product, entity_id)
    vault_uri = f"s3://letter-vault-private/{key}"
    manifest = {
        "product": product,
        "proposal_id": proposal_id,
        "contract_id": contract_id,
        "lease_equity_pauta_id": lease_equity_pauta_id,
        "photos_count": len(photos),
        "photos": photos,
        "purpose": "ONBOARDING_VISTORIA_NATIVA",
        "auction_evidence_note": "Evidência vinculada para leilão em caso de inadimplência",
        "submitted_at": datetime.now(UTC).isoformat(),
    }
    storage = get_storage()
    storage.put(key, json.dumps(manifest, ensure_ascii=False).encode("utf-8"), "application/json")

    item = db.scalar(
        select(CollateralNativeInspection).where(
            CollateralNativeInspection.organization_id == user.organization_id,
            CollateralNativeInspection.proposal_id == proposal_id,
        )
    )
    if item:
        item.photos_count = len(photos)
        item.metadata_json = json.dumps(photos, ensure_ascii=False)
        item.vault_s3_uri = vault_uri
        if contract_id:
            item.contract_id = contract_id
        if lease_equity_pauta_id:
            item.lease_equity_pauta_id = lease_equity_pauta_id
    else:
        item = CollateralNativeInspection(
            organization_id=user.organization_id,
            product=product,
            proposal_id=proposal_id,
            contract_id=contract_id,
            lease_equity_pauta_id=lease_equity_pauta_id,
            photos_count=len(photos),
            metadata_json=json.dumps(photos, ensure_ascii=False),
            vault_s3_uri=vault_uri,
        )
        db.add(item)
    db.flush()
    return item


def register_contract_native_inspection(
    db: Session, user: User, contract: Contract, photos: list[dict],
) -> CollateralNativeInspection:
    proposal = db.get(Proposal, contract.proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    if proposal.product not in {"SDC", "FLASH_CREDIT"}:
        raise HTTPException(
            status_code=422,
            detail="Vistoria nativa obrigatória apenas para SDC e Flash Capital",
        )
    return upsert_native_inspection(
        db, user,
        product=proposal.product,
        proposal_id=proposal.id,
        contract_id=contract.id,
        photos=photos,
    )


def resolve_inspection_for_contract(db: Session, contract_id: str) -> CollateralNativeInspection | None:
    return db.scalar(
        select(CollateralNativeInspection).where(CollateralNativeInspection.contract_id == contract_id)
    )


def resolve_inspection_for_proposal(db: Session, proposal_id: str) -> CollateralNativeInspection | None:
    return db.scalar(
        select(CollateralNativeInspection).where(CollateralNativeInspection.proposal_id == proposal_id)
    )


def resolve_auction_photo_reference(db: Session, proposal_id: str, contract_id: str | None = None) -> str | None:
    if contract_id:
        item = resolve_inspection_for_contract(db, contract_id)
        if item:
            return item.vault_s3_uri
    item = resolve_inspection_for_proposal(db, proposal_id)
    return item.vault_s3_uri if item else None


def inspection_view(item: CollateralNativeInspection) -> dict:
    return {
        "id": item.id,
        "product": item.product,
        "proposal_id": item.proposal_id,
        "contract_id": item.contract_id,
        "lease_equity_pauta_id": item.lease_equity_pauta_id,
        "photos_count": item.photos_count,
        "vault_s3_uri": item.vault_s3_uri,
        "auction_evidence_ready": item.auction_evidence_ready,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def link_inspection_to_contract(db: Session, proposal_id: str, contract_id: str) -> None:
    item = resolve_inspection_for_proposal(db, proposal_id)
    if item and not item.contract_id:
        item.contract_id = contract_id
        db.flush()
