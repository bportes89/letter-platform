def test_desk_tapaf_config_get_put(client, auth_headers):
    default = client.get("/api/v1/desk/tapaf-config", headers=auth_headers)
    assert default.status_code == 200
    assert default.json()["SDC"] == "1500.00"
    updated = client.put(
        "/api/v1/desk/tapaf-config",
        headers=auth_headers,
        json={"SDC": "1750.50", "FLASH": "1600"},
    )
    assert updated.status_code == 200
    assert updated.json()["SDC"] == "1750.50"
    assert updated.json()["FLASH"] == "1600.00"
