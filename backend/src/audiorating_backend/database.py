
# database.py
from sqlmodel import SQLModel, create_engine, Session, select
from typing import Generator
from .models import Study, Song, StudyRatingDimension, StudySongLink, StudyParticipantLink, Participant
from .parsers.studies_config import load_studies_config
from .settings import settings
import logging
from datetime import datetime


logger = logging.getLogger("audiorating_backend.database")

engine = create_engine(settings.database_url)

def create_db_and_tables():
    """Create all database tables"""
    SQLModel.metadata.create_all(engine)
    create_config_file_studies(settings.studies_config_path)


def create_config_file_studies(config_path: str):
    """Create default studies from a configuration file"""

    config = load_studies_config(config_path) # will raise FileNotFoundError if not found, which is fine. That file is required.

    logger.info(f"Checking whether studies need to be created based on config file at '{config_path}'")

    with Session(engine) as session:
        for study_cfg in config.studies:
            # Check if study already exists
            existing_study = session.exec(
                select(Study).where(Study.name_short == study_cfg.name_short)
            ).first()

            if not existing_study:
                logger.info(f"Creating new study: {study_cfg.name_short}")

                new_study = Study(
                    name=study_cfg.name,
                    name_short=study_cfg.name_short,
                    description=study_cfg.description,
                    allow_unlisted_participants=study_cfg.allow_unlisted_participants,
                    data_collection_start=study_cfg.data_collection_start,
                    data_collection_end=study_cfg.data_collection_end
                )
                session.add(new_study)
                session.commit()
                session.refresh(new_study)

                # Add pre-listed participants to the study (ONLY ONCE)
                for participant_id in study_cfg.study_participant_ids:
                    # Check if participant exists, create if not
                    existing_participant = session.exec(
                        select(Participant).where(Participant.id == participant_id)
                    ).first()

                    if not existing_participant:
                        participant = Participant(id=participant_id)
                        session.add(participant)
                        logger.info(f"Created pre-listed participant: {participant_id}")
                    else:
                        participant = existing_participant
                        logger.info(f"Using existing participant: {participant_id}")

                    # Check if link already exists before creating
                    existing_link = session.exec(
                        select(StudyParticipantLink).where(
                            StudyParticipantLink.study_id == new_study.id,
                            StudyParticipantLink.participant_id == participant.id
                        )
                    ).first()

                    if not existing_link:
                        # Create the study-participant link
                        participant_link = StudyParticipantLink(
                            study_id=new_study.id,
                            participant_id=participant.id
                        )
                        session.add(participant_link)
                        logger.info(f"Added pre-listed participant to study: {participant_id}")

                # Add songs to the study (with proper n:m relationships)
                for song_index, song_cfg in enumerate(study_cfg.songs_to_rate):
                    # Check if song already exists by media_url
                    existing_song = session.exec(
                        select(Song).where(Song.media_url == song_cfg.media_url)
                    ).first()

                    if existing_song:
                        song = existing_song
                        logger.info(f"Using existing song: {song_cfg.media_url}")
                    else:
                        song = Song(
                            display_name=song_cfg.display_name,
                            media_url=song_cfg.media_url,
                            description=song_cfg.description
                        )
                        session.add(song)
                        session.commit()
                        session.refresh(song)
                        logger.info(f"Created new song: {song_cfg.media_url}")

                    # Check if song link already exists before creating
                    existing_song_link = session.exec(
                        select(StudySongLink).where(
                            StudySongLink.study_id == new_study.id,
                            StudySongLink.song_id == song.id
                        )
                    ).first()

                    if not existing_song_link:
                        # Create StudySongLink (n:m relationship)
                        song_link = StudySongLink(
                            study_id=new_study.id,
                            song_id=song.id,
                            song_index=song_index
                        )
                        session.add(song_link)

                # Add rating dimensions to the study
                for dim_index, dimension_cfg in enumerate(study_cfg.rating_dimensions):
                    # Check if dimension already exists before creating
                    existing_dimension = session.exec(
                        select(StudyRatingDimension).where(
                            StudyRatingDimension.study_id == new_study.id,
                            StudyRatingDimension.dimension_title == dimension_cfg.dimension_title
                        )
                    ).first()

                    if not existing_dimension:
                        new_dimension = StudyRatingDimension(
                            study_id=new_study.id,
                            dimension_title=dimension_cfg.dimension_title,
                            num_values=dimension_cfg.num_values,
                            dimension_order=dim_index,
                            description=dimension_cfg.description
                        )
                        session.add(new_dimension)
                        logger.info(f"Added rating dimension: {dimension_cfg.dimension_title}")

                # Commit all relationships for this study
                session.commit()
                logger.info(f"Successfully created study '{study_cfg.name_short}' with {len(study_cfg.songs_to_rate)} songs and {len(study_cfg.rating_dimensions)} rating dimensions")
            else:
                logger.info(f"Study already exists: {study_cfg.name_short}")


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def report_on_db_contents():
    """Report on the contents of the database for debugging purposes"""
    with Session(engine) as session:
        studies = session.exec(select(Study)).all()
        logger.info(f"Database contains {len(studies)} studies.")

        for study in studies:
            # Get songs through song_links relationship
            song_links = session.exec(
                select(StudySongLink)
                .where(StudySongLink.study_id == study.id)
                .order_by(StudySongLink.song_index)
            ).all()

            # Get rating dimensions
            rating_dims = session.exec(
                select(StudyRatingDimension)
                .where(StudyRatingDimension.study_id == study.id)
                .order_by(StudyRatingDimension.dimension_order)
            ).all()

            logger.info(f"Study '{study.name_short}' has {len(song_links)} songs and {len(rating_dims)} rating dimensions.")

            # Log songs
            for song_link in song_links:
                song = session.exec(select(Song).where(Song.id == song_link.song_id)).first()
                if song:
                    logger.info(f" - Song: {song.display_name} ({song.media_url}): {song.description}")

            # Log rating dimensions
            for dimension in rating_dims:
                logger.info(f" - Rating Dimension: {dimension.dimension_title} ({dimension.num_values} values): {dimension.description}")

            # report whether study allows unlisted participants
            logger.info(f" - Allows unlisted participants: {study.allow_unlisted_participants}")

            if not study.allow_unlisted_participants:
                # Get participants through participant_links relationship
                participant_links = session.exec(
                    select(StudyParticipantLink)
                    .where(StudyParticipantLink.study_id == study.id)
                ).all()
                participant_ids = [link.participant_id for link in participant_links]
                logger.info(f" - Study participant IDs: {participant_ids}")

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    create_config_file_studies(settings.studies_config_path)
    report_on_db_contents()

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session