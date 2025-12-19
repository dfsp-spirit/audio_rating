from fastapi import FastAPI, HTTPException, Request, status, Response, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from pydantic import ValidationError, BaseModel
from fastapi.exceptions import RequestValidationError
import logging
import uuid
from typing import List, Optional, Tuple
from datetime import datetime, timedelta, timezone
import csv
import json
import io
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from urllib.parse import urlparse
import secrets
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.sql import func
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi import Header, Query
from typing import Dict, List
from sqlalchemy import delete
from .utils import utc_now
from fastapi import Header, Query
from typing import Dict, List
from sqlalchemy import delete


security = HTTPBasic()

# Initialize templates with absolute path
current_dir = Path(__file__).parent
templates = Jinja2Templates(directory=str(current_dir / "templates"))
static_dir = Path(__file__).parent / "static"



from .logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from .settings import settings
from .models import Participant, Study, Song, Rating, StudyParticipantLink, StudySongLink, StudyRatingDimension, RatingSegment, RatingSegmentBase
from .database import get_session, create_db_and_tables
from pydantic import field_validator

class RatingSubmitRequest(BaseModel):
    """Request body for submitting ratings - Pure API schema, not a database model"""
    timestamp: datetime
    ratings: Dict[str, List[RatingSegmentBase]]

    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware and in UTC"""
        if v.tzinfo is None:
            raise ValueError("Timestamp must include timezone information")
        return v.astimezone(timezone.utc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"TUD Backend starting with allowed origins: {settings.allowed_origins}")
    if settings.debug:
        print(f"Debug mode enabled.")

    logger.info("Running on_startup tasks...")
    create_db_and_tables()

    yield
    # Shutdown
    logger.info("TUD Backend shutting down")


app = FastAPI(title="Audiorating (AR) API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Operation"] # custom header to tell frontend on submit if the entry was created or updated.
)



@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = static_dir / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    return Response(status_code=204)

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(
        credentials.username,
        settings.admin_username
    )
    correct_password = secrets.compare_digest(
        credentials.password,
        settings.admin_password
    )

    if not (correct_username and correct_password):
        logger.info(f"Failed admin authentication attempt for user '{credentials.username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    logger.info(f"Admin '{credentials.username}' authenticated successfully.")

    return credentials.username



@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler that ensures CORS headers are always set,
    even in case of exceptions.
    Otherwise, an internal server error may appear as a CORS error in the
    browser, which is misleading during development.
    This also creates a unique error ID for tracking and systematic logging.
    """
    error_id = str(uuid.uuid4())

    # Log the actual error
    logger.error(f"Unhandled exception ID {error_id}: {str(exc)}", exc_info=True)

    # Determine status code based on exception type
    status_code = 500
    if isinstance(exc, HTTPException):
        status_code = exc.status_code

    # Create response with CORS headers
    response = JSONResponse(
        status_code=status_code,
        content={
            "detail": "Internal server error",
            "error_id": error_id,
            "message": "Something went wrong on our end"
        }
    )

    # Get the origin from the request
    origin = request.headers.get("origin")

    def is_localhost(origin: str) -> bool:
        """Check if the origin corresponds to localhost."""
        if not origin:
            return False
        try:
            parsed = urlparse(origin)
            return parsed.hostname in ["localhost", "127.0.0.1", "::1"]
        except:
            return False

    # Check if the origin is in our configured allowed origins
    if origin in settings.allowed_origins or is_localhost(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Expose-Headers"] = "X-Operation"

    return response


# Add this exception handler for request validation errors
@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    error_id = str(uuid.uuid4())

    # Log detailed error information server-side
    error_details = []
    for error in exc.errors():
        error_details.append({
            "field": " -> ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    logger.error(
        f"Request Validation error ID {error_id}: "
        f"Path: {request.url.path}, "
        f"Errors: {error_details}, "
        f"Client: {request.client.host if request.client else 'unknown'}"
    )

    # Send generic error to client
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Invalid request data",
            "error_id": error_id,
            "message": "Please check your request data format and values"
        }
    )

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    # Generate a unique error ID for tracking
    error_id = str(uuid.uuid4())

    # Log detailed error information server-side
    error_details = []
    for error in exc.errors():
        error_details.append({
            "field": " -> ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    logger.error(
        f"Validation error ID {error_id}: "
        f"Path: {request.url.path}, "
        f"Errors: {error_details}, "
        f"Client: {request.client.host if request.client else 'unknown'}"
    )

    # Send generic error to client
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Invalid request data",
            "error_id": error_id,  # Client can reference this if needed
            "message": "Please check your request data format and values"
        }
    )


