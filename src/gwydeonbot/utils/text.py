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
