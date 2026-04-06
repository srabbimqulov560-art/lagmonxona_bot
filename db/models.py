from sqlalchemy import BigInteger, String, Column, DateTime, Integer, Float, ForeignKey, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

# Foydalanuvchilar jadvali
class User(Base):
    __tablename__ = 'users'
    telegram_id = Column(BigInteger, primary_key=True) 
    full_name = Column(String(100), nullable=True)
    phone_number = Column(String(20), nullable=False)
    language = Column(String(5), default="uz")
    created_at = Column(DateTime, default=datetime.utcnow)

# Asosiy buyurtmalar jadvali
class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True, autoincrement=True)
    daily_order_number = Column(Integer, default=1)
    telegram_id = Column(BigInteger, ForeignKey('users.telegram_id'))
    status = Column(String(20), default="active")
    total_price = Column(Float, default=0.0)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    courier_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

# Buyurtma qilingan taomlar tarixi
class OrderItem(Base):
    __tablename__ = 'order_items'
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('orders.id'))
    product_id = Column(String(50))
    quantity = Column(Integer, default=1)
    price = Column(Float)

# Savat jadvali
class Cart(Base):
    __tablename__ = 'carts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, ForeignKey('users.telegram_id'), unique=True)
    
# Savatdagi taomlar
class CartItem(Base):
    __tablename__ = 'cart_items'
    id = Column(Integer, primary_key=True, autoincrement=True)
    cart_id = Column(Integer, ForeignKey('carts.id'))
    product_id = Column(String(50))
    quantity = Column(Integer, default=1)