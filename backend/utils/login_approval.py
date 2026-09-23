"""Login approval gate for admin/professor accounts.

On first login, and again after 30 days of inactivity, admin/professor
accounts are blocked until a one-click email link is approved by the
designated approver. Other roles (student, cashier, accountant) are
never gated.
"""
import html
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from supabase import Client

from utils.email import send_email

log = logging.getLogger(__name__)

GATED_ROLES = {"admin", "professor", "rh", "assistant_rh", "comptabilite"}
INACTIVITY_DAYS = 30
TOKEN_TTL_HOURS = 24 * 7  # 7 days to click the email link
LAST_LOGIN_WRITE_THROTTLE_MINUTES = 10  # avoid a write on every single request

APPROVER_EMAIL = os.environ.get("LOGIN_APPROVER_EMAIL", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5178")

ROLE_LABELS = {
    "admin": "Administrateur", "professor": "Professeur",
    "rh": "RH", "assistant_rh": "Assistant RH", "comptabilite": "Comptabilité",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


_FRACTIONAL_SECONDS_RE = re.compile(r"\.(\d+)")


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    ts = ts.replace("Z", "+00:00")
    # PostgREST trims trailing zeros off the fractional-seconds part of a
    # timestamptz, so it can come back with 1-6 digits (e.g. ".7744") instead
    # of a fixed width. Python's datetime.fromisoformat() before 3.11 only
    # accepts exactly 3 or 6 digits and raises ValueError on anything else —
    # pad/truncate to 6 (microseconds) so any precision parses.
    ts = _FRACTIONAL_SECONDS_RE.sub(lambda m: "." + m.group(1)[:6].ljust(6, "0"), ts, count=1)
    return datetime.fromisoformat(ts)


def _approval_email_html(full_name: str, email: str, roles: list[str], reason: str, approve_url: str) -> str:
    # Hex equivalents of the app's OKLCH brand palette (DESIGN_SYSTEM.md) —
    # email clients (especially Outlook desktop) don't render oklch(), and
    # most strip <style> blocks, so everything here is inlined, table-based.
    ink, primary, primary_deep = "#16302b", "#2f6e60", "#1f4d42"
    cream, paper, line, muted = "#f7f5f0", "#ffffff", "#e3e6e2", "#6c7570"
    good, warn = "#3f9c6d", "#c98a2e"

    name = html.escape(full_name)
    mail = html.escape(email)
    role_labels = html.escape(", ".join(ROLE_LABELS.get(r, r) for r in roles if r in GATED_ROLES))
    is_first_login = reason == "first_login"

    badge_color, badge_bg, badge_text = (
        (good, "#e8f5ee", "PREMIÈRE CONNEXION") if is_first_login else (warn, "#faf1e2", "COMPTE INACTIF 30+ JOURS")
    )
    reason_text = (
        f"<b>{name}</b> vient de tenter de se connecter à IPISB&nbsp;Connect pour la toute première fois. "
        f"Par sécurité, l'accès de tout nouveau compte administrateur ou professeur doit être validé manuellement."
        if is_first_login
        else
        f"<b>{name}</b> n'a plus été actif·ve sur la plateforme depuis plus de 30&nbsp;jours et tente de s'y "
        f"reconnecter. Par sécurité, les comptes dormants doivent être revalidés avant de retrouver l'accès."
    )

    return f"""\
<div style="background:{cream};padding:32px 16px;font-family:Georgia,'Times New Roman',serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;margin:0 auto;">
    <tr><td style="padding-bottom:20px;text-align:center;">
      <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto;">
        <tr>
          <td style="width:30px;height:30px;background:{ink};border-radius:8px;text-align:center;vertical-align:middle;">
            <span style="color:{paper};font-family:Georgia,serif;font-size:15px;font-weight:bold;line-height:30px;">I</span>
          </td>
          <td style="padding-left:10px;font-family:Georgia,serif;font-size:17px;line-height:1;">
            <span style="color:{ink};font-weight:bold;">IPISB</span>
            <span style="color:{primary};font-style:italic;">&nbsp;Connect</span>
          </td>
        </tr>
      </table>
    </td></tr>

    <tr><td style="background:{paper};border:1px solid {line};border-radius:16px;padding:36px 32px;">

      <p style="margin:0 0 14px;font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:bold;
                letter-spacing:.14em;color:{primary};text-transform:uppercase;">
        Demande d'accès
      </p>

      <h1 style="margin:0 0 18px;font-family:Georgia,serif;font-size:26px;font-weight:normal;color:{ink};line-height:1.25;">
        {"Autoriser une nouvelle" if is_first_login else "Revalider une"} connexion&nbsp;?
      </h1>

      <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">
        <tr><td style="background:{badge_bg};border-radius:999px;padding:5px 12px;">
          <span style="font-family:Arial,Helvetica,sans-serif;font-size:10.5px;font-weight:bold;
                       letter-spacing:.06em;color:{badge_color};">{badge_text}</span>
        </td></tr>
      </table>

      <p style="margin:0 0 24px;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.65;color:#3a3f3c;">
        {reason_text}
      </p>

      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="background:{cream};border:1px solid {line};border-left:3px solid {primary};
                    border-radius:10px;margin:0 0 28px;">
        <tr><td style="padding:16px 18px;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:{ink};line-height:1.9;">
          <b>Nom</b> &nbsp;{name}<br/>
          <b>Email</b> &nbsp;{mail}<br/>
          <b>Rôle</b> &nbsp;{role_labels}
        </td></tr>
      </table>

      <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 22px;">
        <tr><td style="background:{ink};border-radius:999px;">
          <a href="{approve_url}"
             style="display:inline-block;padding:13px 28px;font-family:Arial,Helvetica,sans-serif;
                    font-size:14px;font-weight:bold;color:{paper};text-decoration:none;">
            Autoriser cette connexion →
          </a>
        </td></tr>
      </table>

      <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:11.5px;color:{muted};line-height:1.6;">
        Si le bouton ne fonctionne pas, copiez ce lien&nbsp;:<br/>
        <a href="{approve_url}" style="color:{primary_deep};word-break:break-all;">{approve_url}</a>
      </p>
    </td></tr>

    <tr><td style="padding-top:22px;text-align:center;">
      <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:11px;color:{muted};line-height:1.7;">
        Ce lien expire dans 7&nbsp;jours. Si vous n'êtes pas à l'origine de cette demande, ignorez simplement cet email.<br/>
        IPISB Connect — El Jadida, Maroc
      </p>
    </td></tr>
  </table>
</div>"""


def _create_and_send_approval(db: Client, user_id: str, email: str, full_name: str, roles: list[str], reason: str) -> None:
    existing = (
        db.from_("login_approval_requests")
        .select("id, expires_at")
        .eq("user_id", user_id).eq("status", "pending")
        .execute().data
        or []
    )
    now = _now()
    if any((_parse(r["expires_at"]) or now) > now for r in existing):
        return  # a live request is already pending — don't spam another email

    token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(hours=TOKEN_TTL_HOURS)
    db.from_("login_approval_requests").insert({
        "user_id": user_id, "token": token, "reason": reason,
        "status": "pending", "expires_at": expires_at.isoformat(),
    }).execute()

    if not APPROVER_EMAIL:
        return
    approve_url = f"{FRONTEND_URL}/approve-login?token={token}"
    subject = (
        f"Nouvelle connexion à valider — {full_name}"
        if reason == "first_login"
        else f"Connexion à revalider — {full_name} inactif depuis 30+ jours"
    )
    send_email(APPROVER_EMAIL, subject, _approval_email_html(full_name, email, roles, reason, approve_url))


def enforce_login_gate(db: Client, user_id: str, email: str, roles: list[str]) -> None:
    """Raises HTTPException(403) and fires an approval email if this
    admin/professor account is pending first-time or post-inactivity
    approval. No-op for other roles. Refreshes last_login_at on success."""
    if not GATED_ROLES.intersection(roles):
        return

    try:
        rows = (
            db.from_("profiles").select("full_name, login_approved_at, last_login_at")
            .eq("id", user_id).execute().data
        )
    except Exception:
        # login_approved_at/last_login_at not provisioned yet (migration not
        # run) — fail open rather than locking every admin/professor out.
        log.warning("Login approval gate: could not read profiles columns — is the migration applied?", exc_info=True)
        return
    profile = rows[0] if rows else {}
    full_name = profile.get("full_name") or email
    login_approved_at = _parse(profile.get("login_approved_at"))
    last_login_at = _parse(profile.get("last_login_at"))
    now = _now()

    if login_approved_at is None:
        _create_and_send_approval(db, user_id, email, full_name, roles, "first_login")
        raise HTTPException(403, "pending_approval")

    if last_login_at is not None and (now - last_login_at) > timedelta(days=INACTIVITY_DAYS):
        _create_and_send_approval(db, user_id, email, full_name, roles, "inactivity")
        raise HTTPException(403, "pending_approval")

    if last_login_at is None or (now - last_login_at) > timedelta(minutes=LAST_LOGIN_WRITE_THROTTLE_MINUTES):
        db.from_("profiles").update({"last_login_at": now.isoformat()}).eq("id", user_id).execute()


def approve_login_token(db: Client, token: str) -> bool:
    """Returns True if the token was valid and the account is now approved."""
    rows = (
        db.from_("login_approval_requests").select("id, user_id, expires_at, status")
        .eq("token", token).execute().data
    )
    if not rows:
        return False
    req = rows[0]
    if req["status"] != "pending" or (_parse(req["expires_at"]) or _now()) < _now():
        return False

    now = _now()
    db.from_("login_approval_requests").update({"status": "approved", "approved_at": now.isoformat()}).eq("id", req["id"]).execute()
    # last_login_at cleared so the next login isn't immediately re-flagged as
    # "inactive" by a stale timestamp from before this approval.
    db.from_("profiles").update({"login_approved_at": now.isoformat(), "last_login_at": None}).eq("id", req["user_id"]).execute()
    return True
