# Run this script ONCE (after applying sql/supabase_l19_roles_caisse_approvals.sql)
# to seed the caisse (cashier) and comptable (accountant) staff accounts.
import os
from datetime import datetime, timezone
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

STAFF = [
    {"email": "caisse@ipisb.ma",    "password": "Caisse@IPISB2026!", "full_name": "Caisse IPISB",    "role": "cashier"},
    {"email": "comptable@ipisb.ma", "password": "Compta@IPISB2026!", "full_name": "Comptable IPISB", "role": "accountant"},
]


def seed_staff(email: str, password: str, full_name: str, role: str):
    try:
        existing = db.auth.admin.list_users()
        existing_by_email = {u.email: u for u in existing}
    except Exception as e:
        print(f"[WARN] Could not list users: {e}")
        existing_by_email = {}

    user = existing_by_email.get(email)
    if user is not None:
        print(f"[SKIP] {email} already exists — ensuring profile + role.")
        uid = str(user.id)
    else:
        try:
            res = db.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"full_name": full_name},
            })
        except Exception as e:
            print(f"[ERROR] Failed to create auth user for {email}: {e}")
            return
        if res.user is None:
            print(f"[ERROR] No user returned for {email}")
            return
        uid = str(res.user.id)

    now = datetime.now(timezone.utc).isoformat()
    try:
        db.from_("profiles").upsert({
            "id": uid, "email": email, "full_name": full_name, "created_at": now,
        }).execute()
    except Exception as e:
        print(f"[ERROR] Failed to upsert profile for {email}: {e}")
        return

    try:
        db.from_("user_roles").upsert({"user_id": uid, "role": role}).execute()
    except Exception as e:
        print(f"[ERROR] Failed to assign role '{role}' for {email}: {e}")
        print("        (Did you run sql/supabase_l19_roles_caisse_approvals.sql first?)")
        return

    print(f"[OK] {role:10s} {email}  /  {password}")


if __name__ == "__main__":
    print("Seeding IPISB staff accounts (caisse + comptable)...")
    for s in STAFF:
        seed_staff(**s)
    print("Done.")
