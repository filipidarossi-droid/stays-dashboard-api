#!/bin/bash


set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

API_BASE=${1:-"https://stays-dashboard-api.onrender.com"}
WEB_BASE=${2:-"https://stays-dashboard-web.onrender.com"}
API_TOKEN="OkcL1yODuVSaB725koNMGL_Gml28lJIrxeV9RWfbHxE"

echo -e "${YELLOW}=== Stays Dashboard Production Validation ===${NC}"
echo "API Base: $API_BASE"
echo "Web Base: $WEB_BASE"
echo ""

echo -e "${YELLOW}1. Testing Health Endpoint${NC}"
HEALTH_RESPONSE=$(curl -s -w "%{http_code}" "$API_BASE/health")
HTTP_CODE="${HEALTH_RESPONSE: -3}"
HEALTH_BODY="${HEALTH_RESPONSE%???}"

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Health check passed${NC}"
    echo "Response: $HEALTH_BODY"
else
    echo -e "${RED}❌ Health check failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $HEALTH_BODY"
fi
echo ""

echo -e "${YELLOW}2. Testing Protected API Endpoints${NC}"

echo "Testing /calendario..."
CALENDARIO_RESPONSE=$(curl -s -w "%{http_code}" \
    -H "Authorization: Bearer $API_TOKEN" \
    "$API_BASE/calendario?mes=2025-08")
HTTP_CODE="${CALENDARIO_RESPONSE: -3}"
CALENDARIO_BODY="${CALENDARIO_RESPONSE%???}"

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Calendario endpoint working${NC}"
    echo "Sample: $(echo "$CALENDARIO_BODY" | jq -r '.mes // "No mes field"')"
else
    echo -e "${RED}❌ Calendario endpoint failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $CALENDARIO_BODY"
fi

echo "Testing /repasse..."
REPASSE_RESPONSE=$(curl -s -w "%{http_code}" \
    -H "Authorization: Bearer $API_TOKEN" \
    "$API_BASE/repasse?mes=2025-08")
HTTP_CODE="${REPASSE_RESPONSE: -3}"
REPASSE_BODY="${REPASSE_RESPONSE%???}"

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Repasse endpoint working${NC}"
    echo "Meta: $(echo "$REPASSE_BODY" | jq -r '.meta // "No meta field"')"
else
    echo -e "${RED}❌ Repasse endpoint failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $REPASSE_BODY"
fi

echo "Testing /reservas..."
RESERVAS_RESPONSE=$(curl -s -w "%{http_code}" \
    -H "Authorization: Bearer $API_TOKEN" \
    "$API_BASE/reservas?from=2025-08-01&to=2025-08-31")
HTTP_CODE="${RESERVAS_RESPONSE: -3}"
RESERVAS_BODY="${RESERVAS_RESPONSE%???}"

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Reservas endpoint working${NC}"
    echo "Count: $(echo "$RESERVAS_BODY" | jq '. | length')"
else
    echo -e "${RED}❌ Reservas endpoint failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $RESERVAS_BODY"
fi
echo ""

echo -e "${YELLOW}3. Testing Authentication${NC}"

echo "Testing without Authorization header..."
NO_AUTH_RESPONSE=$(curl -s -w "%{http_code}" "$API_BASE/calendario?mes=2025-08")
HTTP_CODE="${NO_AUTH_RESPONSE: -3}"

