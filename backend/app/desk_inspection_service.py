"""Persistência de autovistoria (SDC / Flash)."""

from __future__ import annotations

from fastapi import HTTPException, UploadFile

from app.desk_property_inspection import attach_photo_ref, merge_inspection_payload
from app.desk_workflow_helpers import inspections_from_item, save_inspections_on_item
from app.document_service import persist_upload


def patch_property_inspection(db, user, item, payload: dict) -> list:
    from app.sdc_desk_service import assert_desk_access as sdc_access
    from app.flash_desk_service import assert_desk_access as flash_access

    try:
        sdc_access(user)
    except HTTPException:
        flash_access(user)
    if getattr(item, "status", "") in {"APPROVED", "REJECTED", "CANCELLED"}:
        raise HTTPException(status_code=422, detail="Solicitação encerrada.")
    rows = merge_inspection_payload(inspections_from_item(item), payload)
    save_inspections_on_item(item, rows)
    db.flush()
    return rows


async def upload_property_inspection_photo(
    db,
    user,
    item,
    *,
    upload: UploadFile,
    matricula: str,
    photo_key: str,
    camera_native: bool,
    storage_scope: str,
) -> list:
    from app.sdc_desk_service import assert_desk_access as sdc_access
    from app.flash_desk_service import assert_desk_access as flash_access

    try:
        sdc_access(user)
    except HTTPException:
        flash_access(user)
    if getattr(item, "status", "") not in {"AWAITING_DOCS", "PENDING"}:
        raise HTTPException(status_code=422, detail="Fotos de autovistoria só na fase de documentação.")
    if not camera_native:
        raise HTTPException(status_code=422, detail="Use a câmera do dispositivo — não é permitido enviar da galeria.")
    document = await persist_upload(upload, user, storage_scope, item.id, f"INSPECTION_{photo_key[:40]}")
    ref = {"document_id": document.id, "filename": document.filename, "capture": "CAMERA_NATIVE"}
    try:
        rows = attach_photo_ref(
            inspections_from_item(item),
            matricula,
            photo_key,
            ref,
            camera_native=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    save_inspections_on_item(item, rows)
    db.flush()
    return rows