@app.get("/api")
def root():
    return {"message": "AR API is running"}


@app.post("/api/participants/{participant_id}/studies/{study_name_short}/songs/{song_index}/ratings")
async def submit_rating_restful(
    participant_id: str,  # Now a path parameter
    study_name_short: str,
    song_index: int,
    rating_request: RatingSubmitRequest,
    session: Session = Depends(get_session)
):
    """
    Submit ratings for a specific study, song, and participant.
    - participant_id: Participant ID from X-Participant-ID header
    - study_name_short: Short name of the study (from URL)
    - song_index: Index of the song in the study (from URL)
    - rating_request: Contains timestamp and ratings data
    - session: Database session dependency
    Returns success message with details.
    """
    try:
        # Get study
        study = session.exec(
            select(Study).where(Study.name_short == study_name_short)
        ).first()

        if not study:
            raise HTTPException(
                status_code=404,
                detail=f"Study '{study_name_short}' not found"
            )

        # Validate study dates
        now = utc_now()
        if now < study.data_collection_start:
            raise HTTPException(
                status_code=403,
                detail=f"Study hasn't started yet (starts {study.data_collection_start.isoformat()})"
            )
        if now > study.data_collection_end:
            raise HTTPException(
                status_code=403,
                detail=f"Study has ended (ended {study.data_collection_end.isoformat()})"
            )

        # Get or create participant
        participant = session.exec(
            select(Participant).where(Participant.id == participant_id)
        ).first()

        if not participant:
            participant = Participant(id=participant_id)
            session.add(participant)
            logger.info(f"Created new participant: {participant.id}")

        # Check participant authorization if needed
        if not study.allow_unlisted_participants:
            link_exists = session.exec(
                select(StudyParticipantLink).where(
                    StudyParticipantLink.study_id == study.id,
                    StudyParticipantLink.participant_id == participant.id
                )
            ).first()
            if not link_exists:
                raise HTTPException(
                    status_code=403,
                    detail="Participant not authorized for this study"
                )

        # Get song by index in study
        song_link = session.exec(
            select(StudySongLink, Song)
            .join(Song, StudySongLink.song_id == Song.id)
            .where(
                StudySongLink.study_id == study.id,
                StudySongLink.song_index == song_index
            )
        ).first()

        if not song_link:
            raise HTTPException(
                status_code=404,
                detail=f"Song with index {song_index} not found in study '{study_name_short}'"
            )

        song = song_link[1]  # Get the Song object

        # Process all ratings in a single batch
        rating_count = 0
        segment_count = 0

        for rating_name, segments in rating_request.ratings.items():
            # Find or create rating
            rating = session.exec(
                select(Rating).where(
                    Rating.participant_id == participant.id,
                    Rating.study_id == study.id,
                    Rating.song_id == song.id,
                    Rating.rating_name == rating_name
                )
            ).first()

            if rating:
                # Delete existing segments
                session.exec(
                    delete(RatingSegment).where(RatingSegment.rating_id == rating.id)
                )
                rating.timestamp = rating_request.timestamp
                operation = "updated"
            else:
                rating = Rating(
                    participant_id=participant.id,
                    study_id=study.id,
                    song_id=song.id,
                    rating_name=rating_name,
                    timestamp=rating_request.timestamp
                )
                session.add(rating)
                rating_count += 1
                operation = "created"

            # Flush to get rating ID for segments
            session.flush()

            # Add all segments for this rating
            for segment_order, segment_data in enumerate(segments):
                segment = RatingSegment(
                    rating_id=rating.id,
                    start_time=segment_data.start,
                    end_time=segment_data.end,
                    value=segment_data.value,
                    segment_order=segment_order
                )
                session.add(segment)
                segment_count += 1

            logger.info(f"{operation.capitalize()} rating '{rating_name}' with {len(segments)} segments")

        session.commit()

        # Set operation header for frontend
        response_headers = {
            "X-Operation": "updated" if rating_count == 0 else "created"
        }

        return JSONResponse(
            content={
                "status": "success",
                "message": f"Submitted {len(rating_request.ratings)} ratings with {segment_count} segments",
                "study": study_name_short,
                "song_index": song_index,
                "song_url": song.media_url,
                "participant_id": participant.id,
                "ratings_created": rating_count,
                "ratings_updated": len(rating_request.ratings) - rating_count,
                "segments_saved": segment_count,
                "timestamp": rating_request.timestamp.isoformat()
            },
            headers=response_headers
        )

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Rating submission error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )



