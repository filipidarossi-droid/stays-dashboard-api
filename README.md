# Stays Dashboard API

API FastAPI para integração com a plataforma Stays, fornecendo endpoints para consulta de reservas, calendário e cálculo de repasse.

## 🚀 Funcionalidades

- **GET /health** - Health check da API
- **GET /reservas** - Lista reservas por período
- **GET /calendario** - Visualização de calendário com reservas
- **GET /repasse** - Cálculo de repasse com base nas reservas
- **POST /webhooks/stays** - Webhook para atualizações da Stays (opcional)

## 📋 Pré-requisitos

- Python 3.10+
- Conta na Stays com credenciais de API
- Conta no Render para deploy

## 🛠️ Instalação Local

### 1. Clone o repositório
```bash
git clone <repository-url>
cd stays-dashboard-api
```

### 2. Crie ambiente virtual
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows
```

### 3. Instale dependências
```bash
pip install -r requirements.txt
```

### 4. Configure variáveis de ambiente
```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas credenciais:
```env
STAYS_URL=https://sua-conta.stays.net
STAYS_LOGIN=seu_login
STAYS_PASSWORD=sua_senha
API_TOKEN=seu_token_seguro_aqui
CORS_ORIGINS=https://seu-dominio.com,http://localhost:3000
META_REPASSE=3500
INCLUIR_LIMPEZA_DEFAULT=true
```

### 5. Execute a aplicação
```bash
uvicorn main:app --reload
```

A API estará disponível em: http://localhost:8000

## 📚 Documentação da API

### Autenticação

Todos os endpoints (exceto `/health`) requerem autenticação via Bearer Token:

```bash
curl -H "Authorization: Bearer SEU_TOKEN" http://localhost:8000/reservas
```

### Endpoints

#### GET /health
```bash
curl http://localhost:8000/health
```
Resposta:
```json
{"status": "ok"}
```

#### GET /reservas
```bash
curl -H "Authorization: Bearer SEU_TOKEN" \
  "http://localhost:8000/reservas?from=2025-08-01&to=2025-08-31&listing_id=1"
```

Parâmetros:
- `from` (obrigatório): Data inicial (YYYY-MM-DD)
- `to` (obrigatório): Data final (YYYY-MM-DD)
- `listing_id` (opcional): ID do imóvel

#### GET /calendario
```bash
curl -H "Authorization: Bearer SEU_TOKEN" \
  "http://localhost:8000/calendario?mes=2025-08"
```

Parâmetros:
- `mes` (obrigatório): Mês no formato YYYY-MM

#### GET /repasse
```bash
curl -H "Authorization: Bearer SEU_TOKEN" \
  "http://localhost:8000/repasse?mes=2025-08&incluir_limpeza=true"
```

Parâmetros:
- `mes` (obrigatório): Mês no formato YYYY-MM
- `incluir_limpeza` (opcional): true/false, padrão definido em INCLUIR_LIMPEZA_DEFAULT

#### POST /webhooks/stays
```bash
curl -X POST -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event": "reservation_updated"}' \
  http://localhost:8000/webhooks/stays
```

## 🚀 Deploy no Render

### 1. Conecte o repositório
- Acesse [Render](https://render.com)
- Conecte sua conta GitHub
- Selecione o repositório

### 2. Configure o Web Service
- **Runtime**: Python 3
- **Branch**: main
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers`

### 3. Configure variáveis de ambiente
No painel do Render, adicione:
- `STAYS_URL`
- `STAYS_LOGIN`
- `STAYS_PASSWORD`
- `API_TOKEN`
- `CORS_ORIGINS`
- `META_REPASSE`
- `INCLUIR_LIMPEZA_DEFAULT`

### 4. Deploy automático
- Habilite "Auto-Deploy" para deploy automático a cada push na branch main

## 🔧 Estrutura do Projeto

```
stays-dashboard-api/
├── main.py              # Aplicação FastAPI principal
├── stays_client.py      # Cliente para API da Stays
├── repasse.py          # Cálculos de repasse
├── store.py            # Sistema de cache
├── requirements.txt    # Dependências Python
├── runtime.txt         # Versão do Python
├── Procfile           # Configuração do Render
├── .env.example       # Exemplo de variáveis de ambiente
└── README.md          # Este arquivo
```

## 📊 Cálculo de Repasse

A fórmula utilizada:
```
repasse = valor_venda - taxa_limpeza(opcional) - taxa_api - comissao_anfitriao
```

Percentuais padrão:
- Taxa de limpeza: 15% (se incluir_limpeza=true)
- Taxa da API/plataforma: 3%
- Comissão do anfitrião: 10%

## 🔄 Cache

A API utiliza cache com TTL de 15 minutos para:
- Consultas de reservas
- Dados do calendário
- Cálculos de repasse

O cache é limpo automaticamente via webhook `/webhooks/stays`.

## 🧪 Testes

### Teste local com curl
```bash
# Health check
curl http://localhost:8000/health

# Teste com autenticação
export TOKEN="seu_token_aqui"
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/reservas?from=2025-08-01&to=2025-08-31"
```

### Teste de CORS
```bash
curl -H "Origin: https://seu-dominio.com" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization" \
  -X OPTIONS http://localhost:8000/reservas
```

## 🐛 Troubleshooting

### Erro de build no Render
- Verifique se todas as dependências em `requirements.txt` são compatíveis
- Confirme que `runtime.txt` especifica Python 3.10.13
- Evite pacotes que requerem compilação (Rust, C++)

### Erro de autenticação
- Verifique se `API_TOKEN` está configurado corretamente
- Confirme que o header `Authorization: Bearer TOKEN` está sendo enviado

### Erro de CORS
- Verifique se `CORS_ORIGINS` inclui o domínio correto
- Para desenvolvimento local, inclua `http://localhost:3000`

## 📝 Logs

Para visualizar logs no Render:
```bash
# Via CLI do Render (se instalado)
render logs -s seu-service-id

# Ou acesse o painel web do Render
```

## 🔐 Segurança

- Nunca commite credenciais no repositório
- Use tokens seguros para `API_TOKEN`
- Configure `CORS_ORIGINS` apenas para domínios confiáveis
- Monitore logs para tentativas de acesso não autorizado

## 📞 Suporte

Para problemas com a integração Stays:
1. Verifique as credenciais em `STAYS_URL`, `STAYS_LOGIN`, `STAYS_PASSWORD`
2. Confirme se a API da Stays está acessível
3. Verifique os logs da aplicação para erros específicos

## 🔄 Atualizações

Para atualizar a aplicação:
1. Faça as alterações no código
2. Commit e push para a branch main
3. O Render fará deploy automático
4. Monitore os logs para confirmar sucesso
