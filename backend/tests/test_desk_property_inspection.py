from app.desk_property_inspection import validate_inspection_block, validate_property_inspections


def test_urban_lote_min_photos():
    block = {
        "matricula": "123",
        "zone": "URBANO",
        "lot_type": "LOTE",
        "photos": {"RUA": [{"id": "1"}], "GERAL": [{"id": "2"}]},
    }
    errs = validate_inspection_block(block)
    assert any("mínimo" in e.lower() for e in errs)


def test_urban_complete_room_photo():
    block = {
        "matricula": "1",
        "zone": "URBANO",
        "built_area_m2": 80,
        "rooms": {"QUARTO": 1, "SALA": 1},
        "photos": {
            "EXTERNA": [{"id": "1"}],
            "RUA": [{"id": "2"}],
            "SALA": [{"id": "3"}],
            "QUARTO": [{"id": "4"}],
        },
    }
    assert validate_inspection_block(block) == []


def test_validate_by_matricula():
    props = [{"matricula": "99"}]
    assert validate_property_inspections([], props, asset_is_real_estate=True)
