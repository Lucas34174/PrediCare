"""Parser spécialisé pour les Conditions Générales des formules PrediCare.

Structure observée :
- Fichiers : Conditions_Generales_{CONFORT,ESSENTIEL,PREMIUM}.pdf
- Organisés en articles : "## Article N – Titre"
- Certains articles contiennent des tableaux (garanties, pièces justificatives)

Stratégie : 1 article = 1 bloc parsé, avec son titre et son contenu complet.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pdfplumber

from predicare.rag.parsers.base import BaseParser, ParsedDocument

logger = logging.getLogger(__name__)

# Regex pour détecter les articles : "## Article 5 – Tableau des garanties"
RE_ARTICLE = re.compile(
    r"^[ \t]*Article\s+(\d+)\s*[^\w\s]?\s*(.*?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# Regex pour extraire la formule du nom de fichier
RE_FORMULE = re.compile(r"Conditions_Generales_(CONFORT|ESSENTIEL|PREMIUM)\.pdf$")


def _normalize(text: str) -> str:
    """Remplace les espaces insécables et autres caractères exotiques."""
    return (
        text.replace("\u00a0", " ")  # espace insécable
        .replace("\u202f", " ")  # espace fine insécable
        .replace("\u2009", " ")  # espace fine
    )


def _extraire_texte_pdf(path: Path) -> str:
    """Extrait le texte complet du PDF (toutes pages concaténées)."""
    textes: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            texte = page.extract_text() or ""
            # Marqueur de page pour pouvoir tracer plus tard
            textes.append(f"\n<<<PAGE:{page_num}>>>\n{texte}")
    return "\n".join(textes)


def _detecter_formule(path: Path) -> str | None:
    """Extrait la formule du nom de fichier."""
    match = RE_FORMULE.search(path.name)
    return match.group(1) if match else None


# def calculer_checksum(path: Path, version_parser: str = "v1") -> str:
# h = hashlib.sha256()
# h.update(version_parser.encode())
# with path.open("rb") as f:
# for chunk in iter(lambda: f.read(8192), b""):
# h.update(chunk)
# return h.hexdigest()


class ConditionsGeneralesParser(BaseParser):
    """Parser des Conditions Générales."""

    doc_type = "conditions_generales"

    def parse(self, path: Path) -> ParsedDocument:
        logger.info("Parsing Conditions Générales : %s", path.name)

        texte = _extraire_texte_pdf(path)
        formule = _detecter_formule(path)

        # Découper par article
        blocs = self._split_articles(texte)

        logger.info("Formule %s : %d articles détectés", formule or "?", len(blocs))

        return ParsedDocument(
            source_path=path,
            doc_type=self.doc_type,
            raw_blocks=blocs,
            metadata={
                "formule": formule,
                "type_source": "conditions_generales",
            },
            nb_pages=texte.count("<<<PAGE:"),
        )

    @staticmethod
    # Dans _split_articles, remplace la détection par :
    def _split_articles(texte: str) -> list[dict]:
        # Regex simple : "Article" suivi d'un nombre

        texte = _normalize(texte)
        matches = list(RE_ARTICLE.finditer(texte))

        if not matches:
            logger.warning("Aucun article détecté. Extrait du texte : %s", texte[:500])
            return []

        blocs = []
        for i, match in enumerate(matches):
            numero = int(match.group(1))
            fin_ligne = match.group(2).strip()  # peut contenir "– Titre" ou rien
            # Nettoie le séparateur en début de titre
            titre = re.sub(r"^[–\-—:.]\s*", "", fin_ligne).strip() or f"Article {numero}"

            debut = match.start()
            fin = matches[i + 1].start() if i + 1 < len(matches) else len(texte)
            contenu = texte[debut:fin].strip()

            pages = sorted(set(int(p) for p in re.findall(r"<<<PAGE:(\d+)>>>", contenu)))
            contenu_propre = re.sub(r"<<<PAGE:\d+>>>", "", contenu).strip()

            blocs.append(
                {
                    "block_type": "article",
                    "article_num": numero,
                    "article_titre": titre,
                    "contenu": contenu_propre,
                    "pages": pages,
                    "char_count": len(contenu_propre),
                }
            )
        return blocs
