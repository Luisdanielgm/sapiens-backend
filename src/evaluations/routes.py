from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import defaultdict

from bson import ObjectId
from flask import request

from src.correction.services import CorrectionService
from src.evaluations.models import EvaluationResource, EvaluationRubric
from src.evaluations.services import EvaluationService
from src.evaluations.weighted_grading_service import weighted_grading_service
from src.resources.services import ResourceFolderService, ResourceService
from src.shared.constants import ROLES
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.validators import validate_object_id


evaluation_routes = APIBlueprint("evaluations", __name__, url_prefix="/api/evaluations")
evaluation_service = EvaluationService()
correction_service = CorrectionService()
resource_folder_service = ResourceFolderService()
resource_service = ResourceService()


def _maybe_oid(value: Optional[str]) -> Optional[ObjectId]:
    if not value or not validate_object_id(value):
        return None
    return ObjectId(value)


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _current_user_id() -> Optional[str]:
    return getattr(request, "user_id", None)


def _is_teacher_or_admin() -> bool:
    roles: set[str] = set()
    workspace_role = getattr(request, "workspace_role", None)
    if workspace_role:
        roles.add(str(workspace_role).upper())
    for r in getattr(request, "user_roles", []) or []:
        roles.add(str(r).upper())
    return bool(roles.intersection({"TEACHER", "ADMIN", "INSTITUTE_ADMIN"}))


