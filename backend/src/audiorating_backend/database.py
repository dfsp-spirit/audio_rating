# database.py
from sqlmodel import SQLModel, create_engine, Session, select
from typing import Generator
from .models import Study, Song

from .settings import settings
engine = create_engine(settings.database_url)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

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
                study_id=default_study.id,
                song_index=0,
                song_name="default",
                song_url="demo.wav"
            )
            session.add(default_song)
            session.commit()

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session