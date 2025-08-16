import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

def calcular_repasse(reservas: List[Dict], incluir_limpeza: bool = True) -> Dict:
    """
    Calcula o repasse baseado nas reservas
    Fórmula: repasse = valor_venda - taxa_limpeza(opcional) - taxa_api - comissao_anfitriao
    """
    
    meta_repasse = float(os.getenv("META_REPASSE", "3500"))
    
    total_vendas = 0
    total_taxas = 0
    total_limpeza = 0
    total_comissao_anfitriao = 0
    total_taxa_api = 0
    
    detalhes_reservas = []
    
    for reserva in reservas:
        valor_bruto = reserva.get("total_bruto", 0)
        taxas = reserva.get("taxas", 0)
        
        taxa_limpeza = valor_bruto * 0.15 if incluir_limpeza else 0  # 15% para limpeza
        taxa_api = valor_bruto * 0.03  # 3% taxa da plataforma/API
        comissao_anfitriao = valor_bruto * 0.10  # 10% comissão do anfitrião
        
        repasse_reserva = valor_bruto - taxa_limpeza - taxa_api - comissao_anfitriao - taxas
        
        total_vendas += valor_bruto
        total_taxas += taxas
        total_limpeza += taxa_limpeza
        total_taxa_api += taxa_api
        total_comissao_anfitriao += comissao_anfitriao
        
        detalhes_reservas.append({
            "id": reserva.get("id"),
            "hospede": reserva.get("hospede"),
            "checkin": reserva.get("checkin"),
            "checkout": reserva.get("checkout"),
            "valor_bruto": valor_bruto,
            "taxa_limpeza": taxa_limpeza,
            "taxa_api": taxa_api,
            "comissao_anfitriao": comissao_anfitriao,
            "taxas_extras": taxas,
            "repasse_liquido": repasse_reserva
        })
    
    repasse_total = total_vendas - total_limpeza - total_taxa_api - total_comissao_anfitriao - total_taxas
    
    if repasse_total >= meta_repasse:
        status = "meta batida"
    elif repasse_total >= meta_repasse * 0.8:
        status = "próximo da meta"
    elif repasse_total >= meta_repasse * 0.5:
        status = "em progresso"
    else:
        status = "início do período"
    
    return {
        "meta": meta_repasse,
        "repasse_estimado": round(repasse_total, 2),
        "status": status,
        "detalhes": {
            "total_vendas": round(total_vendas, 2),
            "total_limpeza": round(total_limpeza, 2) if incluir_limpeza else 0,
            "total_taxa_api": round(total_taxa_api, 2),
            "total_comissao_anfitriao": round(total_comissao_anfitriao, 2),
            "total_taxas_extras": round(total_taxas, 2),
            "incluiu_limpeza": incluir_limpeza,
            "numero_reservas": len(reservas),
            "reservas": detalhes_reservas
        }
    }

def calcular_ocupacao(reservas: List[Dict], periodo_dias: int) -> Dict:
    """
    Calcula métricas de ocupação
    """
    dias_ocupados = 0
    
    dias_com_reserva = set()
    
    for reserva in reservas:
        try:
            from datetime import datetime, timedelta
            checkin = datetime.strptime(reserva.get("checkin", ""), "%Y-%m-%d")
            checkout = datetime.strptime(reserva.get("checkout", ""), "%Y-%m-%d")
            
            current_date = checkin
            while current_date < checkout:
                dias_com_reserva.add(current_date.strftime("%Y-%m-%d"))
                current_date += timedelta(days=1)
                
        except Exception as e:
            print(f"Erro ao calcular ocupação para reserva {reserva.get('id')}: {e}")
            continue
    
    dias_ocupados = len(dias_com_reserva)
    taxa_ocupacao = (dias_ocupados / periodo_dias * 100) if periodo_dias > 0 else 0
    
    return {
        "dias_ocupados": dias_ocupados,
        "dias_totais": periodo_dias,
        "taxa_ocupacao": round(taxa_ocupacao, 2),
        "dias_livres": periodo_dias - dias_ocupados
    }
