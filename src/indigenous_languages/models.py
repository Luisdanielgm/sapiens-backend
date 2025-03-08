from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional

class Translation:
    def __init__(self,
                 español: str,
                 traduccion: str,  # Texto en la lengua originaria
                 dialecto: str,
                 language_pair: str,  # ej: "español-pemon", "español-warao"
                 type_data: str):
        self.español = español
        self.traduccion = traduccion
        self.dialecto = dialecto
        self.language_pair = language_pair
        self.type_data = type_data
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "_id": ObjectId(),  # Generamos el ID al crear el diccionario
            "español": self.español,
            "traduccion": self.traduccion,
            "dialecto": self.dialecto,
            "language_pair": self.language_pair,
            "type_data": self.type_data,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class Language:
    def __init__(self,
                 name: str,
                 code: str,
                 region: str,
                 active: bool = True):
        self.name = name
        self.code = code
        self.region = region
        self.active = active
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "_id": ObjectId(),
            "name": self.name,
            "code": self.code,
            "region": self.region,
            "active": self.active,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }