from types import SimpleNamespace

from app.public_chat_native_service import _bank_pick_item, STEP_BANK_ACCOUNTS


def test_bank_pick_item_offers_continue_when_selected():
    banks = [
        SimpleNamespace(id="b1", name="Banco A"),
        SimpleNamespace(id="b2", name="Banco B"),
    ]
    item = _bank_pick_item(
        selected=["b1"],
        banks=banks,
        step=STEP_BANK_ACCOUNTS,
        prompt_text="Teste",
    )
    saves = {o["save"] for o in item["options"]}
    assert "done" in saves
    assert "b2" in saves
    assert "b1" not in saves
