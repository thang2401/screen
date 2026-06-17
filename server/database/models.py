from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Client(Base):
    __tablename__ = "clients"

    mac_address = Column(String, primary_key=True, index=True)
    client_id = Column(String, unique=True, index=True, nullable=False)
    ip_address = Column(String, nullable=False)
    hostname = Column(String, nullable=False)
    os_info = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sessions = relationship("Session", back_populates="client")
    ai_events = relationship("AIEvent", back_populates="client")

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mac_address = Column(String, ForeignKey("clients.mac_address"), nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    bandwidth_used = Column(Float, default=0.0) # in MB

    client = relationship("Client", back_populates="sessions")

class AIEvent(Base):
    __tablename__ = "ai_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mac_address = Column(String, ForeignKey("clients.mac_address"), nullable=False)
    event_type = Column(String, nullable=False) # e.g., "Cheating", "Gaming", "Idle"
    confidence = Column(Float, nullable=False) # e.g., 0.95
    evidence_path = Column(String, nullable=True) # path to .jpg
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    client = relationship("Client", back_populates="ai_events")
