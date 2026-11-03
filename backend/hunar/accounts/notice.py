"""Itemised consent notice (Digital Personal Data Protection Act 2023, s. 5-6; DPDP Rules 2025, r. 3).

Each purpose lists the personal data it uses. Consent is asked per purpose, can be withdrawn as easily
as it was given, and withdrawal of a purpose stops that processing (profile hidden, or the whole account
erased). The app shows this text in the user's language; the server records which notice version and
language the person saw.

Every worker takes the skill quiz right after registering (project decision of 2026-11-04), so the
"assessment" purpose is required for workers: a worker account cannot exist without it.

Only adults (18+) can register: the DPDP Act treats anyone under 18 as a child, whose data needs
verifiable parental consent, and RPL under PMKVY 4.0 is for ages 18-59.
"""
from __future__ import annotations

NOTICE_VERSION = "2026-11-04.2"  # .2: the skill quiz became required for workers

PURPOSES: dict[str, dict] = {
    "account": {
        "roles": ["worker", "customer", "facilitator", "assessor", "admin"],
        "required": True,
        "data": ["phone number", "display name", "preferred language", "PIN (stored only as a salted hash)"],
        "why": "to let you log in and to tell the other person in a booking who you are",
        "withdraw": "erases your account",
    },
    "assessment": {
        "roles": ["worker"],
        "required": True,
        "data": ["quiz answers and answer times", "your work declaration", "practical assessment records",
                 "task photos (faces blurred before storage)"],
        "why": "to estimate your skills with a quiz right after you register, and to let an assessor review them",
        "withdraw": "erases your account and your quiz answers (every worker takes the quiz); assessor records "
                    "already signed off are kept only as the signed-off result",
    },
    "profile_display": {
        "roles": ["worker"],
        "required": False,
        "data": ["display name", "trade", "years of experience", "district and PIN code", "languages",
                 "assessor-verified result and its date", "booking ratings"],
        "why": "to show your profile to customers who search for a worker",
        "withdraw": "hides your profile at once",
    },
    "contact_share": {
        "roles": ["worker", "customer"],
        "required": True,
        "data": ["phone number"],
        "why": "to share your phone number with the other person only after a booking is accepted",
        "withdraw": "erases your account (bookings need a way to contact each other)",
    },
}


def purposes_for(role: str) -> dict[str, dict]:
    return {k: v for k, v in PURPOSES.items() if role in v["roles"]}
