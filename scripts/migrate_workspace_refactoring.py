#!/usr/bin/env python3
"""
Script de Migración: Refactorización de Roles y Modelo de Workspaces

Este script implementa la migración completa para:
1. Eliminar roles obsoletos SYSTEM y SUPER_ADMIN de usuarios existentes
2. Convertir roles INDIVIDUAL_TEACHER e INDIVIDUAL_STUDENT a roles base
3. Actualizar membresías existentes con campos de workspace
4. Asegurar integridad de datos en el modelo de workspaces

Ejecución: python scripts/migrate_workspace_refactoring.py
"""

import sys
import os
from datetime import datetime
from bson import ObjectId
import logging

# Agregar el directorio raíz al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import get_db
from src.classes.services import ClassService
from src.members.services import MembershipService

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration_workspace_refactoring.log'),
        logging.StreamHandler()
    ]
)

class WorkspaceRefactoringMigration:
    def __init__(self):
        self.db = get_db()
        self.class_service = ClassService()
        self.membership_service = MembershipService()
        self.migration_stats = {
            'users_migrated': 0,
            'memberships_updated': 0,
            'classes_linked': 0,
            'errors': 0
        }

    def run_migration(self):
        """Ejecuta la migración completa"""
        logging.info("=== Iniciando Migración de Refactorización de Workspaces ===")
        
        try:
            # Paso 1: Asegurar entidades genéricas
            self._ensure_generic_entities()
            
            # Paso 2: Migrar usuarios con roles obsoletos
            self._migrate_obsolete_user_roles()
            
            # Paso 3: Actualizar membresías existentes
            self._update_existing_memberships()
            
            # Paso 4: Crear workspaces faltantes para usuarios existentes
            self._create_missing_workspaces()
            
            # Paso 5: Vincular clases personales existentes
            self._link_personal_classes()
            
            # Paso 6: Verificar integridad de datos
            self._verify_data_integrity()
            
            logging.info("=== Migración Completada Exitosamente ===")
            self._print_migration_stats()
            
        except Exception as e:
            logging.error(f"Error durante la migración: {str(e)}")
            raise

    def _ensure_generic_entities(self):
        """Asegura que existan las entidades genéricas"""
        logging.info("Paso 1: Verificando entidades genéricas...")
        
        try:
            # Obtener o crear entidades genéricas directamente desde la base de datos
            entities = self._get_or_create_generic_entities()
            logging.info(f"Entidades genéricas verificadas: Instituto ID {entities['institute_id']}")
        except Exception as e:
            logging.error(f"Error al verificar entidades genéricas: {str(e)}")
            raise

    def _migrate_obsolete_user_roles(self):
        """Migra usuarios con roles obsoletos a roles base"""
        logging.info("Paso 2: Migrando usuarios con roles obsoletos...")
        
        # Mapeo de roles obsoletos a roles base
        role_mapping = {
            'individual_teacher': 'teacher',
            'individual_student': 'student',
            'super_admin': 'admin',
            'system': 'admin'  # O eliminar si son usuarios técnicos
        }
        
        for old_role, new_role in role_mapping.items():
            users_to_update = list(self.db.users.find({"role": old_role}))
            
            if users_to_update:
                logging.info(f"Encontrados {len(users_to_update)} usuarios con rol '{old_role}'")
                
                for user in users_to_update:
                    try:
                        # Actualizar rol del usuario
                        result = self.db.users.update_one(
                            {"_id": user["_id"]},
                            {"$set": {"role": new_role}}
                        )
                        
                        if result.modified_count > 0:
                            logging.info(f"Usuario {user['email']} migrado de '{old_role}' a '{new_role}'")
                            self.migration_stats['users_migrated'] += 1
                        
                    except Exception as e:
                        logging.error(f"Error al migrar usuario {user['email']}: {str(e)}")
                        self.migration_stats['errors'] += 1
            else:
                logging.info(f"No se encontraron usuarios con rol '{old_role}'")

    def _update_existing_memberships(self):
        """Actualiza membresías existentes con campos de workspace"""
        logging.info("Paso 3: Actualizando membresías existentes...")
        
        # Obtener instituto genérico
        entities = self._get_or_create_generic_entities()
        generic_institute_id = ObjectId(entities['institute_id'])
        
        # Actualizar todas las membresías que no tienen workspace_type
        memberships_to_update = list(self.db.institute_members.find({
            "workspace_type": {"$exists": False}
        }))
        
        logging.info(f"Encontradas {len(memberships_to_update)} membresías para actualizar")
        
        for membership in memberships_to_update:
            try:
                update_data = {}
                
                # Determinar workspace_type
                if membership['institute_id'] == generic_institute_id:
                    # Es del instituto genérico, determinar por rol
                    if membership['role'] in ['teacher', 'individual_teacher']:
                        update_data['workspace_type'] = 'INDIVIDUAL_TEACHER'
                        # Obtener nombre del usuario para workspace_name
                        user = self.db.users.find_one({"_id": membership['user_id']})
                        if user:
                            update_data['workspace_name'] = f"Clases de {user['name']}"
                    elif membership['role'] in ['student', 'individual_student']:
                        update_data['workspace_type'] = 'INDIVIDUAL_STUDENT'
                        # Obtener nombre del usuario para workspace_name
                        user = self.db.users.find_one({"_id": membership['user_id']})
                        if user:
                            update_data['workspace_name'] = f"Aprendizaje de {user['name']}"
                else:
                    # Es de un instituto real
                    update_data['workspace_type'] = 'INSTITUTE'
                    # Para institutos reales, workspace_name será el nombre del instituto
                    institute = self.db.institutes.find_one({"_id": membership['institute_id']})
                    if institute:
                        update_data['workspace_name'] = institute['name']
                
                # Normalizar rol si es necesario
                if membership['role'] == 'individual_teacher':
                    update_data['role'] = 'teacher'
                elif membership['role'] == 'individual_student':
                    update_data['role'] = 'student'
                
                # Actualizar membresía
                result = self.db.institute_members.update_one(
                    {"_id": membership['_id']},
                    {"$set": update_data}
                )
                
                if result.modified_count > 0:
                    self.migration_stats['memberships_updated'] += 1
                    logging.debug(f"Membresía {membership['_id']} actualizada")
                
            except Exception as e:
                logging.error(f"Error al actualizar membresía {membership['_id']}: {str(e)}")
                self.migration_stats['errors'] += 1

    def _create_missing_workspaces(self):
        """Crea workspaces faltantes para usuarios existentes"""
        logging.info("Paso 4: Creando workspaces faltantes...")
        
        # Obtener entidades genéricas
        entities = self._get_or_create_generic_entities()
        generic_institute_id = entities['institute_id']
        
        # Obtener todos los usuarios
        users = list(self.db.users.find({}))
        
        for user in users:
            try:
                user_id = str(user['_id'])
                user_role = user['role']
                
                # Verificar workspaces existentes
                existing_workspaces = list(self.db.institute_members.find({
                    "user_id": user['_id'],
                    "institute_id": ObjectId(generic_institute_id)
                }))
                
                workspace_types = [ws.get('workspace_type') for ws in existing_workspaces]
                
                # Crear workspace de estudiante individual si no existe
                if 'INDIVIDUAL_STUDENT' not in workspace_types:
                    self.membership_service.add_institute_member({
                        "institute_id": generic_institute_id,
                        "user_id": user_id,
                        "role": "student",
                        "workspace_type": "INDIVIDUAL_STUDENT",
                        "workspace_name": f"Aprendizaje de {user['name']}"
                    })
                    logging.info(f"Workspace INDIVIDUAL_STUDENT creado para {user['email']}")
                
                # Crear workspace de profesor individual solo para docentes
                if user_role == 'teacher' and 'INDIVIDUAL_TEACHER' not in workspace_types:
                    teacher_member_id = self.membership_service.add_institute_member({
                        "institute_id": generic_institute_id,
                        "user_id": user_id,
                        "role": "teacher",
                        "workspace_type": "INDIVIDUAL_TEACHER",
                        "workspace_name": f"Clases de {user['name']}"
                    })
                    
                    # Crear clase personal si no existe
                    existing_class = self.db.classes.find_one({
                        "created_by": user['_id'],
                        "institute_id": ObjectId(generic_institute_id)
                    })
                    
                    if not existing_class:
                        class_data = {
                            "institute_id": ObjectId(entities["institute_id"]),
                            "subject_id": ObjectId(entities["subject_id"]),
                            "section_id": ObjectId(entities["section_id"]),
                            "academic_period_id": ObjectId(entities["academic_period_id"]),
                            "level_id": ObjectId(entities["level_id"]),
                            "name": f"Clase Personal de {user['name']}",
                            "access_code": f"PERS{str(user['_id'])[-6:]}",
                            "created_by": user['_id']
                        }
                        success, class_id = self.class_service.create_class(class_data)
                        if success:
                            # Actualizar membresía con class_id
                            self.membership_service.update_institute_member(
                                teacher_member_id, 
                                {"class_id": class_id}
                            )
                            logging.info(f"Clase personal creada para {user['email']}")
                    
                    logging.info(f"Workspace INDIVIDUAL_TEACHER creado para {user['email']}")
                
            except Exception as e:
                logging.error(f"Error al crear workspaces para {user['email']}: {str(e)}")
                self.migration_stats['errors'] += 1

    def _link_personal_classes(self):
        """Vincula clases personales existentes con sus workspaces"""
        logging.info("Paso 5: Vinculando clases personales existentes...")
        
        # Obtener entidades genéricas
        entities = self._get_or_create_generic_entities()
        generic_institute_id = ObjectId(entities['institute_id'])
        
        # Buscar membresías de profesores individuales sin class_id
        teacher_memberships = list(self.db.institute_members.find({
            "institute_id": generic_institute_id,
            "workspace_type": "INDIVIDUAL_TEACHER",
            "class_id": {"$exists": False}
        }))
        
        logging.info(f"Encontradas {len(teacher_memberships)} membresías de profesores sin clase vinculada")
        
        for membership in teacher_memberships:
            try:
                # Buscar clase personal del profesor
                personal_class = self.db.classes.find_one({
                    "created_by": membership['user_id'],
                    "institute_id": generic_institute_id
                })
                
                if personal_class:
                    # Vincular clase con membresía
                    result = self.db.institute_members.update_one(
                        {"_id": membership['_id']},
                        {"$set": {"class_id": personal_class['_id']}}
                    )
                    
                    if result.modified_count > 0:
                        self.migration_stats['classes_linked'] += 1
                        logging.info(f"Clase {personal_class['name']} vinculada con workspace")
                
            except Exception as e:
                logging.error(f"Error al vincular clase para membresía {membership['_id']}: {str(e)}")
                self.migration_stats['errors'] += 1

    def _verify_data_integrity(self):
        """Verifica la integridad de los datos después de la migración"""
        logging.info("Paso 6: Verificando integridad de datos...")
        
        # Verificar que no queden usuarios con roles obsoletos
        obsolete_roles = ['individual_teacher', 'individual_student', 'super_admin', 'system']
        for role in obsolete_roles:
            count = self.db.users.count_documents({"role": role})
            if count > 0:
                logging.warning(f"Aún existen {count} usuarios con rol obsoleto '{role}'")
        
        # Verificar que todas las membresías tengan workspace_type
        memberships_without_workspace = self.db.institute_members.count_documents({
            "workspace_type": {"$exists": False}
        })
        if memberships_without_workspace > 0:
            logging.warning(f"Existen {memberships_without_workspace} membresías sin workspace_type")
        
        # Verificar que todos los usuarios tengan al menos un workspace individual
        users_without_individual_workspace = []
        for user in self.db.users.find({}):
            individual_workspaces = self.db.institute_members.count_documents({
                "user_id": user['_id'],
                "workspace_type": {"$in": ["INDIVIDUAL_STUDENT", "INDIVIDUAL_TEACHER"]}
            })
            if individual_workspaces == 0:
                users_without_individual_workspace.append(user['email'])
        
        if users_without_individual_workspace:
            logging.warning(f"Usuarios sin workspace individual: {users_without_individual_workspace}")
        
        logging.info("Verificación de integridad completada")

    def _get_or_create_generic_entities(self):
        """Obtiene o crea las entidades genéricas necesarias"""
        # Buscar o crear instituto genérico
        generic_institute = self.db.institutes.find_one({"name": "Instituto Genérico"})
        if not generic_institute:
            institute_data = {
                "name": "Instituto Genérico",
                "description": "Instituto para usuarios individuales",
                "created_at": datetime.utcnow()
            }
            result = self.db.institutes.insert_one(institute_data)
            institute_id = str(result.inserted_id)
        else:
            institute_id = str(generic_institute['_id'])
        
        # Buscar o crear materia genérica
        generic_subject = self.db.subjects.find_one({"name": "Materia General"})
        if not generic_subject:
            subject_data = {
                "name": "Materia General",
                "description": "Materia genérica para clases personales",
                "created_at": datetime.utcnow()
            }
            result = self.db.subjects.insert_one(subject_data)
            subject_id = str(result.inserted_id)
        else:
            subject_id = str(generic_subject['_id'])
        
        # Buscar o crear sección genérica
        generic_section = self.db.sections.find_one({"name": "Sección General"})
        if not generic_section:
            section_data = {
                "name": "Sección General",
                "description": "Sección genérica",
                "created_at": datetime.utcnow()
            }
            result = self.db.sections.insert_one(section_data)
            section_id = str(result.inserted_id)
        else:
            section_id = str(generic_section['_id'])
        
        # Buscar o crear período académico genérico
        generic_period = self.db.academic_periods.find_one({"name": "Período General"})
        if not generic_period:
            period_data = {
                "name": "Período General",
                "description": "Período académico genérico",
                "start_date": datetime.utcnow(),
                "end_date": datetime.utcnow(),
                "created_at": datetime.utcnow()
            }
            result = self.db.academic_periods.insert_one(period_data)
            period_id = str(result.inserted_id)
        else:
            period_id = str(generic_period['_id'])
        
        # Buscar o crear nivel genérico
        generic_level = self.db.levels.find_one({"name": "Nivel General"})
        if not generic_level:
            level_data = {
                "name": "Nivel General",
                "description": "Nivel genérico",
                "created_at": datetime.utcnow()
            }
            result = self.db.levels.insert_one(level_data)
            level_id = str(result.inserted_id)
        else:
            level_id = str(generic_level['_id'])
        
        return {
            "institute_id": institute_id,
            "subject_id": subject_id,
            "section_id": section_id,
            "academic_period_id": period_id,
            "level_id": level_id
        }

    def _print_migration_stats(self):
        """Imprime estadísticas de la migración"""
        logging.info("=== Estadísticas de Migración ===")
        logging.info(f"Usuarios migrados: {self.migration_stats['users_migrated']}")
        logging.info(f"Membresías actualizadas: {self.migration_stats['memberships_updated']}")
        logging.info(f"Clases vinculadas: {self.migration_stats['classes_linked']}")
        logging.info(f"Errores encontrados: {self.migration_stats['errors']}")
        logging.info("=================================")

def main():
    """Función principal"""
    try:
        migration = WorkspaceRefactoringMigration()
        migration.run_migration()
        print("\n✅ Migración completada exitosamente")
        print("📋 Revisa el archivo 'migration_workspace_refactoring.log' para detalles")
    except Exception as e:
        print(f"\n❌ Error durante la migración: {str(e)}")
        print("📋 Revisa el archivo 'migration_workspace_refactoring.log' para detalles")
        sys.exit(1)

if __name__ == "__main__":
    main()