from fastapi import FastAPI, HTTPException, Request, status, Response, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from pydantic import ValidationError, BaseModel
from fastapi.exceptions import RequestValidationError
import logging
import uuid
import sys
from typing import List, Optional, Tuple
from datetime import datetime, timezone
import csv
import io
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from urllib.parse import urlparse, urljoin
from urllib import request as urllib_request
from urllib import error as urllib_error
import secrets
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.sql import func
from pathlib import Path
from typing import Dict
from sqlalchemy import delete
from .utils import utc_now
from .logging_config import setup_logging, get_admin_audit_logger
from .settings import settings
from .models import (
    Participant,
    Study,
    Song,
    Rating,
    StudyParticipantLink,
    StudySongLink,
    StudyRatingDimension,
    RatingSegment,
    RatingSegmentBase,
)
from .database import get_session, create_db_and_tables
from .parsers.studies_config import (
    CfgFileStudyConfig,
    load_studies_config,
    resolve_localized_text,
)
from pydantic import field_validator
import audiorating_backend


# Add with other imports at the top
import argparse
from .database import engine


security = HTTPBasic()

# Initialize templates with absolute path
current_dir = Path(__file__).parent
templates = Jinja2Templates(directory=str(current_dir / "templates"))
static_dir = Path(__file__).parent / "static"


setup_logging()
logger = logging.getLogger(__name__)
admin_audit_logger = get_admin_audit_logger()

# Define command line arguments for out app (not fastapi/uvicorn): you would run it like:
#   uv run python -m audiorating_backend.api --drop-study "study_name_short_to_delete"
parser = argparse.ArgumentParser(description="Audiorating Backend API", add_help=False)
parser.add_argument(
    "--drop-study",
    type=str,
    metavar="STUDY_SHORT_NAME",
    help="rop all data for a specific study and exit. Use with caution, this will delete all ratings, segments, and study-specific links for the specified study, but will keep songs and participants (but not their links to the study). The argument is the 'name_short' of the study you want to delete, e.g., --drop-study 'pilot_study'.",
)
# Create a mutually exclusive group for the frontend check: this allows checking whether the audio files configured actually exist on disk in the frontend dir.
frontend_group = parser.add_argument_group("frontend audio check options")
frontend_group.add_argument(
    "--check-frontend-audio-files",
    type=str,
    metavar="FRONTEND_DIR",
    help="Check audio files in given frontend directory on disk",
)
frontend_group.add_argument(
    "--studies-config-json-file",
    type=str,
    metavar="CONFIG_FILE",
    help="Configuration file containing paths of the audio files for frontend audio check (requires --check-frontend-audio-files)",
)
# Parse only known arguments to avoid interfering with uvicorn
args, unknown = parser.parse_known_args()

if args.studies_config_json_file and not args.check_frontend_audio_files:
    parser.error("--studies-config-json-file requires --check-frontend-audio-files")

# Store the parsed args globally
_cli_args = args


def audit_admin_action(admin_username: str, action_text: str) -> None:
    """Write a high-level admin action entry to the dedicated audit log."""
    admin_audit_logger.info("Admin '%s' %s", admin_username, action_text)


