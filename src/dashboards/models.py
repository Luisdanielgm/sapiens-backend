from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional

class AdminDashboard:
    def __init__(self,
                 system_stats: Dict[str, int],
                 top_institutes: List[Dict],
                 institutes_performance: List[Dict],
                 recent_stats: Dict[str, int],
                 generated_at: datetime = None):
        self.system_stats = system_stats
        self.top_institutes = top_institutes
        self.institutes_performance = institutes_performance
        self.recent_stats = recent_stats
        self.generated_at = generated_at or datetime.now()

    def to_dict(self) -> dict:
        return {
            "system_stats": self.system_stats,
            "top_institutes": self.top_institutes,
            "institutes_performance": self.institutes_performance,
            "recent_stats": self.recent_stats,
            "generated_at": self.generated_at
        }

class TeacherDashboard:
    def __init__(self,
                 teacher_id: str,
                 classes: List[Dict],
                 overall_metrics: Dict[str, float]):
        self.teacher_id = ObjectId(teacher_id)
        self.classes = classes
        self.overall_metrics = overall_metrics
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "teacher_id": str(self.teacher_id),
            "classes": self.classes,
            "overall_metrics": self.overall_metrics,
            "created_at": self.created_at
        }

class StudentDashboard:
    def __init__(self,
                 student_id: str,
                 classes: List[Dict],
                 subjects: List[Dict]):
        self.student_id = ObjectId(student_id)
        self.classes = classes
        self.subjects = subjects
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "student_id": str(self.student_id),
            "classes": self.classes,
            "subjects": self.subjects,
            "created_at": self.created_at
        }

class InstituteDashboard:
    def __init__(self,
                 institute_id: str,
                 overview_metrics: Dict[str, int],
                 programs_stats: List[Dict],
                 levels_stats: List[Dict],
                 sections_stats: Dict[str, any],
                 subjects_stats: Dict[str, any],
                 periods_stats: Dict[str, any],
                 classes_stats: Dict[str, any],
                 teachers_stats: Dict[str, any],
                 students_stats: Dict[str, any],
                 timestamp: datetime = None):
        self.institute_id = ObjectId(institute_id)
        self.overview_metrics = overview_metrics
        self.programs_stats = programs_stats
        self.levels_stats = levels_stats
        self.sections_stats = sections_stats
        self.subjects_stats = subjects_stats
        self.periods_stats = periods_stats
        self.classes_stats = classes_stats
        self.teachers_stats = teachers_stats
        self.students_stats = students_stats
        self.timestamp = timestamp or datetime.now()
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "institute_id": str(self.institute_id),
            "overview_metrics": self.overview_metrics,
            "programs_stats": self.programs_stats,
            "levels_stats": self.levels_stats,
            "sections_stats": self.sections_stats,
            "subjects_stats": self.subjects_stats,
            "periods_stats": self.periods_stats,
            "classes_stats": self.classes_stats,
            "teachers_stats": self.teachers_stats,
            "students_stats": self.students_stats,
            "timestamp": self.timestamp,
            "created_at": self.created_at
        } 