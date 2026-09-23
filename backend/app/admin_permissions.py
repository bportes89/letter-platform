"""Catálogo de permissões administrativas granulares (modelo plataforma legada → LETTER)."""

from __future__ import annotations

import json
from typing import TypedDict

from app.models import Role, User

ALL_MODULES = "*"


class PermissionDef(TypedDict):
    key: str
    label: str
    modules: list[str]
    scopes: list[str]


class PermissionGroupDef(TypedDict):
    group: str
    items: list[PermissionDef]


# Mapeamento baseado na lista enviada pelo cliente (prints), adaptada aos módulos LETTER.
PERMISSION_GROUPS: list[PermissionGroupDef] = [
    {
        "group": "Administração",
        "items": [
            {"key": "admin.users", "label": "Administradores", "modules": ["identity", "rbac"], "scopes": ["admin:users"]},
            {"key": "admin.administradoras", "label": "Administradoras", "modules": ["administrators"], "scopes": ["admin:users"]},
            {"key": "admin.operations", "label": "Operações e observabilidade", "modules": ["operations"], "scopes": ["operations:write"]},
            {"key": "admin.backoffice", "label": "Backoffice / configurações", "modules": ["admin"], "scopes": ["admin:users"]},
        ],
    },
    {
        "group": "Cadastros e Marketplace",
        "items": [
            {"key": "cadastro.novos", "label": "Cadastro (Novos)", "modules": ["cadastros"], "scopes": ["leads:read"]},
            {"key": "cadastro.negociacao", "label": "Cadastro (Em negociação)", "modules": ["cadastros"], "scopes": ["leads:read"]},
            {"key": "cadastro.incompleto", "label": "Cadastro (Incompleto)", "modules": ["cadastros"], "scopes": ["leads:read"]},
            {"key": "cadastro.concluido", "label": "Cadastro (Concluído)", "modules": ["cadastros"], "scopes": ["leads:read"]},
            {"key": "cadastro.cancelados", "label": "Cadastro (Cancelados)", "modules": ["cadastros"], "scopes": ["leads:read"]},
            {"key": "cadastro.compras", "label": "Compras", "modules": ["cadastros"], "scopes": ["leads:read"]},
            {"key": "marketplace.venda_direta", "label": "Venda Direta", "modules": ["venda-direta-manual"], "scopes": ["leads:write", "proposals:write"]},
            {"key": "marketplace.venda_direta_robo", "label": "Venda Direta (Robô)", "modules": ["venda-direta-robo"], "scopes": ["leads:write", "proposals:write"]},
            {"key": "marketplace.fornecedores", "label": "Fornecedores", "modules": ["fornecedores"], "scopes": ["inventory:write"]},
            {"key": "marketplace.inventario", "label": "Inventário de cotas", "modules": ["inventory"], "scopes": ["inventory:write"]},
            {"key": "marketplace.vender_cota", "label": "Vender minha cota / compliance", "modules": ["vender-cota"], "scopes": ["inventory:write"]},
        ],
    },
    {
        "group": "Rede e parceiros",
        "items": [
            {"key": "rede.parceiro_franqueado", "label": "Parceiro / Franqueado", "modules": ["mmn", "crm"], "scopes": ["network:read", "network:invite"]},
            {"key": "rede.vendedores", "label": "Vendedores", "modules": ["mmn", "crm"], "scopes": ["network:read"]},
            {"key": "rede.regional", "label": "Regional", "modules": ["mmn", "crm"], "scopes": ["network:read"]},
            {"key": "rede.supervisores", "label": "Supervisores", "modules": ["mmn", "crm"], "scopes": ["network:read"]},
            {"key": "rede.gestores", "label": "Gestores", "modules": ["mmn", "crm"], "scopes": ["network:read"]},
            {"key": "rede.qualificacao", "label": "Qualificação de parceiros", "modules": ["identity", "mmn"], "scopes": ["admin:users", "network:read"]},
        ],
    },
    {
        "group": "Produtos e mesas",
        "items": [
            {"key": "produto.propostas", "label": "Propostas e simulações", "modules": ["proposals"], "scopes": ["proposals:read", "proposals:write"]},
            {"key": "produto.sdc", "label": "SDC — Solicitação de crédito", "modules": ["sdc"], "scopes": ["proposals:write"]},
            {"key": "produto.flash_capital", "label": "Flash Capital", "modules": ["flash-capital"], "scopes": ["proposals:write"]},
            {"key": "produto.quitcon", "label": "QuitCon", "modules": ["quitcon"], "scopes": ["proposals:write"]},
            {"key": "produto.lease_equity", "label": "Lease Equity", "modules": ["lease-equity"], "scopes": ["proposals:write"]},
            {"key": "produto.leilao", "label": "Leilão", "modules": ["leilao"], "scopes": ["investments:read"]},
            {"key": "produto.lss", "label": "SaaS LSS", "modules": ["lss"], "scopes": ["proposals:read"]},
            {"key": "produto.nina", "label": "NINA Engine", "modules": ["nina"], "scopes": ["payments:review"]},
            {"key": "produto.structured", "label": "Imóveis estruturados", "modules": ["structured-properties"], "scopes": ["payments:review"]},
        ],
    },
    {
        "group": "Financeiro e BANK",
        "items": [
            {"key": "financeiro.pagamentos", "label": "Pagamentos e escrow", "modules": ["payments", "bank-control"], "scopes": ["payments:review"]},
            {"key": "financeiro.carteira", "label": "BANK — Carteira", "modules": ["my-wallet"], "scopes": ["wallet:read"]},
            {"key": "financeiro.ledger", "label": "Ledger e saldos", "modules": ["wallet"], "scopes": ["wallet:read"]},
            {"key": "financeiro.cobranca", "label": "Cobrança e inadimplência", "modules": ["collections"], "scopes": ["payments:review"]},
            {"key": "financeiro.flash_invest", "label": "Flash Invest", "modules": ["flash-invest"], "scopes": ["investments:write"]},
            {"key": "financeiro.extrato_plataforma", "label": "Extrato (Plataforma)", "modules": ["wallet", "reports"], "scopes": ["wallet:read", "audit:read"]},
            {"key": "financeiro.extrato_parceiros", "label": "Extrato (Parceiros / Franq.)", "modules": ["mmn", "reports"], "scopes": ["network:read", "wallet:read"]},
            {"key": "financeiro.extrato_fornecedores", "label": "Extrato (Fornecedores)", "modules": ["fornecedores", "reports"], "scopes": ["inventory:write"]},
            {"key": "financeiro.saques_parceiros", "label": "Saques (Parceiro / Franq.)", "modules": ["payments", "mmn"], "scopes": ["payments:review"]},
            {"key": "financeiro.saques_fornecedores", "label": "Saques (Fornecedores)", "modules": ["payments", "fornecedores"], "scopes": ["payments:review"]},
            {"key": "financeiro.comissoes", "label": "Rede e comissões (MMN)", "modules": ["mmn"], "scopes": ["network:read"]},
            {"key": "financeiro.taxtech", "label": "TaxTech", "modules": ["taxtech"], "scopes": ["admin:users"]},
            {"key": "financeiro.estatisticas", "label": "Estatísticas / BI", "modules": ["reports"], "scopes": ["audit:read"]},
        ],
    },
    {
        "group": "Documentos e conteúdo",
        "items": [
            {"key": "conteudo.contratos", "label": "Contratos e documentos", "modules": ["contracts"], "scopes": ["documents:write"]},
            {"key": "conteudo.documentos_tipo", "label": "Documentos (tipo)", "modules": ["contracts"], "scopes": ["documents:write"]},
            {"key": "conteudo.duvidas", "label": "Dúvidas / FAQ do chat", "modules": ["chat-faq"], "scopes": ["leads:read"]},
            {"key": "conteudo.manuais", "label": "Manuais e contratos", "modules": ["legal-manuals"], "scopes": ["dashboard:read"]},
            {"key": "conteudo.comunicacoes", "label": "E-mails / comunicações", "modules": ["communications"], "scopes": ["dashboard:read"]},
            {"key": "conteudo.crm", "label": "CRM e originação", "modules": ["crm"], "scopes": ["leads:read", "leads:write"]},
        ],
    },
]

