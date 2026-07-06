from fastapi import APIRouter, HTTPException
from app.models import Item, item_store

router = APIRouter()


@router.get("/items")
def list_items():
    return {"items": list(item_store.values())}


@router.get("/items/{item_id}")
def get_item(item_id: int):
    if item_id not in item_store:
        raise HTTPException(status_code=404, detail="Item not found")
    return item_store[item_id]


@router.post("/items", status_code=201)
def create_item(item: Item):
    item_id = max(item_store.keys(), default=0) + 1
    item_store[item_id] = {"id": item_id, **item.model_dump()}
    return item_store[item_id]


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    if item_id not in item_store:
        raise HTTPException(status_code=404, detail="Item not found")
    del item_store[item_id]