def _normalize_score_source(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return value

    v = value.strip().lower()
    mapping = {
        "manual": "manual",
        "deliverable": "deliverable",
        "quiz": "quiz_linked",
        "quiz_linked": "quiz_linked",
        "interactive": "interactive_result",
        "interactive_result": "interactive_result",
        "topic": "topic_result",
        "topic_result": "topic_result",
        "module": "module_result",
        "module_result": "module_result",
        "content_result": "content_result",
        "auto": "topic_result",
    }

    return mapping.get(v, value)


def _normalize_blocking_scope(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return value

    v = value.strip().lower()
    mapping = {
        "none": "none",
        "topic": "topic_virtual",
        "topic_virtual": "topic_virtual",
        "module": "module_virtual",
        "virtual_module": "module_virtual",
        "module_virtual": "module_virtual",
    }

    return mapping.get(v, value)


def _enrich_submissions(submissions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    resource_ids: List[ObjectId] = []
    for submission in submissions:
        rid = submission.get("resource_id")
        if isinstance(rid, ObjectId):
            resource_ids.append(rid)
        elif isinstance(rid, str) and validate_object_id(rid):
            resource_ids.append(ObjectId(rid))

    resource_map: Dict[str, Dict[str, Any]] = {}
    if resource_ids:
        resources = list(evaluation_service.db.resources.find({"_id": {"$in": list(set(resource_ids))}}))
        for resource in resources:
            resource_map[str(resource["_id"])] = resource

    enriched: List[Dict[str, Any]] = []
    for submission in submissions:
        if "id" not in submission and "_id" in submission:
            submission = {**submission, "id": str(submission["_id"])}
        rid = submission.get("resource_id")
        rid_str = str(rid) if isinstance(rid, ObjectId) else (rid if isinstance(rid, str) else None)
        resource = resource_map.get(rid_str) if rid_str else None
        if resource:
            submission = {**submission}
            submission["resource"] = resource
            submission["file_name"] = submission.get("file_name") or resource.get("name")
            submission["file_url"] = submission.get("file_url") or resource.get("url")
            submission["file_type"] = submission.get("file_type") or resource.get("type")
            submission["file_size"] = submission.get("file_size") or resource.get("size")
        enriched.append(submission)
    return enriched


def _attach_deliverable_attempts(*, evaluation_id: str, submissions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not submissions or not validate_object_id(evaluation_id):
        return submissions

    student_ids: List[ObjectId] = []
    for submission in submissions:
        sid = submission.get("student_id")
        if isinstance(sid, ObjectId):
            student_ids.append(sid)
        elif isinstance(sid, str) and validate_object_id(sid):
            student_ids.append(ObjectId(sid))

    if not student_ids:
        return submissions

    links = list(
        evaluation_service.resources_collection.find(
            {
                "evaluation_id": ObjectId(evaluation_id),
                "role": "submission",
                "created_by": {"$in": list(set(student_ids))},
            }
        ).sort("created_at", -1)
    )

    resource_ids: List[ObjectId] = []
    for link in links:
        rid = link.get("resource_id")
        if isinstance(rid, ObjectId):
            resource_ids.append(rid)

    resource_map: Dict[str, Dict[str, Any]] = {}
    if resource_ids:
        resources = list(evaluation_service.db.resources.find({"_id": {"$in": list(set(resource_ids))}}))
        for resource in resources:
            resource_map[str(resource["_id"])] = resource

    by_student: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for link in links:
        rid = link.get("resource_id")
        sid = link.get("created_by")
        if not isinstance(rid, ObjectId) or not isinstance(sid, ObjectId):
            continue
        resource = resource_map.get(str(rid))
        if not resource:
            continue
        by_student[str(sid)].append(
            {
                "link_id": str(link.get("_id")),
                "created_at": link.get("created_at"),
                "resource": resource,
            }
        )

    out: List[Dict[str, Any]] = []
    for submission in submissions:
        sid = submission.get("student_id")
        sid_str = str(sid) if isinstance(sid, ObjectId) else (sid if isinstance(sid, str) else "")
        item = dict(submission)
        item["deliverable_attempts"] = by_student.get(sid_str, [])
        out.append(item)

    return out


def _safe_folder_name(value: str, *, max_len: int = 64) -> str:
    name = (value or "").strip()
    if not name:
        return "Sin nombre"
    # Evitar separadores y nombres raros
    for ch in ["\\", "/", ":", "*", "?", "\"", "<", ">", "|"]:
        name = name.replace(ch, " ")
    name = " ".join(name.split())
    return name[:max_len]


def _get_user_email_by_id(user_id: str) -> Optional[str]:
    if not validate_object_id(user_id):
        return None
    user = evaluation_service.db.users.find_one({"_id": ObjectId(user_id)}, {"email": 1})
    return user.get("email") if user else None


def _get_or_create_student_deliverables_folder_id(*, evaluation_id: str, student_id: str) -> Optional[str]:
    email = _get_user_email_by_id(student_id)
    if not email:
        return None

    evaluation = evaluation_service.get_evaluation(evaluation_id) or {}
    title = _safe_folder_name(str(evaluation.get("title") or "Evaluación"))
    short_id = str(evaluation_id)[-6:]
    eval_folder_name = _safe_folder_name(f"{title} ({short_id})", max_len=80)

    root_folder = resource_folder_service.get_user_root_folder(email)
    root_id = str(root_folder.get("_id"))
    if not validate_object_id(root_id):
        return None

    deliverables_id = resource_folder_service.get_or_create_subfolder(root_id, "Entregables", student_id)
    if not deliverables_id:
        return None
    evaluations_id = resource_folder_service.get_or_create_subfolder(deliverables_id, "Evaluaciones", student_id)
    if not evaluations_id:
        return None
    return resource_folder_service.get_or_create_subfolder(evaluations_id, eval_folder_name, student_id)


def _enrich_resource_links(links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    resource_ids = [link["resource_id"] for link in links if isinstance(link.get("resource_id"), ObjectId)]
    resource_map: Dict[str, Dict[str, Any]] = {}
    if resource_ids:
        resources = list(evaluation_service.db.resources.find({"_id": {"$in": list(set(resource_ids))}}))
        for resource in resources:
            resource_map[str(resource["_id"])] = resource
    out: List[Dict[str, Any]] = []
    for link in links:
        if "id" not in link and "_id" in link:
            link = {**link, "id": str(link["_id"])}
        rid = link.get("resource_id")
        if isinstance(rid, ObjectId):
            resource = resource_map.get(str(rid))
            if resource:
                link = {**link, "resource": resource}
        out.append(link)
    return out


def _upsert_submission_from_resource(*, evaluation_id: str, student_id: str, resource_id: str) -> str:
    evaluation = evaluation_service.get_evaluation(evaluation_id)
    due_date = evaluation.get("due_date") if evaluation else None
    is_late = isinstance(due_date, datetime) and datetime.now() > due_date
    now = datetime.now()

    existing = evaluation_service.submissions_collection.find_one(
        {"evaluation_id": ObjectId(evaluation_id), "student_id": ObjectId(student_id)}
    )
    if existing:
        attempts = int(existing.get("attempts", 1)) + 1
        evaluation_service.submissions_collection.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "submission_type": "file",
                "resource_id": ObjectId(resource_id),
                "status": "submitted",
                "is_late": is_late,
                "attempts": attempts,
                "updated_at": now,
            }},
        )
        return str(existing["_id"])

    submission_id = evaluation_service.create_submission({
        "evaluation_id": evaluation_id,
        "student_id": student_id,
        "submission_type": "file",
        "resource_id": resource_id,
        "status": "submitted",
        "is_late": is_late,
        "attempts": 1,
        "created_at": now,
        "updated_at": now,
    })
    return submission_id


# ==================== CRUD Operations ====================


@evaluation_routes.route("", methods=["GET"])
@evaluation_routes.route("/", methods=["GET"])
@APIRoute.standard(auth_required_flag=True)
def list_evaluations():
    query: Dict[str, Any] = {}

    topic_id = request.args.get("topic_id")
    evaluation_type = request.args.get("evaluation_type")
    status = request.args.get("status")
    score_source = request.args.get("score_source")
    blocking_scope = request.args.get("blocking_scope")
    blocking_condition = request.args.get("blocking_condition")
    virtual_topic_id = request.args.get("virtual_topic_id")
    virtual_module_id = request.args.get("virtual_module_id")
    plan_id = request.args.get("plan_id")
    module_id = request.args.get("module_id")
    class_id = request.args.get("class_id")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    topic_oid = _maybe_oid(topic_id)
    if topic_oid:
        query["topic_ids"] = topic_oid
    if evaluation_type:
        query["evaluation_type"] = evaluation_type
    if status:
        query["status"] = status
    if score_source:
        query["score_source"] = score_source
    if blocking_scope:
        query["blocking_scope"] = blocking_scope
    if blocking_condition:
        query["blocking_condition"] = blocking_condition

    vtid = _maybe_oid(virtual_topic_id)
    if vtid:
        query["virtual_topic_id"] = vtid
    vmid = _maybe_oid(virtual_module_id)
    if vmid:
        query["virtual_module_id"] = vmid
    pid = _maybe_oid(plan_id)
    if pid:
        query["plan_id"] = pid
    mid = _maybe_oid(module_id)
    if mid:
        query["module_id"] = mid
    cid = _maybe_oid(class_id)
    if cid:
        query["class_id"] = cid

    dt_from = _parse_iso_datetime(date_from)
    dt_to = _parse_iso_datetime(date_to)
    if dt_from or dt_to:
        query["due_date"] = {}
        if dt_from:
            query["due_date"]["$gte"] = dt_from
        if dt_to:
            query["due_date"]["$lte"] = dt_to
        if not query["due_date"]:
            query.pop("due_date", None)

    evaluations = list(evaluation_service.evaluations_collection.find(query).sort("created_at", -1))
    for ev in evaluations:
        if "id" not in ev and "_id" in ev:
            ev["id"] = ev["_id"]
    return APIRoute.success(data={"evaluations": evaluations})


@evaluation_routes.route("/<evaluation_id>/deliverables-folder", methods=["GET"])
@APIRoute.standard(auth_required_flag=True)
def get_deliverables_folder(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluaciÇün invÇ­lido.")

    student_id = request.args.get("student_id")
    current_user = _current_user_id()
    if not _is_teacher_or_admin():
        student_id = current_user
    else:
        student_id = student_id or current_user

    if not student_id or not validate_object_id(student_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "student_id requerido y vÇ­lido.")

    evaluation = evaluation_service.get_evaluation(evaluation_id)
    if not evaluation:
        return APIRoute.error(ErrorCodes.NOT_FOUND, "EvaluaciÇün no encontrada.", status_code=404)

    folder_id = _get_or_create_student_deliverables_folder_id(evaluation_id=evaluation_id, student_id=student_id)
    if not folder_id:
        return APIRoute.error(ErrorCodes.OPERATION_FAILED, "No se pudo determinar la carpeta de entregables.", status_code=500)

    return APIRoute.success(data={"folder_id": folder_id})


@evaluation_routes.route("/submissions", methods=["GET"])
@APIRoute.standard(auth_required_flag=True)
def list_student_submissions():
    """
    Lista entregas de un estudiante (vista "Mis entregas").
    - Student: solo sus entregas.
    - Teacher/Admin: puede pasar ?student_id= para ver entregas del estudiante.
    """
    student_id = request.args.get("student_id") or _current_user_id()
    if not validate_object_id(student_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "student_id requerido y válido.")
    if not _is_teacher_or_admin() and _current_user_id() != student_id:
        return APIRoute.error(ErrorCodes.PERMISSION_DENIED, "No tienes permiso para ver estas entregas.", status_code=403)

    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 20)), 1), 100)

    query: Dict[str, Any] = {"student_id": ObjectId(student_id)}
    total = evaluation_service.submissions_collection.count_documents(query)

    cursor = (
        evaluation_service.submissions_collection.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    submissions = list(cursor)
    submissions = _enrich_submissions(submissions)

    evaluation_ids: List[ObjectId] = []
    for s in submissions:
        eid = s.get("evaluation_id")
        if isinstance(eid, ObjectId):
            evaluation_ids.append(eid)
        elif isinstance(eid, str) and validate_object_id(eid):
            evaluation_ids.append(ObjectId(eid))

    evaluation_map: Dict[str, Dict[str, Any]] = {}
    module_ids: List[ObjectId] = []
    if evaluation_ids:
        evaluations = list(evaluation_service.evaluations_collection.find({"_id": {"$in": list(set(evaluation_ids))}}))
        for ev in evaluations:
            evaluation_map[str(ev["_id"])] = ev
            mid = ev.get("module_id")
            if isinstance(mid, ObjectId):
                module_ids.append(mid)

    module_map: Dict[str, str] = {}
    if module_ids:
        try:
            modules = list(evaluation_service.db.modules.find({"_id": {"$in": list(set(module_ids))}}))
            for mod in modules:
                module_map[str(mod["_id"])] = mod.get("name") or mod.get("title") or ""
        except Exception:
            module_map = {}

    results_map: Dict[str, Dict[str, Any]] = {}
    if evaluation_ids:
        results = list(
            evaluation_service.results_collection.find(
                {"student_id": ObjectId(student_id), "evaluation_id": {"$in": list(set(evaluation_ids))}}
            )
        )
        for r in results:
            results_map[str(r.get("evaluation_id"))] = r

    out: List[Dict[str, Any]] = []
    for submission in submissions:
        eid = submission.get("evaluation_id")
        eid_str = str(eid) if isinstance(eid, ObjectId) else (eid if isinstance(eid, str) else None)
        ev = evaluation_map.get(eid_str) if eid_str else None
        module_name = ""
        if ev and ev.get("module_id"):
            module_name = module_map.get(str(ev.get("module_id")), "")

        submitted_at = submission.get("submitted_at") or submission.get("created_at")
        attempt_number = submission.get("attempt_number") or submission.get("attempts")

        result = results_map.get(eid_str) if eid_str else None
        source = submission.get("source") or (result.get("source") if result else None)

        item = dict(submission)
        item["evaluation_title"] = item.get("evaluation_title") or (ev.get("title") if ev else None)
        item["module_name"] = item.get("module_name") or module_name or None
        item["submitted_at"] = submitted_at
        item["attempt_number"] = attempt_number
        if source is not None:
            item["source"] = source
        out.append(item)

    return APIRoute.success(
        data={
            "submissions": out,
            "pagination": {"page": page, "page_size": page_size, "total": total},
        }
    )


@evaluation_routes.route("", methods=["POST"])
@evaluation_routes.route("/", methods=["POST"])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["ADMIN"]],
    required_fields=["topic_ids", "title", "weight", "criteria", "due_date"],
)
def create_evaluation():
    data = request.get_json() or {}

    topic_ids = data.get("topic_ids") or []
    if not isinstance(topic_ids, list) or not topic_ids:
        return APIRoute.error(ErrorCodes.INVALID_DATA, "topic_ids debe ser una lista no vacía.")
    for tid in topic_ids:
        if not validate_object_id(str(tid)):
            return APIRoute.error(ErrorCodes.INVALID_ID, f"topic_id inválido: {tid}")

    due_date = _parse_iso_datetime(data.get("due_date"))
    if not due_date:
        return APIRoute.error(ErrorCodes.INVALID_DATA, "due_date inválido (ISO 8601).")

    user_id = _current_user_id()
    if not user_id or not validate_object_id(user_id):
        return APIRoute.error(ErrorCodes.AUTHENTICATION_ERROR, "Usuario no autenticado.", status_code=401)

    payload: Dict[str, Any] = {
        "module_id": data.get("module_id"),
        "plan_id": data.get("plan_id"),
        "class_id": data.get("class_id"),
        "topic_ids": topic_ids,
        "title": data.get("title"),
        "description": data.get("description", ""),
        "weight": float(data.get("weight")),
        "criteria": data.get("criteria") or [],
        "due_date": due_date,
        "evaluation_type": data.get("evaluation_type", "assignment"),
        "use_quiz_score": bool(data.get("use_quiz_score", False)),
        "requires_submission": bool(data.get("requires_submission", False)),
        "linked_quiz_id": data.get("linked_quiz_id"),
        "linked_content_id": data.get("linked_content_id") or data.get("linked_quiz_id"),
        "auto_grading": data.get("auto_grading"),
        "weightings": data.get("weightings"),
        "rubric": data.get("rubric"),
        "max_attempts": int(data.get("max_attempts", 1)),
        "time_limit": data.get("time_limit"),
        "score_source": _normalize_score_source(data.get("score_source")),
        "blocking_scope": _normalize_blocking_scope(data.get("blocking_scope")),
        "blocking_condition": data.get("blocking_condition"),
        "pass_score": data.get("pass_score"),
        "virtual_topic_id": data.get("virtual_topic_id"),
        "virtual_module_id": data.get("virtual_module_id"),
        "resource_templates": data.get("resource_templates"),
        "allow_manual_override": bool(data.get("allow_manual_override", True)),
        "created_by": user_id,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "status": data.get("status", "active"),
    }

    for key in ["module_id", "plan_id", "class_id", "linked_quiz_id", "linked_content_id", "virtual_topic_id", "virtual_module_id"]:
        if payload.get(key) and not validate_object_id(str(payload[key])):
            return APIRoute.error(ErrorCodes.INVALID_ID, f"{key} inválido.")

    evaluation_id = evaluation_service.create_evaluation(payload)
    return APIRoute.success(
        data={"id": evaluation_id, "evaluation_id": evaluation_id},
        message="Evaluación creada exitosamente.",
        status_code=201,
    )


