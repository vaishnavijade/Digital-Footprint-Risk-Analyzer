import asyncio
import motor.motor_asyncio
import os
from dotenv import load_dotenv

load_dotenv()
MONGODB_URL = os.getenv("MONGODB_URL")
DB_NAME = os.getenv("MONGODB_DB_NAME", "privacy_analyzer")

async def test():
    print(f"Testing: {MONGODB_URL[:50]}...")
    try:
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        await client.admin.command('ping')
        print("✅ CONNECTED!")
        client.close()
    except Exception as e:
        print(f"❌ FAILED: {e}")

asyncio.run(test())