@app.get("/api/participants/{participant_id}/studies/{study_name_short}/songs/{song_index}/ratings")
async def get_rating(
    participant_id: str,  # Now a path parameter
    study_name_short: str,
    song_index: int,
    session: Session = Depends(get_session)
):
    """
    Get existing ratings for a participant, study, and song.

    Returns all rating segments organized by rating name.
    """
    try:
        # Get study
        study = session.exec(
            select(Study).where(Study.name_short == study_name_short)
        ).first()

        if not study:
            raise HTTPException(
                status_code=404,
                detail=f"Study '{study_name_short}' not found"
            )

        # Get participant
        participant = session.exec(
            select(Participant).where(Participant.id == participant_id)
        ).first()

        if not participant:
            # Participant doesn't exist yet, return empty response
            return {
                "study_name_short": study_name_short,
                "song_index": song_index,
                "participant_id": participant_id,
                "ratings": {},
                "message": "No ratings found for this participant",
                "retrieved_at": utc_now().isoformat()
            }

        # Get song by index in study
        song_link = session.exec(
            select(StudySongLink, Song)
            .join(Song, StudySongLink.song_id == Song.id)
            .where(
                StudySongLink.study_id == study.id,
                StudySongLink.song_index == song_index
            )
        ).first()

        if not song_link:
            raise HTTPException(
                status_code=404,
                detail=f"Song with index {song_index} not found in study '{study_name_short}'"
            )

        song = song_link[1]  # Get the Song object

        # Get all ratings with their segments
        ratings = session.exec(
            select(Rating, RatingSegment)
            .join(RatingSegment, Rating.id == RatingSegment.rating_id, isouter=True)
            .where(
                Rating.participant_id == participant.id,
                Rating.study_id == study.id,
                Rating.song_id == song.id
            )
            .order_by(Rating.rating_name, RatingSegment.segment_order)
        ).all()

        # Organize by rating name
        organized_ratings = {}
        for rating, segment in ratings:
            if segment is None:
                # Rating exists but has no segments (shouldn't happen, but handle gracefully)
                continue

            if rating.rating_name not in organized_ratings:
                organized_ratings[rating.rating_name] = {
                    "rating_id": rating.id,
                    "timestamp": rating.timestamp.isoformat() if rating.timestamp else None,
                    "created_at": rating.created_at.isoformat() if rating.created_at else None,
                    "segments": []
                }

            organized_ratings[rating.rating_name]["segments"].append({
                "start": segment.start_time,
                "end": segment.end_time,
                "value": segment.value,
                "segment_order": segment.segment_order
            })

        # Check if we found any ratings
        if not organized_ratings:
            return {
                "study_name_short": study_name_short,
                "song_index": song_index,
                "song_url": song.media_url,
                "participant_id": participant.id,
                "ratings": {},
                "message": "No ratings found",
                "retrieved_at": utc_now().isoformat()
            }

        return {
            "study_name_short": study_name_short,
            "song_index": song_index,
            "song_url": song.media_url,
            "participant_id": participant.id,
            "ratings": organized_ratings,
            "retrieved_at": utc_now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving ratings: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


from pydantic import BaseModel
from typing import List, Optional

# Add this Pydantic model for the response
class ActiveOpenStudyResponse(BaseModel):
    name_short: str
    name: Optional[str] = None
    description: Optional[str] = None

@app.get("/api/active_open_study_names", response_model=List[ActiveOpenStudyResponse])
async def get_active_open_study_names(
    session: Session = Depends(get_session)
):
    """
    Public endpoint (no authentication required) that returns a list of all studies
    that:
    1. Have allow_unlisted_participants set to True
    2. Are currently active (current date is between data_collection_start and data_collection_end)

    Each study object includes name_short, name, and description fields.
    Returns empty list if no studies match criteria.
    """
    try:
        # Get current UTC time
        now = utc_now()

        # Query for studies that match both criteria
        studies = session.exec(
            select(Study).where(
                Study.allow_unlisted_participants == True,
                Study.data_collection_start <= now,
                Study.data_collection_end >= now
            ).order_by(Study.name_short)  # Optional: order alphabetically
        ).all()

        # Create response objects with the required fields
        study_responses = [
            ActiveOpenStudyResponse(
                name_short=study.name_short,
                name=study.name,
                description=study.description
            )
            for study in studies
        ]

        logger.info(f"Found {len(study_responses)} active open studies")

        return study_responses

    except Exception as e:
        logger.error(f"Error fetching active open study names: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching study information"
        )


@app.get("/api/admin/datasets/download")
async def admin_download(
    study_name: str = Query(..., description="Name of the study to download ratings for"),
    format: str = Query("json", description="Output format: json or csv"),
    with_ids: bool = Query(False, description="Include database IDs in the output"),
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin)
):
    """
    Download all ratings for a specific study in JSON or CSV format.
    Requires admin authentication.
    """
    try:
        # Get the study
        study = session.exec(
            select(Study).where(Study.name_short == study_name)
        ).first()

        if not study:
            raise HTTPException(
                status_code=404,
                detail=f"Study '{study_name}' not found"
            )

        # Get all ratings for this study with related data including segments
        statement = (
            select(Rating, Participant, Song, RatingSegment)
            .join(Participant, Rating.participant_id == Participant.id)
            .join(Song, Rating.song_id == Song.id)
            .join(RatingSegment, RatingSegment.rating_id == Rating.id)
            .where(Rating.study_id == study.id)
            .order_by(Rating.participant_id, Rating.song_id, Rating.rating_name, RatingSegment.segment_order)
        )

        results = session.exec(statement)
        rating_data = results.all()

        if not rating_data:
            raise HTTPException(
                status_code=404,
                detail=f"No ratings found for study '{study_name}'"
            )

        logger.info(f"Admin '{current_admin}' downloading {len(rating_data)} rating segments for study '{study_name}'")

        # Transform data for output - now each row is a segment
        segments_data = []
        for rating, participant, song, segment in rating_data:
            segment_data = {
                "study_name": study.name_short,
                "study_description": study.name or study.description,
                "participant_id": participant.id, # This is always included, even if with_ids is False, as it is required context.
                "song_url": song.media_url,
                "song_title": song.display_name,
                "rating_name": rating.rating_name,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "value": segment.value,
                "segment_order": segment.segment_order,
                "rating_created_at": rating.created_at.isoformat() if rating.created_at else None
            }
            if with_ids:
                segment_data["song_id"] = song.id
                segment_data["rating_id"] = rating.id
                segment_data["segment_id"] = segment.id



            segments_data.append(segment_data)

        # Return in requested format
        if format.lower() == "csv":
            return _generate_csv_response(segments_data, study_name, with_ids)
        else:
            return {
                "study": {
                    "name_short": study.name_short,
                    "name": study.name,
                    "description": study.description,
                    "allow_unlisted_participants": study.allow_unlisted_participants
                },
                "total_segments": len(segments_data),
                "segments": segments_data
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading dataset for study '{study_name}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download dataset: {str(e)}"
        )


