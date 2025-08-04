#!/usr/bin/env python3
"""
Script de migración para eliminar roles obsoletos del sistema.

Este script:
1. Elimina roles obsoletos de constants.py
2. Migra usuarios con roles obsoletos a roles válidos
3. Actualiza referencias en la base de datos
4. Limpia datos inconsistentes

Roles a eliminar: SYSTEM, SUPER_ADMIN, INDIVIDUAL_TEACHER, INDIVIDUAL_STUDENT
Roles válidos: TEACHER, STUDENT, INSTITUTE_ADMIN

Ejecución: python scripts/migrate_obsolete_roles.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import get_db
from bson import ObjectId
import logging
import re

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Mapeo de roles obsoletos a roles válidos
ROLE_MIGRATION_MAP = {
    'SYSTEM': 'INSTITUTE_ADMIN',  # Los usuarios SYSTEM se convierten en admins
    'SUPER_ADMIN': 'INSTITUTE_ADMIN',  # Los super admins se convierten en admins
    'INDIVIDUAL_TEACHER': 'TEACHER',  # Los profesores individuales se convierten en profesores
    'INDIVIDUAL_STUDENT': 'STUDENT'   # Los estudiantes individuales se convierten en estudiantes
}

OBSOLETE_ROLES = list(ROLE_MIGRATION_MAP.keys())
VALID_ROLES = ['TEACHER', 'STUDENT', 'INSTITUTE_ADMIN']

def update_constants_file():
    """
    Actualiza el archivo constants.py para eliminar roles obsoletos.
    """
    try:
        constants_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'src', 'shared', 'constants.py'
        )
        
        if not os.path.exists(constants_path):
            logger.error(f"Archivo constants.py no encontrado en: {constants_path}")
            return False
        
        # Leer archivo actual
        with open(constants_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info("Actualizando constants.py...")
        
        # Crear backup
        backup_path = constants_path + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Backup creado en: {backup_path}")
        
        # Actualizar contenido
        updated_content = content
        
        # Buscar y actualizar la definición de USER_ROLES
        user_roles_pattern = r'USER_ROLES\s*=\s*\[(.*?)\]'
        match = re.search(user_roles_pattern, updated_content, re.DOTALL)
        
        if match:
            # Crear nueva lista de roles válidos
            new_roles_list = '[\n    "TEACHER",\n    "STUDENT",\n    "INSTITUTE_ADMIN"\n]'
            updated_content = re.sub(user_roles_pattern, f'USER_ROLES = {new_roles_list}', updated_content, flags=re.DOTALL)
            logger.info("USER_ROLES actualizado")
        
        # Eliminar constantes de roles obsoletos si existen
        for role in OBSOLETE_ROLES:
            # Eliminar líneas que definen constantes de roles obsoletos
            pattern = rf'^{role}\s*=.*$'
            updated_content = re.sub(pattern, '', updated_content, flags=re.MULTILINE)
        
        # Limpiar líneas vacías múltiples
        updated_content = re.sub(r'\n\s*\n\s*\n', '\n\n', updated_content)
        
        # Escribir archivo actualizado
        with open(constants_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        logger.info("constants.py actualizado exitosamente")
        return True
        
    except Exception as e:
        logger.error(f"Error actualizando constants.py: {str(e)}")
        return False

def migrate_user_roles():
    """
    Migra usuarios con roles obsoletos a roles válidos.
    """
    try:
        db = get_db()
        
        # Obtener usuarios con roles obsoletos
        users_with_obsolete_roles = list(db.users.find({'role': {'$in': OBSOLETE_ROLES}}))
        
        logger.info(f"Encontrados {len(users_with_obsolete_roles)} usuarios con roles obsoletos")
        
        stats = {
            'migrated': 0,
            'errors': 0,
            'by_role': {}
        }
        
        for user in users_with_obsolete_roles:
            try:
                old_role = user['role']
                new_role = ROLE_MIGRATION_MAP[old_role]
                
                # Actualizar rol del usuario
                result = db.users.update_one(
                    {'_id': user['_id']},
                    {'$set': {'role': new_role}}
                )
                
                if result.modified_count > 0:
                    logger.info(f"Usuario {user.get('email', str(user['_id']))} migrado de {old_role} a {new_role}")
                    stats['migrated'] += 1
                    stats['by_role'][old_role] = stats['by_role'].get(old_role, 0) + 1
                else:
                    logger.warning(f"No se pudo actualizar usuario {user.get('email', str(user['_id']))}")
                    stats['errors'] += 1
                
            except Exception as user_error:
                logger.error(f"Error migrando usuario {user.get('email', 'unknown')}: {str(user_error)}")
                stats['errors'] += 1
                continue
        
        logger.info(f"Migración de roles completada: {stats['migrated']} usuarios migrados, {stats['errors']} errores")
        logger.info(f"Migración por rol: {stats['by_role']}")
        
        return stats['errors'] == 0
        
    except Exception as e:
        logger.error(f"Error en migración de roles: {str(e)}")
        return False

def clean_obsolete_role_references():
    """
    Limpia referencias a roles obsoletos en otras colecciones.
    """
    try:
        db = get_db()
        
        logger.info("Limpiando referencias a roles obsoletos...")
        
        # Limpiar referencias en institute_members si existen campos de rol
        institute_members_updated = 0
        for member in db.institute_members.find({'role': {'$in': OBSOLETE_ROLES}}):
            try:
                old_role = member['role']
                # Convertir roles de instituto_members (que usan minúsculas)
                if old_role in ['INDIVIDUAL_TEACHER', 'SUPER_ADMIN', 'SYSTEM']:
                    new_role = 'teacher' if old_role == 'INDIVIDUAL_TEACHER' else 'admin'
                elif old_role == 'INDIVIDUAL_STUDENT':
                    new_role = 'student'
                else:
                    new_role = 'student'  # Por defecto
                
                result = db.institute_members.update_one(
                    {'_id': member['_id']},
                    {'$set': {'role': new_role}}
                )
                
                if result.modified_count > 0:
                    institute_members_updated += 1
                    logger.info(f"Membresía actualizada: {old_role} -> {new_role}")
                    
            except Exception as member_error:
                logger.error(f"Error actualizando membresía: {str(member_error)}")
                continue
        
        logger.info(f"Referencias en institute_members actualizadas: {institute_members_updated}")
        
        # Verificar otras colecciones que puedan tener referencias a roles
        collections_to_check = ['classes', 'virtual_modules', 'assignments']
        
        for collection_name in collections_to_check:
            if collection_name in db.list_collection_names():
                collection = db[collection_name]
                
                # Buscar documentos que puedan tener campos de rol
                docs_with_roles = list(collection.find({
                    '$or': [
                        {'role': {'$in': OBSOLETE_ROLES}},
                        {'user_role': {'$in': OBSOLETE_ROLES}},
                        {'created_by_role': {'$in': OBSOLETE_ROLES}}
                    ]
                }))
                
                if docs_with_roles:
                    logger.warning(f"Encontrados {len(docs_with_roles)} documentos en {collection_name} con roles obsoletos")
                    # Aquí podrías agregar lógica específica para limpiar cada colección
        
        return True
        
    except Exception as e:
        logger.error(f"Error limpiando referencias: {str(e)}")
        return False

def verify_migration():
    """
    Verifica que la migración se haya ejecutado correctamente.
    """
    try:
        db = get_db()
        
        # Verificar que no queden usuarios con roles obsoletos
        remaining_obsolete_users = list(db.users.find({'role': {'$in': OBSOLETE_ROLES}}))
        
        if remaining_obsolete_users:
            logger.error(f"Aún quedan {len(remaining_obsolete_users)} usuarios con roles obsoletos")
            for user in remaining_obsolete_users:
                logger.error(f"Usuario con rol obsoleto: {user.get('email', str(user['_id']))} - {user['role']}")
            return False
        
        # Contar usuarios por rol válido
        role_counts = {}
        for role in VALID_ROLES:
            count = db.users.count_documents({'role': role})
            role_counts[role] = count
        
        logger.info("\n=== VERIFICACIÓN DE MIGRACIÓN ===")
        logger.info(f"Usuarios por rol válido: {role_counts}")
        logger.info("✓ No se encontraron usuarios con roles obsoletos")
        
        # Verificar institute_members
        obsolete_members = list(db.institute_members.find({'role': {'$in': OBSOLETE_ROLES}}))
        if obsolete_members:
            logger.warning(f"Encontradas {len(obsolete_members)} membresías con roles obsoletos")
        else:
            logger.info("✓ No se encontraron membresías con roles obsoletos")
        
        return len(remaining_obsolete_users) == 0
        
    except Exception as e:
        logger.error(f"Error en verificación: {str(e)}")
        return False

def main():
    """
    Función principal que ejecuta toda la migración.
    """
    logger.info("Iniciando migración de roles obsoletos...")
    
    # Paso 1: Migrar roles de usuarios
    logger.info("\n=== PASO 1: MIGRAR ROLES DE USUARIOS ===")
    user_migration_success = migrate_user_roles()
    
    if not user_migration_success:
        logger.error("Error en migración de roles de usuarios")
        return False