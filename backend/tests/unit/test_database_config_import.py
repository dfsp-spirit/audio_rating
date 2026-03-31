import json
import os

from sqlmodel import SQLModel, Session, create_engine, select

os.environ.setdefault("AR_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("AR_ALLOWED_ORIGINS", '["http://localhost:3000"]')
os.environ.setdefault("AR_API_ADMIN_USERNAME", "test_admin")
os.environ.setdefault("AR_API_ADMIN_PASSWORD", "test_password")

from audiorating_backend import database as database_module
from audiorating_backend.models import Song, Study, StudyRatingDimension, StudySongLink


def test_create_config_file_studies_resolves_multilingual_fields_to_strings(tmp_path, monkeypatch):
    config_payload = {
        "studies": [
            {
                "name": "Localized Study",
                "name_short": "localized_study",
                "default_language": "en",
                "description": {"en": "English study description", "de": "Deutsche Beschreibung"},
                "songs_to_rate": [
                    {
                        "media_url": "audio_files/localized/song.wav",
                        "display_name": {"en": "English Song", "de": "Deutsches Lied"},
                        "description": {"en": "English song description", "de": "Deutsche Liedbeschreibung"},
                    }
                ],
                "rating_dimensions": [
                    {
                        "dimension_title": "flow",
                        "display_name": {"en": "Flow", "de": "Fluss"},
                        "num_values": 5,
                        "description": {"en": "English dimension description", "de": "Deutsche Dimensionsbeschreibung"},
                    }
                ],
                "study_participant_ids": [],
                "allow_unlisted_participants": True,
                "data_collection_start": "2024-01-01T00:00:00Z",
                "data_collection_end": "2030-01-01T00:00:00Z",
            }
        ]
    }

    config_path = tmp_path / "studies.json"
    config_path.write_text(json.dumps(config_payload), encoding="utf-8")

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    original_engine = database_module.engine
    monkeypatch.setattr(database_module, "engine", engine)
    SQLModel.metadata.create_all(engine)

    try:
        database_module.create_config_file_studies(str(config_path))

        with Session(engine) as session:
            study = session.exec(select(Study).where(Study.name_short == "localized_study")).first()
            assert study is not None
            assert isinstance(study.description, str)
            assert study.description == "English study description"

            song_link = session.exec(select(StudySongLink).where(StudySongLink.study_id == study.id)).first()
            assert song_link is not None

            song = session.exec(select(Song).where(Song.id == song_link.song_id)).first()
            assert song is not None
            assert isinstance(song.display_name, str)
            assert isinstance(song.description, str)
            assert song.display_name == "English Song"
            assert song.description == "English song description"

            dimension = session.exec(
                select(StudyRatingDimension).where(StudyRatingDimension.study_id == study.id)
            ).first()
            assert dimension is not None
            assert isinstance(dimension.description, str)
            assert dimension.description == "English dimension description"
    finally:
        monkeypatch.setattr(database_module, "engine", original_engine)
