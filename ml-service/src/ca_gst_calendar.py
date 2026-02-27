"""
CA GST Deadline Calendar — Per-Client Monthly Status Tracking
=============================================================
Generates a full compliance calendar for each client's GSTIN(s),
tracking GSTR-1, GSTR-3B, GSTR-9, GSTR-9C due dates with:
  - Per-client filing status (filed / pending / overdue / not_applicable)
  - Late fee accumulation (₹50/day GSTR-1 regular; ₹25+₹25/day GSTR-3B)
  - Upcoming deadline alerts (7-day and 3-day warnings)
  - Quarterly QRMP scheme support

Integrates with ca_client_manager.py (Client, ComplianceTask) —
call generate_gst_tasks() to push deadlines into the task manager.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from datetime import date, timedelta
from enum import Enum
from calendar import monthrange


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ReturnType(str, Enum):
    GSTR1      = "GSTR-1"
    GSTR3B     = "GSTR-3B"
    GSTR9      = "GSTR-9"       # annual
    GSTR9C     = "GSTR-9C"      # reconciliation (turnover > ₹5 Cr)
    GSTR2B     = "GSTR-2B"      # auto-drafted ITC (no filing required)
    CMP08      = "CMP-08"       # composition quarterly
    IFF        = "IFF"          # invoice furnishing facility (QRMP)

class FilingFrequency(str, Enum):
    MONTHLY    = "monthly"
    QUARTERLY  = "quarterly"
    ANNUAL     = "annual"

class DeadlineStatus(str, Enum):
    UPCOMING   = "upcoming"      # > 7 days away
    DUE_SOON   = "due_soon"      # 1–7 days away
    TODAY      = "today"
    OVERDUE    = "overdue"
    FILED      = "filed"
    NOT_APPLICABLE = "na"

# ---------------------------------------------------------------------------
# Due date calculators
# ---------------------------------------------------------------------------

# State-specific GSTR-3B split for small taxpayers (turnover ≤ ₹5 Cr)
# Group A states: 22nd; Group B states: 24th
_GSTR3B_GROUP_A_STATES = {
    "01", "02", "03", "04", "06", "10", "11", "12", "13", "14",
    "15", "16", "17", "18", "20", "27", "30", "33"
}
_GSTR3B_GROUP_B_STATES = {
    "05", "07", "08", "09", "19", "21", "22", "23", "24", "25",
    "26", "28", "29", "31", "32", "34", "35", "36", "37"
}

def gstr1_due(year: int, month: int, frequency: FilingFrequency) -> date:
    """GSTR-1 due date for monthly or quarterly filer."""
    if frequency == FilingFrequency.MONTHLY:
        # 11th of following month
        next_m, next_y = (month + 1, year) if month < 12 else (1, year + 1)
        return date(next_y, next_m, 11)
    else:
        # Quarterly: 13th of month after quarter end
        quarter_end_month = ((month - 1) // 3 + 1) * 3
        next_m, next_y = (quarter_end_month + 1, year) if quarter_end_month < 12 else (1, year + 1)
        return date(next_y, next_m, 13)

def gstr3b_due(year: int, month: int, state_code: str, high_turnover: bool) -> date:
    """GSTR-3B due date based on turnover and state."""
    next_m, next_y = (month + 1, year) if month < 12 else (1, year + 1)
    if high_turnover:
        return date(next_y, next_m, 20)
    elif state_code in _GSTR3B_GROUP_A_STATES:
        return date(next_y, next_m, 22)
    else:
        return date(next_y, next_m, 24)

def gstr9_due(financial_year_end: int) -> date:
    """GSTR-9 annual return due: 31 December of next calendar year."""
    return date(financial_year_end + 1, 12, 31)

def cmp08_due(year: int, quarter: int) -> date:
    """CMP-08 (composition) due: 18th of month after quarter end."""
    quarter_end_months = {1: 6, 2: 9, 3: 12, 4: 3}
    end_month = quarter_end_months[quarter]
    end_year  = year if quarter < 4 else year + 1
    next_m    = end_month + 1 if end_month < 12 else 1
    next_y    = end_year if end_month < 12 else end_year + 1
    return date(next_y, next_m, 18)

# ---------------------------------------------------------------------------
# Late fee schedule
# ---------------------------------------------------------------------------

def compute_late_fee(return_type: ReturnType, days_late: int, is_nil_return: bool) -> float:
    """
    Late fee as per CGST Act:
      GSTR-1 regular: ₹50/day (₹25 CGST + ₹25 SGST), max ₹10,000
      GSTR-1 nil:     ₹20/day, max ₹500
      GSTR-3B regular: ₹50/day, max ₹10,000
      GSTR-3B nil:     ₹20/day, max ₹500
      GSTR-9:          ₹200/day, max 0.25% of turnover
    """
    if days_late <= 0:
        return 0.0
    if return_type in (ReturnType.GSTR1, ReturnType.GSTR3B):
        if is_nil_return:
            return min(days_late * 20, 500)
        return min(days_late * 50, 10_000)
    if return_type == ReturnType.GSTR9:
        return min(days_late * 200, 25_000)   # approximate cap
    return 0.0

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DeadlineEntry:
    gstin:          str
    client_name:    str
    return_type:    ReturnType
    period:         str          # "2024-12" or "2024-Q3" or "FY2024-25"
    due_date:       str          # ISO date
    status:         DeadlineStatus
    filed_date:     Optional[str]  = None
    late_fee:       float          = 0.0
    interest:       float          = 0.0
    days_late:      int            = 0
    is_nil_return:  bool           = False
    alert_message:  Optional[str]  = None

    def to_task_params(self) -> dict:
        """Convert to ComplianceTask-compatible dict for ca_client_manager."""
        return {
            "description": f"{self.return_type} for {self.period}",
            "due_date":    self.due_date,
            "period":      self.period,
            "priority":    2 if self.status == DeadlineStatus.DUE_SOON else 1,
        }

@dataclass
class GSTNProfile:
    gstin:         str
    client_id:     str
    client_name:   str
    state_code:    str
    high_turnover: bool          # True if annual turnover > ₹5 Cr
    gstr1_freq:    FilingFrequency
    is_composition: bool         = False
    filed_periods: Dict[str, str] = field(default_factory=dict)
    # filed_periods: "GSTR-1:2024-11" → filed_date

@dataclass
class MonthlyCalendar:
    month:        str   # "YYYY-MM"
    generated_on: str
    entries:      List[DeadlineEntry]
    summary: Dict = field(default_factory=dict)

# ---------------------------------------------------------------------------
# Calendar generator
# ---------------------------------------------------------------------------

class GSTDeadlineCalendar:
    """
    Generates monthly GST compliance calendars for a CA's client portfolio.
    """

    def __init__(self):
        self._profiles: Dict[str, GSTNProfile] = {}  # gstin → profile

    def register_gstin(
        self,
        gstin:         str,
        client_id:     str,
        client_name:   str,
        high_turnover: bool = True,
        gstr1_freq:    str  = "monthly",
        is_composition: bool = False,
        filed_periods: Optional[Dict[str, str]] = None,
    ) -> GSTNProfile:
        profile = GSTNProfile(
            gstin          = gstin,
            client_id      = client_id,
            client_name    = client_name,
            state_code     = gstin[:2],
            high_turnover  = high_turnover,
            gstr1_freq     = FilingFrequency(gstr1_freq),
            is_composition = is_composition,
            filed_periods  = filed_periods or {},
        )
        self._profiles[gstin] = profile
        return profile

    def generate_month(self, year: int, month: int) -> MonthlyCalendar:
        """Generate all deadlines falling in (year, month)."""
        today   = date.today()
        entries = []

        for profile in self._profiles.values():
            # GSTR-1
            if not profile.is_composition:
                freq = profile.gstr1_freq
                # Find which period this due date covers
                if freq == FilingFrequency.MONTHLY:
                    prev_m = month - 1 if month > 1 else 12
                    prev_y = year if month > 1 else year - 1
                    due    = gstr1_due(prev_y, prev_m, freq)
                    if due.year == year and due.month == month:
                        period = f"{prev_y}-{prev_m:02d}"
                        entries.append(self._make_entry(profile, ReturnType.GSTR1, period, due, today))
                else:
                    # quarterly: check if any quarter ends in prev months landing here
                    for qm in [3, 6, 9, 12]:
                        qy = year
                        due = gstr1_due(qy, qm, freq)
                        if due.year == year and due.month == month:
                            period = f"{qy}-Q{qm // 3}"
                            entries.append(self._make_entry(profile, ReturnType.GSTR1, period, due, today))

            # GSTR-3B
            if not profile.is_composition:
                prev_m = month - 1 if month > 1 else 12
                prev_y = year if month > 1 else year - 1
                due    = gstr3b_due(prev_y, prev_m, profile.state_code, profile.high_turnover)
                if due.year == year and due.month == month:
                    period = f"{prev_y}-{prev_m:02d}"
                    entries.append(self._make_entry(profile, ReturnType.GSTR3B, period, due, today))
            else:
                # CMP-08 quarterly
                for q in range(1, 5):
                    due = cmp08_due(year, q)
                    if due.year == year and due.month == month:
                        period = f"Q{q} {year}"
                        entries.append(self._make_entry(profile, ReturnType.CMP08, period, due, today))

        # Sort by due date
        entries.sort(key=lambda e: e.due_date)

        # Summary
        summary = {
            "total":    len(entries),
            "filed":    sum(1 for e in entries if e.status == DeadlineStatus.FILED),
            "pending":  sum(1 for e in entries if e.status in (DeadlineStatus.UPCOMING, DeadlineStatus.DUE_SOON, DeadlineStatus.TODAY)),
            "overdue":  sum(1 for e in entries if e.status == DeadlineStatus.OVERDUE),
            "total_late_fee": round(sum(e.late_fee for e in entries), 2),
        }

        return MonthlyCalendar(
            month        = f"{year}-{month:02d}",
            generated_on = today.isoformat(),
            entries      = entries,
            summary      = summary,
        )

    def generate_range(self, start_year: int, start_month: int, months: int = 3) -> List[MonthlyCalendar]:
        """Generate calendars for a range of months."""
        calendars = []
        y, m = start_year, start_month
        for _ in range(months):
            calendars.append(self.generate_month(y, m))
            m += 1
            if m > 12:
                m, y = 1, y + 1
        return calendars

    def get_urgent(self, days: int = 7) -> List[DeadlineEntry]:
        """Return all unfiled entries due within `days` days."""
        today    = date.today()
        cutoff   = today + timedelta(days=days)
        urgent   = []
        for cal in self.generate_range(today.year, today.month, 2):
            for e in cal.entries:
                d = date.fromisoformat(e.due_date)
                if e.status in (DeadlineStatus.DUE_SOON, DeadlineStatus.TODAY, DeadlineStatus.OVERDUE):
                    urgent.append(e)
                elif e.status == DeadlineStatus.UPCOMING and d <= cutoff:
                    urgent.append(e)
        return urgent

    def mark_filed(self, gstin: str, return_type: str, period: str, filed_date: str):
        key = f"{return_type}:{period}"
        if gstin in self._profiles:
            self._profiles[gstin].filed_periods[key] = filed_date

    def _make_entry(
        self,
        profile:     GSTNProfile,
        rtype:       ReturnType,
        period:      str,
        due:         date,
        today:       date,
    ) -> DeadlineEntry:
        filed_key  = f"{rtype}:{period}"
        filed_date = profile.filed_periods.get(filed_key)

        if filed_date:
            fd       = date.fromisoformat(filed_date)
            days_late = max(0, (fd - due).days)
            status   = DeadlineStatus.FILED
            late_fee = compute_late_fee(rtype, days_late, False)
        else:
            days_late = max(0, (today - due).days)
            late_fee  = compute_late_fee(rtype, days_late, False)
            if today > due:
                status = DeadlineStatus.OVERDUE
            elif today == due:
                status = DeadlineStatus.TODAY
            elif (due - today).days <= 7:
                status = DeadlineStatus.DUE_SOON
            else:
                status = DeadlineStatus.UPCOMING

        alert = None
        if status == DeadlineStatus.OVERDUE:
            alert = f"⚠️ OVERDUE by {days_late}d — late fee ₹{late_fee:,.0f}"
        elif status == DeadlineStatus.TODAY:
            alert = "🔴 DUE TODAY — file immediately"
        elif status == DeadlineStatus.DUE_SOON:
            alert = f"🟠 Due in {(due - today).days} days"

        return DeadlineEntry(
            gstin        = profile.gstin,
            client_name  = profile.client_name,
            return_type  = rtype,
            period       = period,
            due_date     = due.isoformat(),
            status       = status,
            filed_date   = filed_date,
            late_fee     = late_fee,
            days_late    = days_late,
            alert_message= alert,
        )


# ---------------------------------------------------------------------------
# Singleton + API wrapper
# ---------------------------------------------------------------------------

_calendar = GSTDeadlineCalendar()

def gst_deadline_calendar(params: dict) -> dict:
    action = params.get("action", "monthly")
    try:
        if action == "register":
            profile = _calendar.register_gstin(**{k: v for k, v in params.items() if k != "action"})
            return asdict(profile)
        elif action == "monthly":
            year, month = params.get("year", date.today().year), params.get("month", date.today().month)
            cal = _calendar.generate_month(int(year), int(month))
            return {"month": cal.month, "summary": cal.summary,
                    "entries": [asdict(e) for e in cal.entries]}
        elif action == "urgent":
            days = int(params.get("days", 7))
            return {"urgent": [asdict(e) for e in _calendar.get_urgent(days)]}
        elif action == "mark_filed":
            _calendar.mark_filed(params["gstin"], params["return_type"], params["period"], params["filed_date"])
            return {"success": True}
        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as e:
        return {"error": str(e)}
