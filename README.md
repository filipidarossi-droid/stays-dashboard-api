# Stays Dashboard API

API FastAPI para integração com a plataforma Stays, fornecendo endpoints para dashboard de ocupação, calendário e cálculos de repasse.

## 🚀 Funcionalidades

- **Autenticação**: Bearer token para proteção de webhooks
- **Calendário**: Visualização de reservas por mês com status detalhado
- **Ocupação**: Cálculo de métricas de ocupação (até hoje, futuro, fechamento)
- **Repasse**: Cálculo financeiro com base nas reservas
- **Webhooks**: Endpoint idempotente para receber atualizações da plataforma Stays
- **Persistência**: PostgreSQL para armazenamento confiável
- **Cache**: Sistema de cache em memória para otimização
- **Monitoramento**: Health check com verificação de conectividade
- **Segurança**: CORS restrito, PII mascarado, tokens seguros

## 📋 Endpoints

### Públicos
- `GET /health` - Status da API e conectividade do banco

### Protegidos (Bearer Token)
- `GET /reservas` - Lista reservas por período
- `GET /calendario` - Calendário mensal com reservas
- `GET /repasse` - Cálculo de repasse financeiro
- `POST /webhooks/stays` - Webhook idempotente para atualizações da Stays

## 🔧 Configuração

### Variáveis de Ambiente

```bash
# Banco de Dados (OBRIGATÓRIO em produção)
DATABASE_URL=postgresql://user:password@host:port/database

# Autenticação (OBRIGATÓRIO - mínimo 32 caracteres)
API_TOKEN=your-secure-token-here-minimum-32-chars

# CORS (domínios permitidos)
CORS_ORIGINS=https://stays-dashboard-web.onrender.com,https://your-custom-domain.com

# Integração Stays
STAYS_URL=https://your-account.stays.net
STAYS_LOGIN=your_username
STAYS_PASSWORD=your_password

# Configurações de Negócio
META_REPASSE=3500
INCLUIR_LIMPEZA_DEFAULT=true

# Timezone
TZ=America/Sao_Paulo
```

### Banco de Dados PostgreSQL

A API requer PostgreSQL em produção. As tabelas são criadas automaticamente:

```sql
-- Reservas
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
);

-- Calendário
CREATE TABLE IF NOT EXISTS calendars (
  id SERIAL PRIMARY KEY,
  listing_id VARCHAR,
  date DATE,
  reserved BOOLEAN,
  source VARCHAR,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(listing_id, date)
);

-- Eventos de Webhook (idempotência)
CREATE TABLE IF NOT EXISTS webhook_events (
  id SERIAL PRIMARY KEY,
  event_hash VARCHAR UNIQUE NOT NULL,
  received_at TIMESTAMP DEFAULT NOW(),
  raw JSONB
);
```

## 🏃‍♂️ Execução Local

### Pré-requisitos
- Python 3.12+
- PostgreSQL (local ou Docker)

### Setup
```bash
# Clone e entre no diretório
git clone https://github.com/filipidarossi-droid/stays-dashboard-api.git
cd stays-dashboard-api

# Crie ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# Instale dependências
pip install -r requirements.txt

# Gere token seguro
python generate_token.py

# Configure variáveis de ambiente
cp .env.example .env
# Edite .env com suas configurações

# Execute a API
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### PostgreSQL Local (Docker)
```bash
# Inicie PostgreSQL
docker run --name stays-postgres -e POSTGRES_PASSWORD=password -e POSTGRES_DB=stays -p 5432:5432 -d postgres:15