def _generate_csv_response(segments_data: List[dict], study_name: str, with_ids: bool) -> StreamingResponse:
    """Generate CSV response with all segment data."""
    if not segments_data:
        raise HTTPException(status_code=404, detail="No data to export")

    # Create CSV output
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header - now includes all segment details
    headers = [
        "study_name", "study_description", "participant_id",
        "song_url", "song_title", "rating_name",
        "start_time", "end_time", "value", "segment_order",
        "rating_created_at"
    ]

    if with_ids:
        headers.extend(["song_id", "rating_id", "segment_id"])

    writer.writerow(headers)

    # Write data rows - each row is one segment
    for segment in segments_data:

        row = [
            segment["study_name"],
            segment["study_description"],
            segment["participant_id"],
            segment["song_url"],
            segment["song_title"],
            segment["rating_name"],
            segment["start_time"],
            segment["end_time"],
            segment["value"],
            segment["segment_order"],
            segment["rating_created_at"]
        ]

        if with_ids:
            row.append(segment["song_id"])
            row.append(segment["rating_id"])
            row.append(segment["segment_id"])

        writer.writerow(row)

    # Prepare response
    output.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{study_name}_rating_segments_{timestamp}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin)
):
    """
    Main admin dashboard showing all studies and participation statistics.
    Access via: /admin with HTTP Basic Auth
    """
    try:
        # Get all studies with basic info
        studies = session.exec(select(Study).order_by(Study.created_at)).all()

        study_stats = []

        for study in studies:
            # Get total songs in this study
            song_links = session.exec(
                select(StudySongLink).where(StudySongLink.study_id == study.id)
            ).all()
            total_songs = len(song_links)

            # Get all participants linked to this study (pre-listed)
            participant_links = session.exec(
                select(StudyParticipantLink).where(StudyParticipantLink.study_id == study.id)
            ).all()
            pre_listed_participants = [link.participant_id for link in participant_links]

            # Get all participants who have actually submitted ratings for this study
            participants_with_ratings = session.exec(
                select(Rating.participant_id)
                .where(Rating.study_id == study.id)
                .distinct()
            ).all()

            # Get all ratings for this study to analyze participation
            ratings = session.exec(
                select(Rating, Participant, Song, func.count(RatingSegment.id).label("segment_count"))
                .join(Participant, Rating.participant_id == Participant.id)
                .join(Song, Rating.song_id == Song.id)
                .join(RatingSegment, RatingSegment.rating_id == Rating.id, isouter=True)
                .where(Rating.study_id == study.id)
                .group_by(Rating.id, Participant.id, Song.id)
                .order_by(Participant.id, Song.display_name, Rating.rating_name)
            ).all()

            # Organize data by participant
            participants_data = {}
            for rating, participant, song, segment_count in ratings:
                if participant.id not in participants_data:
                    participants_data[participant.id] = {
                        "id": participant.id,
                        "created_at": participant.created_at,
                        "is_pre_listed": participant.id in pre_listed_participants,
                        "songs_rated": set(),
                        "ratings": [],
                        "total_segments": 0,
                        "last_activity": rating.timestamp if rating.timestamp else rating.created_at
                    }

                participants_data[participant.id]["songs_rated"].add(song.display_name)
                participants_data[participant.id]["ratings"].append({
                    "song": song.display_name,
                    "song_url": song.media_url,
                    "rating_name": rating.rating_name,
                    "segment_count": segment_count,
                    "timestamp": rating.timestamp,
                    "created_at": rating.created_at
                })
                participants_data[participant.id]["total_segments"] += segment_count

                # Update last activity if this rating is newer
                if rating.timestamp and rating.timestamp > participants_data[participant.id]["last_activity"]:
                    participants_data[participant.id]["last_activity"] = rating.timestamp

            # Convert sets to lists for template
            for participant_id in participants_data:
                participants_data[participant_id]["songs_rated"] = list(
                    participants_data[participant_id]["songs_rated"]
                )
                participants_data[participant_id]["songs_rated_count"] = len(
                    participants_data[participant_id]["songs_rated"]
                )

            # Get unique participants who submitted ratings
            active_participants = list(participants_data.values())

            # Calculate coverage percentage safely
            total_participants = len(set(pre_listed_participants + [p["id"] for p in active_participants]))
            if total_songs > 0 and total_participants > 0:
                # Simplified: percentage of total possible ratings (participants × songs) that have been completed
                total_possible_ratings = total_participants * total_songs
                coverage_percentage = 0  # Default
            else:
                coverage_percentage = 0

            study_stats.append({
                "id": study.id,
                "name_short": study.name_short,
                "name": study.name,
                "description": study.description,
                "total_songs": total_songs,
                "allow_unlisted_participants": study.allow_unlisted_participants,
                "pre_listed_participants": pre_listed_participants,
                "pre_listed_count": len(pre_listed_participants),
                "active_participants": active_participants,
                "active_participants_count": len(active_participants),
                "total_participants": total_participants,
                "coverage_percentage": coverage_percentage
            })

        return templates.TemplateResponse(
            "admin_dashboard.html",
            {
                "request": request,
                "studies": study_stats,
                "admin_user": current_admin,
                "current_time": datetime.now()
            }
        )

    except Exception as e:
        logger.error(f"Error loading admin dashboard: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load admin dashboard: {str(e)}"
        )


