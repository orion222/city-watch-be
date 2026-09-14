def _address_payload(**overrides):
    payload = {
        "street": "1 Main St",
        "city": "Sometown",
        "state": "ON",
        "postal_code": "S1M 1TN",
        "country": "Canada",
    }
    payload.update(overrides)
    return payload


def test_get_addresses(client):
    client.post("/address", json=_address_payload())
    resp = client.get("/address")
    assert resp.status_code == 200
    assert len(resp.json()["addresses"]) >= 1


def test_get_address_by_id(client):
    created = client.post("/address", json=_address_payload()).json()["address"]
    resp = client.get(f"/address/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["address"]["id"] == created["id"]


def test_get_address_nonexistent_404(client):
    resp = client.get("/address/999999")
    assert resp.status_code == 404


def test_post_address(client):
    resp = client.post("/address", json=_address_payload(city="Newcity"))
    assert resp.status_code == 200
    assert resp.json()["address"]["city"] == "Newcity"


def test_put_address(client):
    created = client.post("/address", json=_address_payload()).json()["address"]
    resp = client.put(f"/address/{created['id']}", json={"city": "Renamedville"})
    assert resp.status_code == 200
    assert resp.json()["address"]["city"] == "Renamedville"


def test_put_address_nonexistent_404(client):
    resp = client.put("/address/999999", json={"city": "Nowhere"})
    assert resp.status_code == 404


def test_delete_address(client):
    created = client.post("/address", json=_address_payload()).json()["address"]
    resp = client.delete(f"/address/{created['id']}")
    assert resp.status_code == 200

    follow_up = client.get(f"/address/{created['id']}")
    assert follow_up.status_code == 404


def test_delete_address_nonexistent_404(client):
    resp = client.delete("/address/999999")
    assert resp.status_code == 404
