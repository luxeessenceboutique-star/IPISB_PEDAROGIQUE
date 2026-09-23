import os
from functools import lru_cache
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from gotrue.errors import AuthRetryableError
from dotenv import load_dotenv

from utils.login_approval import enforce_login_gate
from permissions import Channel, ENTITY_CHANNELS, channel_for

load_dotenv()

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY: str = os.environ["SUPABASE_SERVICE_KEY"]
FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "http://localhost:5178")


def _force_http1(client: Client) -> None:
    """postgrest-py ET gotrue-py forcent http2=True pour leurs sessions HTTP
    (voir postgrest/_sync/client.py::SyncPostgrestClient.create_session et
    gotrue/_sync/gotrue_base_api.py::SyncGoTrueBaseAPI.__init__) sans laisser
    de moyen public de le désactiver via create_client/ClientOptions dans ces
    versions. Sur ce déploiement, la connexion HTTP/2 vers Supabase est coupée
    par le réseau (RemoteProtocolError/ConnectionTerminated) après seulement
    1-2 requêtes — pas seulement après une inactivité prolongée — ce qui
    pointe vers un intermédiaire réseau qui gère mal le multiplexage HTTP/2
    plutôt qu'un simple timeout d'inactivité. HTTP/1.1 keep-alive ne connaît
    pas ce mode de panne, donc on remplace les deux sessions (REST ET auth —
    get_current_user appelle db.auth.get_user() à chaque requête) par des
    équivalentes en HTTP/1.1 juste après la création du client."""
    old = client.postgrest.session  # déclenche la création lazy si besoin
    new = type(old)(
        base_url=old.base_url,
        headers=old.headers,
        timeout=old.timeout,
        follow_redirects=True,
        http2=False,
    )
    client.postgrest.session = new
    try:
        old.close()
    except Exception:
        pass

    old_auth = client.auth._http_client
    new_auth = type(old_auth)(follow_redirects=True, http2=False)
    client.auth._http_client = new_auth
    # client.auth.admin (SyncGoTrueAdminAPI) reçoit sa propre référence à
    # _http_client à la construction de GoTrueClient (voir gotrue_client.py
    # `self.admin = SyncGoTrueAdminAPI(http_client=self._http_client)`) —
    # réassigner client.auth._http_client ci-dessus ne le met PAS à jour. Sans
    # cette ligne, client.auth.admin garde le client HTTP/2 fermé juste après
    # (old_auth.close()) et toute création/suppression d'utilisateur échoue
    # avec "Cannot send a request, as the client has been closed."
    client.auth.admin._http_client = new_auth
    try:
        old_auth.close()
    except Exception:
        pass


@lru_cache(maxsize=1)
def _client() -> Client:
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    _force_http1(client)
    return client


def get_db() -> Client:
    return _client()


def reset_db_client() -> None:
    """Jette le client Supabase mis en cache pour forcer une nouvelle connexion
    à la prochaine requête. Le client (et son pool de connexions sous-jacent)
    est un singleton réutilisé pour toute la durée de vie du process ; si une
    connexion se retrouve coupée côté serveur/réseau, httpx ne s'en aperçoit
    qu'en la réutilisant, ce qui fait échouer la requête suivante avec un
    RemoteProtocolError. Voir le handler dans main.py."""
    _client.cache_clear()


_bearer = HTTPBearer(auto_error=True)


