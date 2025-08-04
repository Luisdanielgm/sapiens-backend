#!/usr/bin/env python3
"""
Script de migración para actualizar el sistema de registro de usuarios
y asegurar que todos los usuarios existentes tengan los workspaces correctos.

Este script:
1. Verifica que todos los usuarios tengan workspaces por defecto
2. Crea workspaces faltantes según el rol del usuario
3. Actualiza membresías existentes con campos de workspace
4. Vincula clases personales con workspaces de profesores

Ejecución: python scripts/migrate_user_registration_workspaces.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import get_db
from src.institute.services import GenericAcademicService
from src.members.services import MembershipService
from src.classes.services import ClassService
from bson import ObjectId
from datetime import datetime
import uuid
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_user_workspaces():
    """
    Migra todos los usuarios existentes para asegurar que tengan
    los workspaces por defecto según su rol.
    """
    try:
        db = get_db()
        generic_service = GenericAcademicService()
        membership_service = MembershipService()
        class_service = ClassService()
        
        # Obtener entidades genéricas
        logger.info("Obteniendo entidades genéricas...")
        generic_entities = generic_service.get_or_create_generic_entities()
        generic_institute_id = generic_entities["institute_id"]
        
        # Obtener todos los usuarios
        users = list(db.users.find({}))
        logger.info(f"Procesando {len(users)} usuarios...")
        
        stats = {
            'processed': 0,
            'student_workspaces_created': 0,
            'teacher_workspaces_created': 0,
            'classes_created': 0,
            'errors': 0
        }
        
        for user in users:
            try:
                user_id = str(user['_id'])
                user_role = user.get('role', '')
                user_name = user.get('name', 'Usuario')
                
                logger.info(f"Procesando usuario: {user.get('email')} (Rol: {user_role})")
                
                # Verificar si ya tiene workspace de estudiante individual
                existing_student_workspace = db.institute_members.find_one({
                    'user_id': ObjectId(user_id),
                    'institute_id': ObjectId(generic_institute_id),
                    'workspace_type': 'INDIVIDUAL_STUDENT'
                })
                
                # Crear workspace de estudiante individual si no existe
                if not existing_student_workspace:
                    logger.info(f"Creando workspace INDIVIDUAL_STUDENT para {user.get('email')}")
                    membership_service.add_institute_member({
                        "institute_id": generic_institute_id,
                        "user_id": user_id,
                        "role": "student",
                        "workspace_type": "INDIVIDUAL_STUDENT",
                        "workspace_name": f"Aprendizaje de {user_name}"
                    })
                    stats['student_workspaces_created'] += 1
                
                # Para profesores, crear workspace de profesor individual
                if user_role == 'TEACHER':
                    existing_teacher_workspace = db.institute_members.find_one({
                        'user_id': ObjectId(user_id),
                        'institute_id': ObjectId(generic_institute_id),
                        'workspace_type': 'INDIVIDUAL_TEACHER'
                    })
                    
                    if not existing_teacher_workspace:
                        logger.info(f"Creando workspace INDIVIDUAL_TEACHER para {user.get('email')}")
                        teacher_member_id = membership_service.add_institute_member({
                            "institute_id": generic_institute_id,
                            "user_id": user_id,
                            "role": "teacher",
                            "workspace_type": "INDIVIDUAL_TEACHER",
                            "workspace_name": f"Clases de {user_name}"
                        })
                        stats['teacher_workspaces_created'] += 1
                        
                        # Buscar clase personal existente
                        existing_class = db.classes.find_one({
                            'created_by': user['_id'],
                            'institute_id': ObjectId(generic_institute_id),
                            'name': {'$regex': f'Clase Personal de {user_name}', '$options': 'i'}
                        })
                        
                        class_id = None
                        if existing_class:
                            class_id = str(existing_class['_id'])
                            logger.info(f"Clase personal existente encontrada: {class_id}")
                        else:
                            # Crear nueva clase personal
                            try:
                                class_data = {
                                    "institute_id": ObjectId(generic_entities["institute_id"]),
                                    "subject_id": ObjectId(generic_entities["subject_id"]),
                                    "section_id": ObjectId(generic_entities["section_id"]),
                                    "academic_period_id": ObjectId(generic_entities["academic_period_id"]),
                                    "level_id": ObjectId(generic_entities["level_id"]),
                                    "name": f"Clase Personal de {user_name}",
                                    "access_code": str(uuid.uuid4())[:8],
                                    "created_by": user['_id']
                                }
                                success_class, class_id = class_service.create_class(class_data)
                                if success_class:
                                    logger.info(f"Clase personal creada: {class_id}")
                                    stats['classes_created'] += 1
                                else:
                                    logger.warning(f"No se pudo crear clase personal para {user.get('email')}")
                            except Exception as class_error:
                                logger.error(f"Error al crear clase personal: {str(class_error)}")
                        
                        # Vincular clase con workspace si existe
                        if class_id and teacher_member_id:
                            try:
                                membership_service.update_institute_member(teacher_member_id, {"class_id": class_id})
                                logger.info(f"Clase {class_id} vinculada con workspace {teacher_member_id}")
                            except Exception as link_error:
                                logger.error(f"Error al vincular clase con workspace: {str(link_error)}")
                    
                    else:
                        # Verificar si el workspace existente tiene class_id
                        if not existing_teacher_workspace.get('class_id'):
                            # Buscar clase personal y vincularla
                            existing_class = db.classes.find_one({
                                'created_by': user['_id'],
                                'institute_id': ObjectId(generic_institute_id)
                            })
                            
                            if existing_class:
                                try:
                                    membership_service.update_institute_member(
                                        str(existing_teacher_workspace['_id']), 
                                        {"class_id": str(existing_class['_id'])}
                                    )
                                    logger.info(f"Clase existente vinculada con workspace existente")
                                except Exception as link_error:
                                    logger.error(f"Error al vincular clase existente: {str(link_error)}")
                
                stats['processed'] += 1
                
            except Exception as user_error:
                logger.error(f"Error procesando usuario {user.get('email', 'unknown')}: {str(user_error)}")
                stats['errors'] += 1
                continue
        
        # Mostrar estadísticas finales
        logger.info("\n=== MIGRACIÓN COMPLETADA ===")
        logger.info(f"Usuarios procesados: {stats['processed']}")
        logger.info(f"Workspaces de estudiante creados: {stats['student_workspaces_created']}")
        logger.info(f"Workspaces de profesor creados: {stats['teacher_workspaces_created']}")
        logger.info(f"Clases personales creadas: {stats['classes_created']}")
        logger.info(f"Errores: {stats['errors']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error en migración de workspaces de usuarios: {str(e)}")
        return False

def verify_migration():
    """
    Verifica que la migración se haya ejecutado correctamente.
    """
    try:
        db = get_db()
        generic_service = GenericAcademicService()
        
        # Obtener entidades genéricas
        generic_entities = generic_service.get_or_create_generic_entities()
        generic_institute_id = generic_entities["institute_id"]
        
        # Contar usuarios por rol
        users_by_role = {}
        for user in db.users.find({}):
            role = user.get('role', 'unknown')
            users_by_role[role] = users_by_role.get(role, 0) + 1
        
        # Contar workspaces por tipo
        workspaces_by_type = {}
        for workspace in db.institute_members.find({'institute_id': ObjectId(generic_institute_id)}):
            ws_type = workspace.get('workspace_type', 'unknown')
            workspaces_by_type[ws_type] = workspaces_by_type.get(ws_type, 0) + 1
        
        logger.info("\n=== VERIFICACIÓN DE MIGRACIÓN ===")
        logger.info(f"Usuarios por rol: {users_by_role}")
        logger.info(f"Workspaces por tipo: {workspaces_by_type}")
        
        # Verificar que todos los usuarios tengan al menos un workspace INDIVIDUAL_STUDENT
        users_without_student_workspace = []
        for user in db.users.find({}):
            student_workspace = db.institute_members.find_one({
                'user_id': user['_id'],
                'institute_id': ObjectId(generic_institute_id),
                'workspace_type': 'INDIVIDUAL_STUDENT'
            })
            if not student_workspace:
                users_without_student_workspace.append(user.get('email', str(user['_id'])))
        
        if users_without_student_workspace:
            logger.warning(f"Usuarios sin workspace de estudiante: {users_without_student_workspace}")
        else:
            logger.info("✓ Todos los usuarios tienen workspace de estudiante")
        
        # Verificar que todos los profesores tengan workspace de profesor
        teachers_without_teacher_workspace = []
        for user in db.users.find({'role': 'TEACHER'}):
            teacher_workspace = db.institute_members.find_one({
                'user_id': user['_id'],
                'institute_id': ObjectId(generic_institute_id),
                'workspace_type': 'INDIVIDUAL_TEACHER'
            })
            if not teacher_workspace:
                teachers_without_teacher_workspace.append(user.get('email', str(user['_id'])))
        
        if teachers_without_teacher_workspace:
            logger.warning(f"Profesores sin workspace de profesor: {teachers_without_teacher_workspace}")
        else:
            logger.info("✓ Todos los profesores tienen workspace de profesor")
        
        return len(users_without_student_workspace) == 0 and len(teachers_without_teacher_workspace) == 0
        
    except Exception as e:
        logger.error(f"Error en verificación: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Iniciando migración de workspaces de usuarios...")
    
    # Ejecutar migración
    success = migrate_user_workspaces()
    
    if success:
        logger.info("Migración completada exitosamente")
        
        # Verificar migración
        logger.info("Verificando migración...")
        verification_success = verify_migration()
        
        if verification_success:
            logger.info("✓ Verificación exitosa - Migración completada correctamente")
        else:
            logger.warning("⚠ Verificación encontró problemas - Revisar logs")
    else:
        logger.error("❌ Error en la migración")
        sys.exit(1)