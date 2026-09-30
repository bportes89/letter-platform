from app.cms_text_service import decode_z_text_value


def test_decode_z_text_value_plain():
    assert decode_z_text_value("Olá") == "Olá"


def test_decode_z_text_value_base64():
    import base64

    raw = base64.b64encode("<p>Teste</p>".encode()).decode()
    assert "Teste" in decode_z_text_value(raw)
