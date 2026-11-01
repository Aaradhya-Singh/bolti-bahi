from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False, unique=True)
    preferred_language = Column(String, default="hi-IN")
    created_at = Column(DateTime, default=datetime.utcnow)

    shops = relationship("Shop", back_populates="owner")


class Shop(Base):
    __tablename__ = "shops"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    shop_name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="shops")
    customers = relationship("Customer", back_populates="shop")
    transactions = relationship("Transaction", back_populates="shop")
    products = relationship("Product", back_populates="shop")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    name = Column(String, nullable=False)
    phone_number = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="customers")
    transactions = relationship("Transaction", back_populates="customer")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    transaction_type = Column(String, nullable=False)  # sale, credit, repayment, expense
    amount = Column(Float, nullable=False)
    payment_mode = Column(String, nullable=True)  # cash, upi, card, etc.
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)  # for expenses: inventory_purchase, electricity, rent, transportation, salaries, misc
    transaction_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="transactions")
    customer = relationship("Customer", back_populates="transactions")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    quantity = Column(Float, default=0)
    unit = Column(String, nullable=False, default="pcs")
    purchase_price = Column(Float, nullable=True)
    selling_price = Column(Float, nullable=True)
    minimum_stock = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="products")
    inventory_transactions = relationship("InventoryTransaction", back_populates="product")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    transaction_type = Column(String, nullable=False)  # stock_in, stock_out
    quantity = Column(Float, nullable=False)
    transaction_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="inventory_transactions")
