"""
ProgressService - Servicio para cálculo de progreso detallado de estudiantes.

Proporciona métricas desglosadas por:
- Materia/Subject
- Módulo
- Tema/Topic
- Tipo de contenido (slides, interactivos, quizzes)
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from src.shared.database import get_db
from src.shared.standardization import VerificationBaseService
from src.content.models import ContentResult


class ProgressService(VerificationBaseService):
    """
    Servicio para calcular y agregar progreso de estudiantes.
    """
    
    # Pesos de contenido para cálculo de progreso ponderado
    CONTENT_WEIGHTS = {
        "quiz": 0.6,
        "interactive": 0.3,
        "slide_view": 0.1,
        "default": 0.1,
    }
    
    def __init__(self):
        super().__init__(collection_name="content_results")
        self.db = get_db()
        self.logger = logging.getLogger(__name__)
    
    def get_student_progress(self, student_id: str) -> Dict:
        """
        Obtiene el progreso completo de un estudiante.
        
        Returns:
            {
                "overall_progress": float,
                "by_subject": [...],
                "activity_breakdown": {...},
                "recent_activity": [...],
                "vark_profile": {...}
            }
        """
        try:
            student_oid = ObjectId(student_id)
            
            # Obtener todos los content_results del estudiante
            results = list(self.db.content_results.find({
                "student_id": student_oid
            }).sort("recorded_at", -1))
            
            # Obtener virtual_topics del estudiante
            virtual_topics = list(self.db.virtual_topics.find({
                "student_id": student_oid
            }))
            
            # Calcular progreso por materia
            by_subject = self._calculate_progress_by_subject(student_oid, virtual_topics, results)
            
            # Calcular desglose de actividades
            activity_breakdown = self._calculate_activity_breakdown(results)
            
            # Actividad reciente (últimos 10)
            recent_activity = self._get_recent_activity(results[:10])
            
            # Obtener perfil VARK
            vark_profile = self._get_vark_profile(student_id)
            
            # Calcular progreso general ponderado
            overall_progress = self._calculate_overall_progress(by_subject)
            
            return {
                "student_id": student_id,
                "overall_progress": overall_progress,
                "by_subject": by_subject,
                "activity_breakdown": activity_breakdown,
                "recent_activity": recent_activity,
                "vark_profile": vark_profile,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error obteniendo progreso de estudiante {student_id}: {e}")
            return self._empty_progress_response(student_id)
    
    def get_class_students_progress(self, class_id: str) -> Dict:
        """
        Obtiene el progreso de todos los estudiantes de una clase.
        
        Returns:
            {
                "class_id": str,
                "students": [
                    {
                        "student_id": str,
                        "student_name": str,
                        "overall_progress": float,
                        "current_module": str,
                        "current_topic": str,
                        "activities_completed": int,
                        "last_activity": str
                    }
                ],
                "class_average": float
            }
        """
        try:
            class_oid = ObjectId(class_id)
            
            # Obtener estudiantes de la clase
            class_members = list(self.db.class_members.find({
                "class_id": class_oid,
                "role": "STUDENT"
            }))
            
            if not class_members:
                return {
                    "class_id": class_id,
                    "students": [],
                    "class_average": 0,
                    "generated_at": datetime.now().isoformat()
                }
            
            # Obtener info de la clase
            class_info = self.db.classes.find_one({"_id": class_oid})
            study_plan_id = class_info.get("study_plan_id") if class_info else None
            
            students_progress = []
            total_progress = 0
            
            for member in class_members:
                student_id = str(member["user_id"])
                student_progress = self._get_student_class_progress(
                    student_id, class_id, study_plan_id
                )
                students_progress.append(student_progress)
                total_progress += student_progress.get("overall_progress", 0)
            
            # Calcular promedio de clase
            class_average = total_progress / len(students_progress) if students_progress else 0
            
            return {
                "class_id": class_id,
                "class_name": class_info.get("name", "") if class_info else "",
                "students": students_progress,
                "class_average": round(class_average, 1),
                "total_students": len(students_progress),
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error obteniendo progreso de clase {class_id}: {e}")
            return {
                "class_id": class_id,
                "students": [],
                "class_average": 0,
                "error": str(e)
            }
    
    def get_topic_progress(self, student_id: str, topic_id: str) -> Dict:
        """
        Obtiene el progreso detallado de un estudiante en un tema específico.
        """
        try:
            student_oid = ObjectId(student_id)
            topic_oid = ObjectId(topic_id)
            
            # Obtener virtual_topic del estudiante
            virtual_topic = self.db.virtual_topics.find_one({
                "student_id": student_oid,
                "topic_id": topic_oid
            })
            
            if not virtual_topic:
                return {
                    "student_id": student_id,
                    "topic_id": topic_id,
                    "progress": 0,
                    "contents": [],
                    "not_started": True
                }
            
            virtual_topic_id = virtual_topic["_id"]
            
            # Obtener contenidos virtuales del tema
            virtual_contents = list(self.db.virtual_topic_contents.find({
                "virtual_topic_id": virtual_topic_id
            }).sort("order", 1))
            
            # Obtener resultados de contenido
            content_results = list(self.db.content_results.find({
                "student_id": student_oid,
                "topic_id": topic_oid
            }))
            
            results_by_content = {
                str(r.get("virtual_content_id")): r 
                for r in content_results 
                if r.get("virtual_content_id")
            }
            
            contents_progress = []
            completed_count = 0
            total_score = 0
            score_count = 0
            
            for vc in virtual_contents:
                vc_id = str(vc["_id"])
                result = results_by_content.get(vc_id)
                
                content_type = vc.get("content_type", "slide")
                is_interactive = self._is_interactive_content(vc)
                
                status = "not_started"
                score = None
                
                if result:
                    score = result.get("score")
                    if score is not None:
                        status = "completed"
                        completed_count += 1
                        total_score += score
                        score_count += 1
                    else:
                        status = "in_progress"
                
                contents_progress.append({
                    "content_id": vc_id,
                    "content_type": content_type,
                    "title": vc.get("title", ""),
                    "order": vc.get("order", 0),
                    "is_interactive": is_interactive,
                    "status": status,
                    "score": score,
                    "completed_at": result.get("recorded_at").isoformat() if result and result.get("recorded_at") else None
                })
            
            total_contents = len(virtual_contents)
            progress_percentage = (completed_count / total_contents * 100) if total_contents > 0 else 0
            average_score = (total_score / score_count) if score_count > 0 else None
            
            return {
                "student_id": student_id,
                "topic_id": topic_id,
                "virtual_topic_id": str(virtual_topic_id),
                "topic_name": virtual_topic.get("topic_name", ""),
                "progress": round(progress_percentage, 1),
                "completed_count": completed_count,
                "total_count": total_contents,
                "average_score": round(average_score, 1) if average_score else None,
                "contents": contents_progress,
                "last_activity": content_results[0].get("recorded_at").isoformat() if content_results else None
            }
            
        except Exception as e:
            self.logger.error(f"Error obteniendo progreso de tema {topic_id}: {e}")
            return {
                "student_id": student_id,
                "topic_id": topic_id,
                "progress": 0,
                "error": str(e)
            }
    
    # ================ Private Methods ================
    
    def _calculate_progress_by_subject(
        self, 
        student_oid: ObjectId, 
        virtual_topics: List[Dict],
        results: List[Dict]
    ) -> List[Dict]:
        """Calcula el progreso agrupado por materia."""
        
        # Agrupar virtual_topics por subject
        subjects_data = {}
        
        for vt in virtual_topics:
            topic_id = vt.get("topic_id")
            if not topic_id:
                continue
            
            # Obtener info del topic original
            topic = self.db.topics.find_one({"_id": topic_id})
            if not topic:
                continue
            
            module_id = topic.get("module_id")
            if not module_id:
                continue
            
            # Obtener módulo
            module = self.db.modules.find_one({"_id": module_id})
            if not module:
                continue
            
            study_plan_id = module.get("study_plan_id")
            if not study_plan_id:
                continue
            
            # Obtener study_plan para saber la materia
            study_plan = self.db.study_plans.find_one({"_id": study_plan_id})
            if not study_plan:
                continue
            
            subject_id = study_plan.get("subject_id")
            class_id = study_plan.get("class_id")
            
            # Obtener nombre de materia
            subject_name = "Sin materia"
            if subject_id:
                subject = self.db.subjects.find_one({"_id": subject_id})
                if subject:
                    subject_name = subject.get("name", "Sin materia")
            
            subject_key = str(subject_id) if subject_id else str(study_plan_id)
            
            if subject_key not in subjects_data:
                subjects_data[subject_key] = {
                    "subject_id": subject_key,
                    "subject_name": subject_name,
                    "class_id": str(class_id) if class_id else None,
                    "modules": {},
                    "total_topics": 0,
                    "completed_topics": 0
                }
            
            # Agregar módulo
            module_key = str(module_id)
            if module_key not in subjects_data[subject_key]["modules"]:
                subjects_data[subject_key]["modules"][module_key] = {
                    "module_id": module_key,
                    "module_name": module.get("name", ""),
                    "module_order": module.get("order", 0),
                    "topics": [],
                    "completed_topics": 0,
                    "total_topics": 0
                }
            
            # Calcular progreso del tema
            vt_id = vt["_id"]
            virtual_contents = list(self.db.virtual_topic_contents.find({
                "virtual_topic_id": vt_id
            }))
            
            topic_results = [r for r in results if r.get("topic_id") == topic_id]
            completed_contents = len([r for r in topic_results if r.get("score") is not None])
            total_contents = len(virtual_contents)
            
            topic_progress = (completed_contents / total_contents * 100) if total_contents > 0 else 0
            is_completed = topic_progress >= 100
            
            topic_info = {
                "topic_id": str(topic_id),
                "topic_name": topic.get("name", ""),
                "virtual_topic_id": str(vt_id),
                "progress": round(topic_progress, 1),
                "completed_contents": completed_contents,
                "total_contents": total_contents,
                "is_completed": is_completed
            }
            
            subjects_data[subject_key]["modules"][module_key]["topics"].append(topic_info)
            subjects_data[subject_key]["modules"][module_key]["total_topics"] += 1
            subjects_data[subject_key]["total_topics"] += 1
            
            if is_completed:
                subjects_data[subject_key]["modules"][module_key]["completed_topics"] += 1
                subjects_data[subject_key]["completed_topics"] += 1
        
        # Convertir a lista y calcular porcentajes
        result = []
        for subject_key, data in subjects_data.items():
            modules_list = list(data["modules"].values())
            modules_list.sort(key=lambda x: x.get("module_order", 0))
            
            # Calcular progreso del módulo
            for mod in modules_list:
                if mod["total_topics"] > 0:
                    mod["progress_percentage"] = round(
                        mod["completed_topics"] / mod["total_topics"] * 100, 1
                    )
                else:
                    mod["progress_percentage"] = 0
                
                # Ordenar topics
                mod["topics"].sort(key=lambda x: x.get("topic_name", ""))
            
            # Calcular progreso de materia
            if data["total_topics"] > 0:
                progress = round(data["completed_topics"] / data["total_topics"] * 100, 1)
            else:
                progress = 0
            
            # Encontrar módulo y tema actual
            current_module = None
            current_topic = None
            for mod in modules_list:
                for topic in mod["topics"]:
                    if not topic["is_completed"]:
                        current_module = mod["module_name"]
                        current_topic = topic["topic_name"]
                        break
                if current_module:
                    break
            
            result.append({
                "subject_id": data["subject_id"],
                "subject_name": data["subject_name"],
                "class_id": data["class_id"],
                "progress_percentage": progress,
                "completed_topics": data["completed_topics"],
                "total_topics": data["total_topics"],
                "current_module": current_module,
                "current_topic": current_topic,
                "modules": modules_list
            })
        
        return result
    
    def _calculate_activity_breakdown(self, results: List[Dict]) -> Dict:
        """Calcula el desglose de actividades por tipo."""
        
        slides_viewed = 0
        slides_total = 0
        interactive_completed = 0
        interactive_total = 0
        quizzes_passed = 0
        quizzes_total = 0
        quiz_scores = []
        
        for r in results:
            norm_type = r.get("normalization_type", "default")
            score = r.get("score")
            
            if norm_type == "slide_view":
                slides_total += 1
                if score is not None:
                    slides_viewed += 1
            elif norm_type == "interactive":
                interactive_total += 1
                if score is not None:
                    interactive_completed += 1
            elif norm_type == "quiz":
                quizzes_total += 1
                if score is not None:
                    quiz_scores.append(score)
                    if score >= 0.6:  # 60% para aprobar
                        quizzes_passed += 1
        
        avg_quiz_score = round(sum(quiz_scores) / len(quiz_scores) * 100, 1) if quiz_scores else 0
        
        return {
            "slides": {
                "viewed": slides_viewed,
                "total": slides_total,
                "percentage": round(slides_viewed / slides_total * 100, 1) if slides_total > 0 else 0
            },
            "interactive": {
                "completed": interactive_completed,
                "total": interactive_total,
                "percentage": round(interactive_completed / interactive_total * 100, 1) if interactive_total > 0 else 0
            },
            "quizzes": {
                "passed": quizzes_passed,
                "total": quizzes_total,
                "percentage": round(quizzes_passed / quizzes_total * 100, 1) if quizzes_total > 0 else 0,
                "average_score": avg_quiz_score
            },
            "total_activities": len(results),
            "completed_activities": slides_viewed + interactive_completed + quizzes_passed
        }
    
    def _get_recent_activity(self, results: List[Dict]) -> List[Dict]:
        """Obtiene las actividades recientes formateadas."""
        
        recent = []
        for r in results:
            recent.append({
                "content_id": str(r.get("virtual_content_id") or r.get("content_id", "")),
                "content_type": r.get("content_type", "unknown"),
                "normalization_type": r.get("normalization_type", "default"),
                "score": r.get("score"),
                "recorded_at": r.get("recorded_at").isoformat() if r.get("recorded_at") else None,
                "topic_id": str(r.get("topic_id")) if r.get("topic_id") else None
            })
        
        return recent
    
    def _get_vark_profile(self, student_id: str) -> Optional[Dict]:
        """Obtiene el perfil VARK del estudiante."""
        try:
            cognitive_profile = self.db.cognitive_profiles.find_one({
                "user_id": ObjectId(student_id)
            })
            
            if not cognitive_profile:
                return None
            
            # learning_style puede estar en el documento principal o dentro de "profile"
            learning_style = cognitive_profile.get("learning_style", {})
            
            # Si está vacío, intentar cargar desde el campo "profile" serializado
            if not learning_style:
                profile_json = cognitive_profile.get("profile")
                if profile_json:
                    import json
                    try:
                        profile_data = json.loads(profile_json) if isinstance(profile_json, str) else profile_json
                        learning_style = profile_data.get("learning_style", {})
                    except:
                        pass
            
            # Extraer valores VARK
            visual = learning_style.get("visual", 0)
            auditory = learning_style.get("auditory", 0)
            reading_writing = learning_style.get("reading_writing", 0)
            kinesthetic = learning_style.get("kinesthetic", 0)
            
            # Determinar estilo predominante
            vark_values = {
                "visual": visual,
                "auditory": auditory,
                "reading_writing": reading_writing,
                "kinesthetic": kinesthetic
            }
            
            primary_style = None
            if any(v > 0 for v in vark_values.values()):
                primary_style = max(vark_values.items(), key=lambda x: x[1])[0]
            
            return {
                "visual": visual,
                "auditory": auditory,
                "reading_writing": reading_writing,
                "kinesthetic": kinesthetic,
                "primary_style": primary_style,
                "updated_at": cognitive_profile.get("updated_at").isoformat() if cognitive_profile.get("updated_at") else None
            }
            
        except Exception as e:
            self.logger.warning(f"Error obteniendo perfil VARK: {e}")
            return None
    
    def _calculate_overall_progress(self, by_subject: List[Dict]) -> float:
        """Calcula el progreso general ponderado."""
        if not by_subject:
            return 0
        
        total_weight = 0
        weighted_progress = 0
        
        for subject in by_subject:
            # Usar cantidad de topics como peso
            weight = subject.get("total_topics", 1)
            progress = subject.get("progress_percentage", 0)
            
            weighted_progress += progress * weight
            total_weight += weight
        
        return round(weighted_progress / total_weight, 1) if total_weight > 0 else 0
    
    def _get_student_class_progress(
        self, 
        student_id: str, 
        class_id: str, 
        study_plan_id: Optional[ObjectId]
    ) -> Dict:
        """Obtiene el progreso resumido de un estudiante en una clase."""
        try:
            student_oid = ObjectId(student_id)
            
            # Obtener info del estudiante
            user = self.db.users.find_one({"_id": student_oid})
            student_name = ""
            if user:
                student_name = f"{user.get('firstName', '')} {user.get('lastName', '')}".strip()
                if not student_name:
                    student_name = user.get("email", "Sin nombre")
            
            # Obtener virtual_topics del estudiante
            virtual_topics = list(self.db.virtual_topics.find({
                "student_id": student_oid
            }))
            
            if not virtual_topics:
                return {
                    "student_id": student_id,
                    "student_name": student_name,
                    "overall_progress": 0,
                    "current_module": None,
                    "current_topic": None,
                    "activities_completed": 0,
                    "last_activity": None
                }
            
            # Obtener resultados
            results = list(self.db.content_results.find({
                "student_id": student_oid
            }).sort("recorded_at", -1))
            
            # Filtrar por study_plan si está disponible
            if study_plan_id:
                # Obtener topics del study_plan
                modules = list(self.db.modules.find({"study_plan_id": study_plan_id}))
                module_ids = [m["_id"] for m in modules]
                topics = list(self.db.topics.find({"module_id": {"$in": module_ids}}))
                topic_ids = set(str(t["_id"]) for t in topics)
                
                virtual_topics = [vt for vt in virtual_topics if str(vt.get("topic_id")) in topic_ids]
                results = [r for r in results if str(r.get("topic_id")) in topic_ids]
            
            # Calcular progreso
            total_contents = 0
            completed_contents = 0
            current_module = None
            current_topic = None
            
            for vt in virtual_topics:
                vt_contents = self.db.virtual_topic_contents.count_documents({
                    "virtual_topic_id": vt["_id"]
                })
                total_contents += vt_contents
                
                vt_results = [r for r in results if r.get("topic_id") == vt.get("topic_id")]
                completed = len([r for r in vt_results if r.get("score") is not None])
                completed_contents += completed
                
                # Encontrar tema actual
                if completed < vt_contents and not current_topic:
                    topic = self.db.topics.find_one({"_id": vt.get("topic_id")})
                    if topic:
                        current_topic = topic.get("name", "")
                        module = self.db.modules.find_one({"_id": topic.get("module_id")})
                        if module:
                            current_module = module.get("name", "")
            
            progress = round(completed_contents / total_contents * 100, 1) if total_contents > 0 else 0
            last_activity = results[0].get("recorded_at").isoformat() if results else None
            
            return {
                "student_id": student_id,
                "student_name": student_name,
                "overall_progress": progress,
                "current_module": current_module,
                "current_topic": current_topic,
                "activities_completed": completed_contents,
                "total_activities": total_contents,
                "last_activity": last_activity
            }
            
        except Exception as e:
            self.logger.error(f"Error obteniendo progreso de estudiante {student_id}: {e}")
            return {
                "student_id": student_id,
                "student_name": "",
                "overall_progress": 0,
                "error": str(e)
            }
    
    def _is_interactive_content(self, virtual_content: Dict) -> bool:
        """Determina si un contenido virtual es interactivo."""
        content_type = (virtual_content.get("content_type") or "").lower()
        
        interactive_types = [
            "game", "simulation", "interactive", "interactive_exercise",
            "virtual_lab", "mini_game", "challenge"
        ]
        
        if content_type in interactive_types:
            return True
        
        if virtual_content.get("render_engine") == "html_template":
            return True
        
        if virtual_content.get("content", {}).get("attachment", {}).get("type") == "interactive_template":
            return True
        
        return False
    
    def _empty_progress_response(self, student_id: str) -> Dict:
        """Retorna una respuesta vacía de progreso."""
        return {
            "student_id": student_id,
            "overall_progress": 0,
            "by_subject": [],
            "activity_breakdown": {
                "slides": {"viewed": 0, "total": 0, "percentage": 0},
                "interactive": {"completed": 0, "total": 0, "percentage": 0},
                "quizzes": {"passed": 0, "total": 0, "percentage": 0, "average_score": 0},
                "total_activities": 0,
                "completed_activities": 0
            },
            "recent_activity": [],
            "vark_profile": None,
            "generated_at": datetime.now().isoformat()
        }

