"""Parser du Guide Réseau de Soins.

Structure :
- Catégorie en MAJUSCULES (PHARMACIES, GÉNÉRALISTES, SPÉCIALISTES...)
- Ligne de règle (catégorie = ...)
- En-tête tableau (N° Prestataire Horaires Contact Adresse Tarifs)
- Lignes prestataires : N + nom + horaires + contact + adresse + tarifs

Stratégie : 1 prestataire = 1 bloc, avec catégorie + ville en contexte.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pdfplumber

from predicare.rag.parsers.base import BaseParser, ParsedDocument

logger = logging.getLogger(__name__)


# Catégories connues (pour détecter les titres de section)
CATEGORIES_CONNUES = [
    "PHARMACIES",
    "GÉNÉRALISTES",
    "GENERALISTES",
    "SPÉCIALISTES",
    "SPECIALISTES",
    "CLINIQUES ET CENTRES MÉDICAUX",
    "CLINIQUES ET CENTRES MEDICAUX",
    "LABORATOIRES",
    "IMAGERIE MÉDICALE",
    "IMAGERIE MEDICALE",
    "DENTISTES",
    "OPTICIENS",
    "KINÉSITHÉRAPIE",
    "KINESITHERAPIE",
    "MATERNITÉS",
    "MATERNITES",
]


def _normalize(text: str) -> str:
    return (
        text.replace("\u00a0", " ")
            .replace("\u202f", " ")
            .replace("\u2009", " ")
    )


class GuideReseauParser(BaseParser):
    doc_type = "guide_reseau"

    def parse(self, path: Path) -> ParsedDocument:
        logger.info("Parsing Guide Réseau : %s", path.name)

        # Détecter la ville (depuis le titre ou le nom de fichier)
        ville_defaut = self._detecter_ville(path)

        # Extraire toutes les lignes du PDF
        lignes = self._extraire_lignes(path)
        logger.info("  %d lignes extraites", len(lignes))

        # Parser
        blocs = self._parser_lignes(lignes, ville_defaut, path.name)

        logger.info("  %d prestataires détectés", len(blocs))

        return ParsedDocument(
            source_path=path,
            doc_type=self.doc_type,
            raw_blocks=blocs,
            metadata={"ville_defaut": ville_defaut},
            nb_pages=0,  # pas critique ici
        )

    @staticmethod
    def _detecter_ville(path: Path) -> str | None:
        nom = path.stem.lower()
        if "antananarivo" in nom:
            return "Antananarivo"
        if "national" in nom:
            return None  # guide national = multi-villes
        return None

    @staticmethod
    def _extraire_lignes(path: Path) -> list[str]:
        """Extrait toutes les lignes non vides du PDF."""
        lignes: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                texte = page.extract_text() or ""
                for ligne in texte.split("\n"):
                    ligne = _normalize(ligne).strip()
                    if ligne:
                        lignes.append(ligne)
        return lignes

    def _parser_lignes(
        self,
        lignes: list[str],
        ville_defaut: str | None,
        source_nom: str,
    ) -> list[dict[str, Any]]:
        blocs: list[dict[str, Any]] = []
        categorie_courante: str | None = None
        buffer_lignes: list[str] = []  # pour recoller les lignes coupées

        for ligne in lignes:
            # Détecter une nouvelle catégorie
            cat = self._detecter_categorie(ligne)
            if cat:
                categorie_courante = cat
                buffer_lignes = []
                continue

            # Ignorer les en-têtes de tableau et règles
            if self._est_en_tete_ou_regle(ligne):
                continue

            # Ignorer les titres de page / pieds de page
            if self._est_bruit(ligne):
                continue

            # Détecter une ligne prestataire : commence par un nombre
            if re.match(r"^\d+\s", ligne):
                # Flush le buffer précédent
                if buffer_lignes:
                    bloc = self._parser_ligne_prestataire(
                        " ".join(buffer_lignes),
                        categorie_courante,
                        ville_defaut,
                        source_nom,
                        len(blocs),
                    )
                    if bloc:
                        blocs.append(bloc)
                buffer_lignes = [ligne]
            else:
                # Ligne de continuation
                if buffer_lignes:
                    buffer_lignes.append(ligne)

        # Flush final
        if buffer_lignes:
            bloc = self._parser_ligne_prestataire(
                " ".join(buffer_lignes),
                categorie_courante,
                ville_defaut,
                source_nom,
                len(blocs),
            )
            if bloc:
                blocs.append(bloc)

        return blocs

    @staticmethod
    def _detecter_categorie(ligne: str) -> str | None:
        """Détecte une ligne de catégorie (MAJUSCULES)."""
        # Ignorer la ligne de règle "PHARMACIES = ..."
        if "=" in ligne:
            return None
        ligne_nettoyee = ligne.strip().upper()
        for cat in CATEGORIES_CONNUES:
            if ligne_nettoyee == cat or ligne_nettoyee.startswith(cat):
                return cat
        return None

    @staticmethod
    def _est_en_tete_ou_regle(ligne: str) -> bool:
        if "=" in ligne and ligne.split("=")[0].strip().isupper():
            return True
        if ligne.startswith("N°") and "Prestataire" in ligne:
            return True
        if "LISTE NON EXHAUSTIVE" in ligne.upper():
            return True
        return False

    @staticmethod
    def _est_bruit(ligne: str) -> bool:
        """Détecte titres de page, pieds, etc."""
        if ligne.strip().isdigit():
            return True
        if "RÉSEAU DE SOINS CONVENTIONNÉ" in ligne.upper():
            return True
        return False

    @staticmethod
    def _parser_ligne_prestataire(
        ligne: str,
        categorie: str | None,
        ville_defaut: str | None,
        source_nom: str,
        index: int,
    ) -> dict[str, Any] | None:
        """Parse une ligne prestataire (version robuste)."""
        m = re.match(r"^(\d+)\s+(.+)$", ligne)
        if not m:
            return None
        numero = int(m.group(1))
        reste = m.group(2).strip()

        # ─── 1. Contact (téléphone) ─────────────────────────────────────────────
        contact_match = re.search(r"0\d{2}\s?\d{2}\s?\d{3}\s?\d{2}", reste)
        contact = contact_match.group(0) if contact_match else None

        # ─── 2. Qualité "top N" ─────────────────────────────────────────────────
        qualite = None
        qualite_match = re.search(r"\(?top\s+(\d+)(?:\s+qualité/service)?\)?", reste, re.IGNORECASE)
        if qualite_match:
            qualite = f"top {qualite_match.group(1)}"

        # ─── 3. Adresse ─────────────────────────────────────────────────────────
        adresse = None
        adresse_match = re.search(
            r"(Lot\s+[IVX]+\s+[A-Z]\s+\d+\s*(?:Bis|Ter)?\s*,?\s*[A-ZÉÈ][a-zéèêàô]+)",
            reste,
        )
        if adresse_match:
            adresse = adresse_match.group(1).strip()

        # ─── 4. Tarifs ──────────────────────────────────────────────────────────
        tarifs = None
        tarifs_match = re.search(
            r"(TARIF\s+[A-ZÉÈ]+|CONSULTATION\s+[\d\s]+AR(?:\s*[–\-]\s*HOSPITALISATION[^–\-]*?(?:\s*[–\-]\s*TARIF\s+[A-ZÉÈ]+)?)?|VERRE À PARTIR DE[\d\s]+AR[^A-Z]*?MONTURE À PARTIR DE[\d\s]+AR)",
            reste,
        )
        if tarifs_match:
            tarifs = re.sub(r"\s+", " ", tarifs_match.group(1)).strip()

        # ─── 5. Horaires (amélioré) ─────────────────────────────────────────────
        # Capture tout ce qui ressemble à un bloc horaires
        horaires_parts = []
        # Cherche "HEURE DE BUREAU (...)"
        hdb = re.search(r"HEURE DE BUREAU\s*\([^)]*\)", reste, re.IGNORECASE)
        if hdb:
            horaires_parts.append(hdb.group(0))
        # Cherche "24H/24 ET 7J/7"
        if re.search(r"24H/24\s+ET\s+7J/7", reste):
            horaires_parts.append("24H/24 ET 7J/7")
        # Cherche "LUNDI AU VENDREDI ...", "LUNDI AU SAMEDI ..."
        jours = re.search(
            r"(LUNDI|MARDI|MERCREDI|JEUDI|VENDREDI|SAMEDI|DIMANCHE)\s+AU\s+(LUNDI|MARDI|MERCREDI|JEUDI|VENDREDI|SAMEDI|DIMANCHE)[^A-Z]*(?:ET\s+(LUNDI|MARDI|MERCREDI|JEUDI|VENDREDI|SAMEDI|DIMANCHE)[^A-Z]*)?",
            reste,
        )
        if jours:
            horaires_parts.append(jours.group(0).strip())
        if re.search(r"SUR RENDEZ-VOUS", reste, re.IGNORECASE):
            horaires_parts.append("SUR RENDEZ-VOUS")

        horaires = " ".join(horaires_parts) if horaires_parts else None

        # ─── 6. Nom (extraction stricte) ────────────────────────────────────────
        # On coupe TOUT ce qui vient après le nom :
        # - le premier "(" de qualité
        # - le premier contact
        # - le premier "Lot"
        # - le premier "TARIF"
        # - le premier "HEURE DE BUREAU" / "24H/24" / "LUNDI" / "SUR RENDEZ-VOUS"
        nom = reste
        for marker in [contact, adresse, tarifs, horaires]:
            if marker:
                idx = nom.find(marker)
                if idx > 0:
                    nom = nom[:idx]
                    break

        # Nettoyer parenthèses orphelines, doubles espaces, ponctuation
        nom = re.sub(r"\([^)]*$", "", nom)         # "(top 1" orphelin
        nom = re.sub(r"\(top\s*\d*\s*$", "", nom)
        nom = re.sub(r"\s*\($", "", nom)           # "(" orphelin
        nom = re.sub(r"\s+", " ", nom).strip(" -–—,()")

        # Sécurité : si le nom contient encore du bruit, on garde au moins 2 mots
        if len(nom.split()) > 10:
            nom = " ".join(nom.split()[:6])

        # Ville
        ville = ville_defaut
        for v in ["Antananarivo", "Toamasina", "Antsirabe", "Mahajanga",
                  "Fianarantsoa", "Toliara", "Antsiranana"]:
            if v in reste:
                ville = v
                break

        return {
            "block_type": "prestataire",
            "numero": numero,
            "categorie": categorie or "INCONNUE",
            "ville": ville,
            "nom": nom or "Inconnu",
            "horaires": horaires,
            "contact": contact,
            "adresse": adresse,
            "tarifs": tarifs,
            "qualite": qualite,
            "ligne_brute": ligne,
            "source_guide": source_nom,
        }