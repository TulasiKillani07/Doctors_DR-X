"""
Main API Router for DRX Doctor Platform v1
"""

from fastapi import APIRouter
from app.api.v1.auth.routes import router as auth_router
from app.api.v1.organizations.routes import router as organizations_router
from app.api.v1.doctor_organizations.routes import router as doctor_orgs_router
from app.api.v1.doctors.routes import router as doctors_router

api_router = APIRouter()

# Authentication (admin + doctor login/register)
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# Doctor management (Platform Admin only)
api_router.include_router(doctors_router, prefix="/doctors", tags=["Doctors"])

# Organization management (Platform Admin only)
api_router.include_router(organizations_router, prefix="/organizations", tags=["Organizations"])

# Doctor-Organization relationships (Platform Admin only)
api_router.include_router(doctor_orgs_router, prefix="/doctor-organizations", tags=["Doctor-Organization Relationships"])
