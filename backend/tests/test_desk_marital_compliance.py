from app.desk_marital_compliance import (
    validate_desk_marital_compliance,
    validate_partners_marital,
    validate_pf_marital,
)


def test_pf_marital_required():
    assert validate_pf_marital({"person_type": "PF"}) == ["Informe o estado civil do cliente (PF)."]


def test_pf_married_requires_spouse():
    errs = validate_pf_marital(
        {"person_type": "PF", "marital_status": "CASADO", "spouse_name": "", "spouse_document": ""},
    )
    assert "Informe o nome completo do cônjuge." in errs
    assert any("CPF" in e for e in errs)


def test_pf_married_ok():
    assert (
        validate_pf_marital(
            {
                "person_type": "PF",
                "marital_status": "CASADO",
                "spouse_name": "Maria",
                "spouse_document": "123.456.789-09",
            },
        )
        == []
    )


def test_pj_partner_marital_when_row_filled():
    assert validate_partners_marital([{"name": "João", "document": "123"}], context="sócio") == [
        "Informe o estado civil de sócio 1.",
    ]


def test_desk_pj_validates_partners():
    errs = validate_desk_marital_compliance(
        {
            "person_type": "PJ",
            "partners_json": [
                {
                    "name": "Ana",
                    "marital_status": "UNIAO_ESTAVEL",
                    "spouse_name": "Pedro",
                    "spouse_document": "52998224725",
                },
            ],
        },
    )
    assert errs == []