# Configure DATABASE_URL no .env
DATABASE_URL=postgresql://postgres:password@localhost:5432/stays
```

## 🚀 Deploy no Render

### 1. PostgreSQL Database
1. Render Dashboard → New → PostgreSQL
2. Nome: `stays-dashboard-db`
3. Copie a `DATABASE_URL` gerada

### 2. Web Service
1. Render Dashboard → New → Web Service
2. Conecte ao repositório GitHub
3. Configurações:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 3. Environment Variables
Adicione no Render → Settings → Environment:

```
DATABASE_URL=postgresql://...  # Da etapa 1
API_TOKEN=generate-secure-32-char-token
CORS_ORIGINS=https://stays-dashboard-web.onrender.com
STAYS_URL=https://your-account.stays.net
STAYS_LOGIN=your_username
STAYS_PASSWORD=your_password
META_REPASSE=3500
INCLUIR_LIMPEZA_DEFAULT=true
TZ=America/Sao_Paulo
```

### 4. Domínio Customizado (Opcional)
1. Render → Service → Settings → Custom Domains
2. Adicione `api.seudominio.com`
3. Configure CNAME no DNS: `api.seudominio.com` → `your-service.onrender.com`
4. Aguarde TLS ficar "Ready"
5. Atualize `CORS_ORIGINS` para incluir o novo domínio

## 🔗 Webhook da Stays

### Configuração na Plataforma Stays
```
URL: https://stays-dashboard-api.onrender.com/webhooks/stays
Método: POST
Content-Type: application/json
Authorization: Bearer YOUR_API_TOKEN
Eventos: reservation.created, reservation.updated, reservation.cancelled
```

### Teste do Webhook
```bash
curl -X POST https://stays-dashboard-api.onrender.com/webhooks/stays \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "reservation.created",
    "data": {
      "id": "RES123",
      "listing_id": "1",
      "checkin": "2025-08-20",
      "checkout": "2025-08-25",
      "total_bruto": 500.00,
      "canal": "Airbnb",
      "hospede": "João Silva"
    }
  }'
```

### Idempotência
O webhook implementa idempotência automática:
- Primeiro envio: `{"ok": true, "duplicate": false}`
- Envios duplicados: `{"ok": true, "duplicate": true}`

## 📊 Monitoramento

### Health Check
```bash
curl https://stays-dashboard-api.onrender.com/health
# Resposta: {"status": "ok"}
```

### UptimeRobot
Configure monitoramento HTTP:
- **URL**: `https://stays-dashboard-api.onrender.com/health`
- **Intervalo**: 1 minuto
- **Método**: GET
- **Esperado**: Status 200 + `{"status":"ok"}`

## 🔒 Segurança

### Token de API
- Mínimo 32 caracteres
- Use gerador seguro: `python generate_token.py`
- Rotacione periodicamente
- Nunca commite no Git

### CORS
- Restrito aos domínios específicos
- Não use `*` em produção
- Inclua todos os domínios do frontend

### Logs
- PII mascarado automaticamente
- Nomes: `João S***`
- Telefones: removidos dos logs
- IDs de hóspedes: hash SHA256

## 🛠️ Troubleshooting

### Erro 503 "Database not available"
- Verifique `DATABASE_URL` nas variáveis de ambiente
- Teste conectividade: `psql $DATABASE_URL -c "SELECT 1"`
- Verifique logs do PostgreSQL no Render

### Erro 401/403 no Webhook
- Verifique `Authorization: Bearer TOKEN`
- Confirme `API_TOKEN` nas variáveis de ambiente
- Token deve ter ≥32 caracteres

### CORS Blocked
- Adicione domínio em `CORS_ORIGINS`
- Formato: `https://domain.com,https://other.com`
- Sem espaços, separado por vírgula

### Frontend não atualiza
- Webhook configurado corretamente?
- Cache limpo após webhook?
- Verifique logs da API

### Performance
- Cache ativo (TTL 15min)
- Índices no PostgreSQL
- Connection pooling automático

## 📝 Desenvolvimento

### Estrutura do Projeto
```
stays-dashboard-api/
├── main.py              # FastAPI app principal
├── database.py          # Modelos e queries PostgreSQL
├── stays_client.py      # Cliente da API Stays
├── repasse.py           # Cálculos financeiros
├── store.py             # Cache em memória
├── generate_token.py    # Gerador de tokens seguros
├── requirements.txt     # Dependências Python
├── runtime.txt          # Versão Python (3.12.5)
├── Procfile            # Comando de start
└── README.md           # Esta documentação
```

### Padrões de Código
- FastAPI + Pydantic para validação
- SQLAlchemy para queries
- Async/await para I/O
- Logging estruturado
- Error handling com HTTPException
- Timezone: America/Sao_Paulo

### Testes
```bash
# Execute testes (quando disponíveis)
pytest

# Lint
flake8 main.py database.py

# Type check
mypy main.py
```

## 📞 Suporte

Para problemas ou dúvidas:
1. Verifique logs no Render Dashboard
2. Teste endpoints com Postman/curl
3. Confirme variáveis de ambiente
4. Verifique conectividade do banco

---

**Versão**: 2.0.0  
**Última atualização**: Agosto 2025  
**Hardening**: PostgreSQL, Segurança, Idempotência
