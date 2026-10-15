from predicare.core.config import database_url


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
    # L'URL rendue en texte échappe les caractères spéciaux : la connexion reste valide.
    assert "p%40ss%3Aw%2Frd%231" in url.render_as_string(hide_password=False)
