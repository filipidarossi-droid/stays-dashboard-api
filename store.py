import os
import json
import time
from typing import Any, Optional
from diskcache import Cache
from pathlib import Path

class CacheStore:
    def __init__(self, cache_dir: str = "/tmp/stays_cache"):
        """
        Cache simples com TTL usando diskcache (pure Python)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        self.cache = Cache(str(self.cache_dir))
        
        self.memory_cache = {}
        self.memory_ttl = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Recupera valor do cache"""
        if key in self.memory_cache:
            if key in self.memory_ttl and time.time() > self.memory_ttl[key]:
                del self.memory_cache[key]
                del self.memory_ttl[key]
            else:
                return self.memory_cache[key]
        
        try:
            value = self.cache.get(key)
            if value is not None:
                self.memory_cache[key] = value
                return value
        except Exception as e:
            print(f"Erro ao acessar cache em disco: {e}")
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = 900) -> bool:
        """
        Armazena valor no cache com TTL
        ttl: tempo de vida em segundos (padrão: 15 minutos)
        """
        try:
            self.memory_cache[key] = value
            self.memory_ttl[key] = time.time() + ttl
            
            self.cache.set(key, value, expire=ttl)
            
            return True
        except Exception as e:
            print(f"Erro ao armazenar no cache: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Remove item do cache"""
        try:
            if key in self.memory_cache:
                del self.memory_cache[key]
            if key in self.memory_ttl:
                del self.memory_ttl[key]
            
            self.cache.delete(key)
            
            return True
        except Exception as e:
            print(f"Erro ao remover do cache: {e}")
            return False
    
    def clear_all(self) -> bool:
        """Limpa todo o cache"""
        try:
            self.memory_cache.clear()
            self.memory_ttl.clear()
            
            self.cache.clear()
            
            return True
        except Exception as e:
            print(f"Erro ao limpar cache: {e}")
            return False
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do cache"""
        try:
            disk_stats = dict(self.cache.stats())
            
            return {
                "memory_items": len(self.memory_cache),
                "disk_stats": disk_stats,
                "cache_dir": str(self.cache_dir)
            }
        except Exception as e:
            print(f"Erro ao obter estatísticas: {e}")
            return {"error": str(e)}
    
    def cleanup_expired(self):
        """Remove itens expirados do cache em memória"""
        current_time = time.time()
        expired_keys = [
            key for key, expire_time in self.memory_ttl.items()
            if current_time > expire_time
        ]
        
        for key in expired_keys:
            if key in self.memory_cache:
                del self.memory_cache[key]
            if key in self.memory_ttl:
                del self.memory_ttl[key]
        
        return len(expired_keys)
