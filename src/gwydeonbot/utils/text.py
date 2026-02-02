from __future__ import annotations


def normalize_realm_slug(realm: str) -> str:
    return (
        realm.strip()
        .lower()
        .replace("’", "")
        .replace("'", "")
        .replace(" ", "-")
    )


def normalize_character_name(name: str) -> str:
    return name.strip().lower()


def normalize_guild_slug(name: str) -> str:
    """
    Normaliza el nombre de una guild para usarlo como slug en endpoints/URLs.
    Regla práctica: minúsculas, sin apóstrofes, espacios -> guiones.
    """
    return (
        name.strip()
        .lower()
        .replace("’", "")
        .replace("'", "")
        .replace(" ", "-")
    )
