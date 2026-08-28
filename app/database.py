"""
Wave - MongoDB Async Database Connection
Uses Motor (async MongoDB driver) with connection pooling.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings
import logging
import certifi

logger = logging.getLogger(__name__)


class Database:
    """MongoDB async database manager with connection pooling."""

    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None

    async def connect(self) -> None:
        """Establish connection to MongoDB Atlas."""
        try:
            ca_file = certifi.where()
            self.client = AsyncIOMotorClient(
                settings.mongodb_uri,
                maxPoolSize=10,
                minPoolSize=1,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                tlsCAFile=ca_file,
            )
            self.db = self.client[settings.mongodb_db_name]

            # Verify connection by pinging the server
            await self.client.admin.command("ping")
            logger.info(
                f"✅ Connected to MongoDB Atlas — "
                f"Database: {settings.mongodb_db_name}"
            )

            # Create indexes for performance
            await self._create_indexes()

        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            raise

    async def _create_indexes(self) -> None:
        """Create database indexes for optimal query performance."""
        try:
            # Users collection indexes
            await self.db.users.create_index("email", unique=True)
            await self.db.users.create_index("username", unique=True)

            # Playlists collection indexes
            await self.db.playlists.create_index("user_id")

            # Listening history indexes
            await self.db.listening_history.create_index(
                [("user_id", 1), ("played_at", -1)]
            )

            # Song cache indexes
            await self.db.song_cache.create_index("cached_at")

            # Recommendation graph indexes
            await self.db.recommendation_graph.create_index(
                "track_id", unique=True
            )

            logger.info("✅ Database indexes created successfully")

        except Exception as e:
            logger.warning(f"⚠️ Index creation warning: {e}")

    async def disconnect(self) -> None:
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("🔌 Disconnected from MongoDB")

    def get_collection(self, name: str):
        """Get a MongoDB collection by name."""
        return self.db[name]


# Singleton database instance
database = Database()


def get_db() -> AsyncIOMotorDatabase:
    """Dependency injection helper to get the database instance."""
    return database.db
