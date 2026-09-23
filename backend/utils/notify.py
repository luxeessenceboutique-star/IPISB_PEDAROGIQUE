from supabase import Client


def notify_users(
    db: Client,
    user_ids: list[str],
    title: str,
    message: str | None = None,
    type: str = "info",
    link: str | None = None,
) -> None:
    if not user_ids:
        return
    rows = [
        {"user_id": uid, "title": title, "message": message, "type": type, "link": link}
        for uid in user_ids
    ]
    db.from_("notifications").insert(rows).execute()
