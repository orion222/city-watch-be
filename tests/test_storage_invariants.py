import re

from sqlalchemy import text
from sqlmodel import select

from db.models import Address, Marker


def test_seeded_corpus_is_172_markers(db_session):
    assert db_session.exec(select(Marker)).all().__len__() == 172


def test_address_relationship_loads_via_selectinload(client):
    body = client.get("/marker").json()
    markers = body["markers"]
    assert any(m.get("address") is not None for m in markers)
    populated = next(m for m in markers if m.get("address") is not None)
    assert populated["address"]["city"]

    single = client.get(f"/marker/{populated['id']}").json()["marker"]
    assert single["address"]["city"] == populated["address"]["city"]


def test_enum_columns_persist_human_values_not_member_names(db_session):
    # Raw SQL deliberately: the ORM coerces the stored string back into the
    # enum on read, which would hide a values_callable regression entirely.
    statuses = {r[0] for r in db_session.exec(text("select distinct status from marker")).all()}
    categories = {r[0] for r in db_session.exec(text("select distinct category from marker")).all()}
    urgencies = {r[0] for r in db_session.exec(text("select distinct urgency from marker")).all()}

    assert statuses == {"Pending", "In Progress", "Resolved"}
    assert "IN_PROGRESS" not in statuses

    assert categories == {"Crime", "Environment", "Infrastructure", "Safety", "Other"}
    assert not any(c.isupper() for c in categories)

    assert urgencies == {"Low", "Medium", "High", "Critical"}
    assert not any(u.isupper() for u in urgencies)


def test_position_round_trips_through_lat_lng_columns(client, db_session):
    sent = [43.6532, -79.3832]
    created = client.post(
        "/marker",
        json={"position": sent, "title": "round trip", "description": "d"},
    ).json()["marker"]

    fetched = client.get(f"/marker/{created['id']}").json()["marker"]
    assert fetched["position"] == sent  # both elements, right order, no swap

    row = db_session.exec(
        text("select latitude, longitude from marker where id = :id"),
        params={"id": created["id"]},
    ).first()
    assert row[0] == sent[0]
    assert row[1] == sent[1]


def test_timestamps_are_timezone_aware(db_session):
    marker = db_session.exec(select(Marker)).first()
    assert marker.timestamp.tzinfo is not None

    address = db_session.exec(select(Address)).first()
    assert address.created_at.tzinfo is not None


def test_timestamp_json_carries_a_utc_offset(client):
    created = client.post(
        "/marker",
        json={"position": [1.0, 2.0], "title": "tz", "description": "d"},
    )
    # An offset-naive ISO string here would mean the DB gave back a naive datetime.
    assert re.search(r"\d{2}:\d{2}:\d{2}(\.\d+)?(\+\d{2}:\d{2}|Z)", created.text)
