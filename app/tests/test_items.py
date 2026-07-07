from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_list_items_returns_200():
    r = client.get("/api/items")
    assert r.status_code == 200
    assert "items" in r.json()


def test_list_items_is_list():
    r = client.get("/api/items")
    assert isinstance(r.json()["items"], list)


def test_get_existing_item():
    r = client.get("/api/items/1")
    assert r.status_code == 200
    assert r.json()["id"] == 1


def test_get_missing_item_returns_404():
    r = client.get("/api/items/9999")
    assert r.status_code == 404


def test_create_item_success():
    payload = {"name": "Thingamajig", "description": "Very useful", "price": 4.99}
    r = client.post("/api/items", json=payload)
    assert r.status_code == 201
    assert r.json()["name"] == "Thingamajig"
    assert "id" in r.json()


def test_create_item_invalid_price():
    payload = {"name": "Bad", "description": "negative price", "price": -1.0}
    r = client.post("/api/items", json=payload)
    assert r.status_code == 422


def test_create_item_empty_name():
    payload = {"name": "  ", "description": "blank name", "price": 5.0}
    r = client.post("/api/items", json=payload)
    assert r.status_code == 422


def test_delete_existing_item():
    create = client.post("/api/items",
                         json={"name": "Temp", "description": "Delete me", "price": 1.0})
    item_id = create.json()["id"]
    r = client.delete(f"/api/items/{item_id}")
    assert r.status_code == 204


def test_delete_missing_item_returns_404():
    r = client.delete("/api/items/9999")
    assert r.status_code == 404
