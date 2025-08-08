from datetime import datetime
from bson import ObjectId
from src.shared.database import get_db


def migrate_study_plans_to_unified():
    """
    Migra todos los documentos de 'study_plans' a 'study_plans_per_subject'
    """
    db = get_db()

    old_plans_cursor = db.study_plans.find({})
    migrated = 0
    for plan in old_plans_cursor:
        try:
            unified_plan = {
                "version": "1.0",
                "name": plan.get("title", "Plan Personal"),
                "description": plan.get("description", ""),
                # user_id → author_id
                "author_id": plan.get("user_id") if isinstance(plan.get("user_id"), ObjectId) else ObjectId(plan.get("user_id")) if plan.get("user_id") else None,
                "workspace_id": plan.get("workspace_id"),
                "workspace_type": "INDIVIDUAL_STUDENT",
                "is_personal": True,
                "objectives": plan.get("objectives", []),
                "institute_id": plan.get("institute_id"),
                "subject_id": None,
                "status": plan.get("status", "active"),
                "created_at": plan.get("created_at", datetime.utcnow()),
                "updated_at": plan.get("updated_at", datetime.utcnow())
            }

            # Normalizar tipos
            if unified_plan["workspace_id"] and not isinstance(unified_plan["workspace_id"], ObjectId):
                unified_plan["workspace_id"] = ObjectId(unified_plan["workspace_id"])
            if unified_plan["institute_id"] and not isinstance(unified_plan["institute_id"], ObjectId):
                try:
                    unified_plan["institute_id"] = ObjectId(unified_plan["institute_id"])
                except Exception:
                    unified_plan["institute_id"] = None

            db.study_plans_per_subject.insert_one(unified_plan)
            migrated += 1
        except Exception as e:
            print(f"Error migrando plan {plan.get('_id')}: {e}")

    old_count = db.study_plans.count_documents({})
    new_count = db.study_plans_per_subject.count_documents({"is_personal": True})

    if old_count <= new_count and migrated == old_count:
        print(f"Migración exitosa: {migrated} planes migrados")
        return True
    else:
        print(f"Error en migración: {old_count} originales vs {new_count} migrados (migrados en esta corrida: {migrated})")
        return False


def rollback_migration():
    """
    Rollback: elimina planes personales de study_plans_per_subject
    """
    db = get_db()
    result = db.study_plans_per_subject.delete_many({"is_personal": True})
    print(f"Rollback completado: {result.deleted_count} documentos eliminados")


def validate_migration():
    """
    Valida que la migración fue exitosa
    """
    db = get_db()

    old_count = db.study_plans.count_documents({})
    new_personal_count = db.study_plans_per_subject.count_documents({"is_personal": True})

    invalid_docs = db.study_plans_per_subject.count_documents({
        "is_personal": True,
        "$or": [
            {"author_id": {"$exists": False}},
            {"workspace_id": {"$exists": False}}
        ]
    })

    print({
        "migration_complete": old_count == new_personal_count,
        "invalid_documents": invalid_docs,
        "total_migrated": new_personal_count
    })
    return {
        "migration_complete": old_count == new_personal_count,
        "invalid_documents": invalid_docs,
        "total_migrated": new_personal_count
    }