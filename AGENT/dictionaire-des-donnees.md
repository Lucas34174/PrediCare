# Dictionnaire des données – jeu synthétique PrediCare TPA

Document de référence · Jeu de données synthétique pour la détection de fraudes à l'assurance santé

## 1. Présentation et conventions générales

L'ensemble des données décrites dans ce document est **synthétique**. Il ne contient aucun assuré, prestataire, numéro de téléphone ou adresse réels.

| Convention         | Valeur                              |
| ------------------ | ----------------------------------- |
| Nature des données | Synthétiques (aucune donnée réelle) |
| Devise             | Ariary (MGA), montants entiers      |
| Format des dates   | AAAA-MM-JJ                          |
| Encodage           | UTF-8                               |
| Séparateur         | Virgule                             |

## 2. Référentiels

Les référentiels fournissent les tarifs, les produits et les règles de garantie de référence.

| Fichier                     | Contenu                                                                                                                                               |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| referentiel_actes.csv       | Code acte, libellé, catégorie, spécialité, tarifs minimum / référence / maximum, ordonnance requise, entente préalable, restrictions de sexe et d'âge |
| referentiel_medicaments.csv | Code, libellé, prix de référence, **remboursable** (0 = fortifiant, cosmétique, complément), classe, traitement chronique                             |
| garanties.csv               | Par formule (ESSENTIEL, CONFORT, PREMIUM) et par catégorie : taux, plafond annuel, franchise, carence, actes exclus, pièces justificatives            |

## 3. Données métier

| Fichier                                 | Clé                    | Colonnes principales                                                                                                                                                                           |
| --------------------------------------- | ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| prestataires.csv                        | prestataire_id         | Nom fictif, type, spécialité, ville, quartier, horaires, jours_ouverture (1 = lundi … 7 = dimanche), niveau de tarif, note qualité, dates de convention, statut (ACTIF / RADIE)                |
| grille_tarifaire.csv                    | (prestataire_id, code) | Tarif pratiqué par le prestataire                                                                                                                                                              |
| contrats.csv                            | contrat_id             | Police, souscripteur, formule, dates d'effet et de fin, statut, nombre de bénéficiaires, prime                                                                                                 |
| assures.csv                             | assure_id (pseudonyme) | Contrat, rang (ASSURE_PRINCIPAL / CONJOINT / ENFANT), sexe, **année** de naissance, ville, adhésion, radiation                                                                                 |
| identites_pii.csv                       | assure_id              | **Données personnelles à chiffrer** : nom, prénom, date de naissance, téléphone, e-mail, adresse, n° CIN fictif                                                                                |
| ordonnances.csv / ordonnance_lignes.csv | ordonnance_id          | Prescripteur, date, validité (10 jours ; 30 jours pour l'optique), type, diagnostic. Les lignes contiennent le code, la quantité et la posologie.                                              |
| factures.csv                            | facture_id             | Prestataire, assuré, contrat, ordonnance, type, dates (soin, facture, réception, traitement), canal, mode de règlement, attestation (APC), entente préalable, montants, statut, motif de rejet |
| lignes_facture.csv                      | ligne_id               | Code, type de ligne (ACTE / MEDICAMENT), quantité, prix unitaire, montant                                                                                                                      |

## 4. Statut historique des factures

La colonne statut du fichier factures.csv prend les valeurs suivantes :

| Statut   | Signification                                              |
| -------- | ---------------------------------------------------------- |
| PAYEE    | Facture réglée                                             |
| REJETEE  | Facture rejetée, avec un motif de rejet (voir ci-dessous). |
| EN_COURS | Facture reçue dans les 12 derniers jours.                  |

**Motifs de rejet possibles :** PIECE_MANQUANTE_ATTESTATION, ENTENTE_PREALABLE_ABSENTE, HORS_PERIODE_COUVERTURE, DELAI_DE_CARENCE, ORDONNANCE_PERIMEE, PRODUIT_NON_REMBOURSABLE, PLAFOND_ATTEINT, CONTROLE_MEDICAL, FACTURE_INVALIDE.

**\*Attention – fuite de données :\*\*** les colonnes **statut**, **motif_rejet**, **montant_pris_en_charge** et **date_traitement** résultent de la décision historique et sont partiellement corrélées à la fraude. Elles ne doivent pas être utilisées comme variables du modèle de détection.\*

## 5. Labels

Les labels sont fournis dans des fichiers séparés, dans le dossier labels/.

| Fichier                 | Colonnes                                                                                     |
| ----------------------- | -------------------------------------------------------------------------------------------- |
| labels_fraude.csv       | facture_id, est_fraude (0/1), type_fraude, detail_fraude, est_valide (0/1), motif_invalidite |
| labels_prestataires.csv | prestataire_id, est_suspect (prestataires à forte propension de fraude)                      |

## 6. Types de fraude injectés

Le tableau suivant décrit le mécanisme de chaque fraude injectée dans le jeu de données et le signal permettant de la détecter.

| Type                  | Mécanisme                                                                 | Signal exploitable                                        |
| --------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------- |
| SURFACTURATION        | Prix supérieur au tarif maximum (parfois discret)                         | Prix comparé à la grille et au référentiel.               |
| QUANTITE_EXCESSIVE    | Quantité multipliée par 3 à 8                                             | Quantité facturée comparée à l'ordonnance.                |
| UPCODING              | Consultation simple facturée en spécialité, avec majoration ou en urgence | Type de prestataire, heure, jour.                         |
| LIGNES_NON_PRESCRITES | Codes absents de l'ordonnance                                             | Jointure facture ↔ ordonnance.                            |
| SUBSTITUTION_PRODUIT  | Médicament coûteux non prescrit                                           | Jointure et prix.                                         |
| ORDONNANCE_EXPIREE    | Soin réalisé après la validité                                            | date_soin − date_prescription                             |
| SOINS_JOUR_FERME      | Soin un jour de fermeture du prestataire.                                 | jours_ouverture                                           |
| DOUBLON               | Même facture renvoyée.                                                    | (assuré, prestataire, montant, date)                      |
| FRACTIONNEMENT        | Une facture découpée en 2 à 4.                                            | Plusieurs factures le même jour pour le même prestataire. |
| SURCONSOMMATION       | Même ordonnance présentée dans plusieurs pharmacies.                      | Réutilisation d'ordonnance_id.                            |
| ACTE_FICTIF           | Sans ordonnance, ou ordonnance d'un autre assuré.                         | Ordonnance manquante ou incohérente.                      |
| INCOHERENCE_PROFIL    | Acte incompatible avec l'âge ou le sexe.                                  | sexe_requis, age_min, age_max                             |
| PRESTATAIRE_RADIE     | Facturation après la fin de convention.                                   | date_fin_convention                                       |
| HORS_COUVERTURE       | Soin avant l'adhésion, après la radiation ou pendant la carence.          | Dates du contrat et du bénéficiaire.                      |

## 7. Corpus RAG

Le dossier rag_corpus/ regroupe les documents destinés à la recherche documentaire :

- conditions générales par formule ;

- conditions particulières (bénéficiaires pseudonymisés) ;

- guide du réseau de soins (Antananarivo et national, coordonnées fictives) ;

- FAQ assurés ;

- barème de référence des actes.
