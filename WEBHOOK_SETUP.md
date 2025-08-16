# Webhook Configuration Guide - Stays Platform

## Overview
The Stays Dashboard API provides a secure, idempotent webhook endpoint for receiving real-time updates from the Stays platform.

## Webhook Endpoint
```
POST https://stays-dashboard-api.onrender.com/webhooks/stays
```

## Authentication
**Required Headers:**
```
Authorization: Bearer OkcL1yODuVSaB725koNMGL_Gml28lJIrxeV9RWfbHxE
Content-Type: application/json
```

## Configuration in Stays Platform

### Step 1: Access Stays API Settings
1. Login to your Stays account
2. Navigate to **App Center** → **API Stays** → **Chaves da API**
3. Look for "Link de notificações" or "Webhook URL" section

### Step 2: Configure Webhook URL
```
URL: https://stays-dashboard-api.onrender.com/webhooks/stays
Method: POST
Content-Type: application/json
Authorization: Bearer OkcL1yODuVSaB725koNMGL_Gml28lJIrxeV9RWfbHxE
```

### Step 3: Select Events
Enable these events for real-time updates:
- `reservation.created`
- `reservation.updated` 
- `reservation.cancelled`
- `calendar.updated`

## Testing the Webhook

### Test 1: Basic Connectivity
```bash
curl -X POST https://stays-dashboard-api.onrender.com/webhooks/stays \
  -H "Authorization: Bearer OkcL1yODuVSaB725koNMGL_Gml28lJIrxeV9RWfbHxE" \
  -H "Content-Type: application/json" \
  -d '{"event":"test","data":{"message":"connectivity test"}}'
```

**Expected Response:**
```json
{"ok": true, "duplicate": false}
```

### Test 2: Idempotency Check
Run the same command twice - second call should return:
```json
{"ok": true, "duplicate": true}
```

### Test 3: Reservation Event
```bash
curl -X POST https://stays-dashboard-api.onrender.com/webhooks/stays \
  -H "Authorization: Bearer OkcL1yODuVSaB725koNMGL_Gml28lJIrxeV9RWfbHxE" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "reservation.created",
    "data": {
      "id": "RES12345",
      "listing_id": "1",
      "checkin": "2025-08-20",
      "checkout": "2025-08-25",
      "total_bruto": 500.00,
      "canal": "Airbnb",
      "hospede": "João Silva",
      "telefone": "+5511999999999"
    }
  }'
```

## Security Features

### 1. Bearer Token Authentication
- 43-character secure token
- All requests without valid token return 401/403
- Token should be rotated periodically

### 2. Idempotency Protection
- SHA-256 hash of payload prevents duplicate processing
- Duplicate events return `{"ok": true, "duplicate": true}`
- No data duplication in database

### 3. PII Masking
- Guest names logged as "João S***"
- Phone numbers removed from logs
- Only event hashes and IDs logged for debugging

## Response Codes

| Code | Meaning | Response |
|------|---------|----------|
| 200 | Success - New event | `{"ok": true, "duplicate": false}` |
| 200 | Success - Duplicate | `{"ok": true, "duplicate": true}` |
| 401 | Missing Authorization | `{"detail": "Not authenticated"}` |
| 403 | Invalid token | `{"detail": "Forbidden"}` |
| 422 | Invalid JSON | `{"detail": "Validation error"}` |

## Troubleshooting

### Issue: 401 Unauthorized
**Cause:** Missing or malformed Authorization header
**Solution:** Ensure header format: `Authorization: Bearer TOKEN`

### Issue: 403 Forbidden  
**Cause:** Invalid or expired token
**Solution:** Verify token matches: `OkcL1yODuVSaB725koNMGL_Gml28lJIrxeV9RWfbHxE`

### Issue: Webhook not triggering
**Cause:** Stays platform configuration
**Solution:** 
1. Verify URL in Stays settings
2. Check event types are enabled
3. Test with curl command above

### Issue: Data not updating in dashboard
**Cause:** Webhook payload format mismatch
**Solution:** Check Render logs for processing errors

## Monitoring

### Health Check
```bash
curl https://stays-dashboard-api.onrender.com/health
```

### Webhook Logs
Check Render Dashboard → stays-dashboard-api → Logs for:
- Webhook received events
- Processing status
- Error messages (without PII)

### Database Verification
Webhook events are stored in `webhook_events` table with:
- `event_hash`: SHA-256 of payload
- `received_at`: Timestamp
- `raw`: Full payload (JSONB)

## Production Checklist

- [ ] Webhook URL configured in Stays platform
- [ ] Bearer token set correctly
- [ ] Test webhook with curl commands
- [ ] Verify idempotency works (duplicate detection)
- [ ] Check dashboard updates after webhook
- [ ] Monitor logs for errors
- [ ] Set up UptimeRobot monitoring
- [ ] Document webhook events for team

## Support

For webhook issues:
1. Check Render logs first
2. Test with curl commands
3. Verify Stays platform configuration
4. Contact support with event_hash for specific issues

---
**Last Updated:** August 2025  
**API Version:** 2.0.0 (PostgreSQL Hardened)
