"""
Shared field validators for user-facing input (doctors, admins).

Rules:
- username:  6-16 chars, A-Z a-z 0-9 _, rejects placeholder "string"
- password:  8-24 chars, >=1 upper, >=1 lower, >=1 number, >=1 symbol, rejects "string"
- full name: 8-64 chars
- email:     valid format + domain deliverability (MX) via email-validator
- phone:     E.164 format (e.g. +919848012345)
- all strings are stripped of leading/trailing whitespace before validation
"""

import re
from typing import Optional

USERNAME_REGEX = re.compile(r'^[A-Za-z0-9_]{6,16}$')
PASSWORD_REGEX = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)'
    r'(?=.*[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?~`])'
    r'[A-Za-z\d!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?~`]{8,24}$'
)
PHONE_REGEX = re.compile(r'^\+[1-9]\d{7,14}$')  # E.164: + then 8-15 digits total

PLACEHOLDER_VALUES = {"string", "str", "test", "example"}


def validate_username(v: str) -> str:
    """6-16 chars, letters/numbers/underscore only. Stored lowercase."""
    if v is None:
        raise ValueError("Username is required")
    v = v.strip()
    if v.lower() in PLACEHOLDER_VALUES:
        raise ValueError("Please provide a real username")
    if not USERNAME_REGEX.match(v):
        raise ValueError("Username must be 6-16 characters, using only letters, numbers, and underscores")
    return v.lower()


def validate_password(v: str) -> str:
    """8-24 chars with upper, lower, number, symbol."""
    if v is None:
        raise ValueError("Password is required")
    v = v.strip()
    if v.lower() in PLACEHOLDER_VALUES:
        raise ValueError("Please provide a real password")
    if not PASSWORD_REGEX.match(v):
        raise ValueError(
            "Password must be 8-24 characters and include at least one uppercase letter, "
            "one lowercase letter, one number, and one symbol"
        )
    return v


def validate_full_name(v: str) -> str:
    """8-64 chars."""
    if v is None:
        raise ValueError("Full name is required")
    v = v.strip()
    if not (8 <= len(v) <= 64):
        raise ValueError("Full name must be 8-64 characters")
    return v


def validate_phone(v: str) -> str:
    """E.164 format, e.g. +919848012345."""
    if v is None:
        raise ValueError("Phone is required")
    v = v.strip().replace(" ", "")
    if not PHONE_REGEX.match(v):
        raise ValueError("Phone must be in E.164 format, e.g. +919848012345")
    return v


def validate_email_domain(email: str) -> str:
    """
    Validate email format AND that the domain can receive mail (MX check).
    Uses email-validator (already installed via pydantic[email]), which uses
    dnspython under the hood for deliverability.
    """
    from email_validator import validate_email as _ev, EmailNotValidError

    email = (email or "").strip().lower()
    try:
        result = _ev(email, check_deliverability=True)
        return result.normalized
    except EmailNotValidError as e:
        raise ValueError(str(e))
