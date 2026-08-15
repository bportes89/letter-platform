from fastapi import HTTPException

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
    ],
}

FLASH_CAPITAL_STAMP_PURPOSES = {
    "FLASH_CREDIT_PARTIES",
    "FLASH_CAPITAL_PARTIES",
}


def valid_stamp_requirements(asset_type: str) -> dict:
    if asset_type not in FLASH_CAPITAL_VALID_STAMP_REQUIREMENTS:
        raise HTTPException(status_code=422, detail="asset_type deve ser REAL_ESTATE ou VEHICLE")
    required = FLASH_CAPITAL_VALID_STAMP_REQUIREMENTS[asset_type]
    labels = {
        "MATRICULA_ENOTARIADO": "Matrícula atualizada emitida no e-notariado",
        "LAUDO_AVALIACAO": "Laudo de avaliação",
        "FIPE_MOLICAR": "Tabela FIPE ou Molicar (quando não houver FIPE)",
        "SERASA": "Consulta Serasa",
        "BACEN": "Consulta Bacen",
    }
    return {
        "asset_type": asset_type,
        "product": "FLASH_CAPITAL",
        "required_documents": [
            {"code": code, "label": labels[code], "required": True}
            for code in required
        ],
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
