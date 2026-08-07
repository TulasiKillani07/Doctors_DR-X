"""
Main API Router for DRX Doctor Platform v1
"""

from fastapi import APIRouter
from app.api.v1.auth.routes import router as auth_router
from app.api.v1.organizations.routes import router as organizations_router
from app.api.v1.doctor_organizations.routes import router as doctor_orgs_router
from app.api.v1.doctors.routes import router as doctors_router
from app.api.v1.integration.routes import router as integration_router
from app.api.v1.integration_services.routes import router as integration_services_router
from app.api.v1.profile.routes import router as profile_router
from app.api.v1.dashboard.routes import router as dashboard_router
from app.api.v1.notifications.routes import router as notifications_router
from app.api.v1.connections.routes import router as connections_router
from app.api.v1.settings.routes import router as settings_router
from app.api.v1.my_organizations.routes import router as my_organizations_router
from app.api.v1.org_drugs.routes import router as org_drugs_router
from app.api.v1.cme.routes import router as cme_router
from app.api.v1.bookmarks.routes import router as bookmarks_router
from app.api.v1.chat.routes import router as chat_router
from app.api.v1.feed.routes import router as feed_router
from app.api.v1.search.routes import router as search_router
from app.api.v1.groups.routes import router as groups_router
from app.api.v1.activity_logs.routes import router as activity_logs_router

api_router = APIRouter()

# Authentication (admin + doctor login/register)
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# Doctor profile (Doctor views/edits own profile + locations)
api_router.include_router(profile_router, prefix="/profile", tags=["Doctor Profile"])

# Doctor dashboard (Doctor-owned data only)
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Doctor Dashboard"])

# Doctor notifications
api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])

# Doctor connections (doctor-to-doctor network)
api_router.include_router(connections_router, prefix="/connections", tags=["Connections"])

# Doctor chat (doctor-to-doctor messaging)
api_router.include_router(chat_router, prefix="/chat", tags=["Chat"])

# Doctor groups (group chats)
api_router.include_router(groups_router, prefix="/groups", tags=["Groups"])

# Doctor feed/posts (professional network)
api_router.include_router(feed_router, prefix="/network", tags=["Feed & Posts"])

# Doctor search
api_router.include_router(search_router, prefix="/search", tags=["Search"])

# Doctor settings (password, preferences, privacy)
api_router.include_router(settings_router, prefix="/settings", tags=["Settings"])

# My Organizations (doctor views their connected orgs)
api_router.include_router(my_organizations_router, prefix="/my-organizations", tags=["My Organizations"])

# Organization Drugs (doctor views drugs from connected org via MRX)
api_router.include_router(org_drugs_router, prefix="/organizations", tags=["Organization Drugs"])

# CME (registrations owned by DRX, events fetched from MRX)
api_router.include_router(cme_router, prefix="/cme", tags=["CME Events"])

# Drug Bookmarks (per-org, DRX-owned)
api_router.include_router(bookmarks_router, prefix="/bookmarks", tags=["Bookmarks"])

# Doctor management (Platform Admin only)
api_router.include_router(doctors_router, prefix="/doctors", tags=["Doctors (Admin)"])

# Organization management (Platform Admin only)
api_router.include_router(organizations_router, prefix="/organizations", tags=["Organizations (Admin)"])

# Doctor-Organization relationships (Platform Admin only)
api_router.include_router(doctor_orgs_router, prefix="/doctor-organizations", tags=["Doctor-Org Relationships (Admin)"])

# Integration APIs (Service JWT only — backend-to-backend)
api_router.include_router(integration_router, prefix="/integration", tags=["Integration (Service-to-Service)"])

# Integration Services Management (Platform Admin only)
api_router.include_router(integration_services_router, prefix="/integration/services", tags=["Integration Services (Admin)"])

# Activity Logs (Doctor views own activity history)
api_router.include_router(activity_logs_router, prefix="/activity-logs", tags=["Activity Logs"])