@evaluation_routes.route("/<evaluation_id>", methods=["GET"])
@APIRoute.standard(auth_required_flag=True)
def get_evaluation(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluación inválido.")
    evaluation = evaluation_service.get_evaluation(evaluation_id)
    if not evaluation:
        return APIRoute.error(ErrorCodes.NOT_FOUND, "Evaluación no encontrada.", status_code=404)
    if "id" not in evaluation and "_id" in evaluation:
        evaluation["id"] = evaluation["_id"]
    return APIRoute.success(data=evaluation)


@evaluation_routes.route("/<evaluation_id>", methods=["PUT"])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def update_evaluation(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluación inválido.")
    data = request.get_json() or {}
    if "due_date" in data and isinstance(data.get("due_date"), str):
        parsed = _parse_iso_datetime(data.get("due_date"))
        if not parsed:
            return APIRoute.error(ErrorCodes.INVALID_DATA, "due_date inválido (ISO 8601).")
        data["due_date"] = parsed
    if "linked_content_id" in data and data.get("linked_content_id") and not validate_object_id(str(data.get("linked_content_id"))):
        return APIRoute.error(ErrorCodes.INVALID_ID, "linked_content_id inv케lido.")
    if "linked_quiz_id" in data and data.get("linked_quiz_id") and not validate_object_id(str(data.get("linked_quiz_id"))):
        return APIRoute.error(ErrorCodes.INVALID_ID, "linked_quiz_id invकेlido.")
    if "linked_quiz_id" in data and "linked_content_id" not in data:
        data["linked_content_id"] = data.get("linked_quiz_id")
    ok = evaluation_service.update_evaluation(evaluation_id, data)
    if not ok:
        return APIRoute.error(ErrorCodes.NOT_FOUND, "Evaluación no encontrada o no se pudo actualizar.", status_code=404)
    return APIRoute.success(message="Evaluación actualizada exitosamente.")


@evaluation_routes.route("/<evaluation_id>", methods=["DELETE"])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def delete_evaluation(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluación inválido.")
    ok = evaluation_service.delete_evaluation(evaluation_id)
    if not ok:
        return APIRoute.error(ErrorCodes.NOT_FOUND, "Evaluación no encontrada.", status_code=404)
    return APIRoute.success(message="Evaluación eliminada exitosamente.")


# ==================== Submission Management ====================


@evaluation_routes.route("/<evaluation_id>/submissions", methods=["POST"])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["STUDENT"]])
def create_submission(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluación inválido.")
    data = request.get_json() or {}
    submission_type = data.get("submission_type", "text")
    if submission_type not in ["file", "text", "url", "quiz_response", "content_result"]:
        return APIRoute.error(ErrorCodes.INVALID_DATA, "submission_type inválido.")

    student_id = _current_user_id()
    if not student_id or not validate_object_id(student_id):
        return APIRoute.error(ErrorCodes.AUTHENTICATION_ERROR, "Usuario no autenticado.", status_code=401)

    evaluation = evaluation_service.get_evaluation(evaluation_id)
    if not evaluation:
        return APIRoute.error(ErrorCodes.NOT_FOUND, "EvaluaciИn no encontrada.", status_code=404)

    max_attempts = int(evaluation.get("max_attempts", 1) or 1)
    attempts_used = evaluation_service.submissions_collection.count_documents(
        {"evaluation_id": ObjectId(evaluation_id), "student_id": ObjectId(student_id)}
    )
    if attempts_used >= max_attempts:
        return APIRoute.error(
            ErrorCodes.OPERATION_FAILED,
            "Se alcanzó el máximo de intentos para esta evaluación.",
            status_code=409,
        )

    due_date = evaluation.get("due_date")
    is_late = isinstance(due_date, datetime) and datetime.now() > due_date

    resource_id = data.get("resource_id")
    if submission_type == "file":
        if not resource_id or not validate_object_id(resource_id):
            return APIRoute.error(ErrorCodes.MISSING_FIELDS, "resource_id requerido y válido para submissions tipo file.")

    payload = {
        "evaluation_id": evaluation_id,
        "student_id": student_id,
        "submission_type": submission_type,
        "content": data.get("content"),
        "url": data.get("url"),
        "resource_id": resource_id,
        "status": data.get("status", "submitted"),
        "is_late": is_late,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "attempts": attempts_used + 1,
        "submission_metadata": data.get("submission_metadata", {}),
    }
    submission_id = evaluation_service.create_submission(payload)
    return APIRoute.success(
        data={"id": submission_id, "submission_id": submission_id},
        message="Entrega creada.",
        status_code=201,
    )


@evaluation_routes.route("/<evaluation_id>/submissions/<student_id>", methods=["GET"])
@APIRoute.standard(auth_required_flag=True)
def get_student_submissions(evaluation_id: str, student_id: str):
    if not validate_object_id(evaluation_id) or not validate_object_id(student_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "IDs inválidos.")
    if not _is_teacher_or_admin() and _current_user_id() != student_id:
        return APIRoute.error(ErrorCodes.PERMISSION_DENIED, "No tienes permiso para ver estas entregas.", status_code=403)

    submissions = evaluation_service.get_student_submissions(evaluation_id, student_id)
    submissions = _enrich_submissions(submissions)
    submissions = _attach_deliverable_attempts(evaluation_id=evaluation_id, submissions=submissions)
    return APIRoute.success(data={"submissions": submissions})


@evaluation_routes.route("/<evaluation_id>/submissions", methods=["GET"])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def list_submissions(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluación inválido.")

    student_id = request.args.get("student_id")
    status = request.args.get("status")
    late = request.args.get("late")
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 20)), 1), 100)
    sort_by = request.args.get("sort_by", "created_at")
    sort_dir = request.args.get("sort_dir", "desc")

    query: Dict[str, Any] = {"evaluation_id": ObjectId(evaluation_id)}
    if student_id and validate_object_id(student_id):
        query["student_id"] = ObjectId(student_id)
    if status:
        query["status"] = status
    if late is not None:
        if late.lower() in ["true", "1", "yes"]:
            query["is_late"] = True
        elif late.lower() in ["false", "0", "no"]:
            query["is_late"] = False

    total = evaluation_service.submissions_collection.count_documents(query)
    direction = -1 if sort_dir.lower() == "desc" else 1
    if sort_by not in ["created_at", "updated_at", "status", "graded_at"]:
        sort_by = "created_at"

    cursor = (
        evaluation_service.submissions_collection.find(query)
        .sort(sort_by, direction)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    submissions = list(cursor)
    submissions = _enrich_submissions(submissions)
    submissions = _attach_deliverable_attempts(evaluation_id=evaluation_id, submissions=submissions)
    return APIRoute.success(
        data={
            "submissions": submissions,
            "pagination": {"page": page, "page_size": page_size, "total": total},
        }
    )


@evaluation_routes.route("/submissions/<submission_id>/grade", methods=["POST"])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]], required_fields=["grade"])
def grade_submission(submission_id: str):
    if not validate_object_id(submission_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de entrega inválido.")
    data = request.get_json() or {}
    try:
        grade = float(data.get("grade"))
    except Exception:
        return APIRoute.error(ErrorCodes.INVALID_DATA, "La calificación debe ser numérica.")
    if grade < 0 or grade > 100:
        return APIRoute.error(ErrorCodes.INVALID_DATA, "La calificación debe estar entre 0 y 100.")

    ok = evaluation_service.grade_submission(
        submission_id=submission_id,
        grade=grade,
        feedback=data.get("feedback", ""),
        graded_by=_current_user_id(),
        topic_scores=data.get("topic_scores"),
    )
    if not ok:
        return APIRoute.error(ErrorCodes.NOT_FOUND, "Entrega no encontrada.", status_code=404)
    return APIRoute.success(message="Entrega calificada exitosamente.")


@evaluation_routes.route("/submissions/<submission_id>/ai-grade", methods=["POST"])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def ai_grade_submission(submission_id: str):
    if not validate_object_id(submission_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de entrega inválido.")

    data = request.get_json() or {}
    rubric_resource_id = data.get("rubric_resource_id")

    submission = evaluation_service.submissions_collection.find_one({"_id": ObjectId(submission_id)})
    if not submission:
        return APIRoute.error(ErrorCodes.NOT_FOUND, "Entrega no encontrada.", status_code=404)

    evaluation_id = submission.get("evaluation_id")
    submission_resource_id = submission.get("resource_id")
    if not submission_resource_id:
        return APIRoute.error(ErrorCodes.INVALID_DATA, "La entrega no tiene resource_id para procesar con IA.")

    success, task_id = correction_service.start_correction_task(
        evaluation_id=str(evaluation_id),
        submission_resource_id=str(submission_resource_id),
        rubric_resource_id=rubric_resource_id,
        teacher_id=_current_user_id(),
    )
    if not success:
        return APIRoute.error(ErrorCodes.OPERATION_FAILED, "No se pudo iniciar la tarea de corrección.", status_code=500)

    evaluation_service.submissions_collection.update_one(
        {"_id": ObjectId(submission_id)},
        {"$set": {"status": "ai_pending", "updated_at": datetime.now()}},
    )

    try:
        evaluation_service._upsert_evaluation_result(
            evaluation_id=str(evaluation_id),
            student_id=submission.get("student_id"),
            score=0.0,
            source="ai_pending",
            submission_id=submission_id,
            status="pending",
        )
    except Exception:
        pass

    return APIRoute.success(data={"task_id": task_id}, message="Corrección IA iniciada.", status_code=202)


# ==================== Resources Management ====================


@evaluation_routes.route("/<evaluation_id>/resources", methods=["POST"])
@APIRoute.standard(auth_required_flag=True, required_fields=["resource_id", "role"])
def link_resource(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluación inválido.")
    data = request.get_json() or {}
    resource_id = data.get("resource_id")
    role = data.get("role")
    if not resource_id or not validate_object_id(resource_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "resource_id inválido.")
    if role not in ["template", "supporting_material", "submission"]:
        return APIRoute.error(ErrorCodes.INVALID_DATA, "role inválido.")

    user_id = _current_user_id()
    if not user_id or not validate_object_id(user_id):
        return APIRoute.error(ErrorCodes.AUTHENTICATION_ERROR, "Usuario no autenticado.", status_code=401)

    # Estudiantes: solo submissions
    if not _is_teacher_or_admin() and role != "submission":
        return APIRoute.error(ErrorCodes.PERMISSION_DENIED, "Solo puedes vincular entregables (submission).", status_code=403)

    if role == "submission":
        evaluation = evaluation_service.get_evaluation(evaluation_id)
        if not evaluation:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "EvaluaciИn no encontrada.", status_code=404)
        max_attempts = int(evaluation.get("max_attempts", 1) or 1)
        existing = evaluation_service.submissions_collection.find_one(
            {"evaluation_id": ObjectId(evaluation_id), "student_id": ObjectId(user_id)}
        )
        attempts_used = int(existing.get("attempts", 1)) if existing else 0
        if attempts_used >= max_attempts:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                "Se alcanzó el máximo de intentos para esta evaluación.",
                status_code=409,
            )

    existing = evaluation_service.resources_collection.find_one(
        {"evaluation_id": ObjectId(evaluation_id), "resource_id": ObjectId(resource_id)}
    )
    if existing:
        link_id = str(existing["_id"])
    else:
        link = EvaluationResource(
            evaluation_id=evaluation_id,
            resource_id=resource_id,
            role=role,
            created_by=user_id,
        )
        evaluation_service.resources_collection.insert_one(link.to_dict())
        link_id = str(link._id)

    submission_id = None
    if role == "submission":
        submission_id = _upsert_submission_from_resource(
            evaluation_id=evaluation_id,
            student_id=user_id,
            resource_id=resource_id,
        )
        try:
            folder_id = _get_or_create_student_deliverables_folder_id(
                evaluation_id=evaluation_id,
                student_id=user_id,
            )
            student_email = _get_user_email_by_id(user_id)
            if folder_id and student_email:
                resource_service.update_resource(resource_id, {"folder_id": folder_id}, email=student_email)
        except Exception:
            pass

    return APIRoute.success(
        data={"link_id": link_id, "resource_id": resource_id, "submission_id": submission_id},
        message="Recurso vinculado.",
        status_code=201,
    )


@evaluation_routes.route("/<evaluation_id>/resources", methods=["GET"])
@APIRoute.standard(auth_required_flag=True)
def list_resources(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluación inválido.")

    role = request.args.get("role")
    student_id = request.args.get("student_id")

    query: Dict[str, Any] = {"evaluation_id": ObjectId(evaluation_id)}
    if role:
        query["role"] = role
    if role == "submission" and student_id:
        if not validate_object_id(student_id):
            return APIRoute.error(ErrorCodes.INVALID_ID, "student_id inválido.")
        if not _is_teacher_or_admin() and _current_user_id() != student_id:
            return APIRoute.error(ErrorCodes.PERMISSION_DENIED, "No tienes permiso para ver estos recursos.", status_code=403)
        query["created_by"] = ObjectId(student_id)

    links = list(evaluation_service.resources_collection.find(query).sort("created_at", -1))
    links = _enrich_resource_links(links)
    return APIRoute.success(data={"resources": links})


@evaluation_routes.route("/<evaluation_id>/resources/<resource_id>", methods=["DELETE"])
@APIRoute.standard(auth_required_flag=True)
def unlink_resource(evaluation_id: str, resource_id: str):
    if not (validate_object_id(evaluation_id) and validate_object_id(resource_id)):
        return APIRoute.error(ErrorCodes.INVALID_ID, "IDs inválidos.")

    query: Dict[str, Any] = {"evaluation_id": ObjectId(evaluation_id), "resource_id": ObjectId(resource_id)}

    if not _is_teacher_or_admin():
        # Política: el estudiante no puede eliminar/desvincular entregables (trazabilidad).
        # Si requiere "corregir" un archivo, debe subir un nuevo intento.
        return APIRoute.error(
            ErrorCodes.PERMISSION_DENIED,
            "No tienes permiso para eliminar entregables. Sube un nuevo intento si necesitas corregirlo.",
            status_code=403,
        )

    result = evaluation_service.resources_collection.delete_one(query)
    if result.deleted_count == 0:
        return APIRoute.error(ErrorCodes.NOT_FOUND, "Vinculación no encontrada.", status_code=404)
    return APIRoute.success(message="Vinculación eliminada.")


# ==================== Rubric Management ====================


@evaluation_routes.route("/<evaluation_id>/rubric", methods=["GET"])
@APIRoute.standard(auth_required_flag=True)
def get_rubric(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluación inválido.")
    rubric = evaluation_service.rubrics_collection.find_one({"evaluation_id": ObjectId(evaluation_id)})
    if not rubric:
        return APIRoute.error(ErrorCodes.NOT_FOUND, "Rúbrica no encontrada.", status_code=404)
    return APIRoute.success(data={"rubric": rubric})


@evaluation_routes.route("/<evaluation_id>/rubric", methods=["POST"])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["ADMIN"]],
    required_fields=["criteria", "total_points"],
)
def create_or_update_rubric(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluación inválido.")
    data = request.get_json() or {}
    rubric = EvaluationRubric(
        evaluation_id=evaluation_id,
        title=data.get("title", "Rúbrica"),
        description=data.get("description", ""),
        criteria=data.get("criteria", []),
        total_points=float(data.get("total_points", 100.0)),
        grading_scale=data.get("grading_scale"),
        created_by=_current_user_id(),
        rubric_type=data.get("rubric_type", "standard"),
    )
    if not rubric.validate_criteria():
        return APIRoute.error(ErrorCodes.INVALID_DATA, "Los criterios no suman el total de puntos especificado.")
    evaluation_service.rubrics_collection.update_one(
        {"evaluation_id": rubric.evaluation_id},
        {"$set": rubric.to_dict()},
        upsert=True,
    )
    saved = evaluation_service.rubrics_collection.find_one({"evaluation_id": rubric.evaluation_id})
    return APIRoute.success(data={"rubric_id": str(saved["_id"])}, message="Rúbrica guardada.")


# ==================== Weighted Grading / Integrations ====================


@evaluation_routes.route("/<evaluation_id>/students/<student_id>/weighted-grade", methods=["GET"])
@APIRoute.standard(auth_required_flag=True)
def calculate_weighted_grade(evaluation_id: str, student_id: str):
    if not (validate_object_id(evaluation_id) and validate_object_id(student_id)):
        return APIRoute.error(ErrorCodes.INVALID_ID, "IDs inválidos.")
    result = evaluation_service.calculate_weighted_grade(evaluation_id, student_id)
    return APIRoute.success(data=result)


@evaluation_routes.route("/<evaluation_id>/weights", methods=["PUT"])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["ADMIN"]],
    required_fields=["weights"],
)
def update_evaluation_weights(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluación inválido.")
    data = request.get_json() or {}
    ok = evaluation_service.update_evaluation_weights(evaluation_id, data.get("weights"))
    if not ok:
        return APIRoute.error(ErrorCodes.NOT_FOUND, "Evaluación no encontrada.", status_code=404)
    return APIRoute.success(message="Ponderaciones actualizadas exitosamente.")


@evaluation_routes.route("/<evaluation_id>/students/<student_id>/process-content-results", methods=["POST"])
@APIRoute.standard(auth_required_flag=True)
def process_content_result_grading(evaluation_id: str, student_id: str):
    if not (validate_object_id(evaluation_id) and validate_object_id(student_id)):
        return APIRoute.error(ErrorCodes.INVALID_ID, "IDs inválidos.")
    result = evaluation_service.process_content_result_grading(evaluation_id, student_id)
    return APIRoute.success(data=result)


@evaluation_routes.route("/submissions/<submission_id>/grade-with-rubric", methods=["POST"])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["ADMIN"]],
    required_fields=["rubric_id", "criteria_scores"],
)
def grade_with_rubric(submission_id: str):
    if not validate_object_id(submission_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de entrega inválido.")
    data = request.get_json() or {}
    rubric_id = data.get("rubric_id")
    if not validate_object_id(rubric_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de rúbrica inválido.")
    result = evaluation_service.grade_with_rubric(
        submission_id=submission_id,
        rubric_id=rubric_id,
        criteria_scores=data.get("criteria_scores") or {},
        graded_by=_current_user_id(),
    )
    return APIRoute.success(data=result)


@evaluation_routes.route("/by-topic/<topic_id>", methods=["GET"])
@APIRoute.standard(auth_required_flag=True)
def get_evaluations_by_topic(topic_id: str):
    if not validate_object_id(topic_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de tema inválido.")
    evaluations = evaluation_service.get_evaluations_by_topic(topic_id)
    for ev in evaluations:
        if "id" not in ev and "_id" in ev:
            ev["id"] = ev["_id"]
    return APIRoute.success(data=evaluations)


@evaluation_routes.route("/students/<student_id>/summary", methods=["GET"])
@APIRoute.standard(auth_required_flag=True)
def get_student_evaluation_summary(student_id: str):
    if not validate_object_id(student_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "student_id inválido.")
    if not _is_teacher_or_admin() and _current_user_id() != student_id:
        return APIRoute.error(ErrorCodes.PERMISSION_DENIED, "No tienes permiso para ver este resumen.", status_code=403)

    topic_ids = request.args.getlist("topic_ids")
    for tid in topic_ids:
        if not validate_object_id(tid):
            return APIRoute.error(ErrorCodes.INVALID_ID, f"ID de tema inválido: {tid}")

    summary = evaluation_service.get_student_evaluation_summary(
        student_id=student_id,
        topic_ids=topic_ids if topic_ids else None,
    )
    return APIRoute.success(data=summary)


# ==================== Results & Locks ====================


@evaluation_routes.route("/<evaluation_id>/results", methods=["GET"])
@APIRoute.standard(auth_required_flag=True)
def list_evaluation_results(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluación inválido.")

    student_id = request.args.get("student_id")
    status = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 20)), 1), 100)
    sort_by = request.args.get("sort_by", "recorded_at")
    sort_dir = request.args.get("sort_dir", "desc")

    query: Dict[str, Any] = {"evaluation_id": ObjectId(evaluation_id)}
    if student_id and validate_object_id(student_id):
        if not _is_teacher_or_admin() and _current_user_id() != student_id:
            return APIRoute.error(ErrorCodes.PERMISSION_DENIED, "No tienes permiso para ver estos resultados.", status_code=403)
        query["student_id"] = ObjectId(student_id)
    elif not _is_teacher_or_admin():
        query["student_id"] = ObjectId(_current_user_id())

    if status:
        query["status"] = status

    dt_from = _parse_iso_datetime(date_from)
    dt_to = _parse_iso_datetime(date_to)
    if dt_from or dt_to:
        query["recorded_at"] = {}
        if dt_from:
            query["recorded_at"]["$gte"] = dt_from
        if dt_to:
            query["recorded_at"]["$lte"] = dt_to
        if not query["recorded_at"]:
            query.pop("recorded_at", None)

    total = evaluation_service.results_collection.count_documents(query)
    direction = -1 if sort_dir.lower() == "desc" else 1
    if sort_by not in ["recorded_at", "score", "status"]:
        sort_by = "recorded_at"
    cursor = (
        evaluation_service.results_collection.find(query)
        .sort(sort_by, direction)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    results = list(cursor)
    for r in results:
        if "id" not in r and "_id" in r:
            r["id"] = r["_id"]
    return APIRoute.success(data={"results": results, "pagination": {"page": page, "page_size": page_size, "total": total}})


@evaluation_routes.route("/<evaluation_id>/results", methods=["POST", "PUT"])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["ADMIN"]],
    required_fields=["student_id", "score"],
)
def upsert_evaluation_result(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluación inválido.")
    data = request.get_json() or {}
    student_id = data.get("student_id")
    if not validate_object_id(student_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "student_id requerido y válido.")
    try:
        score_val = float(data.get("score"))
    except Exception:
        return APIRoute.error(ErrorCodes.INVALID_DATA, "score debe ser numérico.")

    doc: Dict[str, Any] = {
        "evaluation_id": ObjectId(evaluation_id),
        "student_id": ObjectId(student_id),
        "score": score_val,
        "source": data.get("source", "manual"),
        "status": data.get("status", "completed"),
        "recorded_at": datetime.now(),
    }

    submission_id = data.get("submission_id")
    class_id = data.get("class_id")
    if submission_id and validate_object_id(submission_id):
        doc["submission_id"] = ObjectId(submission_id)
    if class_id and validate_object_id(class_id):
        doc["class_id"] = ObjectId(class_id)

    evaluation_service.results_collection.update_one(
        {"evaluation_id": doc["evaluation_id"], "student_id": doc["student_id"]},
        {"$set": doc},
        upsert=True,
    )
    return APIRoute.success(data={"result": doc}, message="Resultado registrado.")


@evaluation_routes.route("/<evaluation_id>/results", methods=["DELETE"])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def delete_evaluation_result(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluaciИn invкеlido.")
    student_id = request.args.get("student_id")
    if not validate_object_id(student_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "student_id requerido y vкеlido.")

    result = evaluation_service.results_collection.delete_one(
        {"evaluation_id": ObjectId(evaluation_id), "student_id": ObjectId(student_id)}
    )
    if result.deleted_count == 0:
        return APIRoute.error(ErrorCodes.NOT_FOUND, "Resultado no encontrado.", status_code=404)

    return APIRoute.success(message="Resultado eliminado.")


@evaluation_routes.route("/<evaluation_id>/progress-lock", methods=["GET"])
@APIRoute.standard(auth_required_flag=True)
def evaluation_progress_lock(evaluation_id: str):
    student_id = request.args.get("student_id")
    if not validate_object_id(evaluation_id) or not validate_object_id(student_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "evaluation_id y student_id requeridos y válidos.")
    if not _is_teacher_or_admin() and _current_user_id() != student_id:
        return APIRoute.error(ErrorCodes.PERMISSION_DENIED, "No tienes permiso para consultar este lock.", status_code=403)

    evaluation = evaluation_service.get_evaluation(evaluation_id)
    if not evaluation:
        return APIRoute.error(ErrorCodes.NOT_FOUND, "Evaluación no encontrada.", status_code=404)

    blocking_scope = evaluation.get("blocking_scope")
    blocking_condition = evaluation.get("blocking_condition")
    pass_score = evaluation.get("pass_score")

    if not blocking_scope or blocking_scope == "none":
        return APIRoute.success(data={"blocked": False, "reason": None})

    submissions = evaluation_service.get_student_submissions(evaluation_id, student_id)
    latest = submissions[0] if submissions else None
    max_attempts = int(evaluation.get("max_attempts", 1) or 1)
    attempts_used = int(latest.get("attempts", 0) or 0) if latest else 0

    result = evaluation_service.results_collection.find_one(
        {"evaluation_id": ObjectId(evaluation_id), "student_id": ObjectId(student_id)}
    )
    score = result.get("score") if result else None

    blocked = True
    reason: Optional[str] = "Condición de bloqueo no cumplida"

    if blocking_condition == "submission_received":
        if latest is None and result and result.get("score") is not None:
            blocked = False
            reason = None
        else:
            blocked = latest is None
            reason = None if not blocked else "Falta entregar"
    elif blocking_condition == "graded":
        if latest and latest.get("status") == "ai_pending":
            blocked = True
            reason = "Corrección IA en proceso"
        else:
            blocked = not result or result.get("status") not in ["graded", "completed"] or result.get("score") is None
            reason = None if not blocked else "Pendiente de calificar"
        # Para fuentes auto (topic/module/content) podemos tener submission status "auto_graded";
        # en ese caso, o si existe evaluation_result completado, consideramos "graded" cumplido.
        if blocked:
            if result and result.get("status") in ["graded", "completed"] and result.get("score") is not None:
                blocked = False
                reason = None
            elif latest and latest.get("status") in ["graded", "auto_graded"]:
                blocked = False
                reason = None
    elif blocking_condition == "auto_graded_ok":
        threshold = pass_score if pass_score is not None else 0
        score_to_check = score if score is not None else (latest.get("final_grade") if latest else None)
        if latest and latest.get("status") == "ai_pending":
            blocked = True
            reason = "Corrección IA en proceso"
        else:
            blocked = score_to_check is None or score_to_check < threshold
            reason = None if not blocked else f"Requiere puntaje >= {threshold}"
    else:
        blocked = False
        reason = None

    return APIRoute.success(
        data={
            "blocked": blocked,
            "blocking_scope": blocking_scope,
            "blocking_condition": blocking_condition,
            "reason": reason,
            "ai_pending": bool(latest and latest.get("status") == "ai_pending"),
            "latest_submission_id": str(latest["_id"]) if latest else None,
            "max_attempts": max_attempts,
            "attempts_used": attempts_used,
            "can_attempt": attempts_used < max_attempts,
            "score": score,
            "pass_score": pass_score,
        }
    )


# ==================== Bulk / Weighted Service passthrough ====================


@evaluation_routes.route("/multi-topic", methods=["POST"])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["ADMIN"]],
    required_fields=["topic_ids", "title", "description", "weights"],
)
def create_multi_topic_evaluation():
    data = request.get_json() or {}
    topic_ids = data.get("topic_ids") or []
    weights = data.get("weights") or {}
    if not isinstance(topic_ids, list) or not isinstance(weights, dict):
        return APIRoute.error(ErrorCodes.INVALID_DATA, "topic_ids debe ser lista y weights debe ser diccionario.")
    evaluation_id = evaluation_service.create_multi_topic_evaluation(
        topic_ids=topic_ids,
        title=data.get("title"),
        description=data.get("description"),
        weights=weights,
        evaluation_type=data.get("evaluation_type", "assignment"),
        due_date=_parse_iso_datetime(data.get("due_date")),
        criteria=data.get("criteria"),
    )
    return APIRoute.success(data={"id": evaluation_id}, message="Evaluación multi-tema creada.", status_code=201)


