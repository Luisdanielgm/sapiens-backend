from pymongo import MongoClient
import os
import dotenv
dotenv.load_dotenv()

db_uri=os.getenv('MONGO_DB_URI')
db_name=os.getenv('DB_NAME')

def get_db():
    try:
        client = MongoClient(db_uri)
        db = client[db_name]
        print("Conexión a la base de datos establecida.")
        return db
    except Exception as e:
        print("Error al conectar a la base de datos:", e)
        raise