@app.get("/admin/api/stats")
async def admin_api_stats(
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin)
):
    """
    API endpoint for admin dashboard stats (can be used for AJAX updates).
    """
    try:
        # Similar logic as above but returns JSON
        if study_id:
            studies = session.exec(
                select(Study).where(Study.id == study_id)
            ).all()
        else:
            studies = session.exec(select(Study).order_by(Study.created_at)).all()

        study_stats = []

        for study in studies:
            # Simplified stats for API
            total_ratings = session.exec(
                select(func.count(Rating.id)).where(Rating.study_id == study.id)
            ).first() or 0

            unique_participants = session.exec(
                select(func.count(func.distinct(Rating.participant_id)))
                .where(Rating.study_id == study.id)
            ).first() or 0

            total_segments = session.exec(
                select(func.count(RatingSegment.id))
                .join(Rating, Rating.id == RatingSegment.rating_id)
                .where(Rating.study_id == study.id)
            ).first() or 0

            study_stats.append({
                "id": study.id,
                "name_short": study.name_short,
                "name": study.name,
                "total_ratings": total_ratings,
                "unique_participants": unique_participants,
                "total_segments": total_segments,
                "last_activity": session.exec(
                    select(func.max(Rating.timestamp))
                    .where(Rating.study_id == study.id)
                ).first()
            })

        return {
            "studies": study_stats,
            "total_studies": len(study_stats),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in admin API stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get stats: {str(e)}"
        )

