from typing import Tuple, List, Dict, Optional
from bson import ObjectId
from datetime import datetime

from src.shared.database import get_db
from src.shared.constants import ROLES, COLLECTIONS
from src.shared.standardization import BaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import Institute, EducationalProgram, Level, InstituteMember
from src.analytics.services import InstituteAnalyticsService

class InstituteService(BaseService):
    def __init__(self):
        super().__init__(collection_name="institutes")
        self.db = get_db()
        self.analytics_service = InstituteAnalyticsService()

    def create_institute(self, institute_data: dict) -> Tuple[bool, str]:
        try:
            # Crear instituto
            institute = Institute(**institute_data)
            result = self.collection.insert_one(institute.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_institute(self, institute_id: str) -> Optional[Dict]:
        try:
            institute = self.collection.find_one({"_id": ObjectId(institute_id)})
            if not institute:
                return None

            # Obtener miembros
            members = self.db.institute_members.find({"institute_id": ObjectId(institute_id)})
            member_list = []
            for member in members:
                user = self.db.users.find_one({"_id": member["user_id"]})
                if user:
                    member_list.append({
                        "id": str(user["_id"]),
                        "name": user.get("name", ""),
                        "email": user.get("email", ""),
                        "role": member.get("role", ""),
                        "joined_at": member.get("joined_at", datetime.now()).isoformat()
                    })

            institute["members"] = member_list
            institute["_id"] = str(institute["_id"])
            return institute
        except Exception as e:
            print(f"Error al obtener instituto: {str(e)}")
            return None

    def update_institute(self, institute_id: str, updates: dict) -> Tuple[bool, str]:
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(institute_id)},
                {"$set": updates}
            )
            if result.modified_count > 0:
                return True, "Instituto actualizado correctamente"
            return False, "No se realizaron cambios"
        except Exception as e:
            return False, str(e)

    def get_institute_by_admin(self, admin_email: str) -> Optional[Dict]:
        try:
            # Buscar usuario por email
            user = self.db.users.find_one({"email": admin_email})
            if not user:
                return None

            # Buscar membresía como administrador de instituto
            member = self.db.institute_members.find_one({
                "user_id": user["_id"],
                "role": "institute_admin"
            })

            if not member:
                return None

            # Obtener el instituto
            institute = self.collection.find_one({"_id": member["institute_id"]})
            if not institute:
                return None

            # Convertir ids
            institute["_id"] = str(institute["_id"])

            return institute
        except Exception as e:
            print(f"Error al obtener instituto por admin: {str(e)}")
            return None

    def delete_institute(self, institute_id: str, admin_email: str) -> Tuple[bool, str]:
        try:
            # Verificar si existen programas asociados
            programs_count = self.db.educational_programs.count_documents({"institute_id": ObjectId(institute_id)})
            if programs_count > 0:
                return False, f"No se puede eliminar el instituto porque tiene {programs_count} programas asociados"

            # Eliminar miembros del instituto
            self.db.institute_members.delete_many({"institute_id": ObjectId(institute_id)})

            # Eliminar el instituto
            result = self.collection.delete_one({"_id": ObjectId(institute_id)})
            if result.deleted_count > 0:
                return True, "Instituto eliminado correctamente"
            return False, "No se encontró el instituto"
        except Exception as e:
            return False, str(e)

    def get_institute_statistics(self, institute_id: str) -> Optional[Dict]:
        return self.analytics_service.get_institute_statistics(institute_id)

