from predicare.core.config import (
    DEFAULT_FRAUD_THRESHOLD,
    database_url,
    fraud_score_threshold,
    model_path,
    model_version,
)


def test_database_url_reads_environment(monkeypatch):
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "base_test")
    monkeypatch.setenv("DB_USER", "utilisateur")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    url = database_url()
    assert url.drivername == "postgresql+psycopg"
    assert (url.host, url.port, url.database, url.username) == (
        "db",
        5433,
        "base_test",
        "utilisateur",
    )
    assert url.password == "secret"


def test_database_url_keeps_special_characters_in_password(monkeypatch):
    monkeypatch.setenv("DB_PASSWORD", "p@ss:w/rd#1")
    url = database_url()
    assert url.password == "p@ss:w/rd#1"
    assert "p%40ss%3Aw%2Frd%231" in url.render_as_string(hide_password=False)


def test_fraud_score_threshold_defaults_and_env(monkeypatch):
    monkeypatch.delenv("FRAUD_SCORE_THRESHOLD", raising=False)
    assert fraud_score_threshold() == DEFAULT_FRAUD_THRESHOLD
    monkeypatch.setenv("FRAUD_SCORE_THRESHOLD", "0.75")
    assert fraud_score_threshold() == 0.75
    monkeypatch.setenv("FRAUD_SCORE_THRESHOLD", "valeur_invalide")
    assert fraud_score_threshold() == DEFAULT_FRAUD_THRESHOLD


def test_model_path_and_version_env(monkeypatch):
    monkeypatch.delenv("PREDICARE_MODELE_PATH", raising=False)
    monkeypatch.delenv("PREDICARE_MODELE_VERSION", raising=False)
    assert model_path() == "models/model_champion.joblib"
    assert model_version() == "v1.0.0-xgb"
    monkeypatch.setenv("PREDICARE_MODELE_PATH", "models/v2/model.joblib")
    monkeypatch.setenv("PREDICARE_MODELE_VERSION", "v2.0.0-weak")
    assert model_path() == "models/v2/model.joblib"
    assert model_version() == "v2.0.0-weak"
