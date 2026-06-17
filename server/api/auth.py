import time
import jwt
from typing import Optional, Dict
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

# In production, read from env
JWT_SECRET = "super-secret-admin-key-pro"
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRATION_SEC = 3600 # 1 hour

class AuthManager:
    @staticmethod
    def create_token(username: str) -> str:
        payload = {
            "sub": username,
            "exp": time.time() + TOKEN_EXPIRATION_SEC
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict:
        token = credentials.credentials
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

# Dependency for FastAPI
async def get_current_admin(payload: Dict = Depends(AuthManager.verify_token)):
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return username
