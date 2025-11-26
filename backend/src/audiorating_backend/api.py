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

security = HTTPBasic()



from .logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from .settings import settings
from .models import Participant, Study, Song, Rating, StudyParticipantLink, StudySongLink, RatingSubmission
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


app = FastAPI(title="Timeusediary (TUD) API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Operation"] # custom header to tell frontend on submit if the entry was created or updated.
)

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
            link = session.exec(
                select(StudyParticipantLink).where(
                    StudyParticipantLink.study_id == study.id,
                    StudyParticipantLink.participant_id == participant.id
                )
            ).first()

            if not link:
                raise HTTPException(
                    status_code=403,
                    detail=f"Participant '{participant.id}' is not allowed to submit ratings for study '{study.name_short}'."
                )

        existing_link = session.exec(
            select(StudyParticipantLink).where(
                StudyParticipantLink.study_id == study.id,
                StudyParticipantLink.participant_id == participant.id
            )
        ).first()

        if not existing_link:
            study_link = StudyParticipantLink(study_id=study.id, participant_id=participant.id)
            session.add(study_link)
            logger.info(f"Linked participant {participant.id} to study {study.name_short}")

        # Link song to study if not already linked (with correct index)
        existing_song_link = session.exec(
            select(StudySongLink).where(
                StudySongLink.study_id == study.id,
                StudySongLink.song_id == song.id
            )
        ).first()

        if not existing_song_link:
            song_link = StudySongLink(
                study_id=study.id,
                song_id=song.id,
                song_index=metadata.study.song_index
            )
            session.add(song_link)
            logger.info(f"Linked song {song.media_url} to study {study.name_short} at index {metadata.study.song_index}")

        # Save ratings for each dimension
        rating_count = 0
        for rating_name, segments in ratings_data.items():
            # Check if rating already exists (shouldn't, but just in case)
            existing_rating = session.exec(
                select(Rating).where(
                    Rating.participant_id == participant.id,
                    Rating.study_id == study.id,
                    Rating.song_id == song.id,
                    Rating.rating_name == rating_name
                )
            ).first()

            if existing_rating:
                # Update existing rating
                existing_rating.rating_segments = [seg.dict() for seg in segments]
                existing_rating.timestamp = metadata.submission.timestamp
                logger.info(f"Updated existing rating for {rating_name}")
            else:
                # Create new rating
                rating = Rating(
                    participant_id=participant.id,
                    study_id=study.id,
                    song_id=song.id,
                    rating_name=rating_name,
                    rating_segments=[seg.dict() for seg in segments],
                    timestamp=metadata.submission.timestamp
                )
                session.add(rating)
                rating_count += 1

        # Commit all changes
        session.commit()

        logger.info(f"Successfully saved {rating_count} rating dimensions for participant {participant.id}")

        return {
            "status": "success",
            "message": f"Ratings submitted successfully",
            "participant_id": participant.id,
            "study_name": study.name_short,
            "song_url": song.media_url,
            "ratings_saved": rating_count
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
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin)
):
    """
    Download all ratings for a specific study in JSON or CSV format.
    Requires admin authentication. Try something like:
    curl -u "audiorating_api_admin:audiorating_api_admin_password" "http://localhost:8000/api/admin/datasets/download?study_name=default"
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

        # Get all ratings for this study with related data
        # Using your actual relationship paths from the models
        statement = (
            select(Rating, Participant, Song)
            .join(Participant, Rating.participant_id == Participant.id)
            .join(Song, Rating.song_id == Song.id)
            .where(Rating.study_id == study.id)
        )

        results = session.exec(statement)
        ratings = results.all()

        if not ratings:
            raise HTTPException(
                status_code=404,
                detail=f"No ratings found for study '{study_name}'"
            )

        logger.info(f"Admin '{current_admin}' downloading {len(ratings)} ratings for study '{study_name}'")

        # Transform data for output
        ratings_data = []
        for rating, participant, song in ratings:
            rating_data = {
                "study_name": study.name_short,
                "study_description": study.name or study.description,
                "participant_id": participant.id,
                "song_id": song.id,
                "song_url": song.media_url,
                "song_title": song.display_name,
                "song_artist": "Unknown",  # Your model doesn't have artist field
                "rating_name": rating.rating_name,
                "rating_segments": rating.rating_segments,
                "timestamp": rating.timestamp.isoformat() if rating.timestamp else None,
                "created_at": rating.created_at.isoformat() if rating.created_at else None,
                "rating_id": rating.id
            }
            ratings_data.append(rating_data)

        # Return in requested format
        if format.lower() == "csv":
            return _generate_csv_response(ratings_data, study_name)
        else:
            return {
                "study": {
                    "name_short": study.name_short,
                    "name": study.name,
                    "description": study.description,
                    "allow_unlisted_participants": study.allow_unlisted_participants
                },
                "total_ratings": len(ratings_data),
                "ratings": ratings_data
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading dataset for study '{study_name}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download dataset: {str(e)}"
        )


def _generate_csv_response(ratings_data: List[dict], study_name: str) -> StreamingResponse:
    """Generate CSV response from ratings data."""
    if not ratings_data:
        raise HTTPException(status_code=404, detail="No data to export")

    # Create CSV output
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header - adjusted for your model fields
    headers = [
        "study_name", "study_description", "participant_id", "song_id",
        "song_url", "song_title", "rating_name",
        "timestamp", "created_at", "rating_id", "segments_count"
    ]
    writer.writerow(headers)

    # Write data rows
    for rating in ratings_data:
        segments_count = len(rating["rating_segments"]) if rating["rating_segments"] else 0
        writer.writerow([
            rating["study_name"],
            rating["study_description"],
            rating["participant_id"],
            rating["song_id"],
            rating["song_url"],
            rating["song_title"],
            rating["rating_name"],
            rating["timestamp"],
            rating["created_at"],
            rating["rating_id"],
            segments_count
        ])

    # Prepare response
    output.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{study_name}_ratings_{timestamp}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )