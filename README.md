# Stays Dashboard API

API FastAPI para integração com a plataforma Stays, fornecendo endpoints para dashboard de ocupação, calendário e cálculos de repasse.

## 🌐 URLs de Produção

- **API**: https://stays-dashboard-api.onrender.com
- **Frontend**: https://stays-dashboard-web.onrender.com
- **Health Check**: https://stays-dashboard-api.onrender.com/health

## 🚀 Funcionalidades

- **Autenticação**: Bearer token (43 caracteres) para proteção de endpoints
- **Calendário**: Visualização de reservas por mês com status detalhado
- **Ocupação**: Cálculo de métricas de ocupação (até hoje, futuro, fechamento)
- **Repasse**: Cálculo financeiro com base nas reservas
- **Webhooks**: Endpoint idempotente para receber atualizações da plataforma Stays
- **Persistência**: PostgreSQL para armazenamento confiável
- **Cache**: Sistema de cache em memória para otimização (TTL 15min)
- **Monitoramento**: Health check com verificação de conectividade PostgreSQL
- **Segurança**: CORS restrito, PII mascarado, tokens seguros, idempotência SHA-256

## 📋 Endpoints

### Públicos
- `GET /health` - Status da API e conectividade do banco

### Protegidos (Bearer Token)
- `GET /unidades` - Lista unidades ativas
- `GET /reservas` - Lista reservas por período (com filtro opcional por unidade)
- `GET /calendario` - Calendário mensal com reservas (com filtro opcional por unidade)
- `GET /repasse` - Cálculo de repasse financeiro (com filtro opcional por unidade)
- `POST /webhooks/stays` - Webhook idempotente para atualizações da Stays

## 🔧 Configuração

### Variáveis de Ambiente (Produção)

**Obrigatórias:**
```bash
# Banco de Dados PostgreSQL (Render Internal Database URL)
DATABASE_URL=postgresql://user:password@host:port/database

# Token de Autenticação (43 caracteres - NUNCA COMMITAR)
API_TOKEN=YOUR_SECURE_43_CHAR_TOKEN_HERE

# CORS (TRAVADO para frontend de produção)
CORS_ORIGINS=https://stays-dashboard-web.onrender.com
```

**Opcionais:**
```bash
# Integração Stays (configurar quando disponível)
STAYS_URL=https://demo.stays.net
STAYS_LOGIN=demo_user
STAYS_PASSWORD=demo_pass

# Configurações de Negócio
META_REPASSE=3500
INCLUIR_LIMPEZA_DEFAULT=true

# Timezone (Brasil)
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

## 🧪 Testes de Produção

### Validação Automática
```bash
# Execute script de validação completo
./validate_production.sh

# Ou teste endpoints individuais:
curl -s https://stays-dashboard-api.onrender.com/health | jq .
curl -s -H "Authorization: Bearer TOKEN" https://stays-dashboard-api.onrender.com/unidades | jq .
curl -s -H "Authorization: Bearer TOKEN" https://stays-dashboard-api.onrender.com/calendario?mes=2025-08 | jq .
curl -s -H "Authorization: Bearer TOKEN" https://stays-dashboard-api.onrender.com/repasse?mes=2025-08 | jq .

# Teste com filtro por unidade:
curl -s -H "Authorization: Bearer TOKEN" https://stays-dashboard-api.onrender.com/calendario?mes=2025-08&unidade_id=CLO04 | jq .
curl -s -H "Authorization: Bearer TOKEN" https://stays-dashboard-api.onrender.com/repasse?mes=2025-08&unidade_id=CLO04 | jq .
```

### Teste de Webhook Idempotente
```bash
TOKEN="YOUR_SECURE_43_CHAR_TOKEN_HERE"
PAYLOAD='{"event":"test","reservation_id":"TEST-123","updated_at":"2025-08-16T15:45:00Z"}'

# 1ª chamada (deve processar)
curl -X POST https://stays-dashboard-api.onrender.com/webhooks/stays \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
# Resposta: {"ok": true, "duplicate": false}

# 2ª chamada (deve detectar duplicata)
curl -X POST https://stays-dashboard-api.onrender.com/webhooks/stays \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
# Resposta: {"ok": true, "duplicate": true}
```

## 🏃‍♂️ Execução Local (Desenvolvimento)

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

# Gere token seguro para desenvolvimento
python generate_token.py

# Configure variáveis de ambiente
cp .env .env.local
# Edite .env.local com configurações locais

# Execute a API
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### PostgreSQL Local (Docker)
```bash
# Inicie PostgreSQL
docker run --name stays-postgres -e POSTGRES_PASSWORD=password -e POSTGRES_DB=stays -p 5432:5432 -d postgres:15

# Configure DATABASE_URL no .env.local
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

## 📊 Monitoramento com UptimeRobot

### Configuração Manual (CAPTCHA)
1. Acesse: https://dashboard.uptimerobot.com/sign-up
2. Complete o registro (resolver CAPTCHA manualmente)
3. Crie 2 monitores HTTP(s):

**Monitor 1 - API Health:**
- Nome: `Stays API - Health`
- URL: `https://stays-dashboard-api.onrender.com/health`
- Intervalo: 1 minuto
- Método: GET
- Palavra-chave esperada: `ok`

