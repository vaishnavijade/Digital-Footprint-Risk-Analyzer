"""
MongoDB connection and database utilities
Uses Motor for async MongoDB operations
Supports in-memory fallback when MongoDB is unavailable
"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, Dict, List, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# In-memory storage fallback
_memory_storage: Dict[str, List[Dict]] = {}


class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    db = None
    use_memory: bool = False


mongodb = MongoDB()


async def connect_to_mongo():
    """Connect to MongoDB with fallback to in-memory storage"""
    
    # Check if MongoDB URL is configured
    if not settings.MONGODB_URL or settings.MONGODB_URL == "mongodb://localhost:27017":
        logger.warning("⚠️  MongoDB not configured - using IN-MEMORY storage")
        logger.warning("    (Data will be lost on restart)")
        mongodb.use_memory = True
        mongodb.client = None
        mongodb.db = None
        return
    
    try:
        logger.info(f"Connecting to MongoDB at {settings.MONGODB_URL}")
        mongodb.client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=3000)
        mongodb.db = mongodb.client[settings.MONGODB_DB_NAME]
        
        # Test connection
        await mongodb.client.admin.command('ping')
        logger.info("✅ Connected to MongoDB successfully")
        mongodb.use_memory = False
        
        # Create indexes
        await create_indexes()
        
    except Exception as e:
        logger.warning(f"⚠️  MongoDB connection failed: {e}")
        logger.warning("    Using IN-MEMORY storage instead")
        mongodb.use_memory = True
        mongodb.client = None
        mongodb.db = None


async def close_mongo_connection():
    """Close MongoDB connection"""
    if mongodb.client:
        mongodb.client.close()


async def create_indexes():
    """Create database indexes for better performance"""
    if mongodb.use_memory:
        return
    try:
        # Analysis results indexes
        await mongodb.db.analysis_results.create_index("user_id")
        await mongodb.db.analysis_results.create_index("timestamp")
        await mongodb.db.analysis_results.create_index("risk_level")

        # Users indexes
        # Keep unique email index
        await mongodb.db.users.create_index("email", unique=True)

        # Create a unique index on `username` only for documents where
        # `username` exists and is not null. This avoids duplicate-key
        # errors when multiple documents have no `username` field.
        # If an old (strict) unique index exists we attempt to drop it first.
        try:
            await mongodb.db.users.drop_index("username_1")
        except Exception:
            # ignore if index does not exist or cannot be dropped
            pass

        await mongodb.db.users.create_index(
            [("username", 1)],
            unique=True,
            partialFilterExpression={"username": {"$exists": True, "$ne": None}},
        )
    except Exception as e:
        logger.warning(f"Failed creating indexes: {e}")


def get_database():
    """Get database instance (or None if using memory)"""
    return mongodb.db


def use_memory_storage():
    """Check if using in-memory storage"""
    return mongodb.use_memory


# In-memory storage helper functions
async def memory_insert_one(collection: str, document: Dict) -> None:
    """Insert document into memory storage"""
    if collection not in _memory_storage:
        _memory_storage[collection] = []
    _memory_storage[collection].append(document)


async def memory_find_one(collection: str, query: Dict) -> Optional[Dict]:
    """Find one document from memory storage"""
    if collection not in _memory_storage:
        return None
    
    for doc in _memory_storage[collection]:
        if all(doc.get(k) == v for k, v in query.items()):
            return doc
    return None


async def memory_find(collection: str, query: Dict = None, sort: tuple = None, limit: int = 100) -> List[Dict]:
    """Find documents from memory storage"""
    if collection not in _memory_storage:
        return []
    
    items = _memory_storage.get(collection, [])
    
    # Apply query filter
    if query:
        filtered = []
        for item in items:
            match = True
            for key, value in query.items():
                if "." in key:  # Handle nested fields like "risk_score.level"
                    parts = key.split(".")
                    nested_val = item
                    for part in parts:
                        nested_val = nested_val.get(part, {})
                        if not isinstance(nested_val, dict) and part != parts[-1]:
                            break
                    if nested_val != value:
                        match = False
                        break
                else:
                    if item.get(key) != value:
                        match = False
                        break
            if match:
                filtered.append(item)
        items = filtered
    
    # Apply sorting
    if sort:
        field, direction = sort
        reverse = (direction == -1)
        items = sorted(items, key=lambda x: x.get(field, ""), reverse=reverse)
    
    # Apply limit
    return items[:limit]


async def memory_count(collection: str, query: Dict = None) -> int:
    """Count documents in memory storage"""
    items = await memory_find(collection, query, limit=999999)
    return len(items)


async def memory_delete_one(collection: str, query: Dict) -> int:
    """Delete one document from memory storage"""
    if collection not in _memory_storage:
        return 0
    
    for i, doc in enumerate(_memory_storage[collection]):
        if all(doc.get(k) == v for k, v in query.items()):
            _memory_storage[collection].pop(i)
            return 1
    return 0


async def memory_aggregate(collection: str, pipeline: List[Dict]) -> List[Dict]:
    """Simple aggregation for memory storage (limited functionality)"""
    if collection not in _memory_storage:
        return []
    
    items = _memory_storage.get(collection, [])
    
    for stage in pipeline:
        if "$group" in stage:
            # Simple group by
            group_spec = stage["$group"]
            group_id = group_spec.get("_id")
            
            if group_id is None:
                # Global aggregation
                result = {"_id": None}
                if "avg_score" in group_spec:
                    field = group_spec["avg_score"]["$avg"]
                    values = [item.get(field.replace("$", "").split(".")[0], {}).get(field.split(".")[-1], 0) for item in items]
                    result["avg_score"] = sum(values) / len(values) if values else 0
                if "avg_time" in group_spec:
                    field = group_spec["avg_time"]["$avg"]
                    values = [item.get(field.replace("$", ""), 0) for item in items]
                    result["avg_time"] = sum(values) / len(values) if values else 0
                return [result]
            
            elif "$" in str(group_id):
                # Group by field
                field = group_id.replace("$", "")
                groups = {}
                
                for item in items:
                    # Handle nested fields
                    if "." in field:
                        parts = field.split(".")
                        key = item
                        for part in parts:
                            key = key.get(part, {})
                    else:
                        key = item.get(field)
                    
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(item)
                
                # Build result
                results = []
                for key, group_items in groups.items():
                    result = {"_id": key}
                    if "count" in group_spec:
                        result["count"] = len(group_items)
                    results.append(result)
                
                items = results
        
        elif "$unwind" in stage:
            # Unwind array
            field = stage["$unwind"].replace("$", "")
            unwound = []
            for item in items:
                arr = item.get(field, [])
                for element in arr:
                    new_item = item.copy()
                    new_item[field] = element
                    unwound.append(new_item)
            items = unwound
        
        elif "$sort" in stage:
            # Sort
            sort_spec = stage["$sort"]
            for field, direction in sort_spec.items():
                items = sorted(items, key=lambda x: x.get(field, 0), reverse=(direction == -1))
        
        elif "$limit" in stage:
            # Limit
            items = items[:stage["$limit"]]
    
    return items
