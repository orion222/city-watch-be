from types import SimpleNamespace


class _FakeModels:
    def __init__(self, text: str):
        self._text = text

    def generate_content(self, **kwargs):
        return SimpleNamespace(text=self._text)


class _FakeClient:
    def __init__(self, text: str):
        self.models = _FakeModels(text)


def _patch_gemini_response(monkeypatch, response_text: str):
    # routes/gemini.py imports get_client into its own namespace; get_client is
    # @lru_cache'd, so patching the name (not the cached real client) is what
    # keeps the real, paid client from ever being constructed.
    monkeypatch.setattr("routes.gemini.get_client", lambda: _FakeClient(response_text))


def _patch_geocode(monkeypatch, position=(43.6532, -79.3832)):
    monkeypatch.setattr(
        "routes.gemini.geocode_address",
        lambda address: {
            "position": list(position),
            "address_details": {
                "street": "1 Geocoded St",
                "city": "Geocodeville",
                "state": "ON",
                "postal_code": "G3O 1CD",
                "country": "Canada",
            },
        },
    )


GOOD_REPORT = """
{
  "report": {
    "category": "Infrastructure",
    "address": "123 Fake St, Toronto",
    "title": "Broken streetlight",
    "urgency": "Medium",
    "description": "The streetlight has been out for a week."
  }
}
"""


def test_submit_report_gemini_success_creates_marker_and_address(client, monkeypatch):
    _patch_gemini_response(monkeypatch, GOOD_REPORT)
    _patch_geocode(monkeypatch, position=(43.6532, -79.3832))

    resp = client.post("/submit-report-gemini", json={"description": "The streetlight is out."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_marker_id"] is not None
    assert body["created_address_id"] is not None

    marker = client.get(f"/marker/{body['created_marker_id']}").json()["marker"]
    assert marker["position"] == [43.6532, -79.3832]
    assert marker["address"]["city"] == "Geocodeville"


def test_submit_report_gemini_unparseable_json_returns_500(client, monkeypatch):
    _patch_gemini_response(monkeypatch, "not valid json at all")

    resp = client.post("/submit-report-gemini", json={"description": "anything"})
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Invalid JSON returned from AI model"


def test_submit_report_gemini_missing_address_returns_422(client, monkeypatch):
    report_missing_address = """
    {
      "report": {
        "category": "Infrastructure",
        "address": "",
        "title": "Broken streetlight",
        "urgency": "Medium",
        "description": "The streetlight has been out for a week."
      }
    }
    """
    _patch_gemini_response(monkeypatch, report_missing_address)

    resp = client.post("/submit-report-gemini", json={"description": "anything"})
    assert resp.status_code == 422
    assert "We need more context" in resp.json()["detail"]
    assert "address" in resp.json()["detail"]
