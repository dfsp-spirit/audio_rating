import os
import json
from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine, select

os.environ.setdefault("AR_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("AR_ALLOWED_ORIGINS", '["http://localhost:3000"]')
os.environ.setdefault("AR_API_ADMIN_USERNAME", "test_admin")
os.environ.setdefault("AR_API_ADMIN_PASSWORD", "test_password")

from audiorating_backend import api as api_module
from audiorating_backend import database as database_module
from audiorating_backend.models import Participant, Song, Study, StudyParticipantLink, StudyRatingDimension, StudySongLink


BACKEND_ROOT = Path(__file__).resolve().parents[2]
STUDIES_CONFIG_PATH = BACKEND_ROOT / "studies_config.json"


@pytest.mark.asyncio
async def test_runtime_export_file_can_be_reloaded_by_create_config_file_studies(tmp_path, monkeypatch):
    source_db_path = tmp_path / "source.db"
    target_db_path = tmp_path / "target.db"
    export_path = tmp_path / "runtime_export.json"

    source_engine = create_engine(f"sqlite:///{source_db_path}")
    target_engine = create_engine(f"sqlite:///{target_db_path}")

    original_engine = database_module.engine
    monkeypatch.setattr(database_module, "engine", source_engine)
    SQLModel.metadata.create_all(source_engine)

    database_module.create_config_file_studies(str(STUDIES_CONFIG_PATH))

    source_config = json.loads(STUDIES_CONFIG_PATH.read_text(encoding="utf-8"))
    source_studies = source_config["studies"]
    source_study_name_short = source_studies[0]["name_short"]
    source_study_song_urls = sorted(
        song["media_url"] for song in source_studies[0]["songs_to_rate"]
    )
    source_study_dimension_count = len(source_studies[0]["rating_dimensions"])
    arousal_dimension_cfg = next(
        (dimension for dimension in source_studies[0]["rating_dimensions"] if dimension["dimension_title"] == "arousal"),
        None,
    )

    with Session(source_engine) as session:
        source_study = session.exec(select(Study).where(Study.name_short == source_study_name_short)).first()
        assert source_study is not None

        runtime_participant = Participant(id="runtime_added_participant")
        session.add(runtime_participant)
        session.add(
            StudyParticipantLink(
                study_id=source_study.id,
                participant_id=runtime_participant.id,
            )
        )
        session.commit()

        response = await api_module.export_runtime_studies_config(
            current_admin="test_admin",
            session=session,
        )

    export_payload = json.loads(response.body.decode("utf-8"))
    export_path.write_text(json.dumps(export_payload), encoding="utf-8")

    monkeypatch.setattr(database_module, "engine", target_engine)
    SQLModel.metadata.create_all(target_engine)
    database_module.create_config_file_studies(str(export_path))

    with Session(target_engine) as session:
        studies = session.exec(select(Study).order_by(Study.name_short)).all()
        assert len(studies) == len(export_payload["studies_config"]["studies"])

        reloaded_study = session.exec(select(Study).where(Study.name_short == source_study_name_short)).first()
        assert reloaded_study is not None

        participant_links = session.exec(
            select(StudyParticipantLink).where(StudyParticipantLink.study_id == reloaded_study.id)
        ).all()
        participant_ids = sorted(link.participant_id for link in participant_links)
        assert "runtime_added_participant" in participant_ids

        song_links = session.exec(
            select(StudySongLink).where(StudySongLink.study_id == reloaded_study.id)
        ).all()
        rating_dimensions = session.exec(
            select(StudyRatingDimension).where(StudyRatingDimension.study_id == reloaded_study.id)
        ).all()

        assert len(song_links) == len(source_study_song_urls)
        assert len(rating_dimensions) == source_study_dimension_count

        arousal_dimension = next(
            (dimension for dimension in rating_dimensions if dimension.dimension_title == "arousal"),
            None,
        )
        if arousal_dimension_cfg is not None:
            assert arousal_dimension is not None
            assert arousal_dimension.minimal_value == arousal_dimension_cfg["minimal_value"]
            assert arousal_dimension.num_values == arousal_dimension_cfg["num_values"]

        song_ids = [link.song_id for link in song_links]
        songs = session.exec(select(Song).where(Song.id.in_(song_ids))).all()
        song_urls = sorted(song.media_url for song in songs)
        assert song_urls == source_study_song_urls

    monkeypatch.setattr(database_module, "engine", original_engine)