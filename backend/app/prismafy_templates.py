"""Prismafy (Valid-Stamp consultas) — template_ids da doc LETTER (integracao-letter.html)."""

from __future__ import annotations

# Base: https://api.prismafy.com.br/api/v1/executions/<template_id>/run/
PRISMAFY_API_BASE_DEFAULT = "https://api.prismafy.com.br"

# slug HTML (t-*) → template_id UUID
TEMPLATE_BY_SLUG: dict[str, str] = {
    "t-acoes-e-processos-judiciais-pf": "01a03a03-e674-7001-b67c-80b78f2056a5",
    "t-cnd-federais": "01a049ab-7d07-73b3-a666-d282ae23398f",
    "t-cndt": "01a049ab-3e74-73a0-b8a8-05d779d462bc",
    "t-cpr-cpf-cnpj": "019f66e2-2f86-7893-afa8-b343b55153be",
    "t-fgts": "01a049ab-5762-7753-aea5-fdb88f26d098",
    "t-fipe": "01a0acde-64f5-74f1-94de-6c99e3ae5db8",
    "t-gravame": "01a0ac01-8788-7fc2-8f4c-601515359e15",
    "t-historico-de-proprietarios": "01a0ac82-e7b3-7723-8668-e8680b344d17",
    "t-pefin-mercado-financeiro": "01a04446-028b-7d51-912e-e6e240ba85de",
    "t-pgfn": "01a049c3-c686-7141-8e64-9ca2cffbcc2f",
    "t-renajud": "01a0ab8b-e7b0-7962-9ce2-a3a55a4db4d3",
    "t-roubo-e-furto": "01a0ac57-b039-7af1-a2b3-96a65f585771",
    "t-tjsp": "01a049c4-15eb-7610-8c98-4ffc13acb11b",
}

# Atalhos usados na esteira LETTER
TEMPLATE_ALIASES: dict[str, str] = {
    "gravame": TEMPLATE_BY_SLUG["t-gravame"],
    "renajud": TEMPLATE_BY_SLUG["t-renajud"],
    "fgts": TEMPLATE_BY_SLUG["t-fgts"],
    "cnd-federais": TEMPLATE_BY_SLUG["t-cnd-federais"],
    "cndt": TEMPLATE_BY_SLUG["t-cndt"],
    "pgfn": TEMPLATE_BY_SLUG["t-pgfn"],
    "pefin": TEMPLATE_BY_SLUG["t-pefin-mercado-financeiro"],
    "cpr": TEMPLATE_BY_SLUG["t-cpr-cpf-cnpj"],
    "fipe": TEMPLATE_BY_SLUG["t-fipe"],
    "roubo-furto": TEMPLATE_BY_SLUG["t-roubo-e-furto"],
    "historico-proprietarios": TEMPLATE_BY_SLUG["t-historico-de-proprietarios"],
    "acoes-judiciais-pf": TEMPLATE_BY_SLUG["t-acoes-e-processos-judiciais-pf"],
    "tjsp": TEMPLATE_BY_SLUG["t-tjsp"],
}
