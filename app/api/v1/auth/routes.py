"""
Auth routes for DRX Doctor Platform
"""

from fastapi import APIRouter
from app.api.v1.auth.schemas import (
    AdminLoginRequest, AdminCreateRequest, DoctorRegisterRequest, DoctorLoginRequest,
    AdminMessageResponse, DoctorMessageResponse
)
from app.api.v1.auth import service

router = APIRouter()


@router.post("/admin/create", response_model=AdminMessageResponse, status_code=201, summary="Create Platform Admin")
async def create_admin(request: AdminCreateRequest):
    """
    **Purpose:** Create a new platform administrator (internal staff).
    
    **Access:** Public (used to bootstrap the first admin — protect in production)
    
    **Request Body:**
    ```json
    {
      "name": "Vamsi",
      "username": "vamsi_admin",
      "email": "vamsi@drx.com",
      "password": "Admin@123456"
    }
    ```
    
    **Fields:**
    - `name` — Full name (2-100 chars)
    - `username` — Unique username (3-30 chars, alphanumeric + underscores, stored lowercase)
    - `email` — Valid email (unique)
    - `password` — Required, 8-64 chars, must include uppercase, lowercase, number, and symbol
    
    **Response:**
    ```json
    {
      "message": "Platform admin created successfully",
      "user_id": "507f1f77bcf86cd799439011"
    }
    ```
    """
    return await service.create_admin(
        name=request.name,
        email=request.email,
        username=request.username,
        password=request.password
    )


@router.post("/admin/login", summary="Platform Admin Login (Deprecated)")
async def admin_login(request: AdminLoginRequest):
    """
    **DEPRECATED:** DRX platform login has been removed.
    All user authentication is now through Proxzar OAuth.
    Use the Proxzar login flow to obtain a JWT.
    """
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=410,
        content={"detail": "DRX platform login is deprecated. Use Proxzar OAuth to authenticate."}
    )


@router.post("/doctor/register", response_model=DoctorMessageResponse, status_code=201, summary="Doctor Registration")
async def doctor_register(request: DoctorRegisterRequest):
    """
    **Purpose:** Doctor self-registration on the platform.
    
    **Access:** Public
    
    **Request Body:**
    ```json
    {
      "name": "Dr. Arjun Mehta",
      "username": "arjun_mehta",
      "email": "arjun@doctor.com",
      "phone": "9876543210",
      "password": "Doctor@123"
    }
    ```
    
    **Fields:**
    - `name` — Full name (2-100 chars)
    - `username` — Unique username (3-30 chars, alphanumeric + underscores, stored lowercase)
    - `email` — Valid email (unique)
    - `phone` — 10-15 digit phone number (unique)
    - `password` — Required, 8-64 chars, must include uppercase, lowercase, number, and symbol
    
    **Response:**
    ```json
    {
      "message": "Doctor registered successfully",
      "user_id": "507f1f77bcf86cd799439012"
    }
    ```
    
    **After registration:** Doctor authenticates via Proxzar OAuth using their username.
    """
    return await service.doctor_register(
        name=request.name,
        email=request.email,
        phone=request.phone,
        username=request.username,
        password=request.password
    )


@router.post("/doctor/login", summary="Doctor Login (Deprecated)")
async def doctor_login(request: DoctorLoginRequest):
    """
    **DEPRECATED:** DRX platform login has been removed.
    All user authentication is now through Proxzar OAuth.
    Use the Proxzar login flow to obtain a JWT.
    """
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=410,
        content={"detail": "DRX platform login is deprecated. Use Proxzar OAuth to authenticate."}
    )
