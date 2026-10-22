"""Chiffrement et déchiffrement des données personnelles (PB-19).

La table ``identites_pii`` ne contient que des colonnes ``*_chiffre`` en
``bytea``. Le chiffrement est réalisé par PostgreSQL avec ``pgcrypto`` et
l'algorithme AES-256. La clé n'est jamais écrite en base, dans les logs ou
dans les fichiers de rapport.

Le module est volontairement centralisé : aucun autre module ne doit appeler
``pgp_sym_encrypt`` ou ``pgp_sym_decrypt`` directement.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from typing import Any

import pandas as pd
from sqlalchemy import Connection, text

from predicare.db.schemas import PII_ENCRYPTED_COLUMNS

logger = logging.getLogger(__name__)

CANARY_VALUE = "predicare-pii-canary"
MIN_KEY_LENGTH = 32
DEMO_KEY_PREFIX = "change_me"
DEFAULT_KEY_VERSION = 1

_INSERT_IDENTITIES = text(
    """
    INSERT INTO identites_pii (
        assure_id,
        nom_chiffre,
        prenoms_chiffre,
        date_naissance_chiffre,
        telephone_chiffre,
        email_chiffre,
        adresse_chiffre,
        numero_cin_chiffre,
        pii_key_version
    )
    VALUES (
        :assure_id,
        pgp_sym_encrypt(CAST(:nom AS text), CAST(:key AS text), 'cipher-algo=aes256'),
        pgp_sym_encrypt(CAST(:prenoms AS text), CAST(:key AS text), 'cipher-algo=aes256'),
        pgp_sym_encrypt(CAST(:date_naissance AS text), CAST(:key AS text), 'cipher-algo=aes256'),
        pgp_sym_encrypt(CAST(:telephone AS text), CAST(:key AS text), 'cipher-algo=aes256'),
        pgp_sym_encrypt(CAST(:email AS text), CAST(:key AS text), 'cipher-algo=aes256'),
        pgp_sym_encrypt(CAST(:adresse AS text), CAST(:key AS text), 'cipher-algo=aes256'),
        pgp_sym_encrypt(CAST(:numero_cin AS text), CAST(:key AS text), 'cipher-algo=aes256'),
        :pii_key_version
    )
    """
)

_DECRYPT_IDENTITY = text(
    """
    SELECT
        assure_id,
        pgp_sym_decrypt(nom_chiffre, CAST(:key AS text)) AS nom,
        pgp_sym_decrypt(prenoms_chiffre, CAST(:key AS text)) AS prenoms,
        pgp_sym_decrypt(date_naissance_chiffre, CAST(:key AS text)) AS date_naissance,
        pgp_sym_decrypt(telephone_chiffre, CAST(:key AS text)) AS telephone,
        pgp_sym_decrypt(email_chiffre, CAST(:key AS text)) AS email,
        pgp_sym_decrypt(adresse_chiffre, CAST(:key AS text)) AS adresse,
        pgp_sym_decrypt(numero_cin_chiffre, CAST(:key AS text)) AS numero_cin,
        pii_key_version
    FROM identites_pii
    WHERE assure_id = :assure_id
    """
)


class PIIError(RuntimeError):
    """Erreur de configuration ou de manipulation des données PII."""


def get_pii_key() -> str:
    """Lit la clé PII dans l'environnement.

    La clé est obligatoire dès que le bootstrap doit charger ou déchiffrer des
    identités. Elle ne doit jamais être fournie en argument de ligne de
    commande (visible dans l'historique du shell).
    """
    key = os.environ.get("PII_ENCRYPTION_KEY")
    if not key:
        raise PIIError("PII_ENCRYPTION_KEY absente de l'environnement.")
    return key


def pii_key_version() -> int:
    """Version de clé utilisée pour les nouvelles écritures."""
    raw = os.environ.get("PII_KEY_VERSION", str(DEFAULT_KEY_VERSION))
    try:
        version = int(raw)
    except ValueError as exc:
        raise PIIError("PII_KEY_VERSION doit être un entier >= 1.") from exc
    if version < 1:
        raise PIIError("PII_KEY_VERSION doit être un entier >= 1.")
    return version


def validate_pii_key(
    key: str | None = None,
    app_env: str | None = None,
) -> str:
    """Valide la forme de la clé et refuse les valeurs de démonstration en prod."""
    resolved = (key if key is not None else get_pii_key()).strip()
    if len(resolved) < MIN_KEY_LENGTH:
        raise PIIError(f"PII_ENCRYPTION_KEY trop courte : {MIN_KEY_LENGTH} caractères minimum.")

    environment = (app_env or os.environ.get("APP_ENV", "dev")).lower()
    if environment in {"prod", "production"} and resolved.startswith(DEMO_KEY_PREFIX):
        raise PIIError("Clé PII de démonstration interdite en production.")
    if resolved.startswith(DEMO_KEY_PREFIX):
        logger.warning(
            "PII_ENCRYPTION_KEY utilise une valeur de démonstration. "
            "Remplacez-la avant tout déploiement."
        )
    return resolved


def encrypt_canary(conn: Connection, key: str) -> bytes:
    """Chiffre une valeur connue, conservée dans ``ingest_state``."""
    try:
        value = conn.execute(
            text(
                """
                SELECT pgp_sym_encrypt(
                    CAST(:value AS text),
                    CAST(:key AS text),
                    'cipher-algo=aes256'
                ) AS valeur
                """
            ),
            {"value": CANARY_VALUE, "key": key},
        ).scalar_one()
    except Exception as exc:  # noqa: BLE001 - on masque le détail cryptographique
        raise PIIError(
            "Chiffrement canari impossible : clé ou extension pgcrypto invalide."
        ) from exc
    return bytes(value)


def verify_canary(conn: Connection, key: str, ciphertext: bytes) -> None:
    """Vérifie que la clé fournie déchiffre bien le canari du bootstrap précédent."""
    try:
        value = conn.execute(
            text(
                """
                SELECT pgp_sym_decrypt(
                    CAST(:ciphertext AS bytea),
                    CAST(:key AS text)
                ) AS valeur
                """
            ),
            {"ciphertext": ciphertext, "key": key},
        ).scalar_one()
    except Exception as exc:  # noqa: BLE001 - on masque le détail cryptographique
        raise PIIError("Clé PII incorrecte ou canari corrompu.") from exc

    if value != CANARY_VALUE:
        raise PIIError("Clé PII incorrecte : le canari ne correspond pas.")


def canary_check(conn: Connection, key: str) -> None:
    """Vérifie que pgcrypto et la clé permettent un aller-retour."""
    verify_canary(conn, key, encrypt_canary(conn, key))


def _plain(value: Any) -> Any:
    """Convertit les valeurs Pandas/Numpy en valeurs Python natives ou None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            return value
    return value


def _identity_text(value: Any) -> str | None:
    """Normalise un champ PII textuel, notamment les CIN lus en float par Pandas."""
    value = _plain(value)
    if value is None:
        return None
    if isinstance(value, float):
        return str(int(value))
    return str(value).strip() or None


def _chunks(rows: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def insert_identities(
    conn: Connection,
    identities: pd.DataFrame,
    key: str,
    key_version: int | None = None,
) -> int:
    """Chiffre et insère les identités dans ``identites_pii``.

    Le DataFrame doit contenir les colonnes du CSV brut (``nom``, ``prenoms``,
    etc.). Les colonnes ``sexe`` et ``ville`` sont ignorées : elles restent
    dans la table pseudonymisée ``assures``.
    """
    if identities.empty:
        return 0

    version = key_version if key_version is not None else pii_key_version()
    rows: list[dict[str, Any]] = []
    for record in identities.to_dict("records"):
        row = {"assure_id": _plain(record.get("assure_id")), "key": key, "pii_key_version": version}
        for source_column in PII_ENCRYPTED_COLUMNS:
            row[source_column] = _identity_text(record.get(source_column))
        if row["assure_id"] is None:
            raise PIIError("Identité sans assure_id.")
        rows.append(row)

    try:
        for chunk in _chunks(rows, 500):
            conn.execute(_INSERT_IDENTITIES, chunk)
    except Exception:  # noqa: BLE001 - ne pas propager de valeurs PII
        raise PIIError("Insertion des identités chiffrées impossible.") from None
    return len(rows)


def decrypt_identity(conn: Connection, assure_id: str, key: str) -> dict[str, Any] | None:
    """Déchiffre une identité pour un usage explicitement autorisé."""
    try:
        row = (
            conn.execute(_DECRYPT_IDENTITY, {"assure_id": assure_id, "key": key}).mappings().first()
        )
    except Exception:  # noqa: BLE001 - message générique
        raise PIIError(
            "Déchiffrement PII impossible : clé incorrecte ou données corrompues."
        ) from None
    return dict(row) if row else None