class CurrentUser:
    def __init__(self, id: str, email: str, roles: list[str]):
        self.id = id
        self.email = email
        self.roles = roles

    def is_admin(self) -> bool:
        return "admin" in self.roles

    def is_prof(self) -> bool:
        return "professor" in self.roles

    def is_cashier(self) -> bool:
        return "cashier" in self.roles

    def is_accountant(self) -> bool:
        return "accountant" in self.roles

    def is_rh(self) -> bool:
        return "rh" in self.roles

    def is_assistant_rh(self) -> bool:
        return "assistant_rh" in self.roles

    def is_comptabilite(self) -> bool:
        return "comptabilite" in self.roles

    def can_create(self) -> bool:
        return self.is_admin() or self.is_prof()

    def can_read_accounting(self) -> bool:
        """Admin/comptabilité (plein accès), comptable (lecture seule), caissier (saisie→validation)."""
        return self.is_admin() or self.is_comptabilite() or self.is_accountant() or self.is_cashier()

    def can_access_rh(self) -> bool:
        """Toute la plateforme RH (Employés, Congés, Recrutement…) — sauf Paie."""
        return self.is_admin() or self.is_rh() or self.is_assistant_rh()

    def can_access_rh_payroll(self) -> bool:
        """Paie / salaires — assistant_rh en est exclu (accès RH restreint)."""
        return self.is_admin() or self.is_rh()

    def can_access_accounting_full(self) -> bool:
        """Plein accès Comptabilité (équivalent admin) — hors RH/Cours."""
        return self.is_admin() or self.is_comptabilite()

    ADMIN_ASSIGNABLE_ROLES = ["professor", "rh", "assistant_rh", "comptabilite"]

    def assignable_roles(self) -> list[str]:
        """Rôles que cet utilisateur peut attribuer en créant un nouveau compte."""
        if self.is_admin():
            return list(self.ADMIN_ASSIGNABLE_ROLES)
        if self.is_prof():
            return ["student"]
        return []

    # ── Canaux de validation V1/V2 (permissions.py) ─────────────────────
    def has_v1_role(self, entity: str) -> bool:
        """V1 = le(s) rôle(s) métier qui exécute·nt normalement `entity`."""
        _, v1_roles = ENTITY_CHANNELS[entity]
        return any(r in self.roles for r in v1_roles)

    def can_act(self, entity: str, action: str, amount: float | None = None) -> bool:
        """Autorise `action` sur `entity` selon son canal (permissions.py).

        action ∈ {"create", "view", "edit", "export", "import",
        "validate_v1", "validate_v2", "cancel", "delete"}. V2 = admin,
        toujours. Si `entity` a un barème par montant
        (permissions.AMOUNT_TIERED_ENTITIES) et que `amount` est fourni, le
        canal effectif en dépend (ex. Demandes d'achat : ≤500 MAD → canal 1,
        500–10 000 → canal 2, >10 000 → canal 3) ; sinon le canal fixe du
        registre s'applique. Lève KeyError si `entity` n'est pas encore
        enregistrée — un router ne doit appeler ceci qu'une fois son entité
        déclarée dans permissions.py.
        """
        channel = channel_for(entity, amount)
        is_v1 = self.has_v1_role(entity)
        is_v2 = self.is_admin()

        if channel == Channel.SELF_VALIDATED:
            # V1 s'auto-valide entièrement ; V2 garde un accès de supervision
            # sur tout (Voir/Exporter/Annuler/Supprimer comme sur le reste).
            return is_v1 or is_v2

        if channel == Channel.V1_THEN_V2:
            if action in ("cancel", "delete", "validate_v2"):
                return is_v2
            if action == "validate_v1":
                return is_v1
            return is_v1 or is_v2  # create/view/export/import/edit partagés

        if channel == Channel.V2_ONLY:
            return is_v2

        return False


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[Client, Depends(get_db)],
) -> CurrentUser:
    token = credentials.credentials
    try:
        resp = db.auth.get_user(token)
        if resp.user is None:
            raise ValueError("no user")
    except AuthRetryableError:
        # Coupure réseau/connexion transitoire vers Supabase (gotrue classe
        # déjà ça à part des vraies erreurs d'auth) — ne PAS la confondre avec
        # un token invalide/expiré : ça déconnecterait un utilisateur dont la
        # session est parfaitement valide à cause d'un simple aléa réseau.
        # On laisse remonter pour que le middleware de main.py réinitialise
        # le client et retente (GET/HEAD) au lieu d'afficher un faux 401.
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    uid = str(resp.user.id)
    roles_data = db.from_("user_roles").select("role").eq("user_id", uid).execute().data or []
    roles = [r["role"] for r in roles_data]
    enforce_login_gate(db, uid, resp.user.email or "", roles)
    return CurrentUser(id=uid, email=resp.user.email or "", roles=roles)
