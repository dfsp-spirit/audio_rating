import os

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, select

os.environ.setdefault("AR_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("AR_ALLOWED_ORIGINS", '["http://localhost:3000"]')
os.environ.setdefault("AR_API_ADMIN_USERNAME", "test_admin")
os.environ.setdefault("AR_API_ADMIN_PASSWORD", "test_password")

from audiorating_backend import api as api_module
from audiorating_backend.models import (
    Participant,
    Song,
    Study,
    StudyParticipantLink,
    StudyRatingDimension,
    StudySongLink,
)


def test_create_study_admin_endpoint_creates_study_with_relations(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "test_create_study.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    # Avoid running startup side effects that populate the database from config files.
    monkeypatch.setattr(api_module, "create_db_and_tables", lambda: None)
    api_module.app.dependency_overrides[api_module.get_session] = override_get_session

    payload = {
        "name": "API Created Study",
        "name_short": "api_created_study",
        "default_language": "en",
        "description": {"en": "English description", "de": "Deutsche Beschreibung"},
        "songs_to_rate": [
            {
                "media_url": "audio_files/default/song_a.wav",
                "display_name": {"en": "Song A", "de": "Lied A"},
                "description": {
                    "en": "Song A description",
                    "de": "Lied A Beschreibung",
                },
            }
        ],
        "rating_dimensions": [
            {
                "dimension_title": "valence",
                "display_name": {"en": "Valence", "de": "Valenz"},
                "num_values": 7,
                "minimal_value": 1,
                "default_value": 4,
                "description": {
                    "en": "Valence description",
                    "de": "Valenz Beschreibung",
                },
            }
        ],
        "study_participant_ids": ["p1", "p2"],
        "allow_unlisted_participants": False,
        "data_collection_start": "2025-01-01T00:00:00Z",
        "data_collection_end": "2027-01-01T00:00:00Z",
    }

    try:
        with TestClient(api_module.app) as client:
            response = client.post(
                "/api/admin/studies",
                json=payload,
                auth=("test_admin", "test_password"),
            )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name_short"] == "api_created_study"
        assert body["name"] == "API Created Study"
        assert body["songs_count"] == 1
        assert body["rating_dimensions_count"] == 1
        assert body["participant_links_count"] == 2

        with Session(engine) as session:
            study = session.exec(
                select(Study).where(Study.name_short == "api_created_study")
            ).first()
            assert study is not None
            assert study.allow_unlisted_participants is False
            assert study.description == "English description"

            song_link = session.exec(
                select(StudySongLink).where(StudySongLink.study_id == study.id)
            ).first()
            assert song_link is not None
            assert song_link.song_index == 0

            song = session.exec(
                select(Song).where(Song.id == song_link.song_id)
            ).first()
            assert song is not None
            assert song.display_name == "Song A"
            assert song.description == "Song A description"

            dimension = session.exec(
                select(StudyRatingDimension).where(
                    StudyRatingDimension.study_id == study.id
                )
            ).first()
            assert dimension is not None
            assert dimension.dimension_title == "valence"
            assert dimension.num_values == 7
            assert dimension.default_value == 4
            assert dimension.description == "Valence description"

            links = session.exec(
                select(StudyParticipantLink).where(
                    StudyParticipantLink.study_id == study.id
                )
            ).all()
            assert len(links) == 2

            participant_ids = {link.participant_id for link in links}
            assert participant_ids == {"p1", "p2"}

            participants = session.exec(
                select(Participant).where(Participant.id.in_(["p1", "p2"]))
            ).all()
            assert len(participants) == 2
    finally:
        api_module.app.dependency_overrides.clear()
