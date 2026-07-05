from celery import Celery
from config import settings
from logger import get_logger
from core.db import db
from services.redis_service import redis_server
from core.rag_init import init_rag_models, get_rag_index
from qdrant_client import QdrantClient

logger = get_logger(__name__)

logger.info("🚀 Starting agent worker...")

# Database Connection Test
logger.info("🔌 Connecting to Database...")
db.initialize()
if not db.get_connection():
    raise Exception("❌ Database connection failed")
logger.info("✅ Database connection successful")

# Redis Connection Test
logger.info("🔌 Connecting to Redis...")

redis_url = f"redis://:{settings.redis_password}@{settings.redis_host}:{settings.redis_port}/{settings.redis_db}" if settings.redis_password else f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
redis_server.connect()
if not redis_server.test_connection():
    raise Exception("❌ Redis connection failed")
logger.info("✅ Redis connection successful")

try:
    logger.info("📥 Loading embedding model...")
    init_rag_models()
    logger.info("✅ Finished loading embedding model.")
except Exception as e:
    logger.error(f"❌ Failed to load embedding model: {e}")
    exit(1)

# --- Qdrant Connection Test ---
logger.info("🔌 Connecting to Qdrant...")
try:
    qdrant_client = QdrantClient(url=settings.qdrant_url)
    # Perform a simple health check or list collections to verify connectivity
    qdrant_client.get_collections() 
    index = get_rag_index()
    if not index:
        raise Exception("❌ Qdrant index is None")
    logger.info("✅ Qdrant connection and index creation successful")
except Exception as e:
    logger.error(f"❌ Qdrant connection failed: {e}")
    raise Exception(f"❌ Qdrant connection failed: {e}")
# ------------------------------

celery_app = Celery(
    "agent_worker",
    broker=redis_url,
    backend=redis_url,
    include=["agent_tasks", "data_ingestion_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_routes={
        "agent_tasks.process_message": {"queue": "agent_tasks"},
        "agent_tasks.handle_response": {"queue": "agent_tasks"},
        "data_ingestion_tasks.update_knowledge_base": {"queue": "agent_tasks"},
        "data_ingestion_tasks.delete_knowledge_base_file": {"queue": "agent_tasks"},
    },
    task_annotations={
        'agent_tasks.handle_response': {
            'autoretry_for': (Exception,),
            'retry_backoff': 1,
            'max_retries': 5,
            'retry_jitter': True
        }
    }
)

if __name__ == "__main__":
    logger.info("🚀 Starting Celery...")
    try:
        celery_app.start()
    except Exception as e:
        logger.error(f"❌ Celery failed to start: {e}")
        exit(1)
