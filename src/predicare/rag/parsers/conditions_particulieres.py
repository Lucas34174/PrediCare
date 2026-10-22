"""Parser spécialisé pour les Conditions Particulières (CP_CTR-*.pdf).

Structure observée :
- Fichiers : CP_CTR-000048.pdf, CP_CTR-000066.pdf, etc.
- Métadonnées du contrat (numéro, police, formule, souscripteur, dates, prime)
- Tableau des bénéficiaires (identifiants pseudonymisés)
- Section "Garanties applicables"

Stratégie : 3 types de blocs → contrat_metadata, beneficiaire, section_garanties.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pdfplumber

from predicare.rag.parsers.base import BaseParser, ParsedDocument

logger = logging.getLogger(__name__)


# ─── Regex de détection ────────────────────────────────────────────────────────

RE_CONTRAT = re.compile(
    r"Contrat\s+(CTR-\d+)\s*[–\-—]\s*Police\s+([A-Z]{2,4}-[\d-]+)\s*[–\-—]\s*Formule\s+(PREMIUM|CONFORT|ESSENTIEL)",
    re.IGNORECASE,
)
RE_SOUSCRIPTEUR = re.compile(
    r"Souscripteur\s*:\s*(.+?)\s*\((.+?)\)",
    re.IGNORECASE,
)
RE_DATE_POLICE = re.compile(r"Date d'effet de la police\s*:\s*(\d{4}-\d{2}-\d{2})")
RE_DATE_CONTRAT = re.compile(r"Date d'effet du contrat\s*:\s*(\d{4}-\d{2}-\d{2})")
RE_STATUT = re.compile(r"Statut\s*:\s*(\w+)", re.IGNORECASE)
RE_PRIME_TOTALE = re.compile(
    r"Prime annuelle\s*:\s*([\d\s]+)\s*Ar par bénéficiaire,"
    r"\s*soit\s*([\d\s]+)\s*Ar pour\s*(\d+)\s*bénéficiaire"
)
RE_PLAFOND = re.compile(r"Plafond annuel global par bénéficiaire\s*:\s*([\d\s]+)\s*Ar")
RE_SECTION_BENEF = re.compile(r"Bénéficiaires\s*\(identifiants pseudonymisés\)", re.IGNORECASE)
RE_SECTION_GARANTIES = re.compile(r"Garanties applicables", re.IGNORECASE)


# ─── Normalisation ─────────────────────────────────────────────────────────────


def _normalize(text: str) -> str:
    """Normalise les espaces spéciaux."""
    return text.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2009", " ")


def _parse_montant(s: str) -> int | None:
    """Convertit '2 100 000' en 2100000."""
    cleaned = re.sub(r"[^\d]", "", s or "")
    return int(cleaned) if cleaned else None


# ─── Parser ────────────────────────────────────────────────────────────────────


class ConditionsParticulieresParser(BaseParser):
    """Parser des Conditions Particulières."""

    doc_type = "conditions_particulieres"

    def parse(self, path: Path) -> ParsedDocument:
        logger.info("Parsing Conditions Particulières : %s", path.name)

        texte_complet = self._extraire_texte(path)
        texte = _normalize(texte_complet)

        # Extraire les métadonnées du contrat
        metadata = self._extraire_metadata(texte)
        logger.info(
            "Contrat %s | Formule %s | %s bénéficiaires annoncés",
            metadata.get("contract_id"),
            metadata.get("formule"),
            metadata.get("nb_beneficiaires", "?"),
        )

        # Extraire les bénéficiaires (tableau)
        beneficiaires = self._extraire_beneficiaires(path, metadata)

        # Blocs
        blocs: list[dict[str, Any]] = []

        # 1. Métadonnées contrat
        blocs.append(
            {
                "block_type": "contrat_metadata",
                "contract_id": metadata.get("contract_id"),
                "police_id": metadata.get("police_id"),
                "formule": metadata.get("formule"),
                "souscripteur": metadata.get("souscripteur"),
                "secteur": metadata.get("secteur"),
                "date_effet_police": metadata.get("date_effet_police"),
                "date_effet_contrat": metadata.get("date_effet_contrat"),
                "statut": metadata.get("statut"),
                "prime_par_beneficiaire": metadata.get("prime_par_beneficiaire"),
                "prime_totale": metadata.get("prime_totale"),
                "nb_beneficiaires": metadata.get("nb_beneficiaires"),
                "plafond_global": metadata.get("plafond_global"),
            }
        )

        # 2. Bénéficiaires
        for b in beneficiaires:
            blocs.append(
                {
                    "block_type": "beneficiaire",
                    "contract_id": metadata.get("contract_id"),
                    "police_id": metadata.get("police_id"),
                    "formule": metadata.get("formule"),
                    "souscripteur": metadata.get("souscripteur"),
                    **b,
                }
            )

        # 3. Section garanties applicables
        match_gar = RE_SECTION_GARANTIES.search(texte)
        if match_gar:
            # Prendre 500 chars après
            contenu_gar = texte[match_gar.start() : match_gar.start() + 500].strip()
            blocs.append(
                {
                    "block_type": "section_garanties",
                    "contract_id": metadata.get("contract_id"),
                    "police_id": metadata.get("police_id"),
                    "formule": metadata.get("formule"),
                    "contenu": contenu_gar,
                }
            )

        logger.info(
            "CP %s : %d blocs (1 metadata + %d bénéficiaires + 1 garanties)",
            path.name,
            len(blocs),
            len(beneficiaires),
        )

        return ParsedDocument(
            source_path=path,
            doc_type=self.doc_type,
            raw_blocks=blocs,
            metadata=metadata,
            nb_pages=texte_complet.count("<<<PAGE:"),
        )

    @staticmethod
    def _extraire_texte(path: Path) -> str:
        """Extrait le texte complet du PDF."""
        textes: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                t = page.extract_text() or ""
                textes.append(f"\n<<<PAGE:{page_num}>>>\n{t}")
        return "\n".join(textes)

    @staticmethod
    def _extraire_metadata(texte: str) -> dict[str, Any]:
        """Extrait les métadonnées du contrat."""
        metadata: dict[str, Any] = {}

        if m := RE_CONTRAT.search(texte):
            metadata["contract_id"] = m.group(1)
            metadata["police_id"] = m.group(2)
            metadata["formule"] = m.group(3).upper()

        if m := RE_SOUSCRIPTEUR.search(texte):
            metadata["souscripteur"] = m.group(1).strip()
            metadata["secteur"] = m.group(2).strip()

        if m := RE_DATE_POLICE.search(texte):
            metadata["date_effet_police"] = m.group(1)

        if m := RE_DATE_CONTRAT.search(texte):
            metadata["date_effet_contrat"] = m.group(1)

        if m := RE_STATUT.search(texte):
            metadata["statut"] = m.group(1)

        if m := RE_PRIME_TOTALE.search(texte):
            metadata["prime_par_beneficiaire"] = _parse_montant(m.group(1))
            metadata["prime_totale"] = _parse_montant(m.group(2))
            metadata["nb_beneficiaires"] = int(m.group(3))

        if m := RE_PLAFOND.search(texte):
            metadata["plafond_global"] = _parse_montant(m.group(1))

        return metadata

    @staticmethod
    def _extraire_beneficiaires(path: Path, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """Extrait les bénéficiaires depuis les tableaux du PDF."""
        beneficiaires: list[dict[str, Any]] = []

        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    if not table or len(table) < 2:
                        continue
                    header = [_normalize(str(c or "")).strip().lower() for c in table[0]]
                    # Le tableau bénéficiaires contient : Identifiant, Rang, Sexe,
                    # Année naiss., Adhésion, Radiation
                    if "identifiant" in header and "rang" in header:
                        beneficiaires.extend(
                            ConditionsParticulieresParser._parse_tableau_beneficiaires(
                                table, header, metadata
                            )
                        )

        return beneficiaires

    @staticmethod
    def _parse_tableau_beneficiaires(
        table: list[list[str]],
        header: list[str],
        metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        resultats: list[dict[str, Any]] = []

        for row in table[1:]:
            if not row or not row[0]:
                continue
            row_norm = [_normalize(str(c or "")).strip() for c in row]
            data = dict(zip(header, row_norm, strict=False))

            identifiant = data.get("identifiant", "").strip()
            if not identifiant.startswith("ASS-"):
                continue

            annee_naiss = data.get("année naiss.", "").strip()
            try:
                annee_naiss_int = int(annee_naiss) if annee_naiss else None
            except ValueError:
                annee_naiss_int = None

            resultats.append(
                {
                    "beneficiaire_id": identifiant,
                    "rang": data.get("rang", "").strip(),
                    "sexe": data.get("sexe", "").strip(),
                    "annee_naissance": annee_naiss_int,
                    "date_adhesion": data.get("adhésion", "").strip() or None,
                    "date_radiation": data.get("radiation", "").strip() or None,
                }
            )

        return resultats
