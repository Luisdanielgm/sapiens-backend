from typing import List, Dict
from src.shared.database import get_db
from bson import ObjectId
from src.study_plans.services import StudyPlanAssignmentService

class MarketplaceService:
    def __init__(self):
        self.db = get_db()
        self.plans_collection = self.db.study_plans_per_subject
        self.assignment_service = StudyPlanAssignmentService()

    def list_public_plans(self) -> List[Dict]:
        """Lists all study plans marked as public."""
        try:
            public_plans = list(self.plans_collection.find({"is_public": True, "status": "approved"}))
            for plan in public_plans:
                plan["_id"] = str(plan["_id"])
                if isinstance(plan.get("author_id"), ObjectId):
                    plan["author_id"] = str(plan["author_id"])
                if isinstance(plan.get("workspace_id"), ObjectId):
                    plan["workspace_id"] = str(plan["workspace_id"])
                if isinstance(plan.get("institute_id"), ObjectId):
                    plan["institute_id"] = str(plan["institute_id"])
            return public_plans
        except Exception as e:
            # Consider logging the error
            return []

    def fulfill_purchase(self, user_id: str, plan_id: str):
        """Creates a study plan assignment for a user after a successful purchase."""
        try:
            # This is a simplified version. In a real application, you would also create
            # a personal workspace for the user if they don't have one, and assign the plan
            # to a class within that workspace.
            assignment_data = {
                "study_plan_id": plan_id,
                "class_id": "615b5e3b8e3f3a2e4b7d8e3f", # Placeholder for a generic class
                "subperiod_id": "615b5e3b8e3f3a2e4b7d8e3f", # Placeholder
                "assigned_by": user_id, # The user themselves
                "is_active": True
            }
            self.assignment_service.assign_plan_to_class(assignment_data)
        except Exception as e:
            # Log the error
            print(f"Error fulfilling purchase for user {user_id} and plan {plan_id}: {e}")