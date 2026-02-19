"""
CA/Accountant Multi-Client Management System
Provides:
  • Client registry with PAN, GSTIN, engagement type
  • Task management — filing due dates per client
  • Client status dashboard (ITR, GST, ROC compliance)
  • Bulk deadline tracking across client portfolio
  • Client communication log
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ClientType(str, Enum):
    INDIVIDUAL      = "individual"
    HUF             = "huf"
    PROPRIETARY     = "proprietary"
    PARTNERSHIP     = "partnership"
    PRIVATE_LIMITED = "private_limited"
    LLP             = "llp"
    TRUST           = "trust"


class TaskStatus(str, Enum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    OVERDUE     = "overdue"
    CANCELLED   = "cancelled"


class ComplianceType(str, Enum):
    ITR         = "itr"
    GST_GSTR1   = "gst_gstr1"
    GST_GSTR3B  = "gst_gstr3b"
    GST_GSTR9   = "gst_gstr9"
    TDS_RETURN  = "tds_return"
    AUDIT       = "audit"
    ROC_AOC4    = "roc_aoc4"
    ROC_MGT7    = "roc_mgt7"
    ADVANCE_TAX = "advance_tax"
    CUSTOM      = "custom"


@dataclass
class Client:
    client_id:      str
    name:           str
    client_type:    ClientType
    pan:            Optional[str] = None
    gstin:          Optional[str] = None
    email:          Optional[str] = None
    phone:          Optional[str] = None
    address:        Optional[str] = None
    # CA-specific
    engagement_start: Optional[date] = None
    annual_fee:     float = 0.0
    assigned_staff: Optional[str] = None
    notes:          Optional[str] = None
    active:         bool = True


@dataclass
class ComplianceTask:
    task_id:        str
    client_id:      str
    compliance_type: ComplianceType
    description:    str
    due_date:       date
    period:         str           # e.g. "FY 2024-25", "Mar-2025"
    status:         TaskStatus = TaskStatus.PENDING
    assigned_to:    Optional[str] = None
    completed_date: Optional[date] = None
    notes:          Optional[str] = None
    priority:       int = 2       # 1=high, 2=medium, 3=low
    fee:            float = 0.0

    @property
    def days_to_due(self) -> int:
        return (self.due_date - date.today()).days

    @property
    def is_overdue(self) -> bool:
        return date.today() > self.due_date and self.status not in (
            TaskStatus.COMPLETED, TaskStatus.CANCELLED
        )

    @property
    def effective_status(self) -> TaskStatus:
        if self.is_overdue:
            return TaskStatus.OVERDUE
        return self.status


@dataclass
class ClientNote:
    note_id:    str
    client_id:  str
    note_date:  date
    author:     str
    content:    str
    note_type:  str = "general"   # "general" | "advisory" | "complaint" | "meeting"


@dataclass
class ClientSummary:
    client:             Client
    pending_tasks:      int
    overdue_tasks:      int
    completed_tasks:    int
    next_due:           Optional[date]
    next_task:          Optional[str]
    annual_fee:         float
    revenue_ytd:        float   # fees billed this year


@dataclass
class PortfolioDashboard:
    total_clients:        int
    active_clients:       int
    total_tasks:          int
    overdue_tasks:        int
    due_this_week:        int
    due_this_month:       int
    completed_this_month: int
    client_summaries:     List[ClientSummary]
    urgent_items:         List[Dict]
    monthly_revenue:      float
    annual_revenue:       float


class CAClientManager:
    """
    Multi-client management system for Chartered Accountants.

    Usage:
        mgr = CAClientManager(ca_name="CA Ramesh Kumar")
        mgr.add_client(Client(...))
        mgr.add_task(ComplianceTask(...))
        dashboard = mgr.get_portfolio_dashboard()
    """

    def __init__(self, ca_name: str = ""):
        self.ca_name   = ca_name
        self._clients: Dict[str, Client] = {}
        self._tasks:   Dict[str, ComplianceTask] = {}
        self._notes:   Dict[str, List[ClientNote]] = {}

    def add_client(self, client: Client) -> None:
        self._clients[client.client_id] = client
        self._notes[client.client_id]   = []

    def add_task(self, task: ComplianceTask) -> None:
        self._tasks[task.task_id] = task

    def update_task_status(
        self,
        task_id:        str,
        status:         TaskStatus,
        completed_date: Optional[date] = None,
        notes:          Optional[str]  = None,
    ) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status         = status
            task.completed_date = completed_date
            if notes:
                task.notes = notes

    def add_note(self, note: ClientNote) -> None:
        self._notes.setdefault(note.client_id, []).append(note)

    def get_client_tasks(self, client_id: str) -> List[ComplianceTask]:
        return [t for t in self._tasks.values() if t.client_id == client_id]

    def get_client_summary(self, client_id: str) -> Optional[ClientSummary]:
        client = self._clients.get(client_id)
        if not client:
            return None

        tasks     = self.get_client_tasks(client_id)
        pending   = [t for t in tasks if t.effective_status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)]
        overdue   = [t for t in tasks if t.effective_status == TaskStatus.OVERDUE]
        completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]

        upcoming  = sorted(pending, key=lambda t: t.due_date)
        next_task = upcoming[0] if upcoming else None

        revenue_ytd = sum(t.fee for t in tasks if t.status == TaskStatus.COMPLETED)

        return ClientSummary(
            client          = client,
            pending_tasks   = len(pending),
            overdue_tasks   = len(overdue),
            completed_tasks = len(completed),
            next_due        = next_task.due_date if next_task else None,
            next_task       = next_task.description if next_task else None,
            annual_fee      = client.annual_fee,
            revenue_ytd     = revenue_ytd,
        )

    def get_portfolio_dashboard(self) -> PortfolioDashboard:
        today  = date.today()
        week   = today + timedelta(days=7)
        month  = today + timedelta(days=30)

        active_clients = [c for c in self._clients.values() if c.active]
        all_tasks      = list(self._tasks.values())

        overdue       = [t for t in all_tasks if t.effective_status == TaskStatus.OVERDUE]
        due_this_week = [t for t in all_tasks if today <= t.due_date <= week
                         and t.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)]
        due_this_month= [t for t in all_tasks if today <= t.due_date <= month
                         and t.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)]
        completed_tm  = [t for t in all_tasks
                         if t.status == TaskStatus.COMPLETED
                         and t.completed_date and t.completed_date >= today - timedelta(days=30)]

        # Urgent: overdue + due within 3 days
        urgent_cutoff = today + timedelta(days=3)
        urgent = sorted(
            [t for t in all_tasks
             if (t.effective_status == TaskStatus.OVERDUE or t.due_date <= urgent_cutoff)
             and t.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)],
            key=lambda t: t.due_date
        )
        urgent_items = [{
            "task_id":     t.task_id,
            "client_id":   t.client_id,
            "client_name": self._clients.get(t.client_id, Client("","",ClientType.INDIVIDUAL)).name,
            "description": t.description,
            "due_date":    t.due_date.isoformat(),
            "days_to_due": t.days_to_due,
            "status":      t.effective_status.value,
            "priority":    t.priority,
        } for t in urgent[:10]]

        summaries = [self.get_client_summary(c.client_id) for c in active_clients]
        summaries = [s for s in summaries if s is not None]

        monthly_rev = sum(t.fee for t in all_tasks
                          if t.status == TaskStatus.COMPLETED
                          and t.completed_date and t.completed_date.month == today.month)
        annual_rev  = sum(t.fee for t in all_tasks
                          if t.status == TaskStatus.COMPLETED
                          and t.completed_date and t.completed_date.year == today.year)

        return PortfolioDashboard(
            total_clients        = len(self._clients),
            active_clients       = len(active_clients),
            total_tasks          = len(all_tasks),
            overdue_tasks        = len(overdue),
            due_this_week        = len(due_this_week),
            due_this_month       = len(due_this_month),
            completed_this_month = len(completed_tm),
            client_summaries     = summaries,
            urgent_items         = urgent_items,
            monthly_revenue      = monthly_rev,
            annual_revenue       = annual_rev,
        )

    def generate_bulk_itr_list(self, financial_year: str = "2024-25") -> List[Dict]:
        """
        Generate list of clients requiring ITR filing with status and
        suggested ITR form based on client type and income sources.
        """
        itr_list = []
        for client in self._clients.values():
            if not client.active:
                continue

            itr_form = _suggest_itr_form(client.client_type)

            # Find existing ITR task for this FY
            existing = next((t for t in self._tasks.values()
                             if t.client_id == client.client_id
                             and t.compliance_type == ComplianceType.ITR
                             and financial_year in t.period), None)

            itr_list.append({
                "client_id":    client.client_id,
                "client_name":  client.name,
                "client_type":  client.client_type.value,
                "pan":          client.pan,
                "itr_form":     itr_form,
                "financial_year": financial_year,
                "status":       existing.effective_status.value if existing else "not_started",
                "due_date":     "31 Jul 2025",
                "assigned_to":  client.assigned_staff,
            })
        return itr_list


def _suggest_itr_form(client_type: ClientType) -> str:
    return {
        ClientType.INDIVIDUAL:      "ITR-1 or ITR-2",
        ClientType.HUF:             "ITR-2 or ITR-3",
        ClientType.PROPRIETARY:     "ITR-3 or ITR-4",
        ClientType.PARTNERSHIP:     "ITR-5",
        ClientType.PRIVATE_LIMITED: "ITR-6",
        ClientType.LLP:             "ITR-5",
        ClientType.TRUST:           "ITR-7",
    }.get(client_type, "ITR-3")


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def manage_clients(params: dict) -> dict:
    """JSON wrapper for Flask endpoint."""
    from datetime import datetime as _dt

    def _d(s) -> Optional[date]:
        if not s:
            return None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
            try:
                return _dt.strptime(s, fmt).date()
            except (ValueError, TypeError):
                pass
        return None

    mgr = CAClientManager(ca_name=params.get("ca_name", ""))

    for c in params.get("clients", []):
        mgr.add_client(Client(
            client_id        = c.get("client_id", str(id(c))),
            name             = c.get("name", ""),
            client_type      = ClientType(c.get("client_type", "individual")),
            pan              = c.get("pan"),
            gstin            = c.get("gstin"),
            email            = c.get("email"),
            phone            = c.get("phone"),
            engagement_start = _d(c.get("engagement_start")),
            annual_fee       = float(c.get("annual_fee", 0)),
            assigned_staff   = c.get("assigned_staff"),
            active           = bool(c.get("active", True)),
        ))

    for t in params.get("tasks", []):
        mgr.add_task(ComplianceTask(
            task_id         = t.get("task_id", str(id(t))),
            client_id       = t.get("client_id", ""),
            compliance_type = ComplianceType(t.get("compliance_type", "itr")),
            description     = t.get("description", ""),
            due_date        = _d(t.get("due_date")) or date.today(),
            period          = t.get("period", "FY 2024-25"),
            status          = TaskStatus(t.get("status", "pending")),
            assigned_to     = t.get("assigned_to"),
            fee             = float(t.get("fee", 0)),
            priority        = int(t.get("priority", 2)),
        ))

    action = params.get("action", "dashboard")

    if action == "itr_list":
        return {"itr_list": mgr.generate_bulk_itr_list(params.get("financial_year", "2024-25"))}

    if action == "client_summary":
        s = mgr.get_client_summary(params.get("client_id", ""))
        return asdict(s) if s else {"error": "Client not found"}

    dashboard = mgr.get_portfolio_dashboard()
    return {
        "total_clients":        dashboard.total_clients,
        "active_clients":       dashboard.active_clients,
        "total_tasks":          dashboard.total_tasks,
        "overdue_tasks":        dashboard.overdue_tasks,
        "due_this_week":        dashboard.due_this_week,
        "due_this_month":       dashboard.due_this_month,
        "completed_this_month": dashboard.completed_this_month,
        "monthly_revenue":      dashboard.monthly_revenue,
        "annual_revenue":       dashboard.annual_revenue,
        "urgent_items":         dashboard.urgent_items,
        "client_summaries":     [asdict(s) for s in dashboard.client_summaries],
    }
