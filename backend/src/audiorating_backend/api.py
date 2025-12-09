from fastapi import FastAPI, HTTPException, Request, status, Response, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from fastapi.exceptions import RequestValidationError
import logging
import uuid
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
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
from .utils import utc_now

security = HTTPBasic()

# Initialize templates with absolute path
current_dir = Path(__file__).parent
templates = Jinja2Templates(directory=str(current_dir / "templates"))
static_dir = Path(__file__).parent / "static"



from .logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from .settings import settings
from .models import Participant, Study, Song, Rating, StudyParticipantLink, StudySongLink, RatingSubmission, RatingSegment
from .database import get_session, create_db_and_tables



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


@app.post("/api/rating/submit")
async def submit_rating(
    submission: RatingSubmission,
    session: Session = Depends(get_session)
):
    try:
        metadata = submission.metadata_rating
        ratings_data = submission.ratings

        # Get or create participant
        participant = session.exec(
            select(Participant).where(Participant.id == metadata.participant.pid)
        ).first()

        if not participant:
            participant = Participant(id=metadata.participant.pid)
            session.add(participant)
            session.flush()  # Get the ID without committing
            logger.info(f"Created new participant: {participant.id}")

        # Get study or throw error if not found
        study = session.exec(
            select(Study).where(Study.name_short == metadata.study.name_short)
        ).first()

        if not study:
            raise HTTPException(
                status_code=404,
                detail=f"Study with name_short '{metadata.study.name_short}' not found."
            )

        now = utc_now()
        if now < study.data_collection_start:
            raise HTTPException(
                status_code=403,
                detail=f"Study '{study.name_short}' has not started yet. "
                       f"Data collection starts on {study.data_collection_start.isoformat()}."
            )

        if now > study.data_collection_end:
            raise HTTPException(
                status_code=403,
                detail=f"Study '{study.name_short}' has ended. "
                       f"Data collection ended on {study.data_collection_end.isoformat()}."
            )

        # Get song or throw error if not found
        song = session.exec(
            select(Song).where(Song.media_url == metadata.study.song_url)
        ).first()

        if not song:
            raise HTTPException(
                status_code=404,
                detail=f"Song with URL '{metadata.study.song_url}' not found."
            )

        # If the study does not have allow_unlisted_participants set, check whether the participant is assigned to the study
        if not study.allow_unlisted_participants:
            participiant_link = session.exec(
                select(StudyParticipantLink).where(
                    StudyParticipantLink.study_id == study.id,
                    StudyParticipantLink.participant_id == participant.id
                )
            ).first()

            if not participiant_link:
                raise HTTPException(
                    status_code=403,
                    detail=f"Participant '{participant.id}' is not allowed to submit ratings for study '{study.name_short}'."
                )

        # Link song to study if not already linked (with correct index)
        existing_song_link = session.exec(
            select(StudySongLink).where(
                StudySongLink.study_id == study.id,
                StudySongLink.song_id == song.id
            )
        ).first()

        if not existing_song_link:
            raise HTTPException(
                status_code=403,
                detail=f"Song '{song.media_url}' is not linked to study '{study.name_short}', no rating allowed."
            )

        # Save ratings for each dimension
        rating_count = 0
        segment_count = 0

        for rating_name, segments in ratings_data.items():
            # Check if rating already exists
            existing_rating = session.exec(
                select(Rating).where(
                    Rating.participant_id == participant.id,
                    Rating.study_id == study.id,
                    Rating.song_id == song.id,
                    Rating.rating_name == rating_name
                )
            ).first()

            if existing_rating:
                # Delete existing segments first
                existing_segments = session.exec(
                    select(RatingSegment).where(
                        RatingSegment.rating_id == existing_rating.id
                    )
                ).all()

                for seg in existing_segments:
                    session.delete(seg)

                # Update existing rating timestamp
                existing_rating.timestamp = metadata.submission.timestamp
                rating = existing_rating
                logger.info(f"Updated existing rating for {rating_name} and deleted {len(existing_segments)} segments")
            else:
                # Create new rating
                rating = Rating(
                    participant_id=participant.id,
                    study_id=study.id,
                    song_id=song.id,
                    rating_name=rating_name,
                    timestamp=metadata.submission.timestamp
                )
                session.add(rating)
                session.flush()  # Get the rating ID for segments
                rating_count += 1

            # Save all segments for this rating
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

            logger.info(f"Saved {len(segments)} segments for rating {rating_name}")

        # Commit all changes
        session.commit()

        logger.info(f"Successfully saved {rating_count} ratings with {segment_count} total segments for participant {participant.id}")

        return {
            "status": "success",
            "message": f"Ratings submitted successfully",
            "participant_id": participant.id,
            "study_name": study.name_short,
            "song_url": song.media_url,
            "ratings_saved": rating_count,
            "segments_saved": segment_count
        }

    except Exception as e:
        session.rollback()
        logger.error(f"Error submitting rating: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit rating: {str(e)}"
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