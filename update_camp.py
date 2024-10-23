from pymongo import MongoClient
from dotenv import load_dotenv
import os

def get_db():
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_name = os.getenv("DB_NAME")
    client = MongoClient(f'mongodb+srv://{db_user}:{db_password}@{db_host}/?retryWrites=true&w=majority')
    db = client[db_name]
    return db

db = get_db()
tweets_collection = db.tweets

result = tweets_collection.update_many(
    {"categories": {"$exists": False}},
    {"$set": {"thread": "no"}}
)

print(f"Documentos actualizados: {result.modified_count}")