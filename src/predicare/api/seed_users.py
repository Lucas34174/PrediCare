# api/seed_users.py
from .database import SessionLocal
from .models.utilisateur import Utilisateur
from .core.security import get_password_hash

def seed():
    db = SessionLocal()
    try:
        if db.query(Utilisateur).count() > 0:
            print("Des utilisateurs existent déjà. Abandon.")
            return

        # ⚠️ REMPLACE CES VALEURS PAR CELLES TROUVÉES AVEC LE SELECT
        ASSURE_ID = "ASS-00421" 
        PRESTATAIRE_ID = "PR-0015" 

        users = [
            {
                "identifiant": "gestionnaire1", 
                "nom_complet": "Aina Razafy", 
                "role": "gestionnaire",
                "assure_id": None,
                "prestataire_id": None
            },
            {
                "identifiant": "pro1", 
                "nom_complet": "Dr. Solo Rakotondrabe", 
                "role": "professionnel_sante",
                "assure_id": None,
                "prestataire_id": "PRE-00001"  # Lié au prestataire
            },
            {
                "identifiant": "assure1", 
                "nom_complet": "Rabe Rakoto", 
                "role": "assure",
                "assure_id": "ASS-9CAA1484E0", # Lié à l'assuré
                "prestataire_id": None
            },
            {
                "identifiant": "admin1", 
                "nom_complet": "Hery Andriamaro", 
                "role": "administrateur",
                "assure_id": None,
                "prestataire_id": None
            },
        ]

        for u in users:
            user = Utilisateur(
                identifiant=u["identifiant"],
                nom_complet=u["nom_complet"],
                role=u["role"],
                mot_de_passe_hash=get_password_hash("Demo2026!"),
                assure_id=u["assure_id"],
                prestataire_id=u["prestataire_id"],
                actif=True
            )
            db.add(user)
        
        db.commit()
        print("4 utilisateurs créés et liés avec succès.")
    except Exception as e:
        db.rollback()
        print(f"Erreur : {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
