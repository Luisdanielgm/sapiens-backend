#!/usr/bin/env python3
"""
Script de migración para refactorización de workspaces

Este script:
1. Elimina roles obsoletos (SYSTEM, SUPER_ADMIN, INDIVIDUAL_TEACHER, INDIVIDUAL_STUDENT)
2. Migra usuarios existentes con roles obsoletos
3. Crea workspaces por defecto para usuarios existentes
4. Actualiza membresías existentes con información de workspace

Ejecución:
    python scripts/workspace_migration.py
"""

import sys
import os
from datetime import datetime
from bson.objectid import ObjectId

# Agregar el directorio raíz al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import get_db
from src.shared.constants import WORKSPACE_TYPES

def log_migration(message):
    """Log de migración con timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def backup_collections():
    """Crear backup de colecciones críticas antes de la migración"""
    log_migration("Iniciando backup de colecciones...")
    db = get_db()
    
    # Backup de usuarios
    users = list(db.users.find())
    db.users_backup_workspace_migration.drop()
    if users:
        db.users_backup_workspace_migration.insert_many(users)
        log_migration(f"Backup de {len(users)} usuarios creado")
    
    # Backup de institute_members
    institute_members = list(db.institute_members.find())
    db.institute_members_backup_workspace_migration.drop()
    if institute_members:
        db.institute_members_backup_workspace_migration.insert_many(institute_members)
        log_migration(f"Backup de {len(institute_members)} membresías de instituto creado")
    
    # Backup de class_members
    class_members = list(db.class_members.find())
    db.class_members_backup_workspace_migration.drop()
    if class_members:
        db.class_members_backup_workspace_migration.insert_many(class_members)
        log_migration(f"Backup de {len(class_members)} membresías de clase creado")

def migrate_obsolete_user_roles():
    """Migrar usuarios con roles obsoletos"""
    log_migration("Migrando usuarios con roles obsoletos...")
    db = get_db()
    
    obsolete_roles = ['SYSTEM', 'SUPER_ADMIN', 'INDIVIDUAL_TEACHER', 'INDIVIDUAL_STUDENT']
    
    for obsolete_role in obsolete_roles:
        users_with_obsolete_role = list(db.users.find({"role": obsolete_role}))
        
        if users_with_obsolete_role:
            log_migration(f"Encontrados {len(users_with_obsolete_role)} usuarios con rol {obsolete_role}")
            
            for user in users_with_obsolete_role:
                new_role = None
                
                if obsolete_role in ['SYSTEM', 'SUPER_ADMIN']:
                    new_role = 'admin'
                elif obsolete_role == 'INDIVIDUAL_TEACHER':
                    new_role = 'teacher'
                elif obsolete_role == 'INDIVIDUAL_STUDENT':
                    new_role = 'student'
                
                if new_role:
                    # Actualizar rol del usuario
                    db.users.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"role": new_role}}
                    )
                    log_migration(f"Usuario {user.get('email', user['_id'])} migrado de {obsolete_role} a {new_role}")

def create_default_workspaces_for_existing_users():
    """Crear workspaces por defecto para usuarios existentes que no los tengan"""
    log_migration("Creando workspaces por defecto para usuarios existentes...")
    db = get_db()
    
    # Obtener todos los usuarios
    users = list(db.users.find())
    
    for user in users:
        user_id = user["_id"]
        user_role = user.get("role")
        
        # Verificar si ya tiene workspaces
        existing_workspaces = list(db.institute_members.find({"user_id": user_id}))
        
        if not existing_workspaces:
            log_migration(f"Creando workspaces para usuario {user.get('email', user_id)}")
            
            # Crear workspace INDIVIDUAL_STUDENT para todos
            student_workspace = {
                "_id": ObjectId(),
                "institute_id": ObjectId(),  # ID único para workspace individual
                "user_id": user_id,
                "role": "student",
                "workspace_type": WORKSPACE_TYPES["INDIVIDUAL_STUDENT"],
                "workspace_name": f"Workspace Personal - {user.get('first_name', 'Usuario')}",
                "class_id": None,
                "status": "active",
                "joined_at": datetime.utcnow()
            }
            
            db.institute_members.insert_one(student_workspace)
            log_migration(f"Workspace INDIVIDUAL_STUDENT creado para {user.get('email', user_id)}")
            
            # Si es teacher, crear también workspace INDIVIDUAL_TEACHER
            if user_role == 'teacher':
                teacher_workspace = {
                    "_id": ObjectId(),
                    "institute_id": ObjectId(),  # ID único para workspace individual
                    "user_id": user_id,
                    "role": "teacher",
                    "workspace_type": WORKSPACE_TYPES["INDIVIDUAL_TEACHER"],
                    "workspace_name": f"Workspace Docente - {user.get('first_name', 'Profesor')}",
                    "class_id": None,
                    "status": "active",
                    "joined_at": datetime.utcnow()
                }
                
                db.institute_members.insert_one(teacher_workspace)
                log_migration(f"Workspace INDIVIDUAL_TEACHER creado para {user.get('email', user_id)}")
                
                # Crear clase asociada al workspace de teacher
                class_doc = {
                    "_id": ObjectId(),
                    "name": f"Clase Personal - {user.get('first_name', 'Profesor')}",
                    "description": "Clase personal para contenido individual",
                    "institute_id": teacher_workspace["institute_id"],
                    "teacher_id": user_id,
                    "status": "active",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                
                db.classes.insert_one(class_doc)
                
                # Actualizar workspace con class_id
                db.institute_members.update_one(
                    {"_id": teacher_workspace["_id"]},
                    {"$set": {"class_id": class_doc["_id"]}}
                )
                
                log_migration(f"Clase personal creada para teacher {user.get('email', user_id)}")

def update_existing_institute_memberships():
    """Actualizar membresías existentes de institutos con información de workspace"""
    log_migration("Actualizando membresías existentes de institutos...")
    db = get_db()
    
    # Obtener todas las membresías que no tienen workspace_type
    memberships_without_workspace = list(db.institute_members.find({
        "workspace_type": {"$exists": False}
    }))
    
    log_migration(f"Encontradas {len(memberships_without_workspace)} membresías sin workspace_type")
    
    for membership in memberships_without_workspace:
        # Obtener información del instituto
        institute = db.institutes.find_one({"_id": membership["institute_id"]})
        
        if institute:
            workspace_name = institute.get("name", "Instituto")
            
            # Actualizar con información de workspace
            update_data = {
                "workspace_type": WORKSPACE_TYPES["INSTITUTE"],
                "workspace_name": workspace_name
            }
            
            # Si no tiene class_id y es teacher, buscar si tiene clases en el instituto
            if membership.get("role") == "teacher" and not membership.get("class_id"):
                teacher_class = db.classes.find_one({
                    "institute_id": membership["institute_id"],
                    "teacher_id": membership["user_id"]
                })
                
                if teacher_class:
                    update_data["class_id"] = teacher_class["_id"]
            
            db.institute_members.update_one(
                {"_id": membership["_id"]},
                {"$set": update_data}
            )
            
            log_migration(f"Membresía actualizada para usuario {membership['user_id']} en instituto {workspace_name}")

def verify_migration():
    """Verificar que la migración se completó correctamente"""
    log_migration("Verificando migración...")
    db = get_db()
    
    # Verificar que no hay usuarios con roles obsoletos
    obsolete_roles = ['SYSTEM', 'SUPER_ADMIN', 'INDIVIDUAL_TEACHER', 'INDIVIDUAL_STUDENT']
    users_with_obsolete_roles = db.users.count_documents({"role": {"$in": obsolete_roles}})
    
    if users_with_obsolete_roles > 0:
        log_migration(f"⚠️  ADVERTENCIA: Aún hay {users_with_obsolete_roles} usuarios con roles obsoletos")
    else:
        log_migration("✅ No hay usuarios con roles obsoletos")
    
    # Verificar que todos los usuarios tienen al menos un workspace
    total_users = db.users.count_documents({})
    users_with_workspaces = db.users.aggregate([
        {
            "$lookup": {
                "from": "institute_members",
                "localField": "_id",
                "foreignField": "user_id",
                "as": "workspaces"
            }
        },
        {
            "$match": {
                "workspaces": {"$ne": []}
            }
        },
        {
            "$count": "users_with_workspaces"
        }
    ])
    
    users_with_workspaces_count = list(users_with_workspaces)
    if users_with_workspaces_count:
        users_with_workspaces_count = users_with_workspaces_count[0]["users_with_workspaces"]
    else:
        users_with_workspaces_count = 0
    
    if users_with_workspaces_count < total_users:
        log_migration(f"⚠️  ADVERTENCIA: {total_users - users_with_workspaces_count} usuarios sin workspaces")
    else:
        log_migration(f"✅ Todos los {total_users} usuarios tienen workspaces")
    
    # Verificar que todas las membresías tienen workspace_type
    memberships_without_workspace_type = db.institute_members.count_documents({
        "workspace_type": {"$exists": False}
    })
    
    if memberships_without_workspace_type > 0:
        log_migration(f"⚠️  ADVERTENCIA: {memberships_without_workspace_type} membresías sin workspace_type")
    else:
        log_migration("✅ Todas las membresías tienen workspace_type")

def main():
    """Función principal de migración"""
    log_migration("=== INICIANDO MIGRACIÓN DE WORKSPACES ===")
    
    try:
        # 1. Crear backup
        backup_collections()
        
        # 2. Migrar roles obsoletos
        migrate_obsolete_user_roles()
        
        # 3. Crear workspaces por defecto
        create_default_workspaces_for_existing_users()
        
        # 4. Actualizar membresías existentes
        update_existing_institute_memberships()
        
        # 5. Verificar migración
        verify_migration()
        
        log_migration("=== MIGRACIÓN COMPLETADA EXITOSAMENTE ===")
        
    except Exception as e:
        log_migration(f"❌ ERROR EN MIGRACIÓN: {str(e)}")
        log_migration("Se recomienda restaurar desde backup si es necesario")
        raise

if __name__ == "__main__":
    main()