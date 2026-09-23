import os
import time
from functools import lru_cache
from pathlib import Path
import jwt
from dotenv import load_dotenv

load_dotenv()


class JaasNotConfigured(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _config() -> tuple[str, str, str]:
    """Lazily resolve JaaS config on first use, not at import time — a missing
    key here must only break meeting joins, never crash the whole app on boot
    (which is what happened when the gitignored local secrets/ file wasn't
    present on the Railway deploy)."""
    app_id = os.environ.get("JAAS_APP_ID")
    kid = os.environ.get("JAAS_API_KEY_ID")
    if not app_id or not kid:
        raise JaasNotConfigured("JAAS_APP_ID / JAAS_API_KEY_ID are not set")

    # Preferred in production: paste the full PEM directly into JAAS_PRIVATE_KEY.
    # Some env var UIs (Railway included) collapse newlines, so normalize \n.
    private_key = os.environ.get("JAAS_PRIVATE_KEY")
    if private_key:
        private_key = private_key.replace("\\n", "\n")
    else:
        # Local dev fallback: a key file on disk (gitignored, never deployed).
        default_path = Path(__file__).resolve().parent.parent / "secrets" / "jaas_private_key.pem"
        key_path = Path(os.environ.get("JAAS_PRIVATE_KEY_PATH", str(default_path)))
        if not key_path.exists():
            raise JaasNotConfigured(
                f"No JAAS_PRIVATE_KEY env var and no key file at {key_path}"
            )
        private_key = key_path.read_text()

    return app_id, kid, private_key


def generate_jaas_token(
    room: str,
    user_id: str,
    name: str,
    email: str,
    moderator: bool,
    ttl_seconds: int = 3 * 60 * 60,
) -> str:
    """Build a signed JaaS JWT so the room is authenticated from the start,
    which removes meet.jit.si's 5-minute limit on anonymous group calls."""
    app_id, kid, private_key = _config()
    now = int(time.time())
    payload = {
        "aud": "jitsi",
        "iss": "chat",
        "sub": app_id,
        "room": room,
        "iat": now,
        "nbf": now - 10,
        "exp": now + ttl_seconds,
        "context": {
            "user": {
                "id": user_id,
                "name": name,
                "email": email,
                "moderator": moderator,
            },
            "features": {
                "livestreaming": moderator,
                "recording": moderator,
                "transcription": moderator,
                "outbound-call": False,
            },
        },
    }
    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )


def jaas_app_id() -> str:
    app_id, _, _ = _config()
    return app_id
