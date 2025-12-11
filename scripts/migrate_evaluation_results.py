"""
Migración de evaluation_submissions -> evaluation_results.
- Upsert por (evaluation_id, student_id)
- Usa final_grade/grade/ai_score como score
- source: ai | content_result | manual

Ejecución (desde sapiens-backend):
    python scripts/migrate_evaluation_results.py
"""
from datetime import datetime
from bson import ObjectId
from src.shared.database import get_db


def detect_source(submission: dict) -> str:
    if submission.get("ai_score") is not None:
        return "ai"
    if submission.get("submission_type") == "content_result":
        return "content_result"
    return "manual"


def migrate_submission(submission: dict, db) -> bool:
    evaluation_id = submission.get("evaluation_id")
    student_id = submission.get("student_id")
    if not evaluation_id or not student_id:
        return False

    score = submission.get("final_grade")
    if score is None:
        score = submission.get("grade")
    if score is None:
        score = submission.get("ai_score")
    if score is None:
        score = 0.0

    source = detect_source(submission)
    status = submission.get("status", "completed")

    result_doc = {
        "evaluation_id": ObjectId(evaluation_id),
        "student_id": ObjectId(student_id),
        "score": score,
        "source": source,
        "status": status,
        "submission_id": submission.get("_id"),
        "recorded_at": submission.get("graded_at") or submission.get("created_at") or datetime.now(),
    }

    db.evaluation_results.update_one(
        {"evaluation_id": result_doc["evaluation_id"], "student_id": result_doc["student_id"]},
        {"$set": result_doc},
        upsert=True,
    )
    return True


def main():
    db = get_db()
    submissions = db.evaluation_submissions.find({})
    total = 0
    migrated = 0
    for sub in submissions:
        total += 1
        try:
            if migrate_submission(sub, db):
                migrated += 1
        except Exception as exc:
            print(f"[WARN] No se migró submission {sub.get('_id')}: {exc}")
    print(f"Migración completada. Migrados {migrated}/{total} submissions a evaluation_results.")


if __name__ == "__main__":
    main()


