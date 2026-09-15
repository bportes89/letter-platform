from app.email_delivery_service import send_transactional_email
from app.models import CommunicationDelivery, CommunicationTemplate
from app.tax_communication_service import deliver_communication


def test_send_without_provider_returns_mock():
    ok, provider, message_id = send_transactional_email("convidado@example.com", "Assunto", "Corpo")
    assert ok is False
    assert provider == "MOCK"
    assert message_id is None


def test_deliver_communication_marks_mock_when_unconfigured():
    delivery = CommunicationDelivery(
        organization_id="org-1",
        template_id="tpl-1",
        subject_type="USER_INVITATION",
        subject_id="inv-1",
        destination_masked="co***com",
        idempotency_key="test-mock-delivery",
        rendered_body="Olá, use o link.",
    )
    result = deliver_communication(delivery, "convidado@example.com", "Convite LETTER")
    assert result.status == "MOCK"
    assert result.provider == "MOCK"


def test_deliver_communication_uses_resend_when_configured(monkeypatch):
    monkeypatch.setattr(
        "app.email_delivery_service.settings.resend_api_key",
        "re_test_key",
    )

    def fake_post(url, **kwargs):
        class Response:
            status_code = 200

            @staticmethod
            def json():
                return {"id": "email_123"}

        return Response()

    monkeypatch.setattr("app.email_delivery_service.httpx.post", fake_post)
    delivery = CommunicationDelivery(
        organization_id="org-1",
        template_id="tpl-1",
        subject_type="USER_INVITATION",
        subject_id="inv-2",
        destination_masked="co***com",
        idempotency_key="test-resend-delivery",
        rendered_body="Olá, use o link.",
    )
    result = deliver_communication(delivery, "convidado@example.com", "Convite LETTER")
    assert result.status == "DELIVERED"
    assert result.provider == "RESEND"
    assert result.provider_message_id == "email_123"
