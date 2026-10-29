from pydantic import BaseModel, ConfigDict


class RestaurantBase(BaseModel):
    name: str
    cuisine: str
    opens_at: str
    closes_at: str
    avg_prep_minutes: int


class RestaurantResponse(RestaurantBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class MenuItemBase(BaseModel):
    restaurant_id: int
    name: str
    price_cents: int


class MenuItemResponse(MenuItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