@app.get("/api/participants/{participant_id}/studies/{study_name}/config")
async def get_study_config(
    participant_id: str,
    study_name: str,
    session: Session = Depends(get_session)
):
    """
    Get configuration for a specific study, with participant authorization check.

    Returns study configuration without sensitive information (no study_participant_ids).
    Checks if participant is authorized to access this study.
    """
    try:
        # Get study from database
        study = session.exec(
            select(Study).where(Study.name_short == study_name)
        ).first()

        if not study:
            raise HTTPException(
                status_code=404,
                detail=f"Study '{study_name}' not found"
            )

        # Check if study is active (within data collection period)
        now = utc_now()
        if now < study.data_collection_start:
            raise HTTPException(
                status_code=403,
                detail=f"Study '{study_name}' has not started yet. "
                       f"Data collection starts on {study.data_collection_start.isoformat()}"
            )

        if now > study.data_collection_end:
            raise HTTPException(
                status_code=403,
                detail=f"Study '{study_name}' has ended. "
                       f"Data collection ended on {study.data_collection_end.isoformat()}"
            )

        # Check participant authorization if study doesn't allow unlisted participants
        if not study.allow_unlisted_participants:
            # Check if participant is pre-listed for this study
            participant_link = session.exec(
                select(StudyParticipantLink).where(
                    StudyParticipantLink.study_id == study.id,
                    StudyParticipantLink.participant_id == participant_id
                )
            ).first()

            if not participant_link:
                raise HTTPException(
                    status_code=403,
                    detail=f"Participant '{participant_id}' is not authorized to access study '{study_name}'"
                )

        # Get all songs linked to this study (ordered by song_index)
        song_links = session.exec(
            select(StudySongLink, Song)
            .join(Song, StudySongLink.song_id == Song.id)
            .where(StudySongLink.study_id == study.id)
            .order_by(StudySongLink.song_index)
        ).all()

        # Get all rating dimensions for this study (ordered by dimension_order)
        rating_dims = session.exec(
            select(StudyRatingDimension)
            .where(StudyRatingDimension.study_id == study.id)
            .order_by(StudyRatingDimension.dimension_order)
        ).all()

        # Build the response - FILTERED (no sensitive information)
        study_config = {
            "name": study.name,
            "name_short": study.name_short,
            "description": study.description,
            "songs_to_rate": [
                {
                    "media_url": song.media_url,
                    "display_name": song.display_name
                }
                for _, song in song_links  # song_links is tuple of (StudySongLink, Song)
            ],
            "rating_dimensions": [
                {
                    "dimension_title": dim.dimension_title,
                    "num_values": dim.num_values
                }
                for dim in rating_dims
            ],
            "allow_unlisted_participants": study.allow_unlisted_participants,
            "data_collection_start": study.data_collection_start.isoformat(),
            "data_collection_end": study.data_collection_end.isoformat()
        }

        logger.info(
            f"Returning config for study '{study_name}' to participant '{participant_id}' "
            f"with {len(song_links)} songs and {len(rating_dims)} dimensions"
        )

        return study_config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error loading study config for '{study_name}' (participant '{participant_id}'): {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to load study configuration"
        )