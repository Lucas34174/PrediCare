"""Chunker des Conditions Particulières.

3 types de chunks :
- contrat_metadata  : 1 par contrat
- beneficiaire      : 1 par bénéficiaire
- section_garanties : 1 par contrat
"""

from __future__ import annotations

from typing import Any

from predicare.rag.chunkers.base import BaseChunker, Chunk


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _fmt_montant(v: int | None) -> str:
    if v is None:
        return "non renseigné"
    return f"{v:,} Ar".replace(",", " ")


class BeneficiaireChunker(BaseChunker):
    chunk_type = "beneficiaire"  # valeur par défaut, chaque chunk override

    def chunk(self, blocks: list[dict[str, Any]]) -> list[Chunk]:
        chunks: list[Chunk] = []
        idx = 0

        for block in blocks:
            bt = block["block_type"]
            if bt == "contrat_metadata":
                chunks.append(self._chunk_metadata(idx, block))
            elif bt == "beneficiaire":
                chunks.append(self._chunk_beneficiaire(idx, block))
            elif bt == "section_garanties":
                chunks.append(self._chunk_garanties(idx, block))
            idx += 1

        return chunks

    def _chunk_metadata(self, idx: int, block: dict[str, Any]) -> Chunk:
        prefix = (
            f"[Conditions Particulières | Contrat {block.get('contract_id')} "
            f"| Police {block.get('police_id')} | Formule {block.get('formule')}]"
        )
        contenu = (
            f"{prefix}\n"
            f"Contrat : {block.get('contract_id')}\n"
            f"Police : {block.get('police_id')}\n"
            f"Formule : {block.get('formule')}\n"
            f"Souscripteur : {block.get('souscripteur')} ({block.get('secteur')})\n"
            f"Date d'effet de la police : {block.get('date_effet_police')}\n"
            f"Date d'effet du contrat : {block.get('date_effet_contrat')}\n"
            f"Statut : {block.get('statut')}\n"
            f"Nombre de bénéficiaires : {block.get('nb_beneficiaires')}\n"
            f"Prime annuelle par bénéficiaire : {_fmt_montant(block.get('prime_par_beneficiaire'))}"
            f"Prime annuelle totale : {_fmt_montant(block.get('prime_totale'))}\n"
            f"Plafond annuel global par bénéficiaire : {_fmt_montant(block.get('plafond_global'))}"
        )
        return Chunk(
            chunk_index=idx,
            chunk_type="contrat_metadata",
            contenu_enrichi=contenu,
            metadonnees={
                "contract_id": block.get("contract_id"),
                "police_id": block.get("police_id"),
                "formule": block.get("formule"),
                "souscripteur": block.get("souscripteur"),
                "secteur": block.get("secteur"),
                "date_effet_police": block.get("date_effet_police"),
                "date_effet_contrat": block.get("date_effet_contrat"),
                "statut": block.get("statut"),
                "nb_beneficiaires": block.get("nb_beneficiaires"),
                "prime_par_beneficiaire": block.get("prime_par_beneficiaire"),
                "prime_totale": block.get("prime_totale"),
                "plafond_global": block.get("plafond_global"),
                "block_type": "contrat_metadata",
                "doc_type": "conditions_particulieres",
            },
            token_count=_approx_tokens(contenu),
        )

    def _chunk_beneficiaire(self, idx: int, block: dict[str, Any]) -> Chunk:
        prefix = (
            f"[Conditions Particulières | Contrat {block.get('contract_id')} "
            f"| Formule {block.get('formule')} | Bénéficiaire]"
        )
        contenu = (
            f"{prefix}\n"
            f"Identifiant : {block.get('beneficiaire_id')}\n"
            f"Rang : {block.get('rang')}\n"
            f"Sexe : {block.get('sexe')}\n"
            f"Année de naissance : {block.get('annee_naissance')}\n"
            f"Date d'adhésion : {block.get('date_adhesion')}\n"
            f"Date de radiation : {block.get('date_radiation') or 'aucune'}"
        )
        return Chunk(
            chunk_index=idx,
            chunk_type="beneficiaire",
            contenu_enrichi=contenu,
            metadonnees={
                "contract_id": block.get("contract_id"),
                "police_id": block.get("police_id"),
                "formule": block.get("formule"),
                "souscripteur": block.get("souscripteur"),
                "beneficiaire_id": block.get("beneficiaire_id"),
                "rang": block.get("rang"),
                "sexe": block.get("sexe"),
                "annee_naissance": block.get("annee_naissance"),
                "date_adhesion": block.get("date_adhesion"),
                "date_radiation": block.get("date_radiation"),
                "block_type": "beneficiaire",
                "doc_type": "conditions_particulieres",
            },
            token_count=_approx_tokens(contenu),
        )

    def _chunk_garanties(self, idx: int, block: dict[str, Any]) -> Chunk:
        prefix = (
            f"[Conditions Particulières | Contrat {block.get('contract_id')} "
            f"| Formule {block.get('formule')} | Garanties applicables]"
        )
        contenu = f"{prefix}\n\n{block.get('contenu', '')}"
        return Chunk(
            chunk_index=idx,
            chunk_type="section_garanties",
            contenu_enrichi=contenu,
            metadonnees={
                "contract_id": block.get("contract_id"),
                "police_id": block.get("police_id"),
                "formule": block.get("formule"),
                "block_type": "section_garanties",
                "doc_type": "conditions_particulieres",
            },
            token_count=_approx_tokens(contenu),
        )
