import uuid


def test_list_returns_events_with_distances(client, make_event):
    make_event("Alpha Run")
    res = client.get("/api/v1/events")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["name"] == "Alpha Run"
    assert [d["name"] for d in body[0]["distances"]] == ["5K", "10K"]


def test_list_hides_past_events_by_default(client, make_event):
    make_event("Old Run", days_from_now=-10)
    assert client.get("/api/v1/events").json() == []
    assert len(client.get("/api/v1/events?upcoming_only=false").json()) == 1


def test_get_event_by_id(client, make_event):
    event = make_event("Beta Run")
    res = client.get(f"/api/v1/events/{event.id}")
    assert res.status_code == 200
    assert res.json()["name"] == "Beta Run"


def test_missing_event_returns_404(client):
    res = client.get(f"/api/v1/events/{uuid.uuid4()}")
    assert res.status_code == 404


def test_malformed_id_returns_422(client):
    assert client.get("/api/v1/events/not-a-uuid").status_code == 422