

from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from typing import List, Optional, Dict, Any
from sqlalchemy import UniqueConstraint
import uuid
from datetime import datetime

# Generate UUID as default
def generate_uuid():
    return str(uuid.uuid4())

# Many-to-Many relationship tables
class StudyParticipantLink(SQLModel, table=True):
    study_id: Optional[str] = Field(default=None, foreign_key="study.id", primary_key=True)
    participant_id: Optional[str] = Field(default=None, foreign_key="participant.id", primary_key=True)

class StudySongLink(SQLModel, table=True):
    study_id: Optional[str] = Field(default=None, foreign_key="study.id", primary_key=True)
    song_id: Optional[str] = Field(default=None, foreign_key="song.id", primary_key=True)
    song_index: int = Field(default=0)  # Order of songs in the study

# Main tables
class Participant(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    studies: List["Study"] = Relationship(back_populates="participants", link_model=StudyParticipantLink)
    ratings: List["Rating"] = Relationship(back_populates="participant")

class Study(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    name_short: str = Field(unique=True, index=True)  # "default", "emotion_study", etc.
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    participants: List[Participant] = Relationship(back_populates="studies", link_model=StudyParticipantLink)
    songs: List["Song"] = Relationship(back_populates="studies", link_model=StudySongLink)
    ratings: List["Rating"] = Relationship(back_populates="study")

class Song(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    song_url: str = Field(index=True)  # "demo.wav", "song1.mp3", etc.

    # Relationships
    studies: List[Study] = Relationship(back_populates="songs", link_model=StudySongLink)
    ratings: List["Rating"] = Relationship(back_populates="song")

class Rating(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)

    # Foreign keys
    participant_id: str = Field(foreign_key="participant.id")
    study_id: str = Field(foreign_key="study.id")
    song_id: str = Field(foreign_key="song.id")

    # Rating dimensions and segments
    rating_name: str = Field(index=True)  # "valence", "arousal", "enjoyment", "is_cool"
    rating_segments: Dict[str, Any] = Field(sa_column=Column(JSON))  # List of {start, end, value}

    # Timestamp from frontend
    timestamp: datetime

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    participant: Participant = Relationship(back_populates="ratings")
    study: Study = Relationship(back_populates="ratings")
    song: Song = Relationship(back_populates="ratings")

    # Unique constraint: one rating per participant-study-song-dimension combination
    __table_args__ = (
        UniqueConstraint('participant_id', 'study_id', 'song_id', 'rating_name',
                        name='uq_participant_study_song_rating'),
    )

# Pydantic models for API requests/responses
class RatingSegment(SQLModel):
    start: float
    end: float
    value: int

class RatingSubmission(SQLModel):
    uid: str  # participant ID
    name_short: str
    song_index: int
    song_url: str
    ratings: Dict[str, List[RatingSegment]]  # dimension_name -> list of segments
    timestamp: datetime

class StudyConfigResponse(SQLModel):
    id: str
    name_short: str
    study_participant_ids: List[str]
    allow_unlisted_participants: bool
    songs_to_rate: List[str]

# Create all tables
def create_db_and_tables(engine):
    SQLModel.metadata.create_all(engine)

