from app.identity_admin_service import safe_user_view
from app.models import Role, User


def test_safe_user_view_accepts_legacy_invalid_email():
    user = User(
        id="user-legacy-1",
        organization_id="org-1",
        branch_id=None,
        name="Usuário legado",
        email="email-invalido",
        password_hash="x",
        role=Role.CLIENT,
    )
    view = safe_user_view(user)
    assert view.id == "user-legacy-1"
    assert view.email.endswith("@example.com")
    assert view.role == Role.CLIENT
