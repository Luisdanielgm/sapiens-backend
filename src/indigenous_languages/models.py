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
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.verificaciones_count = 0  # Contador de verificaciones

    def to_dict(self) -> dict:
        return {
            "_id": ObjectId(),
            "español": self.español,
            "traduccion": self.traduccion,
            "dialecto": self.dialecto,
            "language_pair": self.language_pair,
            "type_data": self.type_data,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "verificaciones_count": self.verificaciones_count
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

class Verificador:
    def __init__(self,
                 nombre: str,
                 tipo: str,  # "hablante_nativo", "miembro_etnia", "organismo", "académico", etc.
                 etnia: str,  # Pueblo indígena al que pertenece o sobre el que certifica
                 descripcion: str = None,  # Cargo, función, detalles adicionales
                 institucion: str = None,  # Si pertenece a alguna institución
                 activo: bool = True):
        self.nombre = nombre
        self.tipo = tipo
        self.etnia = etnia
        self.descripcion = descripcion
        self.institucion = institucion
        self.activo = activo
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
    def to_dict(self) -> dict:
        return {
            "_id": ObjectId(),
            "nombre": self.nombre,
            "tipo": self.tipo,
            "etnia": self.etnia,
            "descripcion": self.descripcion,
            "institucion": self.institucion,
            "activo": self.activo,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class Verificacion:
    def __init__(self,
                 translation_id: str,
                 verificador_id: str,
                 comentario: str = None):
        self.translation_id = translation_id
        self.verificador_id = verificador_id
        self.comentario = comentario
        self.created_at = datetime.utcnow()
        
    def to_dict(self) -> dict:
        return {
            "_id": ObjectId(),
            "translation_id": self.translation_id,
            "verificador_id": self.verificador_id,
            "comentario": self.comentario,
            "created_at": self.created_at
        }