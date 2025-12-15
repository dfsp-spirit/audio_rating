from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from typing import List, Optional, Dict, Any
from sqlalchemy import UniqueConstraint, DateTime
import uuid
from datetime import datetime, timezone
from .utils import utc_now

# Generate UUID as default
def generate_uuid():
    return str(uuid.uuid4())

# Many-to-Many relationship tables
class StudyParticipantLink(SQLModel, table=True):
    study_id: Optional[str] = Field(default=None, foreign_key="study.id", primary_key=True)
    participant_id: Optional[str] = Field(default=None, foreign_key="participant.id", primary_key=True)

    # Relationships - use strings for forward references
    study: "Study" = Relationship(back_populates="participant_links")
    participant: "Participant" = Relationship(back_populates="study_links")

class StudySongLink(SQLModel, table=True):
    study_id: Optional[str] = Field(default=None, foreign_key="study.id", primary_key=True)
    song_id: Optional[str] = Field(default=None, foreign_key="song.id", primary_key=True)
    song_index: int = Field(default=0)

    # Relationships - use strings for forward references
    study: "Study" = Relationship(back_populates="song_links")
    song: "Song" = Relationship(back_populates="study_links")

# New table for study rating dimensions
class StudyRatingDimension(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    study_id: str = Field(foreign_key="study.id")
    dimension_title: str
    num_values: int
    dimension_order: int = Field(default=0)

    # Relationship
    study: "Study" = Relationship(back_populates="rating_dimensions")

    __table_args__ = (
        UniqueConstraint('study_id', 'dimension_title', name='uq_study_dimension_title'),
    )


class RatingSegment(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    rating_id: str = Field(foreign_key="rating.id")
    start_time: float = Field(description="Segment start time in seconds")
    end_time: float = Field(description="Segment end time in seconds")
    value: int = Field(description="Rating value for this segment")
    segment_order: int = Field(default=0, description="Order of segment in the rating")
    created_at: datetime = Field(default_factory=utc_now)

    # Relationship
    rating: "Rating" = Relationship(back_populates="segments")

    __table_args__ = (
        UniqueConstraint('rating_id', 'segment_order', name='uq_rating_segment_order'),
    )

# Main tables
class Participant(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)

    # Relationships
    study_links: List["StudyParticipantLink"] = Relationship(back_populates="participant")
    ratings: List["Rating"] = Relationship(back_populates="participant")

class Study(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    name_short: str = Field(unique=True, index=True)
    name: Optional[str] = None
    description: Optional[str] = None
    allow_unlisted_participants: bool = Field(default=True)
    data_collection_start : datetime = Field(sa_type=DateTime(timezone=True))
    data_collection_end: datetime = Field(sa_type=DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))

    # Relationships
    participant_links: List["StudyParticipantLink"] = Relationship(back_populates="study")
    song_links: List["StudySongLink"] = Relationship(back_populates="study")
    ratings: List["Rating"] = Relationship(back_populates="study")
    rating_dimensions: List["StudyRatingDimension"] = Relationship(back_populates="study")

class Song(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    display_name: str
    media_url: str = Field(index=True)

    # Relationships
    study_links: List["StudySongLink"] = Relationship(back_populates="song")
    ratings: List["Rating"] = Relationship(back_populates="song")

class Rating(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    participant_id: str = Field(foreign_key="participant.id")
    study_id: str = Field(foreign_key="study.id")
    song_id: str = Field(foreign_key="song.id")
    rating_name: str = Field(index=True)
    # REMOVED: rating_segments: Dict[str, Any] = Field(sa_column=Column(JSON))
    timestamp: datetime
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))

    # Relationships
    participant: "Participant" = Relationship(back_populates="ratings")
    study: "Study" = Relationship(back_populates="ratings")
    song: "Song" = Relationship(back_populates="ratings")
    # NEW: Relationship to segments
    segments: List["RatingSegment"] = Relationship(back_populates="rating")

    __table_args__ = (
        UniqueConstraint('participant_id', 'study_id', 'song_id', 'rating_name',
                        name='uq_participant_study_song_rating'),
    )

# Update forward references (new syntax)
StudyParticipantLink.update_forward_refs()
StudySongLink.update_forward_refs()
StudyRatingDimension.update_forward_refs()
RatingSegment.update_forward_refs()  # NEW
Participant.update_forward_refs()
Study.update_forward_refs()
Song.update_forward_refs()
Rating.update_forward_refs()

# Pydantic models for API requests/responses - KEEP THESE FOR API
class RatingSegmentBase(SQLModel):
    start: float
    end: float
    value: int

class SongConfig(SQLModel):
    media_url: str
    display_name: str

class RatingDimensionConfig(SQLModel):
    dimension_title: str
    num_values: int

class StudyConfig(SQLModel):
    name: str
    name_short: str
    description: Optional[str] = None
    songs_to_rate: List[SongConfig]
    rating_dimensions: List[RatingDimensionConfig]
    study_participant_ids: List[str] = []
    allow_unlisted_participants: bool = True

class StudiesConfig(SQLModel):
    studies: List[StudyConfig]

class ParticipantMetadata(SQLModel):
    pid: str

class StudyMetadata(SQLModel):
    name_short: str
    song_index: int
    song_url: str

class SubmissionMetadata(SQLModel):
    timestamp: datetime

class MetadataRating(SQLModel):
    participant: ParticipantMetadata
    study: StudyMetadata
    submission: SubmissionMetadata

class RatingSubmission(SQLModel):
    metadata_rating: MetadataRating
    ratings: Dict[str, List[RatingSegmentBase]]

class StudyConfigResponse(SQLModel):
    id: str
    name_short: str
    study_participant_ids: List[str]
    allow_unlisted_participants: bool
    songs_to_rate: List[str]
    rating_dimensions: List[RatingDimensionConfig]

def create_db_and_tables(engine):
    SQLModel.metadata.create_all(engine)

