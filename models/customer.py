from typing import Optional
from pydantic import BaseModel


class Customer(BaseModel):

    customer_id: str
    customer_name: str
    email: str
    phone: str
    tier: str
    join_date: str
    status: str


class Order(BaseModel):

    order_id: str
    customer_id: str
    product_id: str
    order_date: str
    delivery_date: str
    amount: float
    order_status: str


class Product(BaseModel):

    product_id: str
    product_name: str
    category: str
    brand: str
    price: float
    warranty_months: int
    return_window_days: int
