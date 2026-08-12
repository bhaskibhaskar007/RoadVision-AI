from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from app.config import settings
password_hash = PasswordHash.recommended(); bearer = HTTPBearer()
def hash_password(password: str) -> str: return password_hash.hash(password)
def verify_password(password: str, hashed: str) -> bool: return password_hash.verify(password, hashed)
def create_token(subject: str) -> str: return jwt.encode({"sub": subject, "exp": datetime.now(timezone.utc)+timedelta(hours=12)}, settings.secret_key, algorithm="HS256")
def token_subject(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    try: return jwt.decode(credentials.credentials, settings.secret_key, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
