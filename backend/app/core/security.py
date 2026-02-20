"""
Security utilities for authentication and authorization
Handles JWT tokens and password hashing
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
import hashlib

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def _hash_password_for_bcrypt(password: str) -> str:
    """
    Pre-hash password with SHA256 to ensure it's always under 72 bytes for bcrypt
    
    Args:
        password: Plain text password (any length)
        
    Returns:
        SHA256 hash of password (always 64 hex chars = 64 bytes)
    """
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        # Pre-hash the plain password with SHA256
        prehashed = _hash_password_for_bcrypt(plain_password)
        # Then verify against bcrypt hash
        return pwd_context.verify(prehashed, hashed_password)
    except Exception as e:
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a password using SHA256 + bcrypt
    
    Args:
        password: Plain text password (any length)
        
    Returns:
        Bcrypt hash of SHA256 pre-hash
    """
    # Step 1: Pre-hash with SHA256 (ensures always under 72 bytes)
    prehashed = _hash_password_for_bcrypt(password)
    
    # Step 2: Hash with bcrypt
    return pwd_context.hash(prehashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a new JWT access token
    
    Args:
        data: Data to encode in the token
        expires_delta: Optional expiration time delta
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT access token
    
    Args:
        token: JWT token to decode
        
    Returns:
        Decoded token data or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