@evaluation_routes.route("/bulk/create", methods=["POST"])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["ADMIN"]],
    required_fields=["evaluations"],
)
def bulk_create_evaluations():
    data = request.get_json() or {}
    evaluations = data.get("evaluations")
    if not isinstance(evaluations, list):
        return APIRoute.error(ErrorCodes.INVALID_DATA, "evaluations debe ser una lista.")

    created: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for i, ev_data in enumerate(evaluations):
        try:
            ev_data = dict(ev_data or {})
            ev_data["created_by"] = _current_user_id()
            ev_data["created_at"] = datetime.now()
            ev_data["updated_at"] = datetime.now()
            ev_id = evaluation_service.create_evaluation(ev_data)
            created.append({"index": i, "id": ev_id})
        except Exception as e:
            errors.append({"index": i, "error": str(e)})

    return APIRoute.success(data={"created": created, "errors": errors, "errors_count": len(errors)})


@evaluation_routes.route("/<evaluation_id>/students/<student_id>/calculate-weighted-grade", methods=["POST"])
@APIRoute.standard(auth_required_flag=True)
def calculate_weighted_grade_for_student(evaluation_id: str, student_id: str):
    if not (validate_object_id(evaluation_id) and validate_object_id(student_id)):
        return APIRoute.error(ErrorCodes.INVALID_ID, "IDs inválidos.")
    result = weighted_grading_service.calculate_weighted_grade_for_student(evaluation_id, student_id)
    if "error" in result:
        return APIRoute.error(ErrorCodes.OPERATION_FAILED, result["error"])
    return APIRoute.success(data=result)


