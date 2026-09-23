"""Agenda de gestion — calcule les échéances RH/Comptabilité/Tâches qui
requièrent une action, et relance la personne responsable par notification.

Une seule fonction de calcul (`compute_agenda_items`) sert deux usages :
  - lecture directe par GET /api/agenda-gestion/overview (page Agenda de
    gestion) ;
  - relance périodique (`scan_and_notify`, appelée par la boucle asyncio de
    main.py et par POST /api/agenda-gestion/scan-now) — avec anti-doublon
    (pas de rappel si un identique a déjà été envoyé dans les ~20 dernières
    heures)."""
import logging
from datetime import date, datetime, timedelta, timezone

from supabase import Client

from utils.notify import notify_users

log = logging.getLogger(__name__)

TASK_DUE_WINDOW_DAYS = 2       # tâche en retard, du jour, ou à J+1/J+2
LEAVE_PENDING_DAYS = 2          # congé en attente de décision depuis N jours
CONTRACT_WINDOW_DAYS = 30       # fin de contrat dans les N jours
PROBATION_WINDOW_DAYS = 7       # fin de période d'essai dans les N jours
APPROVAL_AGE_DAYS = 3           # opération en attente depuis N jours


def _role_ids(db: Client, roles: list[str]) -> list[str]:
    rows = db.from_("user_roles").select("user_id, role").in_("role", roles).execute().data or []
    return list({r["user_id"] for r in rows if r.get("user_id")})


def _safe(query_fn):
    """Exécute une requête et avale toute erreur (colonne/table pas encore
    migrée, etc.) — une source d'échéances indisponible ne doit jamais faire
    échouer tout l'agenda. Journalise pour rester diagnosticable."""
    try:
        return query_fn()
    except Exception:
        log.warning("Agenda de gestion — source indisponible (migration manquante ?)", exc_info=True)
        return None


