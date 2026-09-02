from pathlib import Path

from app.legacy_export_service import export_legacy_bundle, write_bundle
from app.legacy_sql_parser import load_table, parse_values_block


FIXTURE_SQL = """
INSERT INTO `administrators` (`id`, `active`, `name`, `image`, `type`, `order`, `created_at`, `updated_at`, `banco`, `correntista`, `nome_sujo`, `email`, `phone`, `cotas_categories`, `ano_fabricacao_max`) VALUES
(1, 1, 'Embracon', '', NULL, 999, '2023-09-13 07:12:17', '2024-02-20 17:24:10', 0, 0, 0, '', '', '[2,6,9,10,14]', '[5]');

INSERT INTO `affiliates` (`id`, `active`, `assinatura_cobrar`, `name`, `image`, `affiliates_qualification`, `type`, `order`, `created_at`, `updated_at`, `cpf`, `rg`, `rg_orgao`, `rg_estados`, `fantasia`, `cnpj`, `ie`, `date_fundacao`, `phone`, `email`, `password`, `remember_token`, `verified_at`, `zipcode`, `street`, `number`, `complement`, `neighborhood`, `uf`, `city`, `bank`, `agency`, `account`, `type_account`, `pix`, `pix_type`, `url`, `supervisores_vendedores`, `adicionar_comissao`, `price_assinatura`, `birth`, `porc`, `porc_capital_giro`, `porc_compra`, `supervisors`, `managers`, `regionais`, `partners`, `franquias`, `saldo`, `txt`, `razao_social`, `idade`, `porc_a_mais`, `venda_direta`, `sdc`, `price_total`, `price_apuracao`, `affiliates_qualification_apuracao`, `affiliates_qualification_apuracao_name`) VALUES
(8, 1, 0, 'Paulo Stutz', '', 1, 'partners', 999, '2023-09-27 00:33:54', '2026-06-15 23:22:45', '038.259.565-39', NULL, NULL, NULL, NULL, NULL, NULL, NULL, '(33) 99198-8170', 'contato@fpsconsorcios.com.br', 'hash', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0, NULL, 0, 'paulostutz', 1, 1, 0.00, '1989-08-16', 3.00, 0.00, 0.00, 0, 0, 0, 0, 0, 0.00, '', '', 34, 0.00, 1, 1, 0.00, 0.00, NULL, '- - - -');

INSERT INTO `suppliers` (`id`, `active`, `name`, `image`, `type`, `order`, `created_at`, `updated_at`, `cpf`, `rg`, `rg_orgao`, `rg_estados`, `fantasia`, `cnpj`, `ie`, `date_fundacao`, `phone`, `url`, `email`, `password`, `remember_token`, `verified_at`, `zipcode`, `street`, `number`, `complement`, `neighborhood`, `uf`, `city`, `bank`, `agency`, `account`, `type_account`, `pix`, `pix_type`, `saldo`, `birth`, `idade`, `api`, `txt`, `quem_paga_comissao`) VALUES
(1, 1, 'Cont. F&B', '', '', 999, '2023-09-13 04:55:27', '2026-06-22 22:29:10', '038.259.565-39', NULL, NULL, NULL, NULL, NULL, NULL, NULL, '(33) 99198-8170', NULL, 'contato@fpsconsorcios.com.br', 'hash', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0, NULL, 3, 0.00, NULL, 34, 'https://example.com', 'API', 0);

INSERT INTO `customers` (`id`, `active`, `name`, `type`, `status`, `partners`, `quotas`, `price`, `email`, `phone`, `cpf`, `sdc`) VALUES
(24, 1, 'Cliente Teste', 'customers', 2, '8', '[21]', 51071.00, 'cliente@test.com', '(73) 99935-3818', '948.790.445-04', 0);

INSERT INTO `quotas` (`id`, `active`, `status`, `status_api`, `name`, `image`, `type`, `order`, `created_at`, `updated_at`, `suppliers`, `administrators`, `quotas_categories`, `price`, `price_entrada`, `parcelas`, `price_parcela`, `date_vencimento`, `api`, `api_url`, `api_url_type`, `parcelas_add`, `administrators_txt`, `txt`, `partners`) VALUES
(21, 1, 1, 0, '', '', NULL, 999, '2023-09-28 11:31:17', '2026-06-11 15:30:06', 1, 0, 2, 51071.00, 18540.00, 33, 1580.00, '2026-09-10', 4696, NULL, NULL, '', 'Embracon', NULL, NULL);

INSERT INTO `quotas_categories` (`id`, `active`, `name`, `image`, `type`, `subcategories`, `order`, `created_at`, `updated_at`, `title_sub`) VALUES
(2, 1, 'VEICULOS', '', 0, NULL, 1, '2023-09-03 01:10:31', '2026-06-14 14:35:03', 'Veículo');

INSERT INTO `users` (`id`, `active`, `name`, `email`, `phone`, `permissions`, `permissions_all`, `password`, `remember_token`, `verified_at`, `created_at`, `updated_at`) VALUES
(2, 1, 'Administrador', 'admin@admin', NULL, '', 1, 'hash', NULL, NULL, '2025-01-01 06:00:00', '2026-09-01 15:45:22');
"""


def test_parse_values_block():
    block = "(1, 'Embracon', NULL, '2023-09-13 07:12:17'), (2, 'HS', 0, '2024-01-01 00:00:00')"
    rows = parse_values_block(block)
    assert rows == [
        [1, "Embracon", None, "2023-09-13 07:12:17"],
        [2, "HS", 0, "2024-01-01 00:00:00"],
    ]


def test_load_table_fixture():
    rows = load_table(FIXTURE_SQL, "administrators")
    assert len(rows) == 1
    assert rows[0]["name"] == "Embracon"


def test_export_legacy_bundle_fixture(tmp_path: Path):
    sql_path = tmp_path / "fixture.sql"
    sql_path.write_text(FIXTURE_SQL, encoding="utf-8")
    bundle = export_legacy_bundle(sql_path, legacy_source="letter_test")
    counts = bundle["meta"]["exported_counts"]
    assert counts["administrators"] == 1
    assert counts["users"] >= 3
    assert counts["leads"] == 1
    assert counts["quotas"] == 1
    assert counts["proposals"] == 1
    lead = bundle["entities"]["leads"][0]
    assert lead["owner_user_legacy_id"] == "affiliate-8"
    quota = bundle["entities"]["quotas"][0]
    assert quota["group_code"] == "4696"
    assert quota["category"] == "VEHICLE"

    out = tmp_path / "bundle.json"
    write_bundle(bundle, out)
    assert out.is_file()