class RatingSubmitRequest(BaseModel):
    """Request body for submitting ratings - Pure API schema, not a database model"""

    timestamp: datetime
    ratings: Dict[str, List[RatingSegmentBase]]

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware and in UTC"""
        if v.tzinfo is None:
            raise ValueError("Timestamp must include timezone information")
        return v.astimezone(timezone.utc)


def drop_study_data(study_name_short: str):
    """Drop all data for a specific study. Deletes ratings, segments, and study-specific links, but keeps songs and participants (but not their links to the study)."""
    with Session(engine) as session:
        # Find the study
        study = session.exec(
            select(Study).where(Study.name_short == study_name_short)
        ).first()

        if not study:
            logger.warning(
                f"Study '{study_name_short}' not found, cannot delete data for this study. Ignoring --drop-study argument."
            )
            return

        logger.info(
            f"Found study '{study_name_short}' (ID: {study.id}). Deleting related data..."
        )

        # Delete rating segments for this study
        segments_deleted = session.exec(
            delete(RatingSegment).where(
                RatingSegment.rating_id.in_(
                    select(Rating.id).where(Rating.study_id == study.id)
                )
            )
        ).rowcount

        # Delete ratings for this study
        ratings_deleted = session.exec(
            delete(Rating).where(Rating.study_id == study.id)
        ).rowcount

        # Delete study-specific links
        song_links_deleted = session.exec(
            delete(StudySongLink).where(StudySongLink.study_id == study.id)
        ).rowcount

        participant_links_deleted = session.exec(
            delete(StudyParticipantLink).where(
                StudyParticipantLink.study_id == study.id
            )
        ).rowcount

        rating_dims_deleted = session.exec(
            delete(StudyRatingDimension).where(
                StudyRatingDimension.study_id == study.id
            )
        ).rowcount

        # Finally, delete the study itself
        session.delete(study)

        # Commit all deletions
        session.commit()

        logger.info(f"Deleted study '{study_name_short}' and related data:")
        logger.info(f"  - Rating segments: {segments_deleted}")
        logger.info(f"  - Ratings: {ratings_deleted}")
        logger.info(f"  - Song links: {song_links_deleted}")
        logger.info(f"  - Participant links: {participant_links_deleted}")
        logger.info(f"  - Rating dimensions: {rating_dims_deleted}")


# get version from __init__.py


ar_version = audiorating_backend.__version__


if _cli_args.drop_study:
    print(f"Dropping data for study: {_cli_args.drop_study}")
    # We need to ensure database engine is initialized
    from .database import engine

    # Call the function immediately
    drop_study_data(_cli_args.drop_study)
    # Exit
    sys.exit(0)

if _cli_args.check_frontend_audio_files:
    from .frontend_audio_check import check_frontend_audio_files

    check_frontend_audio_files(
        _cli_args.check_frontend_audio_files, _cli_args.studies_config_json_file
    )
    sys.exit(0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(
        f"AR Backend version {ar_version} starting with allowed origins: {settings.allowed_origins}"
    )
    if settings.debug:
        print("Debug mode enabled.")

    logger.info("Running FastAPI on_startup tasks...")

    create_db_and_tables()

    yield  # running

    # This line is reached only at shutdown
    logger.info(f"AR version {ar_version} Backend shutting down")


app = FastAPI(
    title="Audiorating (AR) API",
    version=ar_version,
    root_path=settings.rootpath,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Operation"
    ],  # custom header to tell frontend on submit if the entry was created or updated.
)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = static_dir / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    return Response(status_code=204)


def verify_admin(
    request: Request, credentials: HTTPBasicCredentials = Depends(security)
):
    is_valid_admin = any(
        secrets.compare_digest(credentials.username, username)
        and secrets.compare_digest(credentials.password, password)
        for username, password in settings.admin_credentials
    )

    if not is_valid_admin:
        logger.info(
            f"Failed admin authentication attempt for user '{credentials.username}'"
        )
        admin_audit_logger.warning(
            "Failed admin authentication for user '%s' on %s %s",
            credentials.username,
            request.method,
            request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    logger.info(f"Admin '{credentials.username}' authenticated successfully.")
    admin_audit_logger.info(
        "Admin '%s' authenticated on %s %s",
        credentials.username,
        request.method,
        request.url.path,
    )

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
            "message": "Something went wrong on our end",
        },
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
        except Exception as e:
            logger.error(
                f"Error parsing origin '{origin}': assuming not localhost. Exception: {e}"
            )
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
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    error_id = str(uuid.uuid4())

    # Log detailed error information server-side
    error_details = []
    for error in exc.errors():
        error_details.append(
            {
                "field": " -> ".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

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
            "message": "Please check your request data format and values",
        },
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    # Generate a unique error ID for tracking
    error_id = str(uuid.uuid4())

    # Log detailed error information server-side
    error_details = []
    for error in exc.errors():
        error_details.append(
            {
                "field": " -> ".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

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
            "message": "Please check your request data format and values",
        },
    )


@app.get("/api")
def root():
    return {"message": "AR API is running"}


@app.post(
    "/api/participants/{participant_id}/studies/{study_name_short}/songs/{song_index}/ratings"
)
async def submit_rating_restful(
    participant_id: str,  # Now a path parameter
    study_name_short: str,
    song_index: int,
    rating_request: RatingSubmitRequest,
    session: Session = Depends(get_session),
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
                status_code=404, detail=f"Study '{study_name_short}' not found"
            )

        # Validate study dates
        now = utc_now()
        if now < study.data_collection_start:
            raise HTTPException(
                status_code=403,
                detail=f"Study hasn't started yet (starts {study.data_collection_start.isoformat()})",
            )
        if now > study.data_collection_end:
            raise HTTPException(
                status_code=403,
                detail=f"Study has ended (ended {study.data_collection_end.isoformat()})",
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
                    StudyParticipantLink.participant_id == participant.id,
                )
            ).first()
            if not link_exists:
                raise HTTPException(
                    status_code=403, detail="Participant not authorized for this study"
                )

        # Get song by index in study
        song_link = session.exec(
            select(StudySongLink, Song)
            .join(Song, StudySongLink.song_id == Song.id)
            .where(
                StudySongLink.study_id == study.id,
                StudySongLink.song_index == song_index,
            )
        ).first()

        if not song_link:
            raise HTTPException(
                status_code=404,
                detail=f"Song with index {song_index} not found in study '{study_name_short}'",
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
                    Rating.rating_name == rating_name,
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
                    timestamp=rating_request.timestamp,
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
                    segment_order=segment_order,
                )
                session.add(segment)
                segment_count += 1

            logger.info(
                f"{operation.capitalize()} rating '{rating_name}' with {len(segments)} segments"
            )

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
                "timestamp": rating_request.timestamp.isoformat(),
            },
            headers=response_headers,
        )

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Rating submission error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get(
    "/api/participants/{participant_id}/studies/{study_name_short}/songs/{song_index}/ratings"
)
async def get_rating(
    participant_id: str,  # Now a path parameter
    study_name_short: str,
    song_index: int,
    session: Session = Depends(get_session),
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
                status_code=404, detail=f"Study '{study_name_short}' not found"
            )

        # Check whether study is open to all participants or not, and if not, check if participant is authorized
        if not study.allow_unlisted_participants:
            link_exists = session.exec(
                select(StudyParticipantLink).where(
                    StudyParticipantLink.study_id == study.id,
                    StudyParticipantLink.participant_id == participant_id,
                )
            ).first()
            if not link_exists:
                raise HTTPException(
                    status_code=403, detail="Participant not authorized for this study"
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
                "message": "No ratings found for this participant, participant does not exist yet",
                "retrieved_at": utc_now().isoformat(),
                "has_ratings": False,
                "has_participant": False,
            }

        # Get song by index in study
        song_link = session.exec(
            select(StudySongLink, Song)
            .join(Song, StudySongLink.song_id == Song.id)
            .where(
                StudySongLink.study_id == study.id,
                StudySongLink.song_index == song_index,
            )
        ).first()

        if not song_link:
            raise HTTPException(
                status_code=404,
                detail=f"Song with index {song_index} not found in study '{study_name_short}'",
            )

        song = song_link[1]  # Get the Song object

        # Get all ratings with their segments
        ratings = session.exec(
            select(Rating, RatingSegment)
            .join(RatingSegment, Rating.id == RatingSegment.rating_id, isouter=True)
            .where(
                Rating.participant_id == participant.id,
                Rating.study_id == study.id,
                Rating.song_id == song.id,
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
                    "timestamp": rating.timestamp.isoformat()
                    if rating.timestamp
                    else None,
                    "created_at": rating.created_at.isoformat()
                    if rating.created_at
                    else None,
                    "segments": [],
                }

            organized_ratings[rating.rating_name]["segments"].append(
                {
                    "start": segment.start_time,
                    "end": segment.end_time,
                    "value": segment.value,
                    "segment_order": segment.segment_order,
                }
            )

        # Check if we found any ratings
        if not organized_ratings:
            return {
                "study_name_short": study_name_short,
                "song_index": song_index,
                "song_url": song.media_url,
                "participant_id": participant.id,
                "ratings": {},
                "message": "No ratings found",
                "retrieved_at": utc_now().isoformat(),
                "has_ratings": False,
                "has_participant": True,
            }
        else:
            return {
                "study_name_short": study_name_short,
                "song_index": song_index,
                "song_url": song.media_url,
                "participant_id": participant.id,
                "ratings": organized_ratings,
                "retrieved_at": utc_now().isoformat(),
                "message": "",
                "has_ratings": True,
                "has_participant": True,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving ratings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# Add this Pydantic model for the response
class ActiveOpenStudyResponse(BaseModel):
    name_short: str
    name: Optional[str] = None
    description: Optional[str] = None


@app.get("/api/active_open_study_names", response_model=List[ActiveOpenStudyResponse])
async def get_active_open_study_names(session: Session = Depends(get_session)):
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
            select(Study)
            .where(
                Study.allow_unlisted_participants,
                Study.data_collection_start <= now,
                Study.data_collection_end >= now,
            )
            .order_by(Study.name_short)  # Optional: order alphabetically
        ).all()

        # Create response objects with the required fields
        study_responses = [
            ActiveOpenStudyResponse(
                name_short=study.name_short,
                name=study.name,
                description=study.description,
            )
            for study in studies
        ]

        logger.info(f"Found {len(study_responses)} active open studies")

        return study_responses

    except Exception as e:
        logger.error(f"Error fetching active open study names: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching study information",
        )


def _generate_csv_response(
    segments_data: List[dict], study_name: str, with_ids: bool
) -> StreamingResponse:
    """Generate CSV response with all segment data."""
    if not segments_data:
        raise HTTPException(status_code=404, detail="No data to export")

    # Create CSV output
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header - now includes all segment details
    headers = [
        "study_name",
        "study_description",
        "participant_id",
        "song_url",
        "song_title",
        "rating_name",
        "start_time",
        "end_time",
        "value",
        "segment_order",
        "rating_created_at",
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
            segment["rating_created_at"],
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
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/admin/export/studies-runtime-config")
async def export_runtime_studies_config(
    study_name: Optional[str] = None,
    current_admin: str = Depends(verify_admin),
    session: Session = Depends(get_session),
):
    """Export runtime study config plus logged ratings as JSON.

    Response format:
    - `studies_config`: studies-config-compatible structure with runtime participant IDs
    - `logged_ratings`: ratings grouped by study name short, then participant, then song
    """
    cfg = load_studies_config(settings.studies_config_path)
    cfg_studies_by_name = {study_cfg.name_short: study_cfg for study_cfg in cfg.studies}

    study_query = select(Study).order_by(Study.name_short)
    if study_name:
        study_query = study_query.where(Study.name_short == study_name)

    studies = session.exec(study_query).all()
    if study_name and not studies:
        raise HTTPException(status_code=404, detail=f"Study '{study_name}' not found")

    exported_studies = []
    logged_ratings_by_study = {}

    for study in studies:
        cfg_study = cfg_studies_by_name.get(study.name_short)
        exported_studies.append(
            _build_runtime_study_config_export(study, session, cfg_study)
        )
        logged_ratings_by_study[study.name_short] = (
            _build_logged_ratings_export_for_study(study, session)
        )

    logger.info(
        "Admin '%s' exported runtime studies config%s",
        current_admin,
        f" for study '{study_name}'" if study_name else " for all studies",
    )
    audit_admin_action(
        current_admin,
        f"exported runtime studies config{f' for study {study_name}' if study_name else ' for all studies'}",
    )

    response_payload = {
        "studies_config": {
            "studies": exported_studies,
        },
        "logged_ratings": logged_ratings_by_study,
        "audiorating_backend_version": ar_version,
    }

    export_date = utc_now().strftime("%Y-%m-%d")
    filename = (
        f"studies_runtime_config_{study_name}_{export_date}.json"
        if study_name
        else f"studies_runtime_config_{export_date}.json"
    )

    return JSONResponse(
        content=jsonable_encoder(response_payload),
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/admin/datasets/download", name="admin_download")
async def admin_download(
    study_name: str = Query(
        ..., description="Name of the study to download ratings for"
    ),
    format: str = Query("json", description="Output format: json or csv"),
    with_ids: bool = Query(False, description="Include database IDs in the output"),
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin),
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
                status_code=404, detail=f"Study '{study_name}' not found"
            )

        # Get all ratings for this study with related data including segments
        statement = (
            select(Rating, Participant, Song, RatingSegment)
            .join(Participant, Rating.participant_id == Participant.id)
            .join(Song, Rating.song_id == Song.id)
            .join(RatingSegment, RatingSegment.rating_id == Rating.id)
            .where(Rating.study_id == study.id)
            .order_by(
                Rating.participant_id,
                Rating.song_id,
                Rating.rating_name,
                RatingSegment.segment_order,
            )
        )

        results = session.exec(statement)
        rating_data = results.all()

        if not rating_data:
            raise HTTPException(
                status_code=404, detail=f"No ratings found for study '{study_name}'"
            )

        logger.info(
            f"Admin '{current_admin}' downloading {len(rating_data)} rating segments for study '{study_name}'"
        )
        audit_admin_action(
            current_admin,
            f"downloaded {len(rating_data)} rating segments for study {study_name} in format {format.lower()}",
        )

        # Transform data for output - now each row is a segment
        segments_data = []
        for rating, participant, song, segment in rating_data:
            segment_data = {
                "study_name": study.name_short,
                "study_description": study.name or study.description,
                "participant_id": participant.id,  # This is always included, even if with_ids is False, as it is required context.
                "song_url": song.media_url,
                "song_title": song.display_name,
                "rating_name": rating.rating_name,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "value": segment.value,
                "segment_order": segment.segment_order,
                "rating_created_at": rating.created_at.isoformat()
                if rating.created_at
                else None,
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
                    "allow_unlisted_participants": study.allow_unlisted_participants,
                },
                "total_segments": len(segments_data),
                "segments": segments_data,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading dataset for study '{study_name}': {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to download dataset: {str(e)}"
        )


@app.get("/admin/api/stats", name="admin_api_stats")
async def admin_api_stats(
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin),
):
    """
    API endpoint for admin dashboard stats.
    """
    if study_id:
        logger.debug(
            f"Admin '{current_admin}' requested API stats for study_id='{study_id}'"
        )
    else:
        logger.debug(f"Admin '{current_admin}' requested API stats for all studies")

    try:
        audit_admin_action(
            current_admin,
            f"requested admin stats{f' for study_id {study_id}' if study_id else ' for all studies'}",
        )
        # Similar logic as above but returns JSON
        if study_id:
            studies = session.exec(select(Study).where(Study.id == study_id)).all()
        else:
            studies = session.exec(select(Study).order_by(Study.created_at)).all()

        study_stats = []

        for study in studies:
            # Simplified stats for API
            total_ratings = (
                session.exec(
                    select(func.count(Rating.id)).where(Rating.study_id == study.id)
                ).first()
                or 0
            )

            unique_participants = (
                session.exec(
                    select(func.count(func.distinct(Rating.participant_id))).where(
                        Rating.study_id == study.id
                    )
                ).first()
                or 0
            )

            total_segments = (
                session.exec(
                    select(func.count(RatingSegment.id))
                    .join(Rating, Rating.id == RatingSegment.rating_id)
                    .where(Rating.study_id == study.id)
                ).first()
                or 0
            )

            study_rating_dimensions = session.exec(
                select(StudyRatingDimension).where(
                    StudyRatingDimension.study_id == study.id
                )
            ).all()

            study_stats.append(
                {
                    "id": study.id,
                    "name_short": study.name_short,
                    "name": study.name,
                    "rating_dimensions": [
                        {
                            "dimension_title": dim.dimension_title,
                            "num_values": dim.num_values,
                            "minimal_value": dim.minimal_value,
                            "default_value": dim.default_value,
                            "description": dim.description,
                        }
                        for dim in study_rating_dimensions
                    ],
                    "total_ratings": total_ratings,
                    "unique_participants": unique_participants,
                    "total_segments": total_segments,
                    "data_collection_start": study.data_collection_start,
                    "data_collection_end": study.data_collection_end,
                    "is_currently_active": study.data_collection_start
                    <= utc_now()
                    <= study.data_collection_end,
                    "last_activity": session.exec(
                        select(func.max(Rating.timestamp)).where(
                            Rating.study_id == study.id
                        )
                    ).first(),
                }
            )

        return {
            "studies": study_stats,
            "total_studies": len(study_stats),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error in admin API stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@app.get("/admin", name="admin_dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin),
):
    """
    Main admin dashboard showing all studies and participation statistics.
    Access via: /admin with HTTP Basic Auth
    """
    base_url = str(request.base_url).rstrip("/")  # This gives "http://localhost:8000"
    root_path = request.scope.get(
        "root_path", ""
    )  # This gives "" locally, "/ar_backend" in prod

    # Combine them properly
    if root_path and not base_url.endswith(root_path):
        api_base = f"{base_url}{root_path}"
    else:
        api_base = base_url

    try:
        audit_admin_action(current_admin, "opened admin dashboard")
        studies_config = load_studies_config(settings.studies_config_path)
        studies_config_by_short = {
            study_cfg.name_short: study_cfg for study_cfg in studies_config.studies
        }

        def to_i18n_map(value: object, default_language: str) -> Dict[str, str]:
            if isinstance(value, dict):
                return {
                    str(language): str(text)
                    for language, text in value.items()
                    if text is not None and str(text) != ""
                }
            if value is None:
                return {}
            text = str(value)
            if text == "":
                return {}
            return {default_language: text}

        # Get all studies with basic info
        studies = session.exec(select(Study).order_by(Study.created_at)).all()

        study_stats = []

        for study in studies:
            study_cfg = studies_config_by_short.get(study.name_short)
            default_language = study_cfg.default_language if study_cfg else "en"

            # Get total songs in this study
            song_links = session.exec(
                select(StudySongLink).where(StudySongLink.study_id == study.id)
            ).all()
            total_songs = len(song_links)

            songs_for_study = session.exec(
                select(StudySongLink, Song)
                .join(Song, StudySongLink.song_id == Song.id)
                .where(StudySongLink.study_id == study.id)
                .order_by(StudySongLink.song_index, Song.id)
            ).all()

            songs_cfg_by_media_url = (
                {song_cfg.media_url: song_cfg for song_cfg in study_cfg.songs_to_rate}
                if study_cfg
                else {}
            )

            songs_report = []
            for song_link, song in songs_for_study:
                song_cfg = songs_cfg_by_media_url.get(song.media_url)

                display_name_source = (
                    song_cfg.display_name if song_cfg else song.display_name
                )
                description_source = (
                    song_cfg.description if song_cfg else song.description
                )

                songs_report.append(
                    {
                        "song_index": song_link.song_index,
                        "media_url": song.media_url,
                        "display_name": resolve_localized_text(
                            display_name_source, default_language
                        )
                        if isinstance(display_name_source, dict)
                        else (display_name_source or ""),
                        "description": resolve_localized_text(
                            description_source, default_language
                        )
                        if isinstance(description_source, dict)
                        else (description_source or ""),
                        "display_name_i18n": to_i18n_map(
                            display_name_source, default_language
                        ),
                        "description_i18n": to_i18n_map(
                            description_source, default_language
                        ),
                    }
                )

            # Get all participants linked to this study (pre-listed)
            participant_links = session.exec(
                select(StudyParticipantLink).where(
                    StudyParticipantLink.study_id == study.id
                )
            ).all()
            pre_listed_participants = [
                link.participant_id for link in participant_links
            ]

            participant_ids_with_ratings = session.exec(
                select(Participant.id)
                .join(Rating, Rating.participant_id == Participant.id)
                .where(Rating.study_id == study.id)
                .distinct()
            ).all()

            # Get all ratings for this study to analyze participation
            ratings = session.exec(
                select(
                    Rating,
                    Participant,
                    Song,
                    func.count(RatingSegment.id).label("segment_count"),
                )
                .join(Participant, Rating.participant_id == Participant.id)
                .join(Song, Rating.song_id == Song.id)
                .join(RatingSegment, RatingSegment.rating_id == Rating.id, isouter=True)
                .where(Rating.study_id == study.id)
                .group_by(Rating.id, Participant.id, Song.id)
                .order_by(Participant.id, Song.id, Rating.rating_name)
            ).all()

            rating_dimensions = session.exec(
                select(StudyRatingDimension).where(
                    StudyRatingDimension.study_id == study.id
                )
            ).all()

            dimensions_cfg_by_title = (
                {
                    dimension_cfg.dimension_title: dimension_cfg
                    for dimension_cfg in study_cfg.rating_dimensions
                }
                if study_cfg
                else {}
            )

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
                        "last_activity": rating.timestamp
                        if rating.timestamp
                        else rating.created_at,
                    }

                song_display_name = (
                    resolve_localized_text(song.display_name)
                    if isinstance(song.display_name, dict)
                    else (song.display_name or "")
                )
                participants_data[participant.id]["songs_rated"].add(song_display_name)
                participants_data[participant.id]["ratings"].append(
                    {
                        "song": song_display_name,
                        "song_url": song.media_url,
                        "rating_name": rating.rating_name,
                        "segment_count": segment_count,
                        "timestamp": rating.timestamp,
                        "created_at": rating.created_at,
                    }
                )
                participants_data[participant.id]["total_segments"] += segment_count

                # Update last activity if this rating is newer
                if (
                    rating.timestamp
                    and rating.timestamp
                    > participants_data[participant.id]["last_activity"]
                ):
                    participants_data[participant.id]["last_activity"] = (
                        rating.timestamp
                    )

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

            rating_dimensions_report = [
                {
                    "dimension_title": dim.dimension_title,
                    "num_values": dim.num_values,
                    "minimal_value": (
                        dim.minimal_value if dim.minimal_value is not None else 1
                    ),
                    "default_value": (
                        dim.default_value
                        if dim.default_value is not None
                        else (
                            (dim.minimal_value if dim.minimal_value is not None else 1)
                            + dim.num_values
                            - 1
                        )
                        // 2
                    ),
                    "max_value": (
                        dim.minimal_value if dim.minimal_value is not None else 1
                    )
                    + dim.num_values
                    - 1,
                    "description": resolve_localized_text(
                        dim.description, default_language
                    )
                    if isinstance(dim.description, dict)
                    else (dim.description or ""),
                    "description_i18n": to_i18n_map(
                        dimensions_cfg_by_title.get(dim.dimension_title).description
                        if dimensions_cfg_by_title.get(dim.dimension_title)
                        else dim.description,
                        default_language,
                    ),
                }
                for dim in rating_dimensions
            ]

            # Calculate coverage percentage safely
            total_participants = len(
                set(pre_listed_participants + participant_ids_with_ratings)
            )
            if total_songs > 0 and total_participants > 0:
                # Simplified: percentage of total possible ratings (participants × songs) that have been completed
                coverage_percentage = 0  # Default
            else:
                coverage_percentage = 0

            study_stats.append(
                {
                    "id": study.id,
                    "name_short": study.name_short,
                    "name": study.name,
                    "description": study.description,
                    "rating_dimensions": rating_dimensions_report,
                    "songs": songs_report,
                    "total_songs": total_songs,
                    "default_language": default_language,
                    "allow_unlisted_participants": study.allow_unlisted_participants,
                    "pre_listed_participants": pre_listed_participants,
                    "pre_listed_count": len(pre_listed_participants),
                    "active_participants": active_participants,
                    "active_participants_count": len(active_participants),
                    "total_participants": total_participants,
                    "coverage_percentage": coverage_percentage,
                    "data_collection_start": study.data_collection_start,
                    "data_collection_end": study.data_collection_end,
                    "is_currently_active": study.data_collection_start
                    <= utc_now()
                    <= study.data_collection_end,
                }
            )

        # Render template manually to avoid Starlette TemplateResponse caching issues with wheel-installed packages
        # See: https://github.com/encode/starlette/issues/2531
        # When templates are installed from a wheel, Starlette's TemplateResponse cache fails with "unhashable type: dict"
        # Using direct Jinja2 rendering bypasses this bug entirely
        context_dict = {
            "request": request,
            "studies": study_stats,
            "admin_user": current_admin,
            "current_time": datetime.now(),
            "api_base": api_base,
        }
        template = templates.get_template("admin_dashboard.html")
        html_content = template.render(context_dict)
        return HTMLResponse(content=html_content)

    except Exception as e:
        import traceback

        logger.error(f"Error loading admin dashboard: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail=f"Failed to load admin dashboard: {str(e)}"
        )


@app.get("/api/participants/{participant_id}/studies/{study_name}/config")
async def get_study_config(
    participant_id: str, study_name: str, session: Session = Depends(get_session)
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
            logger.warning(
                f"Study '{study_name}' not found when participant '{participant_id}' requested config"
            )
            raise HTTPException(
                status_code=404, detail=f"Study '{study_name}' not found"
            )

        # Check if study is active (within data collection period)
        now = utc_now()
        if now < study.data_collection_start:
            logger.warning(
                f"Study '{study_name}' has not started yet, starts at {study.data_collection_start} but it is now {now} (requested by participant '{participant_id}')"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Study '{study_name}' has not started yet. "
                f"Data collection starts on {study.data_collection_start.isoformat()}",
            )

        if now > study.data_collection_end:
            logger.warning(
                f"Study '{study_name}' has ended on {study.data_collection_end} but now it is {now} (requested by participant '{participant_id}')"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Study '{study_name}' has ended. "
                f"Data collection ended on {study.data_collection_end.isoformat()}",
            )

        # Check participant authorization if study doesn't allow unlisted participants
        if not study.allow_unlisted_participants:
            # Check if participant is pre-listed for this study
            participant_link = session.exec(
                select(StudyParticipantLink).where(
                    StudyParticipantLink.study_id == study.id,
                    StudyParticipantLink.participant_id == participant_id,
                )
            ).first()

            if not participant_link:
                logger.warning(
                    f"Unauthorized access attempt to study '{study_name}' by participant '{participant_id}'"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Participant '{participant_id}' is not authorized to access study '{study_name}'",
                )

        # Load config from studies config file to preserve multilingual text objects
        cfg = load_studies_config(settings.studies_config_path)
        cfg_study = next(
            (s for s in cfg.studies if s.name_short == study.name_short), None
        )

        if cfg_study is None:
            logger.warning(
                f"Study '{study.name_short}' exists in database but was not found in config file '{settings.studies_config_path}'"
            )
            raise HTTPException(
                status_code=500,
                detail="Study configuration inconsistency: study missing in config file",
            )

        # Build response from config file (multilingual), but keep DB-controlled access/date fields
        study_config = {
            "name": cfg_study.name,
            "name_short": cfg_study.name_short,
            "default_language": cfg_study.default_language,
            "description": cfg_study.description,
            "custom_text_instructions": cfg_study.custom_text_instructions,
            "custom_text_thank_you": cfg_study.custom_text_thank_you,
            "songs_to_rate": [song.model_dump() for song in cfg_study.songs_to_rate],
            "rating_dimensions": [
                dim.model_dump() for dim in cfg_study.rating_dimensions
            ],
            "allow_unlisted_participants": study.allow_unlisted_participants,
            "data_collection_start": study.data_collection_start.isoformat(),
            "data_collection_end": study.data_collection_end.isoformat(),
        }

        logger.info(
            f"Returning config for study '{study_name}' to participant '{participant_id}' "
            f"with {len(cfg_study.songs_to_rate)} songs and {len(cfg_study.rating_dimensions)} dimensions"
        )

        return study_config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error loading study config for '{study_name}' (participant '{participant_id}'): {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to load study configuration"
        )


logger = logging.getLogger(__name__)


def _build_runtime_study_config_export(
    study: Study, session: Session, cfg_study=None
) -> dict:
    participant_links = session.exec(
        select(StudyParticipantLink)
        .where(StudyParticipantLink.study_id == study.id)
        .order_by(StudyParticipantLink.participant_id)
    ).all()
    participant_ids = [link.participant_id for link in participant_links]

    if cfg_study is not None:
        return {
            "name": cfg_study.name,
            "name_short": cfg_study.name_short,
            "default_language": cfg_study.default_language,
            "description": cfg_study.description,
            "custom_text_instructions": cfg_study.custom_text_instructions,
            "custom_text_thank_you": cfg_study.custom_text_thank_you,
            "songs_to_rate": [song.model_dump() for song in cfg_study.songs_to_rate],
            "rating_dimensions": [
                dim.model_dump() for dim in cfg_study.rating_dimensions
            ],
            "study_participant_ids": participant_ids,
            "allow_unlisted_participants": study.allow_unlisted_participants,
            "data_collection_start": study.data_collection_start,
            "data_collection_end": study.data_collection_end,
        }

    song_links = session.exec(
        select(StudySongLink, Song)
        .join(Song, StudySongLink.song_id == Song.id)
        .where(StudySongLink.study_id == study.id)
        .order_by(StudySongLink.song_index)
    ).all()
    rating_dimensions = session.exec(
        select(StudyRatingDimension)
        .where(StudyRatingDimension.study_id == study.id)
        .order_by(StudyRatingDimension.dimension_order)
    ).all()

    return {
        "name": study.name,
        "name_short": study.name_short,
        "default_language": "en",
        "description": study.description,
        "custom_text_instructions": None,
        "custom_text_thank_you": None,
        "songs_to_rate": [
            {
                "media_url": song.media_url,
                "display_name": song.display_name,
                "description": song.description,
            }
            for _, song in song_links
        ],
        "rating_dimensions": [
            {
                "dimension_title": dim.dimension_title,
                "display_name": dim.dimension_title,
                "num_values": dim.num_values,
                "minimal_value": dim.minimal_value,
                "default_value": dim.default_value,
                "description": dim.description,
            }
            for dim in rating_dimensions
        ],
        "study_participant_ids": participant_ids,
        "allow_unlisted_participants": study.allow_unlisted_participants,
        "data_collection_start": study.data_collection_start,
        "data_collection_end": study.data_collection_end,
    }


def _build_logged_ratings_export_for_study(study: Study, session: Session) -> dict:
    rating_rows = session.exec(
        select(Rating, Song, RatingSegment)
        .join(Song, Rating.song_id == Song.id)
        .join(RatingSegment, RatingSegment.rating_id == Rating.id, isouter=True)
        .where(Rating.study_id == study.id)
        .order_by(
            Rating.participant_id,
            Song.media_url,
            Rating.rating_name,
            RatingSegment.segment_order,
        )
    ).all()

    song_index_by_id = {
        song_id: song_index
        for song_id, song_index in session.exec(
            select(StudySongLink.song_id, StudySongLink.song_index).where(
                StudySongLink.study_id == study.id
            )
        ).all()
    }

    logged_ratings: Dict[str, Dict[str, dict]] = {}

    for rating, song, segment in rating_rows:
        participant_entry = logged_ratings.setdefault(rating.participant_id, {})
        song_key = str(song_index_by_id.get(song.id, -1))
        song_entry = participant_entry.setdefault(
            song_key,
            {
                "song_index": song_index_by_id.get(song.id),
                "song_url": song.media_url,
                "song_display_name": song.display_name,
                "ratings": {},
            },
        )

        rating_entry = song_entry["ratings"].setdefault(
            rating.rating_name,
            {
                "rating_id": rating.id,
                "timestamp": rating.timestamp,
                "created_at": rating.created_at,
                "segments": [],
            },
        )

        if segment is not None:
            rating_entry["segments"].append(
                {
                    "start": segment.start_time,
                    "end": segment.end_time,
                    "value": segment.value,
                    "segment_order": segment.segment_order,
                    "segment_id": segment.id,
                }
            )

    return logged_ratings


# Pydantic model for the request
class AssignParticipantsRequest(BaseModel):
    participant_ids: List[str]
    must_be_new: bool = False


class CreateStudyResponse(BaseModel):
    id: str
    name_short: str
    name: str
    allow_unlisted_participants: bool
    data_collection_start: datetime
    data_collection_end: datetime
    songs_count: int
    rating_dimensions_count: int
    participant_links_count: int


class UpdateStudyCollectionWindowRequest(BaseModel):
    data_collection_start: Optional[datetime] = None
    data_collection_end: Optional[datetime] = None


class UpdateStudyTypeRequest(BaseModel):
    allow_unlisted_participants: bool


class UpdateStudyTypeResponse(BaseModel):
    study_name_short: str
    allow_unlisted_participants: bool
    study_type: str
    message: str


@app.post(
    "/api/admin/studies",
    name="api_create_study",
    response_model=CreateStudyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_study(
    study_cfg: CfgFileStudyConfig,
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin),
):
    """Create a new study and all related links from a validated study config payload."""
    try:
        existing_study = session.exec(
            select(Study).where(Study.name_short == study_cfg.name_short)
        ).first()
        if existing_study:
            raise HTTPException(
                status_code=409,
                detail=f"Study '{study_cfg.name_short}' already exists",
            )

        new_study = Study(
            name=study_cfg.name,
            name_short=study_cfg.name_short,
            description=resolve_localized_text(
                study_cfg.description, study_cfg.default_language
            ),
            allow_unlisted_participants=study_cfg.allow_unlisted_participants,
            data_collection_start=study_cfg.data_collection_start,
            data_collection_end=study_cfg.data_collection_end,
        )
        session.add(new_study)
        session.flush()

        participant_links_count = 0
        for participant_id in study_cfg.study_participant_ids:
            participant = session.exec(
                select(Participant).where(Participant.id == participant_id)
            ).first()
            if not participant:
                participant = Participant(id=participant_id)
                session.add(participant)
                session.flush()

            existing_link = session.exec(
                select(StudyParticipantLink).where(
                    StudyParticipantLink.study_id == new_study.id,
                    StudyParticipantLink.participant_id == participant_id,
                )
            ).first()
            if not existing_link:
                session.add(
                    StudyParticipantLink(
                        study_id=new_study.id,
                        participant_id=participant_id,
                    )
                )
                participant_links_count += 1

        for song_index, song_cfg in enumerate(study_cfg.songs_to_rate):
            song = session.exec(
                select(Song).where(Song.media_url == song_cfg.media_url)
            ).first()
            if not song:
                song = Song(
                    display_name=resolve_localized_text(
                        song_cfg.display_name, study_cfg.default_language
                    ),
                    media_url=song_cfg.media_url,
                    description=resolve_localized_text(
                        song_cfg.description, study_cfg.default_language
                    ),
                )
                session.add(song)
                session.flush()

            session.add(
                StudySongLink(
                    study_id=new_study.id,
                    song_id=song.id,
                    song_index=song_index,
                )
            )

        for dim_index, dimension_cfg in enumerate(study_cfg.rating_dimensions):
            session.add(
                StudyRatingDimension(
                    study_id=new_study.id,
                    dimension_title=dimension_cfg.dimension_title,
                    num_values=dimension_cfg.num_values,
                    minimal_value=dimension_cfg.minimal_value,
                    default_value=dimension_cfg.default_value,
                    dimension_order=dim_index,
                    description=resolve_localized_text(
                        dimension_cfg.description, study_cfg.default_language
                    ),
                )
            )

        session.commit()
        session.refresh(new_study)

        audit_admin_action(
            current_admin,
            (
                f"created study {new_study.name_short} with {len(study_cfg.songs_to_rate)} songs, "
                f"{len(study_cfg.rating_dimensions)} rating dimensions, and "
                f"{participant_links_count} participant links"
            ),
        )

        return CreateStudyResponse(
            id=new_study.id,
            name_short=new_study.name_short,
            name=new_study.name,
            allow_unlisted_participants=new_study.allow_unlisted_participants,
            data_collection_start=new_study.data_collection_start,
            data_collection_end=new_study.data_collection_end,
            songs_count=len(study_cfg.songs_to_rate),
            rating_dimensions_count=len(study_cfg.rating_dimensions),
            participant_links_count=participant_links_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(
            f"Failed to create study '{study_cfg.name_short}': {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to create study")


@app.patch(
    "/api/admin/studies/{study_name_short}/collection-window",
    name="api_update_study_collection_window",
)
async def update_study_collection_window(
    study_name_short: str,
    payload: UpdateStudyCollectionWindowRequest,
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin),
):
    """Update data collection start/end of an existing study."""
    study = session.exec(
        select(Study).where(Study.name_short == study_name_short)
    ).first()
    if not study:
        raise HTTPException(
            status_code=404, detail=f"Study '{study_name_short}' not found"
        )

    if payload.data_collection_start is None and payload.data_collection_end is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of data_collection_start or data_collection_end must be provided",
        )

    previous_start = study.data_collection_start
    previous_end = study.data_collection_end

    new_start = payload.data_collection_start or previous_start
    new_end = payload.data_collection_end or previous_end

    if new_start >= new_end:
        raise HTTPException(
            status_code=400,
            detail="data_collection_start must be earlier than data_collection_end",
        )

    study.data_collection_start = new_start
    study.data_collection_end = new_end
    session.add(study)
    session.commit()
    session.refresh(study)

    audit_admin_action(
        current_admin,
        (
            f"updated collection window for study {study_name_short} "
            f"from {previous_start.isoformat()}..{previous_end.isoformat()} "
            f"to {study.data_collection_start.isoformat()}..{study.data_collection_end.isoformat()}"
        ),
    )

    return {
        "study_name_short": study_name_short,
        "previous": {
            "data_collection_start": previous_start,
            "data_collection_end": previous_end,
        },
        "updated": {
            "data_collection_start": study.data_collection_start,
            "data_collection_end": study.data_collection_end,
        },
        "is_currently_collecting": study.data_collection_start
        <= utc_now()
        <= study.data_collection_end,
    }


def _is_song_url_available(
    url: str, timeout_seconds: float = 5.0
) -> Tuple[bool, Optional[int], Optional[str]]:
    """Best-effort URL availability check for song assets."""
    try:
        head_request = urllib_request.Request(url, method="HEAD")
        with urllib_request.urlopen(head_request, timeout=timeout_seconds) as response:
            status_code = getattr(response, "status", None)
            return (
                (status_code is not None and 200 <= status_code < 400),
                status_code,
                None,
            )
    except urllib_error.HTTPError as exc:
        if exc.code == 405:
            # Some servers do not allow HEAD for static files; retry with GET.
            try:
                get_request = urllib_request.Request(url, method="GET")
                with urllib_request.urlopen(
                    get_request, timeout=timeout_seconds
                ) as response:
                    status_code = getattr(response, "status", None)
                    return (
                        (status_code is not None and 200 <= status_code < 400),
                        status_code,
                        None,
                    )
            except urllib_error.HTTPError as get_exc:
                return False, get_exc.code, str(get_exc)
            except Exception as get_exc:
                return False, None, str(get_exc)
        return False, exc.code, str(exc)
    except Exception as exc:
        return False, None, str(exc)


@app.post(
    "/api/admin/studies/{study_name_short}/songs/check",
    name="api_check_study_song_availability",
)
async def check_study_song_availability(
    study_name_short: str,
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin),
):
    """Check whether each configured song URL is reachable for a given study."""
    study = session.exec(
        select(Study).where(Study.name_short == study_name_short)
    ).first()
    if not study:
        raise HTTPException(
            status_code=404, detail=f"Study '{study_name_short}' not found"
        )

    songs_for_study = session.exec(
        select(StudySongLink, Song)
        .join(Song, StudySongLink.song_id == Song.id)
        .where(StudySongLink.study_id == study.id)
        .order_by(StudySongLink.song_index, Song.id)
    ).all()

    results = []
    available_count = 0
    missing_count = 0

    for song_link, song in songs_for_study:
        media_url = song.media_url
        check_url = urljoin(settings.frontend_url, media_url)
        available, status_code, error_message = _is_song_url_available(check_url)

        if available:
            available_count += 1
        else:
            missing_count += 1

        results.append(
            {
                "song_index": song_link.song_index,
                "media_url": media_url,
                "check_url": check_url,
                "available": available,
                "status_code": status_code,
                "error": error_message,
            }
        )

    audit_admin_action(
        current_admin,
        f"checked song availability for study {study_name_short}: {available_count} available, {missing_count} missing",
    )

    return {
        "study_name_short": study_name_short,
        "frontend_url": settings.frontend_url,
        "checked": len(results),
        "available": available_count,
        "missing": missing_count,
        "results": results,
    }


# Pydantic model for the response
class ParticipantAssignmentResult(BaseModel):
    participant_id: str
    status: str  # "created_and_assigned" or "already_existed_and_assigned"
    message: str


class StudyAssignmentInfo(BaseModel):
    name_short: str
    allow_unlisted_participants: bool
    total_participants: int  # total participants after assignment


class AssignParticipantsResponse(BaseModel):
    study_info: StudyAssignmentInfo
    results: List[ParticipantAssignmentResult]
    summary: Dict[str, int]


@app.patch(
    "/api/admin/studies/{study_name_short}/study-type",
    name="api_update_study_type",
    response_model=UpdateStudyTypeResponse,
)
async def update_study_type(
    study_name_short: str,
    request: UpdateStudyTypeRequest,
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin),
):
    """Update whether a study is open (allows unlisted participants) or closed."""
    try:
        study = session.exec(
            select(Study).where(Study.name_short == study_name_short)
        ).first()

        if not study:
            raise HTTPException(
                status_code=404,
                detail=f"Study '{study_name_short}' not found",
            )

        was_open = study.allow_unlisted_participants
        target_open = request.allow_unlisted_participants

        if was_open != target_open:
            study.allow_unlisted_participants = target_open
            session.add(study)
            session.commit()
            session.refresh(study)

        logger.info(
            f"Admin updated study type for '{study_name_short}' "
            f"from {'OPEN' if was_open else 'CLOSED'} to {'OPEN' if study.allow_unlisted_participants else 'CLOSED'}"
        )
        audit_admin_action(
            current_admin,
            (
                f"updated study type for {study_name_short} "
                f"from {'OPEN' if was_open else 'CLOSED'} to "
                f"{'OPEN' if study.allow_unlisted_participants else 'CLOSED'}"
            ),
        )

        return UpdateStudyTypeResponse(
            study_name_short=study.name_short,
            allow_unlisted_participants=study.allow_unlisted_participants,
            study_type="open" if study.allow_unlisted_participants else "closed",
            message=(
                f"Study '{study.name_short}' is now "
                f"{'open' if study.allow_unlisted_participants else 'closed'}"
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(
            f"Error updating study type for '{study_name_short}': {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update study type: {str(e)}",
        )


@app.post(
    "/api/admin/studies/{study_name_short}/assign-participants",
    name="api_assign_participants_to_study",
)
async def assign_participants_to_study(
    study_name_short: str,
    request: AssignParticipantsRequest,
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin),
):
    """
    Assign participants to a study.

    - If must_be_new is True: Check if any participants already exist in the system.
      If they do, deny the entire operation.
    - If must_be_new is False (default): Check each participant:
        * If they don't exist, create them and assign to study
        * If they exist, just assign them to study (if not already assigned)
    - Works for both open and closed studies (study.allow_unlisted_participants)
    - Returns detailed information about each participant's status
    """
    try:
        # Get the study
        study = session.exec(
            select(Study).where(Study.name_short == study_name_short)
        ).first()

        if not study:
            raise HTTPException(
                status_code=404, detail=f"Study '{study_name_short}' not found"
            )

        # Validate participant_ids list
        if not request.participant_ids:
            raise HTTPException(status_code=400, detail="No participant IDs provided")

        # Remove duplicates while preserving order
        unique_ids = []
        seen = set()
        for pid in request.participant_ids:
            if pid not in seen:
                seen.add(pid)
                unique_ids.append(pid)

        if len(unique_ids) != len(request.participant_ids):
            logger.info(
                f"Removed {len(request.participant_ids) - len(unique_ids)} duplicate participant IDs"
            )

        participant_ids = unique_ids

        # If must_be_new is True, check if any participants already exist
        if request.must_be_new:
            existing_participants = session.exec(
                select(Participant).where(Participant.id.in_(participant_ids))
            ).all()

            if existing_participants:
                existing_ids = [p.id for p in existing_participants]
                raise HTTPException(
                    status_code=409,  # Conflict
                    detail={
                        "message": "Some participants already exist in the system",
                        "existing_participants": existing_ids,
                        "total_requested": len(participant_ids),
                        "existing_count": len(existing_ids),
                    },
                )

        # Process each participant
        results = []
        created_count = 0
        assigned_count = 0
        already_assigned_count = 0

        for participant_id in participant_ids:
            # Check if participant exists
            participant = session.exec(
                select(Participant).where(Participant.id == participant_id)
            ).first()

            # Check if already linked to study
            existing_link = session.exec(
                select(StudyParticipantLink).where(
                    StudyParticipantLink.study_id == study.id,
                    StudyParticipantLink.participant_id == participant_id,
                )
            ).first()

            if existing_link:
                # Already assigned to study
                results.append(
                    ParticipantAssignmentResult(
                        participant_id=participant_id,
                        status="already_assigned",
                        message="Participant was already assigned to this study",
                    )
                )
                already_assigned_count += 1
                continue

            if not participant:
                # Create new participant
                participant = Participant(id=participant_id)
                session.add(participant)
                # Flush to ensure participant is created before creating link
                session.flush()
                created_count += 1
                status = "created_and_assigned"
                message = "Participant was created and assigned to study"
            else:
                # Participant exists but not linked
                assigned_count += 1
                status = "already_existed_and_assigned"
                message = "Participant already existed and was assigned to study"

            # Create the study-participant link
            participant_link = StudyParticipantLink(
                study_id=study.id, participant_id=participant_id
            )
            session.add(participant_link)

            results.append(
                ParticipantAssignmentResult(
                    participant_id=participant_id, status=status, message=message
                )
            )

        # Commit all changes
        session.commit()

        # Get updated count of participants for this study
        total_participants = (
            session.exec(
                select(func.count(StudyParticipantLink.participant_id)).where(
                    StudyParticipantLink.study_id == study.id
                )
            ).first()
            or 0
        )

        # Log the operation
        logger.info(
            f"Admin assigned {len(participant_ids)} participants to study '{study_name_short}'. "
            f"Created: {created_count}, Assigned: {assigned_count}, "
            f"Already assigned: {already_assigned_count}. "
            f"Study is {'OPEN' if study.allow_unlisted_participants else 'CLOSED'}. "
            f"must_be_new was {request.must_be_new}"
        )
        audit_admin_action(
            current_admin,
            (
                f"assigned {len(participant_ids)} participants to study {study_name_short} "
                f"(created={created_count}, assigned_existing={assigned_count}, already_assigned={already_assigned_count}, "
                f"must_be_new={request.must_be_new})"
            ),
        )

        # Prepare response
        summary = {
            "total_requested": len(participant_ids),
            "created_and_assigned": created_count,
            "already_existed_and_assigned": assigned_count,
            "already_assigned": already_assigned_count,
            "total_after_assignment": total_participants,
        }

        response = AssignParticipantsResponse(
            study_info=StudyAssignmentInfo(
                name_short=study.name_short,
                allow_unlisted_participants=study.allow_unlisted_participants,
                total_participants=total_participants,
            ),
            results=results,
            summary=summary,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(
            f"Error assigning participants to study '{study_name_short}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to assign participants: {str(e)}"
        )


# Endpoint to remove participants from a study
@app.delete(
    "/api/admin/studies/{study_name_short}/participants/{participant_id}",
    name="api_remove_participant_from_study",
)
async def remove_participant_from_study(
    study_name_short: str,
    participant_id: str,
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin),
):
    """
    Remove a participant from a study.

    Note: This only removes the link between study and participant.
    The participant record itself is not deleted.
    """
    try:
        # Get the study
        study = session.exec(
            select(Study).where(Study.name_short == study_name_short)
        ).first()

        if not study:
            raise HTTPException(
                status_code=404, detail=f"Study '{study_name_short}' not found"
            )

        # Check if link exists
        link = session.exec(
            select(StudyParticipantLink).where(
                StudyParticipantLink.study_id == study.id,
                StudyParticipantLink.participant_id == participant_id,
            )
        ).first()

        if not link:
            raise HTTPException(
                status_code=404,
                detail=f"Participant '{participant_id}' is not assigned to study '{study_name_short}'",
            )

        # Delete the link
        session.delete(link)
        session.commit()

        logger.info(
            f"Admin removed participant '{participant_id}' from study '{study_name_short}'"
        )
        audit_admin_action(
            current_admin,
            f"removed participant {participant_id} from study {study_name_short}",
        )

        return {
            "status": "success",
            "message": f"Participant '{participant_id}' removed from study '{study_name_short}'",
            "study_name_short": study.name_short,
            "participant_id": participant_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(
            f"Error removing participant '{participant_id}' from study '{study_name_short}': {e}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to remove participant: {str(e)}"
        )


@app.delete(
    "/api/admin/studies/{study_name_short}/participants/{participant_id}/ratings",
    name="api_delete_participant_ratings",
)
async def delete_participant_ratings(
    study_name_short: str,
    participant_id: str,
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin),
):
    """
    Delete all ratings (and their segments) for a specific participant in a study.

    This only deletes the rating data, not the participant's link to the study.
    The participant remains in the study but all their rating data is removed.

    Returns count of deleted ratings and segments.
    """
    try:
        # Get the study
        study = session.exec(
            select(Study).where(Study.name_short == study_name_short)
        ).first()

        if not study:
            raise HTTPException(
                status_code=404, detail=f"Study '{study_name_short}' not found"
            )

        # Check if participant exists
        participant = session.exec(
            select(Participant).where(Participant.id == participant_id)
        ).first()

        if not participant:
            raise HTTPException(
                status_code=404, detail=f"Participant '{participant_id}' not found"
            )

        # First, get all ratings for this participant in this study
        ratings = session.exec(
            select(Rating).where(
                Rating.study_id == study.id, Rating.participant_id == participant_id
            )
        ).all()

        if not ratings:
            return {
                "status": "success",
                "message": f"No ratings found for participant '{participant_id}' in study '{study_name_short}'",
                "study_name_short": study.name_short,
                "participant_id": participant_id,
                "ratings_deleted": 0,
                "segments_deleted": 0,
            }

        rating_ids = [rating.id for rating in ratings]

        # Delete rating segments first (due to foreign key constraints)
        segments_deleted = session.exec(
            delete(RatingSegment).where(RatingSegment.rating_id.in_(rating_ids))
        ).rowcount

        # Delete the ratings
        ratings_deleted = session.exec(
            delete(Rating).where(
                Rating.study_id == study.id, Rating.participant_id == participant_id
            )
        ).rowcount

        session.commit()

        logger.info(
            f"Admin deleted all ratings for participant '{participant_id}' "
            f"in study '{study_name_short}': "
            f"{ratings_deleted} ratings and {segments_deleted} segments deleted"
        )
        audit_admin_action(
            current_admin,
            (
                f"deleted participant ratings in study {study_name_short} for participant {participant_id} "
                f"({ratings_deleted} ratings, {segments_deleted} segments)"
            ),
        )

        return {
            "status": "success",
            "message": f"Deleted {ratings_deleted} ratings and {segments_deleted} segments for participant '{participant_id}' in study '{study_name_short}'",
            "study_name_short": study.name_short,
            "participant_id": participant_id,
            "ratings_deleted": ratings_deleted,
            "segments_deleted": segments_deleted,
        }

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(
            f"Error deleting ratings for participant '{participant_id}' in study '{study_name_short}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to delete participant ratings: {str(e)}"
        )


# Endpoint to get current participants for a study
@app.get(
    "/api/admin/studies/{study_name_short}/participants",
    name="admin_get_study_participants",
)
async def get_study_participants(
    study_name_short: str,
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(0, ge=0, le=1000),
    current_admin: str = Depends(verify_admin),
):
    """
    Get all participants assigned to a specific study.

    Returns both pre-listed participants and any participants who have submitted ratings.
    """
    try:
        # Get the study
        study = session.exec(
            select(Study).where(Study.name_short == study_name_short)
        ).first()

        if not study:
            raise HTTPException(
                status_code=404, detail=f"Study '{study_name_short}' not found"
            )

        num_study_songs = (
            session.exec(
                select(func.count(StudySongLink.song_id)).where(
                    StudySongLink.study_id == study.id
                )
            ).first()
            or 0
        )

        num_study_rating_dimensions = (
            session.exec(
                select(func.count(StudyRatingDimension.id)).where(
                    StudyRatingDimension.study_id == study.id
                )
            ).first()
            or 0
        )

        # number of expected ratings is number of songs * number of ratings dimensions
        num_expected_ratings_per_participant = (
            num_study_songs * num_study_rating_dimensions
        )

        use_pagination = limit > 0

        if use_pagination:
            # Get all participants linked to this study (pre-listed)
            participant_links = session.exec(
                select(StudyParticipantLink)
                .where(StudyParticipantLink.study_id == study.id)
                .offset(skip)
                .limit(limit)
            ).all()
        else:
            participant_links = session.exec(
                select(StudyParticipantLink).where(
                    StudyParticipantLink.study_id == study.id
                )
            ).all()

        participant_ids = [link.participant_id for link in participant_links]

        # Get participant details
        participants = []
        for participant_id in participant_ids:
            participant = session.exec(
                select(Participant).where(Participant.id == participant_id)
            ).first()

            if participant:
                # Check if participant has submitted any ratings for this study
                num_ratings = (
                    session.exec(
                        select(func.count(Rating.id)).where(
                            Rating.participant_id == participant.id,
                            Rating.study_id == study.id,
                        )
                    ).first()
                    or 0
                )

                has_completed_all_ratings = (
                    num_ratings >= num_expected_ratings_per_participant
                    if num_expected_ratings_per_participant > 0
                    else False
                )

                participants.append(
                    {
                        "id": participant.id,
                        "created_at": participant.created_at.isoformat()
                        if participant.created_at
                        else None,
                        "has_submitted_ratings": num_ratings > 0,
                        "rating_count": num_ratings,
                        "expected_ratings_count": num_expected_ratings_per_participant,
                        "has_completed_all_ratings": has_completed_all_ratings,
                    }
                )

        # Get total count for pagination
        total_count = (
            session.exec(
                select(func.count(StudyParticipantLink.participant_id)).where(
                    StudyParticipantLink.study_id == study.id
                )
            ).first()
            or 0
        )

        audit_admin_action(
            current_admin,
            f"listed participants for study {study_name_short} (skip={skip}, limit={limit})",
        )

        return {
            "study_name_short": study.name_short,
            "allow_unlisted_participants": study.allow_unlisted_participants,
            "participants": participants,
            "pagination": {
                "used": use_pagination,
                "skip": skip if use_pagination else None,
                "limit": limit if use_pagination else None,
                "total": total_count,
                "has_more": (skip + limit) < total_count if use_pagination else False,
            },
        }

    except Exception as e:
        logger.error(f"Error getting participants for study '{study_name_short}': {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get participants: {str(e)}"
        )


@app.get(
    "/admin/participant-management",
    name="admin_participant_management",
    response_class=HTMLResponse,
)
async def admin_participant_management(
    request: Request,
    study_name_short: Optional[str] = Query(None, description="Study to pre-select"),
    session: Session = Depends(get_session),
    current_admin: str = Depends(verify_admin),
):
    """
    Admin page for managing participants in studies.
    Allows adding/removing participants from studies.
    """
    try:
        audit_admin_action(
            current_admin,
            f"opened participant management page{f' for study {study_name_short}' if study_name_short else ''}",
        )
        # Get all studies for the dropdown
        studies = session.exec(select(Study).order_by(Study.name_short)).all()

        # Get pre-selected study details if provided
        selected_study = None
        current_participants = []

        if study_name_short:
            selected_study = session.exec(
                select(Study).where(Study.name_short == study_name_short)
            ).first()

            if selected_study:
                # Get current participants for this study
                participant_links = session.exec(
                    select(StudyParticipantLink).where(
                        StudyParticipantLink.study_id == selected_study.id
                    )
                ).all()

                for link in participant_links:
                    participant = session.exec(
                        select(Participant).where(Participant.id == link.participant_id)
                    ).first()

                    if participant:
                        # Check if participant has ratings
                        has_ratings = (
                            session.exec(
                                select(func.count(Rating.id)).where(
                                    Rating.participant_id == participant.id,
                                    Rating.study_id == selected_study.id,
                                )
                            ).first()
                            or 0
                        )

                        current_participants.append(
                            {
                                "id": participant.id,
                                "created_at": participant.created_at,
                                "has_ratings": has_ratings > 0,
                                "rating_count": has_ratings,
                            }
                        )

        context_dict = {
            "request": request,
            "admin_user": current_admin,
            "studies": studies,
            "selected_study": selected_study,
            "current_participants": current_participants,
            "current_time": datetime.now(),
            "frontend_url": settings.frontend_url,
        }
        template = templates.get_template("admin_participant_management.html")
        html_content = template.render(context_dict)
        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error loading participant management page: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load participant management page: {str(e)}",
        )