PERMISSION_BY_KEY: dict[str, PermissionDef] = {}
for group in PERMISSION_GROUPS:
    for item in group["items"]:
        PERMISSION_BY_KEY[item["key"]] = item

ALL_PERMISSION_KEYS: frozenset[str] = frozenset(PERMISSION_BY_KEY.keys())


def permission_catalog() -> list[PermissionGroupDef]:
    return PERMISSION_GROUPS


def parse_user_permissions(user: User) -> list[str]:
    raw = (user.permissions_json or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(k) for k in data if str(k) in ALL_PERMISSION_KEYS]


def user_has_full_access(user: User) -> bool:
    if user.role == Role.PLATFORM_ADMIN:
        return True
    return bool(user.access_all)


def normalize_permission_keys(keys: list[str] | None) -> list[str]:
    if not keys:
        return []
    seen: list[str] = []
    for key in keys:
        norm = str(key).strip()
        if norm in ALL_PERMISSION_KEYS and norm not in seen:
            seen.append(norm)
    return seen


def get_effective_scopes(user: User) -> list[str]:
    from app.models import ROLE_SCOPES

    if user_has_full_access(user):
        return ["*"]
    custom = parse_user_permissions(user)
    if custom and user.role in {Role.INTERNAL_STAFF, Role.AUDITOR, Role.PLATFORM_ADMIN}:
        scopes: set[str] = set()
        for key in custom:
            scopes.update(PERMISSION_BY_KEY[key]["scopes"])
        return sorted(scopes) if scopes else list(ROLE_SCOPES.get(user.role, []))
    return list(ROLE_SCOPES.get(user.role, []))


def get_effective_module_keys(user: User) -> list[str] | str:
    if user_has_full_access(user):
        return ALL_MODULES
    custom = parse_user_permissions(user)
    if not custom:
        return []
    modules: set[str] = set()
    for key in custom:
        modules.update(PERMISSION_BY_KEY[key]["modules"])
    return sorted(modules)


def effective_modules_for_view(user: User) -> list[str] | None:
    keys = get_effective_module_keys(user)
    if keys == ALL_MODULES:
        return None
    return list(keys)


def user_can_access_module(user: User, module_key: str) -> bool:
    if user_has_full_access(user):
        return True
    allowed = get_effective_module_keys(user)
    if allowed == ALL_MODULES:
        return True
    return module_key in allowed


def serialize_permissions(keys: list[str] | None) -> str | None:
    normalized = normalize_permission_keys(keys)
    if not normalized:
        return None
    return json.dumps(normalized, ensure_ascii=False)


def validate_admin_password(password: str) -> None:
    from fastapi import HTTPException

    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Senha deve ter no mínimo 8 caracteres.")
    if not any(ch.isdigit() for ch in password):
        raise HTTPException(status_code=422, detail="Senha deve ter pelo menos 1 número.")
    if not any(ch.isalpha() for ch in password):
        raise HTTPException(status_code=422, detail="Senha deve ter pelo menos 1 letra.")
    if not any(ch in "@#$" for ch in password):
        raise HTTPException(status_code=422, detail="Senha deve ter pelo menos 1 caractere especial (@, # ou $).")
