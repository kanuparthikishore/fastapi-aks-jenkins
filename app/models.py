from pydantic import BaseModel, field_validator


class Item(BaseModel):
    name: str
    description: str
    price: float

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty")
        return v

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("price must be positive")
        return v


item_store: dict = {
    1: {"id": 1, "name": "Widget", "description": "A useful widget", "price": 9.99},
    2: {"id": 2, "name": "Gadget", "description": "A cool gadget", "price": 19.99},
}