**Monitor 2 - Frontend:**
- Nome: `Stays Dashboard - Web`
- URL: `https://stays-dashboard-web.onrender.com/`
- Intervalo: 5 minutos
- Método: GET

### Health Check Manual
```bash
curl https://stays-dashboard-api.onrender.com/health
# Resposta esperada: {"status": "ok"}
```

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

## 🔧 Como Migrar para Domínio Próprio (Futuro)

### 1. Adicionar Domínios Customizados no Render
```
API: api.seudominio.com
Frontend: dash.seudominio.com
```

### 2. Configurar DNS (CNAMEs)
```
Host: api
Tipo: CNAME
Aponta para: stays-dashboard-api.onrender.com

Host: dash
Tipo: CNAME
Aponta para: stays-dashboard-web.onrender.com
```

### 3. Atualizar CORS na API
```bash
CORS_ORIGINS=https://dash.seudominio.com,https://stays-dashboard-web.onrender.com
```

### 4. Atualizar Frontend config.js
```javascript
window.CONFIG = {
  API_BASE_URL: 'https://api.seudominio.com'
};
```

### 5. Testes de Validação
```bash
curl -I https://api.seudominio.com/health
curl -I https://dash.seudominio.com/

# No console do navegador (dash.seudominio.com):
fetch('https://api.seudominio.com/calendario', {cache:'no-store'})
  .then(r => (console.log('CORS:', r.headers.get('access-control-allow-origin')), r.json()))
  .then(console.log);
```

## 🛠️ Troubleshooting

### Erro 503 "Database not available"
- Verifique `DATABASE_URL` nas variáveis de ambiente do Render
- Teste conectividade PostgreSQL nos logs
- Confirme que o banco está ativo no Render Dashboard

### Erro 401/403 no Webhook
- Verifique header: `Authorization: Bearer YOUR_SECURE_43_CHAR_TOKEN_HERE`
- Confirme `API_TOKEN` nas variáveis de ambiente
- Token deve ter exatamente 43 caracteres

### CORS Blocked
- CORS travado para: `https://stays-dashboard-web.onrender.com`
- Para adicionar domínio: atualize `CORS_ORIGINS` no Render
- Formato: `https://domain1.com,https://domain2.com` (sem espaços)

### Frontend não atualiza
- Webhook configurado na plataforma Stays?
- Cache limpo após webhook (TTL 15min)?
- Verifique logs da API no Render Dashboard

### Performance
- Cache ativo (TTL 15min para todos os endpoints)
- Índices PostgreSQL criados automaticamente
- Connection pooling (5 conexões + 5 overflow)

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

## 📋 Endpoints Detalhados

### GET /unidades
Lista todas as unidades ativas no sistema.

**Headers:**
- `Authorization: Bearer <API_TOKEN>`

**Resposta:**
```json
[
  {
    "id": "CLO04",
    "nome": "Unidade CLO04"
  },
  {
    "id": "CLO05", 
    "nome": "Unidade CLO05"
  }
]
```

### GET /reservas
Lista reservas em um período específico.

**Parâmetros:**
- `from` (obrigatório): Data inicial (YYYY-MM-DD)
- `to` (obrigatório): Data final (YYYY-MM-DD)
- `listing_id` (opcional): Filtrar por unidade específica (compatibilidade)
- `unidade_id` (opcional): Filtrar por unidade específica

**Headers:**
- `Authorization: Bearer <API_TOKEN>`

**Resposta:**
```json
[
  {
    "id": "RES123",
    "listing_id": "UNIT001",
    "checkin": "2025-08-15",
    "checkout": "2025-08-20",
    "total_bruto": 1500.00,
    "taxas": 150.00,
    "canal": "Airbnb",
    "hospede": "João S***",
    "telefone": null
  }
]
```

### GET /calendario
Retorna calendário mensal com reservas e métricas.

**Parâmetros:**
- `mes` (obrigatório): Mês no formato YYYY-MM
- `unidade_id` (opcional): Filtrar por unidade específica

**Headers:**
- `Authorization: Bearer <API_TOKEN>`

**Resposta:**
```json
{
  "mes": "2025-08",
  "dias": [
    {
      "dia": 1,
      "data": "2025-08-01",
      "reservas": [
        {
          "id": "RES123",
          "hospede": "João S***",
          "status": "checkin",
          "total_bruto": 1500.00
        }
      ]
    }
  ]
}
```

### GET /repasse
Calcula repasse mensal com base nas reservas.

**Parâmetros:**
- `mes` (obrigatório): Mês no formato YYYY-MM
- `incluir_limpeza` (opcional): true/false (padrão: true)
- `unidade_id` (opcional): Filtrar por unidade específica

**Headers:**
- `Authorization: Bearer <API_TOKEN>`

**Resposta:**
```json
{
  "meta": 3500.0,
  "repasse_estimado": 2850.75,
  "status": "em progresso",
  "detalhes": {
    "total_vendas": 4200.00,
    "total_limpeza": 420.00,
    "total_taxa_api": 126.00,
    "total_comissao_anfitriao": 420.00,
    "incluiu_limpeza": true,
    "numero_reservas": 3
  }
}
```



---

**Versão**: 2.0.0  
**Última atualização**: Agosto 2025  
**Hardening**: PostgreSQL, Segurança, Idempotência
