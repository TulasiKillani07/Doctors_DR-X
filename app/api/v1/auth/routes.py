"""
Auth routes for DRX Doctor Platform
"""

from fastapi import APIRouter
from app.api.v1.auth.schemas import (
    AdminLoginRequest, AdminCreateRequest, DoctorRegisterRequest, DoctorLoginRequest,
    TokenResponse, MessageResponse
)
from app.api.v1.auth import service

router = APIRouter()


@router.post("/admin/create", response_model=MessageResponse, summary="Create Platform Admin")
async def create_admin(request: AdminCreateRequest):
    """
    **Purpose:** Create a new platform administrator (internal staff).
    
    **Access:** Public (used to bootstrap the first admin — protect in production)
    
    **Request Body:**
    ```json
    {
      "name": "Vamsi",
      "email": "vamsi@drx.com",
      "password": "Admin@123456"
    }
    ```
    
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
        password=request.password
    )


@router.post("/admin/login", response_model=TokenResponse, summary="Platform Admin Login")
async def admin_login(request: AdminLoginRequest):
    """
    **Purpose:** Authenticate platform administrator and return JWT token.
    
    **Access:** Public
    
    **Request Body:**
    ```json
    {
      "email": "vamsi@drx.com",
      "password": "Admin@123456"
    }
    ```
    
    **Response:**
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIs...",
      "token_type": "bearer",
      "role": "PLATFORM_ADMIN",
      "user": { "id": "...", "email": "vamsi@drx.com", "name": "Vamsi" }
    }
    ```
    """
    return await service.admin_login(request.email, request.password)


@router.post("/doctor/register", response_model=MessageResponse, summary="Doctor Registration")
async def doctor_register(request: DoctorRegisterRequest):
    """
    **Purpose:** Doctor self-registration on the platform.
    
    **Access:** Public
    
    **Request Body:**
    ```json
    {
      "name": "Dr. Arjun Mehta",
      "email": "arjun@doctor.com",
      "phone": "9876543210",
      "password": "Doctor@123"
    }
    ```
    
    **Response:**
    ```json
    {
      "message": "Doctor registered successfully",
      "user_id": "507f1f77bcf86cd799439012"
    }
    ```
    
    **After registration:** Doctor can login and complete their professional profile.
    """
    return await service.doctor_register(
        name=request.name,
        email=request.email,
        phone=request.phone,
        password=request.password
    )


@router.post("/doctor/login", response_model=TokenResponse, summary="Doctor Login")
async def doctor_login(request: DoctorLoginRequest):
    """
    **Purpose:** Authenticate doctor and return JWT token.
    
    **Access:** Public
    
    **Request Body (login with email):**
    ```json
    {
      "identifier": "arjun@doctor.com",
      "password": "Doctor@123"
    }
    ```
    
    **Request Body (login with GID):**
    ```json
    {
      "identifier": "PRXDOC482915",
      "password": "Doctor@123"
    }
    ```
    
    **Response:**
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIs...",
      "token_type": "bearer",
      "role": "DOCTOR",
      "user": { "id": "...", "email": "arjun@doctor.com", "name": "Dr. Arjun Mehta", "doctor_gid": "PRXDOC482915" }
    }
    ```
    """
    return await service.doctor_login(request.identifier, request.password)
