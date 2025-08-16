import secrets
import base64

token = secrets.token_urlsafe(32)
print(f"Secure API Token (43 chars): {token}")

token_b64 = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
print(f"Base64 API Token (44 chars): {token_b64}")