@evaluation_routes.route("/<evaluation_id>/students/<student_id>/update-submission-grade", methods=["PUT"])
@APIRoute.standard(auth_required_flag=True)
def update_submission_grade_weighted(evaluation_id: str, student_id: str):
    if not (validate_object_id(evaluation_id) and validate_object_id(student_id)):
        return APIRoute.error(ErrorCodes.INVALID_ID, "IDs inválidos.")
    ok = weighted_grading_service.update_evaluation_submission_grade(evaluation_id, student_id)
    if not ok:
        return APIRoute.error(ErrorCodes.OPERATION_FAILED, "No se pudo actualizar la calificación.")
    return APIRoute.success(message="Calificación actualizada exitosamente.")


@evaluation_routes.route("/<evaluation_id>/recalculate-all-grades", methods=["POST"])
@APIRoute.standard(auth_required_flag=True)
def recalculate_all_grades(evaluation_id: str):
    if not validate_object_id(evaluation_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de evaluación inválido.")
    result = weighted_grading_service.recalculate_all_students_for_evaluation(evaluation_id)
    if "error" in result:
        return APIRoute.error(ErrorCodes.OPERATION_FAILED, result["error"])
    return APIRoute.success(data=result)


@evaluation_routes.route("/validate-topic-weights", methods=["POST"])
@APIRoute.standard(auth_required_flag=True, required_fields=["topic_weights"])
def validate_topic_weights():
    data = request.get_json() or {}
    is_valid, message = weighted_grading_service.validate_topic_weights(data.get("topic_weights"))
    return APIRoute.success(data={"valid": is_valid, "message": message, "topic_weights": data.get("topic_weights")})


@evaluation_routes.route("/topics/<topic_id>/performance-summary", methods=["GET"])
@APIRoute.standard(auth_required_flag=True)
def get_topic_performance_summary(topic_id: str):
    if not validate_object_id(topic_id):
        return APIRoute.error(ErrorCodes.INVALID_ID, "ID de tema inválido.")
    limit = min(max(int(request.args.get("limit", 50)), 1), 200)
    result = weighted_grading_service.get_topic_performance_summary(topic_id, limit)
    if "error" in result:
        return APIRoute.error(ErrorCodes.OPERATION_FAILED, result["error"])
    return APIRoute.success(data=result)


# ==================== Health Check ====================


@evaluation_routes.route("/health", methods=["GET"])
def health_check():
    try:
        evaluation_service.evaluations_collection.find_one()
        return APIRoute.success(
            data={"status": "healthy", "service": "evaluations", "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)