if [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
    echo -e "${GREEN}✅ Authentication properly enforced${NC}"
else
    echo -e "${RED}❌ Authentication not working (HTTP $HTTP_CODE)${NC}"
fi

echo "Testing with invalid token..."
BAD_AUTH_RESPONSE=$(curl -s -w "%{http_code}" \
    -H "Authorization: Bearer invalid-token" \
    "$API_BASE/calendario?mes=2025-08")
HTTP_CODE="${BAD_AUTH_RESPONSE: -3}"

if [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
    echo -e "${GREEN}✅ Invalid token properly rejected${NC}"
else
    echo -e "${RED}❌ Invalid token not rejected (HTTP $HTTP_CODE)${NC}"
fi
echo ""

echo -e "${YELLOW}4. Testing Webhook Idempotency${NC}"

WEBHOOK_PAYLOAD='{"event":"validation_test","reservation_id":"VAL-123","updated_at":"2025-08-16T15:45:00Z"}'

echo "First webhook call (should process)..."
WEBHOOK1_RESPONSE=$(curl -s -w "%{http_code}" \
    -X POST \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$WEBHOOK_PAYLOAD" \
    "$API_BASE/webhooks/stays")
HTTP_CODE="${WEBHOOK1_RESPONSE: -3}"
WEBHOOK1_BODY="${WEBHOOK1_RESPONSE%???}"

if [ "$HTTP_CODE" = "200" ]; then
    DUPLICATE1=$(echo "$WEBHOOK1_BODY" | jq -r '.duplicate')
    if [ "$DUPLICATE1" = "false" ]; then
        echo -e "${GREEN}✅ First webhook call processed${NC}"
    else
        echo -e "${YELLOW}⚠️ First webhook call marked as duplicate${NC}"
    fi
else
    echo -e "${RED}❌ First webhook call failed (HTTP $HTTP_CODE)${NC}"
fi

echo "Second webhook call (should be duplicate)..."
WEBHOOK2_RESPONSE=$(curl -s -w "%{http_code}" \
    -X POST \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$WEBHOOK_PAYLOAD" \
    "$API_BASE/webhooks/stays")
HTTP_CODE="${WEBHOOK2_RESPONSE: -3}"
WEBHOOK2_BODY="${WEBHOOK2_RESPONSE%???}"

if [ "$HTTP_CODE" = "200" ]; then
    DUPLICATE2=$(echo "$WEBHOOK2_BODY" | jq -r '.duplicate')
    if [ "$DUPLICATE2" = "true" ]; then
        echo -e "${GREEN}✅ Second webhook call properly detected as duplicate${NC}"
    else
        echo -e "${RED}❌ Second webhook call not detected as duplicate${NC}"
    fi
else
    echo -e "${RED}❌ Second webhook call failed (HTTP $HTTP_CODE)${NC}"
fi
echo ""

if [ "$1" != "" ]; then
    echo -e "${YELLOW}5. Testing CORS Headers${NC}"
    
    CORS_RESPONSE=$(curl -s -I "$API_BASE/health")
    CORS_ORIGIN=$(echo "$CORS_RESPONSE" | grep -i "access-control-allow-origin" | cut -d' ' -f2- | tr -d '\r\n')
    
    if [ -n "$CORS_ORIGIN" ]; then
        echo -e "${GREEN}✅ CORS headers present${NC}"
        echo "Allowed Origin: $CORS_ORIGIN"
    else
        echo -e "${YELLOW}⚠️ No CORS headers found${NC}"
    fi
    echo ""
fi

echo -e "${YELLOW}6. Testing Frontend Accessibility${NC}"
FRONTEND_RESPONSE=$(curl -s -w "%{http_code}" "$WEB_BASE/")
HTTP_CODE="${FRONTEND_RESPONSE: -3}"

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Frontend accessible${NC}"
    if echo "${FRONTEND_RESPONSE%???}" | grep -q "Stays Dashboard"; then
        echo -e "${GREEN}✅ Frontend contains expected content${NC}"
    else
        echo -e "${YELLOW}⚠️ Frontend may not be fully loaded${NC}"
    fi
else
    echo -e "${RED}❌ Frontend not accessible (HTTP $HTTP_CODE)${NC}"
fi
echo ""

echo -e "${YELLOW}=== Validation Summary ===${NC}"
echo "✅ = Pass, ❌ = Fail, ⚠️ = Warning"
echo ""
echo "Next steps:"
echo "1. Set up UptimeRobot monitoring for both URLs"
echo "2. Configure custom domains if not already done"
echo "3. Update Stays platform webhook configuration"
echo "4. Monitor logs for any issues"
echo ""
echo "For support, check:"
echo "- Render logs: https://dashboard.render.com"
echo "- API health: $API_BASE/health"
echo "- Frontend: $WEB_BASE"
