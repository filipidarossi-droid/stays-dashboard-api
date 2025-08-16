import os
import hashlib
import logging
import json
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import calendar
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, Query, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
import orjson
from stays_client import StaysClient
from repasse import calcular_repasse
from store import CacheStore

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo(os.getenv("TZ", "America/Sao_Paulo"))

app = FastAPI(title="Stays Dashboard API", version="2.0.0")

security = HTTPBearer()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    engine = create_engine(
        DATABASE_URL.replace("postgresql://", "postgresql+psycopg://"),
        pool_size=5, 
        max_overflow=5, 
        pool_pre_ping=True, 
        pool_recycle=1800
    )
    
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS reservations (
                id VARCHAR PRIMARY KEY,
                listing_id VARCHAR,
                checkin DATE,
                checkout DATE,
                gross_total FLOAT,
                channel VARCHAR,
                guest_hash VARCHAR,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS calendars (
                id SERIAL PRIMARY KEY,
                listing_id VARCHAR,
                date DATE,
                reserved BOOLEAN,
                source VARCHAR,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(listing_id, date)
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS webhook_events (
                id SERIAL PRIMARY KEY,
                event_hash VARCHAR UNIQUE NOT NULL,
                received_at TIMESTAMP DEFAULT NOW(),
                raw JSONB
            )
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_reservations_listing_checkin 
            ON reservations(listing_id, checkin, checkout)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_calendars_listing_date 
            ON calendars(listing_id, date)
        """))
        
        conn.commit()
    
    logger.info("PostgreSQL database initialized successfully")
else:
    engine = None
    logger.error("DATABASE_URL not configured - database unavailable")

cache_store = CacheStore()

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "https://stays-dashboard-web.onrender.com").split(",")
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS if origin.strip()]
API_TOKEN = os.getenv("API_TOKEN", "test-token-12345")

if len(API_TOKEN) < 32:
    logger.warning("API_TOKEN should be at least 32 characters for production security")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HealthResponse(BaseModel):
    status: str

class ReservaResponse(BaseModel):
    id: str
    listing_id: str
    checkin: str
    checkout: str
    total_bruto: float
    taxas: float
    canal: str
    hospede: str
    telefone: Optional[str] = None

class CalendarioResponse(BaseModel):
    mes: str
    dias: List[dict]

class RepasseResponse(BaseModel):
    meta: float
    repasse_estimado: float
    status: str
    detalhes: dict

class UnidadeResponse(BaseModel):
    id: str
    nome: str

def today_sp():
    return datetime.now(TIMEZONE).date()

def month_bounds(d: date):
    first = d.replace(day=1)
    last = date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])
    return first, last

def iter_month_days(d: date):
    first, last = month_bounds(d)
    cur = first
    while cur <= last:
        yield cur
        cur += timedelta(days=1)

def event_hash(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",",":")).encode()
    return hashlib.sha256(blob).hexdigest()

def mask_pii(name: str) -> str:
    if not name:
        return "Unknown"
    
    parts = name.split()
    if len(parts) == 1:
        return f"{parts[0][0]}***"
    elif len(parts) >= 2:
        return f"{parts[0][0]}*** {parts[-1][0]}***"
    return "***"

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials

def require_bearer(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    try:
        scheme, token = authorization.split(" ", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Authorization format")
    if scheme.lower() != "bearer" or token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    return token

@app.get("/health", response_model=HealthResponse)
async def health():
    if not engine:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return HealthResponse(status="ok")
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(status_code=503, detail="Database connection failed")

@app.get("/reservas", response_model=List[ReservaResponse])
async def get_reservas(
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    listing_id: Optional[str] = Query(None),
    token: str = Depends(verify_token)
):
    if not engine:
        raise HTTPException(status_code=503, detail="Database not available")
    
    cache_key = f"reservas_{from_date}_{to_date}_{listing_id or 'all'}"
    cached_result = cache_store.get(cache_key)
    
    if cached_result:
        return cached_result
    
    try:
        with engine.connect() as conn:
            query_text = """
                SELECT id, listing_id, checkin, checkout, gross_total, channel, guest_hash
                FROM reservations 
                WHERE checkin <= :end_date AND checkout >= :start_date
            """
            params = {"start_date": from_date, "end_date": to_date}
            
            if listing_id:
                query_text += " AND listing_id = :listing_id"
                params["listing_id"] = listing_id
            
            query_text += " ORDER BY checkin"
            
            result_rows = conn.execute(text(query_text), params)
            reservations_data = result_rows.fetchall()
            
            result = [
                ReservaResponse(
                    id=res.id,
                    listing_id=res.listing_id,
                    checkin=res.checkin.strftime("%Y-%m-%d"),
                    checkout=res.checkout.strftime("%Y-%m-%d"),
                    total_bruto=float(res.gross_total),
                    taxas=0.0,
                    canal=res.channel,
                    hospede=f"Hóspede {res.guest_hash[:8]}",
                    telefone=None
                )
                for res in reservations_data
            ]
        
        cache_store.set(cache_key, result, ttl=900)
        return result
    except Exception as e:
        logger.error(f"Failed to get reservations: {e}")
        raise HTTPException(status_code=503, detail="Failed to retrieve reservations")

@app.get("/calendario", response_model=CalendarioResponse)
async def get_calendario(
    mes: str = Query(...),
    unidade_id: Optional[str] = Query(None),
    token: str = Depends(verify_token)
):
    if not engine:
        raise HTTPException(status_code=503, detail="Database not available")
    
    cache_key = f"calendario_{mes}_{unidade_id or 'all'}"
    cached_result = cache_store.get(cache_key)
    
    if cached_result:
        return cached_result
    
    try:
        year, month = mes.split("-")
        year, month = int(year), int(month)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de mês inválido. Use YYYY-MM")
    
    try:
        with engine.connect() as conn:
            _, num_days = calendar.monthrange(year, month)
            start_date = date(year, month, 1)
            end_date = date(year, month, num_days)
            
            query_text = """
                SELECT id, listing_id, checkin, checkout, gross_total, channel, guest_hash
                FROM reservations 
                WHERE checkin <= :end_date AND checkout >= :start_date
            """
            params = {"start_date": start_date, "end_date": end_date}
            
            if unidade_id:
                query_text += " AND listing_id = :listing_id"
                params["listing_id"] = unidade_id
            
            query_text += " ORDER BY checkin"
            
            result_rows = conn.execute(text(query_text), params)
            reservations_data = result_rows.fetchall()
            
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
        
        result = CalendarioResponse(mes=mes, dias=dias)
        cache_store.set(cache_key, result, ttl=900)
        return result
    except Exception as e:
        logger.error(f"Failed to get calendar for {mes}: {e}")
        raise HTTPException(status_code=503, detail="Failed to retrieve calendar data")

@app.get("/repasse", response_model=RepasseResponse)
async def get_repasse(
    mes: str = Query(...),
    incluir_limpeza: bool = Query(default=None),
    unidade_id: Optional[str] = Query(None),
    token: str = Depends(verify_token)
):
    if incluir_limpeza is None:
        incluir_limpeza = os.getenv("INCLUIR_LIMPEZA_DEFAULT", "true").lower() == "true"
    
    cache_key = f"repasse_{mes}_{incluir_limpeza}_{unidade_id or 'all'}"
    cached_result = cache_store.get(cache_key)
    
    if cached_result:
        return cached_result
    
    try:
        year, month = mes.split("-")
        year, month = int(year), int(month)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de mês inválido. Use YYYY-MM")
    
    from calendar import monthrange
    _, num_days = monthrange(year, month)
    
    first_day = f"{year}-{month:02d}-01"
    last_day = f"{year}-{month:02d}-{num_days:02d}"
    
    stays_client = StaysClient()
    reservas = await stays_client.listar_reservas(first_day, last_day)
    
    result = calcular_repasse(reservas, incluir_limpeza)
    cache_store.set(cache_key, result, ttl=900)  # 15 minutes
    return result

@app.post("/webhooks/stays")
async def webhook_stays(request: Request, authorization: Optional[str] = Header(None)):
    require_bearer(authorization)
    
    if not engine:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    eh = event_hash(payload)
    
    try:
        with engine.begin() as conn:
            try:
                conn.execute(text(
                    "INSERT INTO webhook_events (event_hash, raw) VALUES (:h, :raw)"
                ), {"h": eh, "raw": json.dumps(payload)})
            except Exception as e:
                if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                    logger.info(f"Webhook event already processed: {eh}")
                    return {"ok": True, "duplicate": True}
                raise
            
            if "data" in payload and isinstance(payload["data"], dict):
                reservation_data = payload["data"]
                
                guest_masked = mask_pii(reservation_data.get("hospede", ""))
                logger.info(f"Processing webhook for reservation {reservation_data.get('id')} - Guest: {guest_masked}")
                
                if all(key in reservation_data for key in ["id", "listing_id", "checkin", "checkout"]):
                    guest_hash = hashlib.sha256(f"{reservation_data.get('hospede', '')}{reservation_data.get('telefone', '')}".encode()).hexdigest()[:16]
                    
                    conn.execute(text("""
                        INSERT INTO reservations (id, listing_id, checkin, checkout, gross_total, channel, guest_hash, updated_at)
                        VALUES (:id, :listing_id, :checkin, :checkout, :gross_total, :channel, :guest_hash, NOW())
                        ON CONFLICT (id) DO UPDATE SET
                            listing_id = EXCLUDED.listing_id,
                            checkin = EXCLUDED.checkin,
                            checkout = EXCLUDED.checkout,
                            gross_total = EXCLUDED.gross_total,
                            channel = EXCLUDED.channel,
                            guest_hash = EXCLUDED.guest_hash,
                            updated_at = EXCLUDED.updated_at
                    """), {
                        "id": reservation_data["id"],
                        "listing_id": reservation_data["listing_id"],
                        "checkin": reservation_data["checkin"],
                        "checkout": reservation_data["checkout"],
                        "gross_total": float(reservation_data.get("total_bruto", 0)),
                        "channel": reservation_data.get("canal", ""),
                        "guest_hash": guest_hash
                    })
                    
                    checkin_date = datetime.strptime(reservation_data["checkin"], "%Y-%m-%d").date()
                    checkout_date = datetime.strptime(reservation_data["checkout"], "%Y-%m-%d").date()
                    
                    current_date = checkin_date
                    while current_date < checkout_date:
                        conn.execute(text("""
                            INSERT INTO calendars (listing_id, date, reserved, source)
                            VALUES (:listing_id, :date, :reserved, :source)
                            ON CONFLICT (listing_id, date) DO UPDATE SET
                                reserved = EXCLUDED.reserved,
                                source = EXCLUDED.source
                        """), {
                            "listing_id": reservation_data["listing_id"],
                            "date": current_date,
                            "reserved": True,
                            "source": "webhook"
                        })
                        current_date += timedelta(days=1)
        
        cache_store.clear_all()
        return {"ok": True, "duplicate": False}
        
    except Exception as e:
        logger.error(f"Failed to process webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")

@app.get("/unidades", response_model=List[UnidadeResponse])
async def get_unidades(token: str = Depends(verify_token)):
    if not engine:
        raise HTTPException(status_code=503, detail="Database not available")
    
    cache_key = "unidades_active"
    cached_result = cache_store.get(cache_key)
    
    if cached_result:
        return cached_result
    
    try:
        from database import DatabaseStore
        db_store = DatabaseStore()
        units = db_store.get_active_units()
        result = [UnidadeResponse(id=unit["id"], nome=unit["nome"]) for unit in units]
        cache_store.set(cache_key, result, ttl=3600)
        return result
    except Exception as e:
        logger.error(f"Failed to get units: {e}")
        raise HTTPException(status_code=503, detail="Failed to retrieve units")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
