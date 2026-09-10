from datetime import datetime
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    price = Column(Integer, default=0, nullable=False)  # 0 = Free/Gift
    description = Column(Text, default="", nullable=False)
    photo_file_id = Column(String(255), nullable=True)
    digital_file_id = Column(String(255), nullable=True)
    digital_file_type = Column(String(32), default="audio", nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    payment_type = Column(String(32), default="paid", nullable=False)  # 'paid' or 'free'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(String(64), index=True, nullable=False)
    username = Column(String(128), default="", nullable=False)
    customer_name = Column(String(128), default="", nullable=False)
    phone = Column(String(64), default="", nullable=False)
    product_id = Column(String(64), nullable=False)
    product_name = Column(String(255), nullable=False)
    total = Column(Integer, default=0, nullable=False)
    wallet_used = Column(Integer, default=0, nullable=False)
    receipt_file_id = Column(String(255), nullable=True)
    status = Column(String(32), default="pending", nullable=False)  # pending, approved, rejected
    platform = Column(String(32), default="telegram", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), unique=True, index=True, nullable=False)
    customer_name = Column(String(128), default="", nullable=False)
    phone = Column(String(64), default="", nullable=False)
    terms_accepted = Column(Boolean, default=False, nullable=False)
    wallet_balance = Column(Integer, default=0, nullable=False)
    platform = Column(String(32), default="telegram", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(String(64), index=True, nullable=False)
    username = Column(String(128), default="", nullable=False)
    message_text = Column(Text, nullable=False)
    status = Column(String(32), default="open", nullable=False)
    platform = Column(String(32), default="telegram", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(String(64), unique=True, index=True, nullable=False)
    channel_id = Column(String(128), nullable=False)
    text = Column(Text, nullable=False)
    media_file_id = Column(String(255), nullable=True)
    btn_text = Column(String(128), nullable=True)
    btn_url = Column(String(255), nullable=True)
    scheduled_time = Column(String(64), nullable=False)
    status = Column(String(32), default="pending", nullable=False)
    platform = Column(String(32), default="telegram", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class KeywordRule(Base):
    __tablename__ = "keyword_rules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(32), default="INSTAGRAM", nullable=False)  # INSTAGRAM, TELEGRAM, BALE, RUBIKA, ALL
    keyword = Column(String(255), index=True, nullable=False)
    matching_mode = Column(String(32), default="EXACT", nullable=False)  # EXACT, CONTAINS, STARTS_WITH
    response_type = Column(String(32), default="TEXT", nullable=False)   # TEXT, MEDIA
    response_text = Column(Text, default="", nullable=False)
    media_id = Column(String(255), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
