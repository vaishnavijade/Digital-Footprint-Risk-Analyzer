#!/usr/bin/env python3
"""
Quick test script to verify MongoDB connection
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
DB_NAME = os.getenv("MONGODB_DB_NAME", "privacy_analyzer")

print(f"Testing MongoDB Connection...")
print(f"URL: {MONGODB_URL}")
print(f"Database: {DB_NAME}")
print()

async def test_connection():
    try:
        # Create client
        client = AsyncIOMotorClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        
        # Test ping
        await client.admin.command('ping')
        print("✅ PING: Connected to MongoDB successfully!")
        
        # Get database
        db = client[DB_NAME]
        
        # Try to insert a test document
        test_doc = {"test": "connection", "status": "ok"}
        result = await db.test_connection.insert_one(test_doc)
        print(f"✅ INSERT: Test document inserted with ID: {result.inserted_id}")
        
        # Try to find it
        found = await db.test_connection.find_one({"test": "connection"})
        print(f"✅ FIND: Test document found: {found}")
        
        # Clean up
        await db.test_connection.delete_one({"test": "connection"})
        print(f"✅ DELETE: Test document deleted")
        
        client.close()
        print("\n✅ All tests passed! MongoDB is working correctly.")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print(f"\nPossible issues:")
        print(f"1. Wrong password in MONGODB_URL")
        print(f"2. IP address not whitelisted in MongoDB Atlas")
        print(f"3. Network connectivity issue")
        print(f"4. MongoDB cluster not running")

if __name__ == "__main__":
    asyncio.run(test_connection())
