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
        """Parse une ligne prestataire.

        Format attendu :
        N Nom [top X qualité/service] Horaires Contact Adresse Tarifs

        On ne peut pas garantir une extraction parfaite, donc on garde la
        ligne brute dans le bloc + on tente d'extraire les champs clés.
        """
        # Retirer le numéro en tête
        m = re.match(r"^(\d+)\s+(.+)$", ligne)
        if not m:
            return None
        numero = int(m.group(1))
        reste = m.group(2).strip()

        # Extraire le contact (téléphone malgache : 0XX XX XXX XX ou 0XXXXXXXXX)
        contact_match = re.search(r"0\d{2}\s?\d{2}\s?\d{3}\s?\d{2}", reste)
        contact = contact_match.group(0) if contact_match else None

        # Extraire "top X qualité/service"
        top_match = re.search(r"\(top\s+\d+\s+qualité/service\)", reste, re.IGNORECASE)
        qualite = top_match.group(0) if top_match else None

        # Détecter la ville dans la ligne (si guide national)
        ville = ville_defaut
        for v in ["Antananarivo", "Toamasina", "Antsirabe", "Mahajanga",
                  "Fianarantsoa", "Toliara", "Antsiranana"]:
            if v in reste:
                ville = v
                break

        # Nom : on prend tout ce qui précède les horaires
        # Les horaires commencent souvent par "HEURE DE BUREAU", "LUNDI", "24H", "SUR RENDEZ-VOUS"
        horaires_match = re.search(
            r"(HEURE DE BUREAU|LUNDI|MARDI|MERCREDI|JEUDI|VENDREDI|SAMEDI|DIMANCHE|24H/24|SUR RENDEZ-VOUS)",
            reste,
        )
        if horaires_match:
            nom = reste[:horaires_match.start()].strip()
            horaires = reste[horaires_match.start():].strip()
        else:
            nom = reste
            horaires = None

        # Nettoyer le nom (retirer le "(top X ...)")
        if qualite:
            nom = nom.replace(qualite, "").strip()

        return {
            "block_type": "prestataire",
            "numero": numero,
            "categorie": categorie or "INCONNUE",
            "ville": ville,
            "nom": nom,
            "horaires": horaires,
            "contact": contact,
            "ligne_brute": ligne,
            "qualite": qualite,
            "source_guide": source_nom,
        }