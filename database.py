import os
import hashlib
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Date, DateTime, Float, Boolean, JSON, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)

metadata = MetaData()

reservations = Table("reservations", metadata,
    Column("id", String, primary_key=True),
    Column("listing_id", String, index=True),
    Column("checkin", Date, index=True),
    Column("checkout", Date, index=True),
    Column("gross_total", Float),
    Column("channel", String),
    Column("guest_hash", String),
    Column("created_at", DateTime, default=datetime.utcnow),
    Column("updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
    UniqueConstraint("id")
)

calendars = Table("calendars", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("listing_id", String, index=True),
    Column("date", Date, index=True),
    Column("reserved", Boolean, index=True),
    Column("source", String),
    Column("created_at", DateTime, default=datetime.utcnow),
    UniqueConstraint("listing_id", "date")
)

webhook_events = Table("webhook_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("event_id", String, unique=True, nullable=False),
    Column("received_at", DateTime, default=datetime.utcnow),
    Column("raw", JSON),
)

class DatabaseStore:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required for production")
        
        self.engine = create_engine(self.database_url)
        self._init_tables()
    
    def _init_tables(self):
        """Create tables if they don't exist"""
        try:
            metadata.create_all(self.engine)
            logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database tables: {e}")
            raise
    
    def health_check(self) -> bool:
        """Check if database connection is healthy"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def mask_pii(self, name: str, phone: Optional[str] = None) -> str:
        """Mask PII data for logging"""
        if not name:
            return "Unknown"
        
        parts = name.split()
        if len(parts) == 1:
            return f"{parts[0][0]}***"
        elif len(parts) >= 2:
            return f"{parts[0][0]}*** {parts[-1][0]}***"
        return "***"
    
    def generate_event_id(self, payload: Dict[Any, Any]) -> str:
        """Generate deterministic event ID from payload"""
        if "event_id" in payload:
            return str(payload["event_id"])
        
        if "data" in payload and isinstance(payload["data"], dict):
            data = payload["data"]
            if "id" in data and "updated_at" in data:
                return hashlib.sha256(f"{data['id']}-{data['updated_at']}".encode()).hexdigest()
        
        import json
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(payload_str.encode()).hexdigest()
    
    def record_webhook_event(self, payload: Dict[Any, Any]) -> bool:
        """Record webhook event with idempotency check"""
        event_id = self.generate_event_id(payload)
        
        try:
            with self.engine.connect() as conn:
                stmt = insert(webhook_events).values(
                    event_id=event_id,
                    received_at=datetime.utcnow(),
                    raw=payload
                )
                conn.execute(stmt)
                conn.commit()
                
                logger.info(f"Webhook event recorded: {event_id}")
                return True
                
        except IntegrityError:
            logger.info(f"Webhook event already processed: {event_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to record webhook event: {e}")
            raise
    
    def upsert_reservation(self, reserva: Dict[str, Any]) -> bool:
        """Insert or update reservation data"""
        try:
            guest_hash = hashlib.sha256(f"{reserva.get('hospede', '')}{reserva.get('telefone', '')}".encode()).hexdigest()[:16]
            
            with self.engine.connect() as conn:
                stmt = insert(reservations).values(
                    id=reserva["id"],
                    listing_id=reserva["listing_id"],
                    checkin=datetime.strptime(reserva["checkin"], "%Y-%m-%d").date(),
                    checkout=datetime.strptime(reserva["checkout"], "%Y-%m-%d").date(),
                    gross_total=float(reserva["total_bruto"]),
                    channel=reserva["canal"],
                    guest_hash=guest_hash,
                    updated_at=datetime.utcnow()
                )
                
                stmt = stmt.on_conflict_do_update(
                    index_elements=['id'],
                    set_=dict(
                        listing_id=stmt.excluded.listing_id,
                        checkin=stmt.excluded.checkin,
                        checkout=stmt.excluded.checkout,
                        gross_total=stmt.excluded.gross_total,
                        channel=stmt.excluded.channel,
                        guest_hash=stmt.excluded.guest_hash,
                        updated_at=stmt.excluded.updated_at
                    )
                )
                
                conn.execute(stmt)
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to upsert reservation {reserva.get('id')}: {e}")
            return False
    
    def upsert_calendar_day(self, listing_id: str, date_obj: date, reserved: bool, source: str = "webhook") -> bool:
        """Insert or update calendar day data"""
        try:
            with self.engine.connect() as conn:
                stmt = insert(calendars).values(
                    listing_id=listing_id,
                    date=date_obj,
                    reserved=reserved,
                    source=source
                )
                
                stmt = stmt.on_conflict_do_update(
                    index_elements=['listing_id', 'date'],
                    set_=dict(
                        reserved=stmt.excluded.reserved,
                        source=stmt.excluded.source
                    )
                )
                
                conn.execute(stmt)
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to upsert calendar day {listing_id}/{date_obj}: {e}")
            return False
    
    def query_month_calendar(self, year: int, month: int) -> List[Dict[str, Any]]:
        """Query calendar data for a specific month"""
        try:
            from calendar import monthrange
            _, num_days = monthrange(year, month)
            
            with self.engine.connect() as conn:
                start_date = date(year, month, 1)
                end_date = date(year, month, num_days)
                
                query = text("""
                    SELECT id, listing_id, checkin, checkout, gross_total, channel, guest_hash
                    FROM reservations 
                    WHERE checkin <= :end_date AND checkout >= :start_date
                    ORDER BY checkin
                """)
                
                result = conn.execute(query, {"start_date": start_date, "end_date": end_date})
                reservations_data = result.fetchall()
                
                dias = []
                for day in range(1, num_days + 1):
                    day_date = date(year, month, day)
                    day_str = day_date.strftime("%Y-%m-%d")
                    reservas_do_dia = []
                    
                    for res in reservations_data:
                        checkin_date = res.checkin
                        checkout_date = res.checkout
                        
                        status = None
                        if checkin_date == day_date:
                            status = "checkin"
                        elif checkout_date == day_date:
                            status = "checkout"
                        elif checkin_date < day_date < checkout_date:
                            status = "ocupado"
                        
                        if status:
                            guest_display = f"Hóspede {res.guest_hash[:8]}"
                            reservas_do_dia.append({
                                "id": res.id,
                                "hospede": guest_display,
                                "status": status,
                                "total_bruto": float(res.gross_total)
                            })
                    
                    dias.append({
                        "dia": day,
                        "data": day_str,
                        "reservas": reservas_do_dia
                    })
                
                return dias
                
        except Exception as e:
            logger.error(f"Failed to query month calendar: {e}")
            raise
    
    def query_month_reservations(self, start_date: str, end_date: str, listing_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query reservations for a date range"""
        try:
            with self.engine.connect() as conn:
                query_text = """
                    SELECT id, listing_id, checkin, checkout, gross_total, channel, guest_hash
                    FROM reservations 
                    WHERE checkin <= :end_date AND checkout >= :start_date
                """
                params = {"start_date": start_date, "end_date": end_date}
                
                if listing_id:
                    query_text += " AND listing_id = :listing_id"
                    params["listing_id"] = listing_id
                
                query_text += " ORDER BY checkin"
                
                result = conn.execute(text(query_text), params)
                reservations_data = result.fetchall()
                
                return [
                    {
                        "id": res.id,
                        "listing_id": res.listing_id,
                        "checkin": res.checkin.strftime("%Y-%m-%d"),
                        "checkout": res.checkout.strftime("%Y-%m-%d"),
                        "total_bruto": float(res.gross_total),
                        "taxas": 0.0,  # Placeholder
                        "canal": res.channel,
                        "hospede": f"Hóspede {res.guest_hash[:8]}",
                        "telefone": None  # Masked for privacy
                    }
                    for res in reservations_data
                ]
                
        except Exception as e:
            logger.error(f"Failed to query reservations: {e}")
            raise
    
    def get_active_units(self) -> List[Dict[str, str]]:
        """Get list of active units/listings from database"""
        try:
            with self.engine.connect() as conn:
                query = text("""
                    SELECT DISTINCT listing_id 
                    FROM (
                        SELECT listing_id FROM reservations WHERE listing_id IS NOT NULL
                        UNION
                        SELECT listing_id FROM calendars WHERE listing_id IS NOT NULL
                    ) AS units
                    ORDER BY listing_id
                """)
                
                result = conn.execute(query)
                units_data = result.fetchall()
                
                return [
                    {
                        "id": unit.listing_id,
                        "nome": f"Unidade {unit.listing_id}"
                    }
                    for unit in units_data
                ]
                
        except Exception as e:
            logger.error(f"Failed to get active units: {e}")
            raise
