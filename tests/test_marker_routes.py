from datetime import datetime, timedelta, timezone

from db.models import Marker


def _marker_payload(**overrides):
    payload = {
        "position": [43.6532, -79.3832],
        "description": "Test description",
        "title": "Test marker",
        "urgency": "Medium",
        "category": "Other",
        "status": "Pending",
    }
    payload.update(overrides)
    return payload


def test_post_marker_with_nested_address_links_it(client):
    payload = _marker_payload(
        address={
            "street": "1 Test St",
            "city": "Testville",
            "state": "ON",
            "postal_code": "T3S 7ST",
            "country": "Canada",
        }
    )
    resp = client.post("/marker", json=payload)
    assert resp.status_code == 200
    marker = resp.json()["marker"]
    assert marker["address"]["city"] == "Testville"
    assert marker["address_id"] is not None


def test_post_marker_with_address_id_links_existing_address(client):
    address_resp = client.post(
        "/address",
        json={
            "street": "2 Existing St",
            "city": "Existington",
            "state": "ON",
            "postal_code": "E2X 1ST",
            "country": "Canada",
        },
    )
    address_id = address_resp.json()["address"]["id"]

    before = client.get("/address").json()["addresses"]

    resp = client.post("/marker", json=_marker_payload(address_id=address_id))
    assert resp.status_code == 200
    marker = resp.json()["marker"]
    assert marker["address_id"] == address_id
    assert marker["address"]["city"] == "Existington"

    after = client.get("/address").json()["addresses"]
    assert len(after) == len(before)  # no new address created


def test_get_markers_ordered_by_timestamp_desc(client, db_session):
    # Inserted via the ORM with explicit timestamps rather than the API: two
    # POSTs in the same test transaction share one `now()` value (Postgres
    # resolves it to transaction start), which would make ordering a tie.
    base = datetime.now(timezone.utc)
    older = Marker(
        latitude=1.0, longitude=1.0, description="d", title="older",
        timestamp=base - timedelta(days=1),
    )
    newer = Marker(latitude=2.0, longitude=2.0, description="d", title="newer", timestamp=base)
    db_session.add(older)
    db_session.add(newer)
    db_session.commit()
    db_session.refresh(older)
    db_session.refresh(newer)

    body = client.get("/marker").json()
    ids = [m["id"] for m in body["markers"]]
    assert ids.index(newer.id) < ids.index(older.id)


def test_get_marker_by_id(client):
    created = client.post("/marker", json=_marker_payload()).json()["marker"]
    resp = client.get(f"/marker/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["marker"]["id"] == created["id"]


def test_get_marker_nonexistent_returns_200_with_message(client):
    # Known API wart, not fixed here: a missing marker returns HTTP 200 with a
    # message body rather than a 404. Tracked as a follow-up ticket.
    resp = client.get("/marker/999999")
    assert resp.status_code == 200
    assert resp.json() == {"message": "Marker 999999 not found"}


def test_put_marker_updates_scalar_fields_and_position(client):
    created = client.post("/marker", json=_marker_payload()).json()["marker"]

    update_payload = _marker_payload(
        position=[10.0, 20.0],
        title="Updated title",
        description="Updated description",
        urgency="High",
        category="Crime",
        status="Resolved",
    )
    resp = client.put(f"/marker/{created['id']}", json=update_payload)
    assert resp.status_code == 200
    marker = resp.json()["marker"]
    assert marker["position"] == [10.0, 20.0]
    assert marker["title"] == "Updated title"
    assert marker["urgency"] == "High"
    assert marker["category"] == "Crime"
    assert marker["status"] == "Resolved"


def test_put_marker_updates_nested_address_in_place(client):
    created = client.post(
        "/marker",
        json=_marker_payload(
            address={
                "street": "1 Original St",
                "city": "Originalton",
                "state": "ON",
                "postal_code": "O1R 1GN",
                "country": "Canada",
            }
        ),
    ).json()["marker"]
    original_address_id = created["address_id"]

    update_payload = _marker_payload(
        address={
            "street": "2 Updated St",
            "city": "Updateville",
            "state": "ON",
            "postal_code": "U2P 2DT",
            "country": "Canada",
        }
    )
    resp = client.put(f"/marker/{created['id']}", json=update_payload)
    assert resp.status_code == 200
    marker = resp.json()["marker"]
    # Same address row mutated, not a new one created.
    assert marker["address_id"] == original_address_id
    assert marker["address"]["city"] == "Updateville"


def test_put_marker_nonexistent_returns_200_with_message(client):
    # Same wart as GET — status_code 200, not 404 — asserted as today's actual behaviour.
    resp = client.put("/marker/999999", json=_marker_payload())
    assert resp.status_code == 200
    assert resp.json() == {"message": "Marker 999999 not found"}


def test_marker_without_address_omits_address_key_rather_than_null(client):
    # Known API wart, not fixed here: _serialize only sets "address" when the
    # relationship is truthy, and model_dump() drops relationships entirely,
    # so an addressless marker is missing the key instead of returning null.
    payload = {"position": [1.0, 2.0], "title": "no addr", "description": "d"}
    created = client.post("/marker", json=payload).json()["marker"]
    assert "address" not in created

    listed = next(m for m in client.get("/marker").json()["markers"] if m["id"] == created["id"])
    assert "address" not in listed
