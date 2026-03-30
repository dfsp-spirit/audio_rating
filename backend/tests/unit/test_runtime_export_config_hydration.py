import json

import pytest
from sqlmodel import SQLModel, Session, create_engine, select

from audiorating_backend import api as api_module
from audiorating_backend import database as database_module
from audiorating_backend.models import Participant, Song, Study, StudyParticipantLink, StudyRatingDimension, StudySongLink


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

    database_module.create_config_file_studies("/home/ts/develop_mpiae/audio_rating/backend/studies_config.json")

    with Session(source_engine) as session:
        default_study = session.exec(select(Study).where(Study.name_short == "default")).first()
        assert default_study is not None

        runtime_participant = Participant(id="runtime_added_participant")
        session.add(runtime_participant)
        session.add(
            StudyParticipantLink(
                study_id=default_study.id,
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

        default_study = session.exec(select(Study).where(Study.name_short == "default")).first()
        assert default_study is not None

        participant_links = session.exec(
            select(StudyParticipantLink).where(StudyParticipantLink.study_id == default_study.id)
        ).all()
        participant_ids = sorted(link.participant_id for link in participant_links)
        assert "runtime_added_participant" in participant_ids

        song_links = session.exec(
            select(StudySongLink).where(StudySongLink.study_id == default_study.id)
        ).all()
        rating_dimensions = session.exec(
            select(StudyRatingDimension).where(StudyRatingDimension.study_id == default_study.id)
        ).all()

        assert len(song_links) == 2
        assert len(rating_dimensions) == 4

        song_ids = [link.song_id for link in song_links]
        songs = session.exec(select(Song).where(Song.id.in_(song_ids))).all()
        song_urls = sorted(song.media_url for song in songs)
        assert song_urls == sorted([
            "audio_files/default/demo.wav",
            "audio_files/default/demo2.wav",
        ])

    monkeypatch.setattr(database_module, "engine", original_engine)