"""
Script de migración de evaluaciones (dentro de sapiens-backend/scripts):
- Agrega defaults solo si faltan campos.
  * score_source: 'manual'
  * blocking_scope: 'none'
  * allow_manual_override: True
  * pass_score: 0

Ejecución (desde sapiens-backend):
    python scripts/migrate_evaluations_defaults.py
"""
from src.shared.database import get_db


def main():
    db = get_db()
    evaluations = db.evaluations

    defaults = [
        ("score_source", "manual"),
        ("blocking_scope", "none"),
        ("allow_manual_override", True),
        ("pass_score", 0),
    ]

    total_updated = 0
    for field, value in defaults:
        result = evaluations.update_many(
            {field: {"$exists": False}},
            {"$set": {field: value}},
            upsert=False
        )
        total_updated += result.modified_count
        print(f"Campo '{field}' actualizado en {result.modified_count} evaluaciones (default={value}).")

    print(f"Total de campos aplicados: {total_updated}")


if __name__ == "__main__":
    main()
