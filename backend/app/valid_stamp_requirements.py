from fastapi import HTTPException

from app.vehicle_registry_service import assert_vehicle_cleared_for_stamp

# Entregáveis obrigatórios do Valid-Stamp para Flash Capital (ex-Flash Credit).
FLASH_CAPITAL_VALID_STAMP_REQUIREMENTS: dict[str, list[str]] = {
    "REAL_ESTATE": [
        "MATRICULA_ENOTARIADO",
        "LAUDO_AVALIACAO",
        "SERASA",
        "BACEN",
    ],
    "VEHICLE": [
        "FIPE_MOLICAR",
        "LAUDO_AVALIACAO",
        "SERASA",
        "BACEN",
        "CRLV",
    ],
}

SDC_VEHICLE_VALID_STAMP_REQUIREMENTS: list[str] = [
    "CRLV",
    "FIPE_MOLICAR",
    "LAUDO_AVALIACAO",
    "SERASA",
    "BACEN",
]

FLASH_CAPITAL_STAMP_PURPOSES = {
    "FLASH_CREDIT_PARTIES",
    "FLASH_CAPITAL_PARTIES",
}

SDC_VEHICLE_STAMP_PURPOSES = {
    "SDC_VEHICLE_COLLATERAL",
}

VEHICLE_STAMP_PURPOSES = FLASH_CAPITAL_STAMP_PURPOSES | SDC_VEHICLE_STAMP_PURPOSES


def valid_stamp_requirements(asset_type: str, product: str = "FLASH_CAPITAL") -> dict:
    product_norm = product.upper()
    if product_norm == "SDC" and asset_type == "VEHICLE":
        required = SDC_VEHICLE_VALID_STAMP_REQUIREMENTS
        product_label = "SDC"
    elif asset_type in FLASH_CAPITAL_VALID_STAMP_REQUIREMENTS:
        required = FLASH_CAPITAL_VALID_STAMP_REQUIREMENTS[asset_type]
        product_label = "FLASH_CAPITAL"
    else:
        raise HTTPException(status_code=422, detail="asset_type deve ser REAL_ESTATE ou VEHICLE")
    labels = {
        "MATRICULA_ENOTARIADO": "Matrícula atualizada emitida no e-notariado",
        "LAUDO_AVALIACAO": "Laudo de avaliação",
        "FIPE_MOLICAR": "Tabela FIPE ou Molicar (quando não houver FIPE)",
        "CRLV": "CRLV (referência; consulta DETRAN prevalece)",
        "SERASA": "Consulta Serasa",
        "BACEN": "Consulta Bacen",
    }
    vehicle_classes = None
    if asset_type == "VEHICLE":
        vehicle_classes = [
            {"code": "LIGHT", "label": "Leve"},
            {"code": "HEAVY", "label": "Pesado"},
            {"code": "MACHINE", "label": "Máquina"},
        ]
    return {
        "asset_type": asset_type,
        "product": product_label,
        "required_documents": [
            {"code": code, "label": labels[code], "required": True}
            for code in required
        ],
        "vehicle_classes": vehicle_classes,
        "vehicle_registry_required": asset_type == "VEHICLE",
        "tapaf_required_for_vehicle": asset_type == "VEHICLE",
        "tapaf_required": True,
    }


def validate_flash_capital_stamp_payload(payload: dict) -> None:
    asset_type = payload.get("asset_type")
    if asset_type not in FLASH_CAPITAL_VALID_STAMP_REQUIREMENTS:
        raise HTTPException(
            status_code=422,
            detail="Valid-Stamp Flash Capital exige asset_type REAL_ESTATE ou VEHICLE",
        )
    documents = payload.get("documents")
    if not isinstance(documents, dict):
        raise HTTPException(
            status_code=422,
            detail="Valid-Stamp Flash Capital exige mapa documents com hash de cada lastro",
        )
    missing = [
        code
        for code in FLASH_CAPITAL_VALID_STAMP_REQUIREMENTS[asset_type]
        if not str(documents.get(code, "")).strip()
    ]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Documentos obrigatórios ausentes no Valid-Stamp: {', '.join(missing)}",
        )
    if asset_type == "VEHICLE":
        registry = assert_vehicle_cleared_for_stamp(payload, require_tapaf=True)
        payload["vehicle_registry_snapshot"] = registry


def validate_sdc_vehicle_stamp_payload(payload: dict) -> None:
    if payload.get("asset_type") != "VEHICLE":
        raise HTTPException(status_code=422, detail="Valid-Stamp SDC veículo exige asset_type VEHICLE")
    documents = payload.get("documents")
    if not isinstance(documents, dict):
        raise HTTPException(status_code=422, detail="Valid-Stamp SDC veículo exige mapa documents")
    missing = [
        code for code in SDC_VEHICLE_VALID_STAMP_REQUIREMENTS
        if not str(documents.get(code, "")).strip()
    ]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Documentos obrigatórios ausentes no Valid-Stamp SDC veículo: {', '.join(missing)}",
        )
    registry = assert_vehicle_cleared_for_stamp(payload, require_tapaf=True)
    payload["vehicle_registry_snapshot"] = registry
