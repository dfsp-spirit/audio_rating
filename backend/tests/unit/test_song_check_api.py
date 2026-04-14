import os
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

os.environ.setdefault("AR_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("AR_ALLOWED_ORIGINS", '["http://localhost:3000"]')
os.environ.setdefault("AR_API_ADMIN_USERNAME", "test_admin")
os.environ.setdefault("AR_API_ADMIN_PASSWORD", "test_password")
os.environ.setdefault("AR_FRONTEND_URL", "http://frontend.local/")

from audiorating_backend import api as api_module
from audiorating_backend.models import Song, Study, StudySongLink


def test_check_study_songs_endpoint_returns_availability(tmp_path, monkeypatch):
    db_path = tmp_path / "test_song_check.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        study = Study(
            name="Song Check Study",
            name_short="song_check_study",
            description="Study for song checks",
            allow_unlisted_participants=True,
            data_collection_start=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            data_collection_end=datetime(2028, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        session.add(study)
        session.flush()

        song_ok = Song(
            display_name="Song OK",
            media_url="audio_files/default/song_ok.wav",
            description="ok",
        )
        song_missing = Song(
            display_name="Song Missing",
            media_url="audio_files/default/song_missing.wav",
            description="missing",
        )
        session.add(song_ok)
        session.add(song_missing)
        session.flush()

        session.add(StudySongLink(study_id=study.id, song_id=song_ok.id, song_index=0))
        session.add(StudySongLink(study_id=study.id, song_id=song_missing.id, song_index=1))
        session.commit()

    def override_get_session():
        with Session(engine) as session:
            yield session

    def fake_song_check(url, timeout_seconds=5.0):
        if "song_ok.wav" in url:
            return True, 200, None
        return False, 404, "HTTP Error 404: Not Found"

    monkeypatch.setenv("AR_FRONTEND_URL", "http://frontend.local/")
    monkeypatch.setattr(api_module, "create_db_and_tables", lambda: None)
    monkeypatch.setattr(api_module, "_is_song_url_available", fake_song_check)
    api_module.app.dependency_overrides[api_module.get_session] = override_get_session

    try:
        with TestClient(api_module.app) as client:
            response = client.post(
                "/api/admin/studies/song_check_study/songs/check",
                auth=("test_admin", "test_password"),
            )

        assert response.status_code == 200, response.text
        payload = response.json()

        assert payload["study_name_short"] == "song_check_study"
        assert payload["checked"] == 2
        assert payload["available"] == 1
        assert payload["missing"] == 1

        results = payload["results"]
        assert len(results) == 2

        assert results[0]["song_index"] == 0
        assert results[0]["media_url"] == "audio_files/default/song_ok.wav"
        assert results[0]["check_url"] == "http://frontend.local/audio_files/default/song_ok.wav"
        assert results[0]["available"] is True
        assert results[0]["status_code"] == 200

        assert results[1]["song_index"] == 1
        assert results[1]["media_url"] == "audio_files/default/song_missing.wav"
        assert results[1]["check_url"] == "http://frontend.local/audio_files/default/song_missing.wav"
        assert results[1]["available"] is False
        assert results[1]["status_code"] == 404
    finally:
        api_module.app.dependency_overrides.clear()
