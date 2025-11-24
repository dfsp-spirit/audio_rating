# database.py
from sqlmodel import SQLModel, create_engine, Session, select
from typing import Generator
from .models import Study, Song
from .studies_config import load_studies_config
from .settings import settings
import logging

logger = logging.getLogger("audiorating_backend.database")


engine = create_engine(settings.database_url)


def create_default_studies(config_path: str):
    """Create default studies from a configuration file"""
    try:
        config = load_studies_config(config_path)
    except FileNotFoundError:
        logger.warning("No studies configuration file found. Using default fallback.")
        config = get_fallback_config()

    logger.info(f"Checking whether studies need to be created based on config file at '{config_path}'")


    with Session(engine) as session:
        for study_cfg in config.studies:
            # Check if study already exists
            existing_study = session.exec(
                select(Study).where(Study.name_short == study_cfg.name_short)
            ).first()

            if not existing_study:
                new_study = Study(
                    name=study_cfg.name,
                    name_short=study_cfg.name_short,
                    description=study_cfg.description
                )
                session.add(new_study)
                session.commit()
                session.refresh(new_study)

                # Add songs to the study
                for song_name in study_cfg.songs_to_rate:
                    new_song = Song(
                        display_name=song_name,
                        media_url=song_name
                    )
                    session.add(new_song)
                    session.commit()
                    session.refresh(new_song)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    create_default_studies(settings.studies_config_path)


    # Create default study with single entry name if it doesn't exist
    with Session(engine) as session:
        default_study = session.exec(
            select(Study).where(Study.name_short == "default")
        ).first()

        if not default_study:
            default_study = Study(
                name="Default Study",
                name_short="default",
                description="Default study for music research"
            )
            session.add(default_study)
            session.commit()
            session.refresh(default_study)

            # Create single entry name for default study
            default_song = Song(
                display_name="Demo Song",
                media_url="demo.wav"
            )
            session.add(default_song)
            session.commit()

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

def get_fallback_config():
    """Provide fallback configuration if no config file is found"""
    from .studies_config import StudiesConfig, StudyConfig

    return StudiesConfig(
        studies=[
            StudyConfig(
                name="Default Study",
                name_short="default",
                description="Default study for music aesthetics research",
                songs_to_rate=["demo.wav"],
                study_participant_ids=[],
                allow_unlisted_participants=True
            )
        ]
    )
