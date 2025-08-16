import os
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import orjson
from stays_client import StaysClient
from repasse import calcular_repasse
from store import CacheStore

load_dotenv()

app = FastAPI(title="Stays Dashboard API", version="1.0.0")

security = HTTPBearer()
cache_store = CacheStore()

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "https://stays-dashboard-web.onrender.com,http://localhost:3000,http://localhost:8080").split(",")
API_TOKEN = os.getenv("API_TOKEN", "default-token")

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

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")

@app.get("/reservas", response_model=List[ReservaResponse])
async def get_reservas(
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    listing_id: Optional[str] = Query(None),
    token: str = Depends(verify_token)
):
    cache_key = f"reservas_{from_date}_{to_date}_{listing_id or 'all'}"
    cached_result = cache_store.get(cache_key)
    
    if cached_result:
        return cached_result
    
    stays_client = StaysClient()
    reservas = await stays_client.listar_reservas(from_date, to_date, listing_id)
    
    result = [
        ReservaResponse(
            id=reserva["id"],
            listing_id=reserva["listing_id"],
            checkin=reserva["checkin"],
            checkout=reserva["checkout"],
            total_bruto=reserva["total_bruto"],
            taxas=reserva["taxas"],
            canal=reserva["canal"],
            hospede=reserva["hospede"],
            telefone=reserva.get("telefone")
        )
        for reserva in reservas
    ]
    
    cache_store.set(cache_key, result, ttl=900)  # 15 minutes
    return result

@app.get("/calendario", response_model=CalendarioResponse)
async def get_calendario(
    mes: str = Query(...),
    token: str = Depends(verify_token)
):
    cache_key = f"calendario_{mes}"
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
    
    dias = []
    for day in range(1, num_days + 1):
        day_str = f"{year}-{month:02d}-{day:02d}"
        reservas_do_dia = []
        
        for reserva in reservas:
            checkin_date = reserva["checkin"]
            checkout_date = reserva["checkout"]
            
            status = None
            if checkin_date == day_str:
                status = "checkin"
            elif checkout_date == day_str:
                status = "checkout"
            elif checkin_date < day_str < checkout_date:
                status = "ocupado"
            
            if status:
                reservas_do_dia.append({
                    "id": reserva["id"],
                    "hospede": reserva["hospede"],
                    "status": status,
                    "total_bruto": reserva["total_bruto"]
                })
        
        dias.append({
            "dia": day,
            "data": day_str,
            "reservas": reservas_do_dia
        })
    
    result = CalendarioResponse(mes=mes, dias=dias)
    cache_store.set(cache_key, result, ttl=900)  # 15 minutes
    return result

@app.get("/repasse", response_model=RepasseResponse)
async def get_repasse(
    mes: str = Query(...),
    incluir_limpeza: bool = Query(default=None),
    token: str = Depends(verify_token)
):
    if incluir_limpeza is None:
        incluir_limpeza = os.getenv("INCLUIR_LIMPEZA_DEFAULT", "true").lower() == "true"
    
    cache_key = f"repasse_{mes}_{incluir_limpeza}"
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
async def webhook_stays(payload: dict, token: str = Depends(verify_token)):
    cache_store.clear_all()
    return {"status": "webhook received", "cleared_cache": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
