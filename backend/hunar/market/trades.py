"""Trades, their qualifications and the jobs a customer can book.

Electrical jobs follow the CEA (Measures relating to Safety and Electric Supply) Regulations, 2023,
regulation 31(1): installation work, including additions, alterations, repairs and adjustments, must
be done by a holder of a permit issued or recognised by the State Government (under a licensed
contractor), except replacing lamps, fans, fuses, switches, domestic appliances up to 250 V and
fittings without altering the installation's capacity or character. Jobs outside that exception are
marked needs_permit, and only workers whose permit an admin has checked can be booked for them.

A trade has practical assessments when the rubric has tasks for it (hunar/rubric/tasks, Task.trade):
the assessment then scores only that trade's tasks against that trade's qualification file. A trade
without tasks takes the quiz and can be booked, but cannot ask for a practical assessment.
"""
from __future__ import annotations

TRADES: dict[str, dict] = {
    "electrician": {
        "name": {"en": "Electrician", "hi": "इलेक्ट्रीशियन"},
        "qualification_nqr_id": 13772,
        "jobs": {
            "replace_fitting": {"en": "Replace a lamp, fan, fuse, switch or fitting with the same type (no change to the wiring)",
                                "hi": "बल्ब, पंखा, फ़्यूज़, स्विच या फ़िटिंग बदलना, उसी प्रकार का (वायरिंग में बदलाव नहीं)",
                                "needs_permit": False},
            "appliance": {"en": "Fit a household appliance up to 250 V without changing the wiring",
                          "hi": "250 V तक का घरेलू उपकरण लगाना, वायरिंग बदले बिना",
                          "needs_permit": False},
            "fault_repair": {"en": "Find and repair a fault (tripping, no power, sparking)",
                             "hi": "ख़राबी ढूँढ़कर ठीक करना (ट्रिप होना, बिजली न आना, चिंगारी)",
                             "needs_permit": True},
            "new_point": {"en": "Add a new point, socket or circuit", "hi": "नया पॉइंट, सॉकेट या सर्किट जोड़ना",
                          "needs_permit": True},
            "wiring": {"en": "New wiring or rewiring", "hi": "नई वायरिंग या दोबारा वायरिंग", "needs_permit": True},
            "board": {"en": "Install or change a distribution board, MCB or RCCB",
                      "hi": "डिस्ट्रीब्यूशन बोर्ड, MCB या RCCB लगाना या बदलना", "needs_permit": True},
            "earthing": {"en": "Earthing work or earth testing", "hi": "अर्थिंग का काम या अर्थ की जाँच",
                         "needs_permit": True},
        },
    },
    "plumber": {
        "name": {"en": "Plumber", "hi": "प्लंबर"},
        "qualification_nqr_id": 12957,  # Plumber - General (WMPSC), data/qp_sources.json trade_packs
        "jobs": {
            "tap_leak": {"en": "Repair a leaking tap, valve or joint", "hi": "टपकता नल, वाल्व या जोड़ ठीक करना",
                         "needs_permit": False},
            "toilet": {"en": "Repair or fit a toilet, cistern or wash basin", "hi": "शौचालय, फ़्लश टंकी या वॉश बेसिन ठीक करना या लगाना",
                       "needs_permit": False},
            "drain": {"en": "Clear a blocked drain or trap", "hi": "बंद नाली या ट्रैप खोलना", "needs_permit": False},
            "pipeline": {"en": "Lay or replace water supply pipes", "hi": "पानी की पाइपलाइन बिछाना या बदलना",
                         "needs_permit": False},
            "tank_pump": {"en": "Water tank or pump connections", "hi": "पानी की टंकी या पंप के कनेक्शन",
                          "needs_permit": False},
        },
    },
    "carpenter": {
        "name": {"en": "Carpenter", "hi": "बढ़ई"},
        "qualification_nqr_id": 9884,  # Assistant Carpenter (FFSC); NQR validity ended 31/08/2026
        "qualification_note": "The NQR validity of this qualification file ended on 31 Aug 2026.",
        "jobs": {
            "furniture_repair": {"en": "Repair furniture", "hi": "फ़र्नीचर की मरम्मत", "needs_permit": False},
            "door_window": {"en": "Fit or repair a door, window or frame", "hi": "दरवाज़ा, खिड़की या चौखट लगाना या ठीक करना",
                            "needs_permit": False},
            "lock_hardware": {"en": "Fit a lock, hinge or handle", "hi": "ताला, कब्ज़ा या हैंडल लगाना", "needs_permit": False},
            "assembly": {"en": "Assemble ready-made furniture", "hi": "तैयार फ़र्नीचर जोड़ना", "needs_permit": False},
            "new_furniture": {"en": "Make new furniture or fittings", "hi": "नया फ़र्नीचर या फ़िटिंग बनाना",
                              "needs_permit": False},
        },
    },
}

PERMIT_NOTE = ("This job needs a worker with a State electrical permit (CEA Safety Regulations 2023, reg. 31). "
               "Only replacing lamps, fans, fuses, switches, fittings or appliances up to 250 V without changing "
               "the wiring is exempt.")


PRACTICAL_NOTE = "Practical assessments are not available for this trade yet: its practical tasks are not written."


def has_practical(trade: str) -> bool:
    from hunar.rubric.engine import tasks_for

    return trade in TRADES and bool(tasks_for(trade))


def job(trade: str, job_id: str) -> dict:
    try:
        return TRADES[trade]["jobs"][job_id]
    except KeyError as e:
        raise KeyError(f"unknown job {job_id!r} for trade {trade!r}") from e