class ProgramService(BaseService):
    def __init__(self):
        super().__init__(collection_name="educational_programs")
        self.db = get_db()

    def create_program(self, program_data: dict) -> Tuple[bool, str]:
        try:
            program = EducationalProgram(**program_data)
            result = self.collection.insert_one(program.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_institute_programs(self, institute_id: str) -> List[dict]:
        try:
            programs = list(self.collection.find({"institute_id": ObjectId(institute_id)}))
            
            # Enriquecer datos
            for program in programs:
                program["_id"] = str(program["_id"])
                program["institute_id"] = str(program["institute_id"])
                
                # Obtener niveles
                levels_count = self.db.levels.count_documents({"program_id": program["_id"]})
                program["levels_count"] = levels_count
            
            return programs
        except Exception as e:
            print(f"Error al obtener programas del instituto: {str(e)}")
            return []

    def update_program(self, program_id: str, updates: dict) -> Tuple[bool, str]:
        try:
            # Manejar conversión de instituto_id si está presente
            if 'institute_id' in updates:
                updates['institute_id'] = ObjectId(updates['institute_id'])
                
            result = self.collection.update_one(
                {"_id": ObjectId(program_id)},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                return True, "Programa educativo actualizado correctamente"
            return False, "No se realizaron cambios"
        except Exception as e:
            return False, str(e)

    def delete_program(self, program_id: str) -> Tuple[bool, str]:
        try:
            # Verificar si existen niveles asociados
            levels_count = self.db.levels.count_documents({"program_id": ObjectId(program_id)})
            if levels_count > 0:
                return False, f"No se puede eliminar el programa porque tiene {levels_count} niveles asociados"
                
            # Eliminar el programa
            result = self.collection.delete_one({"_id": ObjectId(program_id)})
            
            if result.deleted_count > 0:
                return True, "Programa educativo eliminado correctamente"
            return False, "No se encontró el programa educativo"
        except Exception as e:
            return False, str(e)

    def get_program_by_id(self, program_id: str) -> Optional[Dict]:
        try:
            program = self.collection.find_one({"_id": ObjectId(program_id)})
            
            if not program:
                return None
                
            # Convertir ObjectIds a strings
            program["_id"] = str(program["_id"])
            program["institute_id"] = str(program["institute_id"])
            
            # Obtener instituto relacionado
            institute = self.db.institutes.find_one({"_id": ObjectId(program["institute_id"])})
            if institute:
                program["institute"] = {
                    "id": str(institute["_id"]),
                    "name": institute.get("name", "")
                }
                
            # Obtener niveles
            levels = list(self.db.levels.find({"program_id": ObjectId(program_id)}).sort("order", 1))
            program["levels"] = []
            
            for level in levels:
                program["levels"].append({
                    "id": str(level["_id"]),
                    "name": level.get("name", ""),
                    "order": level.get("order", 1)
                })
                
            return program
        except Exception as e:
            print(f"Error al obtener programa: {str(e)}")
            return None

class LevelService(BaseService):
    def __init__(self):
        super().__init__(collection_name="levels")
        self.db = get_db()

    def create_level(self, level_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar si existe el programa
            program = self.db.educational_programs.find_one({"_id": ObjectId(level_data['program_id'])})
            if not program:
                return False, "Programa educativo no encontrado"
                
            # Verificar si ya existe un nivel con el mismo orden
            existing_level = self.collection.find_one({
                "program_id": ObjectId(level_data['program_id']),
                "order": level_data['order']
            })
            
            if existing_level:
                return False, f"Ya existe un nivel con el orden {level_data['order']} en este programa"
                
            level = Level(**level_data)
            result = self.collection.insert_one(level.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_program_levels(self, program_id: str) -> List[Dict]:
        try:
            levels = list(self.collection.find(
                {"program_id": ObjectId(program_id)}
            ).sort("order", 1))
            
            for level in levels:
                level["_id"] = str(level["_id"])
                level["program_id"] = str(level["program_id"])
                
            return levels
        except Exception as e:
            print(f"Error al obtener niveles del programa: {str(e)}")
            return []

    def get_level_by_id(self, level_id: str) -> Optional[Dict]:
        try:
            level = self.collection.find_one({"_id": ObjectId(level_id)})
            
            if level:
                level["_id"] = str(level["_id"])
                level["program_id"] = str(level["program_id"])
                
            return level
        except Exception as e:
            print(f"Error al obtener nivel: {str(e)}")
            return None

    def update_level(self, level_id: str, updates: dict) -> Tuple[bool, str]:
        try:
            # Convertir program_id a ObjectId si está presente
            if 'program_id' in updates:
                updates['program_id'] = ObjectId(updates['program_id'])
                
            result = self.collection.update_one(
                {"_id": ObjectId(level_id)},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                return True, "Nivel actualizado correctamente"
            return False, "No se realizaron cambios"
        except Exception as e:
            return False, str(e)

    def delete_level(self, level_id: str) -> Tuple[bool, str]:
        try:
            # Verificar si hay dependencias (materias, secciones, etc.)
            subjects_count = self.db.subjects.count_documents({"level_id": ObjectId(level_id)})
            sections_count = self.db.sections.count_documents({"level_id": ObjectId(level_id)})
            
            if subjects_count > 0 or sections_count > 0:
                return False, f"No se puede eliminar el nivel porque tiene {subjects_count} materias y {sections_count} secciones asociadas"
                
            # Eliminar el nivel
            result = self.collection.delete_one({"_id": ObjectId(level_id)})
            
            if result.deleted_count > 0:
                return True, "Nivel eliminado correctamente"
            return False, "No se encontró el nivel"
        except Exception as e:
            return False, str(e)