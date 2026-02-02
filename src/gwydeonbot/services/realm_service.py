from __future__ import annotations

from ..clients.blizzard_api import BlizzardApiClient
from ..domain.errors import WowNotFound


class RealmService:
    def __init__(self, blizzard: BlizzardApiClient):
        self._blizzard = blizzard

    @property
    def region(self) -> str:
        return self._blizzard.region

    async def get_realm_status_text(self, *, realm_slug: str) -> str:
        idx = await self._blizzard.realm_index()
        realms = idx.get("realms") or []

        realm = next((r for r in realms if isinstance(r, dict) and r.get("slug") == realm_slug), None)
        if not realm:
            raise WowNotFound()

        realm_id = realm.get("id")
        if not realm_id:
            raise WowNotFound()

        realm_data = await self._blizzard.realm_by_id(int(realm_id))
        cr_href = ((realm_data.get("connected_realm") or {}).get("href"))
        if not cr_href:
            return "Desconocido"

        cr_id = BlizzardApiClient.extract_id_from_href(cr_href)
        if not cr_id:
            return "Desconocido"

        cr = await self._blizzard.connected_realm(cr_id)
        status_obj = cr.get("status") or {}
        status_type = status_obj.get("type")  # UP / DOWN

        mapping = {"UP": "Online ✅", "DOWN": "Offline ❌"}
        return mapping.get(status_type, str(status_type or "Desconocido"))