def _parse_date(v) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def compute_agenda_items(db: Client) -> list[dict]:
    """Retourne les échéances RH / Comptabilité / Tâches qui requièrent une
    action, chacune avec sa personne responsable et son niveau d'urgence
    (overdue | today | soon)."""
    today = date.today()
    items: list[dict] = []

    admin_ids = _role_ids(db, ["admin"])
    hr_ids = _role_ids(db, ["admin", "rh", "assistant_rh"])
    accounting_ids = _role_ids(db, ["admin", "comptabilite"])

    def severity_for(delta: int) -> str:
        return "overdue" if delta < 0 else ("today" if delta == 0 else "soon")

    # ── Tâches avec échéance ────────────────────────────────────────────────
    tasks = (
        _safe(lambda: db.from_("tasks").select("id, title, status, priority, domain, assignee_id, due_date")
              .not_.is_("due_date", "null").not_.in_("status", ["done", "cancelled"])
              .execute().data)
        or []
    )
    for t in tasks:
        due = _parse_date(t.get("due_date"))
        if not due:
            continue
        delta = (due - today).days
        if delta > TASK_DUE_WINDOW_DAYS:
            continue
        items.append({
            "category": "task", "domain": t.get("domain") or "general",
            "title": t["title"], "due_date": t["due_date"], "severity": severity_for(delta),
            "responsible": [t["assignee_id"]] if t.get("assignee_id") else [],
            "link": f"/dashboard/tasks?focus={t['id']}",
        })

    # ── RH : congés en attente de décision ──────────────────────────────────
    leaves = _safe(lambda: db.from_("leave_requests").select("id, employee_id, type, start_date, created_at")
                    .eq("status", "pending").execute().data) or []
    emp_ids = list({l["employee_id"] for l in leaves if l.get("employee_id")})
    emp_names = {}
    if emp_ids:
        emp_names = {p["id"]: p.get("full_name") for p in (db.from_("profiles").select("id, full_name").in_("id", emp_ids).execute().data or [])}
    for lv in leaves:
        created = _parse_date(lv.get("created_at"))
        if not created or (today - created).days < LEAVE_PENDING_DAYS:
            continue
        name = emp_names.get(lv.get("employee_id"), "—")
        items.append({
            "category": "hr_leave", "domain": "rh",
            "title": f"Congé en attente — {name}", "due_date": lv.get("start_date"), "severity": "overdue",
            "responsible": hr_ids, "link": f"/dashboard/rh?tab=leaves&focus={lv['id']}",
        })

    # ── RH : fins de contrat proches ────────────────────────────────────────
    employees = _safe(lambda: db.from_("employees").select("id, full_name, contract_end")
                       .not_.is_("contract_end", "null").eq("status", "active")
                       .execute().data) or []
    for e in employees:
        end = _parse_date(e.get("contract_end"))
        if not end:
            continue
        delta = (end - today).days
        if not (0 <= delta <= CONTRACT_WINDOW_DAYS):
            continue
        items.append({
            "category": "hr_contract", "domain": "rh",
            "title": f"Fin de contrat — {e.get('full_name') or '—'}", "due_date": e["contract_end"],
            "severity": severity_for(delta), "responsible": hr_ids,
            "link": f"/dashboard/rh/employees/{e['id']}?tab=profil",
        })

    # ── RH : fins de période d'essai proches ────────────────────────────────
    probation = _safe(lambda: db.from_("employees").select("id, full_name, probation_end_date, probation_status")
                       .not_.is_("probation_end_date", "null").eq("probation_status", "in_progress")
                       .execute().data) or []
    for e in probation:
        end = _parse_date(e.get("probation_end_date"))
        if not end:
            continue
        delta = (end - today).days
        if not (0 <= delta <= PROBATION_WINDOW_DAYS):
            continue
        items.append({
            "category": "hr_probation", "domain": "rh",
            "title": f"Fin de période d'essai — {e.get('full_name') or '—'}", "due_date": e["probation_end_date"],
            "severity": severity_for(delta), "responsible": hr_ids,
            "link": f"/dashboard/rh/employees/{e['id']}?tab=profil",
        })

    # ── Comptabilité : opérations en attente depuis trop longtemps ─────────
    def _aged_pending(table: str, label: str, id_field: str = "id"):
        try:
            rows = db.from_(table).select(f"{id_field}, created_at").eq("status", "pending").execute().data or []
        except Exception:
            return
        for r in rows:
            created = _parse_date(r.get("created_at"))
            if not created or (today - created).days < APPROVAL_AGE_DAYS:
                continue
            items.append({
                "category": "accounting_approval", "domain": "comptabilite",
                "title": f"{label} en attente depuis {(today - created).days} j", "due_date": r.get("created_at"),
                "severity": "overdue", "responsible": accounting_ids,
                "link": f"/dashboard/accounting?tab=validations&focus={r[id_field]}",
            })

    _aged_pending("pending_operations", "Opération de caisse/comptes")
    _aged_pending("cash_notes", "Avance de caisse")
    _aged_pending("mission_notes", "Avance de frais de mission")
    _aged_pending("purchase_requests", "Demande d'achat")

    return items


async def scan_and_notify(db: Client) -> dict:
    """Calcule les échéances et relance chaque responsable — avec
    anti-doublon (pas de répétition d'un même rappel dans les ~20h)."""
    items = compute_agenda_items(db)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=20)).isoformat()
    sent = 0
    for item in items:
        recipients = item.get("responsible") or []
        if not recipients:
            continue
        title = f"Rappel — {item['title']}"
        for uid in recipients:
            try:
                existing = (
                    db.from_("notifications").select("id")
                    .eq("user_id", uid).eq("title", title).gte("created_at", cutoff)
                    .limit(1).execute().data
                )
                if existing:
                    continue
                notify_users(db, [uid], title=title, message=item.get("due_date") and f"Échéance : {item['due_date']}" or None,
                             type="warning" if item.get("severity") == "overdue" else "info", link=item.get("link"))
                sent += 1
            except Exception:
                log.exception("Échec de l'envoi du rappel pour %s (%s)", uid, item.get("category"))
    log.info("Agenda de gestion — scan terminé : %d échéance(s) détectée(s), %d rappel(s) envoyé(s)", len(items), sent)
    return {"items_found": len(items), "reminders_sent": sent}
