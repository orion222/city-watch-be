def _marker_payload(**overrides):
    payload = {
        "position": [43.6532, -79.3832],
        "description": "Test description",
        "title": "Test marker",
    }
    payload.update(overrides)
    return payload


def test_position_wrong_type_422(client):
    resp = client.post("/marker", json=_marker_payload(position="banana"))
    assert resp.status_code == 422


def test_position_latitude_out_of_range_422(client):
    resp = client.post("/marker", json=_marker_payload(position=[91.0, 0.0]))
    assert resp.status_code == 422


def test_position_longitude_out_of_range_422(client):
    resp = client.post("/marker", json=_marker_payload(position=[0.0, 181.0]))
    assert resp.status_code == 422


def test_position_too_short_422(client):
    resp = client.post("/marker", json=_marker_payload(position=[1.0]))
    assert resp.status_code == 422


def test_position_too_long_422(client):
    resp = client.post("/marker", json=_marker_payload(position=[1.0, 2.0, 3.0]))
    assert resp.status_code == 422


def test_invalid_enum_value_422(client):
    resp = client.post("/marker", json=_marker_payload(urgency="Urgent"))
    assert resp.status_code == 422
