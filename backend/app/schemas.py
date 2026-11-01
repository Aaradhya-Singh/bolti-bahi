from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


# ---------- User ----------
class UserCreate(BaseModel):
    name: str
    phone_number: str
    preferred_language: str = "hi-IN"


class UserResponse(BaseModel):
    id: int
    name: str
    phone_number: str
    preferred_language: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Shop ----------
class ShopCreate(BaseModel):
    owner_name: str
    owner_phone: str
    shop_name: str
    address: Optional[str] = None
    preferred_language: str = "hi-IN"


class ShopResponse(BaseModel):
    id: int
    owner_id: int
    shop_name: str
    address: Optional[str]
    created_at: datetime
    owner: Optional[UserResponse] = None

    class Config:
        from_attributes = True


# ---------- Customer ----------
class CustomerCreate(BaseModel):
    name: str
    phone_number: Optional[str] = None


class CustomerResponse(BaseModel):
    id: int
    shop_id: int
    name: str
    phone_number: Optional[str]
    created_at: datetime
    balance: Optional[float] = None  # outstanding credit balance

    class Config:
        from_attributes = True


# ---------- Transaction ----------
class TransactionCreate(BaseModel):
    customer_id: Optional[int] = None
    transaction_type: str  # sale, credit, repayment, expense
    amount: float
    payment_mode: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None  # for expenses
    transaction_date: Optional[datetime] = None


class TransactionResponse(BaseModel):
    id: int
    shop_id: int
    customer_id: Optional[int]
    transaction_type: str
    amount: float
    payment_mode: Optional[str]
    description: Optional[str]
    category: Optional[str]
    transaction_date: datetime
    created_at: datetime
    customer_name: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- Product ----------
class ProductCreate(BaseModel):
    name: str
    category: Optional[str] = None
    quantity: float = 0
    unit: str = "pcs"
    purchase_price: Optional[float] = None
    selling_price: Optional[float] = None
    minimum_stock: float = 0


class ProductResponse(BaseModel):
    id: int
    shop_id: int
    name: str
    category: Optional[str]
    quantity: float
    unit: str
    purchase_price: Optional[float]
    selling_price: Optional[float]
    minimum_stock: float
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Inventory Transaction ----------
class InventoryTransactionCreate(BaseModel):
    transaction_type: str  # stock_in, stock_out
    quantity: float


# ---------- Dashboard ----------
class LowStockProduct(BaseModel):
    id: int
    name: str
    quantity: float
    unit: str
    minimum_stock: float


class DashboardResponse(BaseModel):
    today_sales: float
    today_expenses: float
    total_outstanding_credit: float
    customers_with_pending: int
    low_stock_products: list[LowStockProduct]
    estimated_profit: float


# ---------- Voice ----------
class IntentResult(BaseModel):
    intent: str
    customer_name: Optional[str] = None
    amount: Optional[float] = None
    product_name: Optional[str] = None
    quantity: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    time_period: Optional[str] = None  # today, week, month
    needs_confirmation: bool = False
    confirmation_message: Optional[str] = None


class VoiceCommandResponse(BaseModel):
    transcript: str
    intent: Optional[IntentResult] = None
    action_taken: Optional[str] = None
    response_text: str
    audio_base64: Optional[str] = None
    data: Optional[Any] = None
