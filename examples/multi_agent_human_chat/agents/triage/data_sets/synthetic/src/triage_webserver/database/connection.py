import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from triage_webserver.config import WebServerConfig
from triage_webserver.database.base import Base

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = WebServerConfig()

logger.info(f"Connecting to database at: {config.DATABASE_URL}")

# Create database engine with connection pooling
engine = create_engine(
    config.DATABASE_URL,
    pool_pre_ping=True,  # Check connection liveness
    echo=config.DEBUG    # Log SQL in debug mode
)

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Add engine connection debugging
if config.DEBUG:
    @event.listens_for(engine, "connect")
    def connect(dbapi_connection, connection_record):
        logger.info("Database connection established")

    @event.listens_for(engine, "checkout")
    def checkout(dbapi_connection, connection_record, connection_proxy):
        logger.debug("Database connection checked out")

    @event.listens_for(engine, "checkin")
    def checkin(dbapi_connection, connection_record):
        logger.debug("Database connection checked in")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize the database by creating all tables."""
    try:
        # Import all models here to ensure they are registered with Base
        from triage_webserver.models.data_models import Dataset, Example
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        # Re-raise for proper application error handling
        raise