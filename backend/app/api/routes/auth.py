"""
API Routes - Authentication Endpoints
Handles user registration, login, and token management
"""

from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime
from bson import ObjectId
import uuid
import logging

logger = logging.getLogger(__name__)

from app.models.schemas import (
    UserRegistrationRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    UserInDB,
    ErrorResponse
)
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token
)
from app.core.dependencies import get_current_user
from app.db import (
    get_database,
    use_memory_storage,
    memory_insert_one,
    memory_find_one,
    memory_find
)

router = APIRouter()


# --- Helper Functions ---

async def get_user_by_email(email: str) -> UserInDB | None:
    """Get user from database by email"""
    if use_memory_storage():
        # In-memory storage
        users = await memory_find("users", {"email": email})
        if users:
            user_data = users[0]
            return UserInDB(**user_data)
        return None
    else:
        # MongoDB storage
        db = get_database()
        user_data = await db.users.find_one({"email": email})
        if user_data:
            user_data["user_id"] = str(user_data.pop("_id"))
            return UserInDB(**user_data)
        return None


async def create_user(email: str, password: str, full_name: str | None = None) -> UserInDB:
    """Create a new user in the database"""
    try:
        user_id = str(uuid.uuid4())
        hashed_password = get_password_hash(password)
        
        user_data = {
            "user_id": user_id,
            "email": email,
            "hashed_password": hashed_password,
            "full_name": full_name,
            "created_at": datetime.utcnow(),
            "is_active": True
        }
        
        logger.info(f"Creating user: {email}")
        
        if use_memory_storage():
            logger.info("Using in-memory storage")
            # In-memory storage
            await memory_insert_one("users", user_data)
        else:
            logger.info("Using MongoDB storage")
            # MongoDB storage
            db = get_database()
            # Use user_id as _id for consistency
            mongo_data = user_data.copy()
            mongo_data["_id"] = user_id
            await db.users.insert_one(mongo_data)
            logger.info(f"User created in MongoDB: {user_id}")
        
        return UserInDB(**user_data)
    except Exception as e:
        logger.error(f"Failed to create user {email}: {str(e)}", exc_info=True)
        raise


# --- Authentication Routes ---

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: UserRegistrationRequest):
    """
    Register a new user account
    
    - **email**: User's email address (must be unique)
    - **password**: Password (minimum 8 characters, maximum 100 characters)
    - **full_name**: Optional user's full name
    
    Returns JWT access token and user information
    """
    try:
        # Validate email format
        if not request.email or "@" not in request.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Validate password length (minimum 8 characters)
        if len(request.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        # Check if user already exists
        existing_user = await get_user_by_email(request.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create new user
        user = await create_user(
            email=request.email,
            password=request.password,
            full_name=request.full_name
        )
        
        # Create access token
        access_token = create_access_token(
            data={"user_id": user.user_id, "email": user.email}
        )
        
        # Prepare response
        user_response = UserResponse(
            user_id=user.user_id,
            email=user.email,
            full_name=user.full_name,
            created_at=user.created_at,
            is_active=user.is_active
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_response
        )
    
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"ValueError during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration failed - Error type: {type(e).__name__}, Message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login", response_model=TokenResponse)
async def login(request: UserLoginRequest):
    """
    Login with email and password
    
    - **email**: User's email address
    - **password**: User's password
    
    Returns JWT access token and user information
    """
    try:
        # Get user from database
        user = await get_user_by_email(request.email)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Verify password
        if not verify_password(request.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )
        
        # Create access token
        access_token = create_access_token(
            data={"user_id": user.user_id, "email": user.email}
        )
        
        # Prepare response
        user_response = UserResponse(
            user_id=user.user_id,
            email=user.email,
            full_name=user.full_name,
            created_at=user.created_at,
            is_active=user.is_active
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_response
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserInDB = Depends(get_current_user)):
    """
    Get current authenticated user information
    
    Requires valid JWT token in Authorization header
    """
    return UserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        full_name=current_user.full_name,
        created_at=current_user.created_at,
        is_active=current_user.is_active
    )
