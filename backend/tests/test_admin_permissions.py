from app.admin_permissions import get_effective_scopes, normalize_permission_keys, user_has_full_access
from app.models import Role, User


def test_normalize_permission_keys_dedupes():
    keys = normalize_permission_keys(["cadastro.novos", "cadastro.novos", "invalid"])
    assert keys == ["cadastro.novos"]


def test_full_access_admin_scopes():
    user = User(
        id="u1",
        organization_id="o1",
        name="Admin",
        email="admin@test.com",
        password_hash="x",
        role=Role.PLATFORM_ADMIN,
        access_all=True,
    )
    assert user_has_full_access(user)
    assert get_effective_scopes(user) == ["*"]


def test_custom_permissions_scopes():
    user = User(
        id="u2",
        organization_id="o1",
        name="Ops",
        email="ops@test.com",
        password_hash="x",
        role=Role.INTERNAL_STAFF,
        access_all=False,
        permissions_json='["financeiro.pagamentos","cadastro.novos"]',
    )
    scopes = get_effective_scopes(user)
    assert "payments:review" in scopes
    assert "leads:read" in scopes
