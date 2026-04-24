import pytest
from sqlalchemy import create_engine
from sqlmodel import SQLModel
from audiorating_backend.settings import settings


@pytest.fixture(autouse=True)
def setup_db():
    # Connect to the DB
    engine = create_engine(settings.database_url)

    # Create tables (your backend does this, but we ensure it for tests)
    SQLModel.metadata.create_all(engine)

    yield  # The test runs here

    # Optional: Clear tables after test so they don't leak into the next one
    with engine.connect() as connection:
        for table in reversed(SQLModel.metadata.sorted_tables):
            connection.execute(table.delete())
        connection.commit()
