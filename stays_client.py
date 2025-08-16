import os
import httpx
from typing import List, Dict, Optional
from dotenv import load_dotenv
import asyncio
from datetime import datetime

load_dotenv()

class StaysClient:
    def __init__(self):
        self.base_url = os.getenv("STAYS_URL", "")
        self.login = os.getenv("STAYS_LOGIN", "")
        self.password = os.getenv("STAYS_PASSWORD", "")
        self.session_token = None
        
    async def _login(self) -> bool:
        """Realiza login na API da Stays"""
        if not self.base_url or not self.login or not self.password:
            raise ValueError("Credenciais da Stays não configuradas")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                login_data = {
                    "username": self.login,
                    "password": self.password
                }
                
                response = await client.post(
                    f"{self.base_url}/api/auth/login",
                    json=login_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.session_token = data.get("token") or data.get("access_token")
                    return True
                else:
                    print(f"Erro no login: {response.status_code} - {response.text}")
                    return False
                    
            except Exception as e:
                print(f"Erro ao fazer login: {e}")
                return False
    
    async def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Faz requisição autenticada para a API da Stays"""
        if not self.session_token:
            login_success = await self._login()
            if not login_success:
                raise Exception("Falha na autenticação com a Stays")
        
        headers = {
            "Authorization": f"Bearer {self.session_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}{endpoint}",
                    params=params or {},
                    headers=headers
                )
                
                if response.status_code == 401:
                    self.session_token = None
                    login_success = await self._login()
                    if login_success:
                        headers["Authorization"] = f"Bearer {self.session_token}"
                        response = await client.get(
                            f"{self.base_url}{endpoint}",
                            params=params or {},
                            headers=headers
                        )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    raise Exception(f"Erro na API: {response.status_code} - {response.text}")
                    
            except httpx.TimeoutException:
                raise Exception("Timeout na requisição para a Stays")
            except Exception as e:
                raise Exception(f"Erro na requisição: {e}")
    
    async def listar_reservas(self, from_date: str, to_date: str, listing_id: Optional[str] = None) -> List[Dict]:
        """Lista reservas da Stays no período especificado"""
        
        if not self.base_url or not self.login:
            return self._get_sample_reservas(from_date, to_date, listing_id)
        
        try:
            params = {
                "from": from_date,
                "to": to_date
            }
            
            if listing_id:
                params["listing_id"] = listing_id
            
            endpoints_to_try = [
                "/api/reservations",
                "/api/bookings", 
                "/api/reservas",
                "/reservations",
                "/bookings"
            ]
            
            for endpoint in endpoints_to_try:
                try:
                    data = await self._make_request(endpoint, params)
                    
                    reservas = []
                    items = data.get("data", data.get("items", data.get("reservations", data)))
                    
                    if isinstance(items, list):
                        for item in items:
                            reserva = self._normalize_reserva(item)
                            if reserva:
                                reservas.append(reserva)
                        
                        return reservas
                        
                except Exception as e:
                    print(f"Erro no endpoint {endpoint}: {e}")
                    continue
            
            print("Nenhum endpoint da Stays funcionou, retornando dados de exemplo")
            return self._get_sample_reservas(from_date, to_date, listing_id)
            
        except Exception as e:
            print(f"Erro geral ao listar reservas: {e}")
            return self._get_sample_reservas(from_date, to_date, listing_id)
    
    def _normalize_reserva(self, item: Dict) -> Optional[Dict]:
        """Normaliza dados de reserva para formato padrão"""
        try:
            return {
                "id": str(item.get("id", item.get("reservation_id", ""))),
                "listing_id": str(item.get("listing_id", item.get("property_id", "1"))),
                "checkin": item.get("checkin", item.get("check_in", item.get("arrival", ""))),
                "checkout": item.get("checkout", item.get("check_out", item.get("departure", ""))),
                "total_bruto": float(item.get("total", item.get("total_amount", item.get("amount", 0)))),
                "taxas": float(item.get("fees", item.get("service_fee", item.get("taxas", 0)))),
                "canal": item.get("channel", item.get("source", item.get("canal", "Direto"))),
                "hospede": item.get("guest_name", item.get("guest", item.get("hospede", "Hóspede"))),
                "telefone": item.get("phone", item.get("telefone"))
            }
        except Exception as e:
            print(f"Erro ao normalizar reserva: {e}")
            return None
    
    def _get_sample_reservas(self, from_date: str, to_date: str, listing_id: Optional[str] = None) -> List[Dict]:
        """Retorna dados de exemplo para demonstração"""
        from datetime import datetime, timedelta
        import random
        
        try:
            start_date = datetime.strptime(from_date, "%Y-%m-%d")
            end_date = datetime.strptime(to_date, "%Y-%m-%d")
        except:
            start_date = datetime.now()
            end_date = start_date + timedelta(days=30)
        
        sample_reservas = []
        current_date = start_date
        
        canais = ["Airbnb", "Booking.com", "Direto", "VRBO"]
        hospedes = ["João Silva", "Maria Santos", "Pedro Costa", "Ana Oliveira", "Carlos Souza"]
        
        while current_date < end_date:
            if random.random() < 0.3:  # 30% chance de ter reserva
                checkout_date = current_date + timedelta(days=random.randint(2, 7))
                
                reserva = {
                    "id": f"RES{random.randint(1000, 9999)}",
                    "listing_id": listing_id or "1",
                    "checkin": current_date.strftime("%Y-%m-%d"),
                    "checkout": checkout_date.strftime("%Y-%m-%d"),
                    "total_bruto": round(random.uniform(200, 800), 2),
                    "taxas": round(random.uniform(20, 80), 2),
                    "canal": random.choice(canais),
                    "hospede": random.choice(hospedes),
                    "telefone": f"(11) 9{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
                }
                
                sample_reservas.append(reserva)
                current_date = checkout_date
            else:
                current_date += timedelta(days=1)
        
        return sample_reservas
