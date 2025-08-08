import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from bson import ObjectId

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.study_plans.services import StudyPlanService

class TestUnifiedStudyPlans(unittest.TestCase):
    @patch('src.shared.database.get_db')
    def test_create_personal_study_plan(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.study_plans_per_subject.insert_one.return_value.inserted_id = ObjectId()

        service = StudyPlanService()
        plan_id = service.create_personal_study_plan(
            user_id=str(ObjectId()),
            workspace_id=str(ObjectId()),
            title="Mi Plan Personal",
            description="Descripción del plan",
            objectives=["obj1"]
        )
        self.assertTrue(isinstance(plan_id, str))
        mock_db.study_plans_per_subject.insert_one.assert_called()

    @patch('src.shared.database.get_db')
    def test_get_workspace_study_plan_endpoint(self, mock_get_db):
        # Mock plan
        sample_id = ObjectId()
        mock_plan = {
            "_id": sample_id,
            "name": "Plan Personal",
            "description": "",
            "author_id": ObjectId(),
            "workspace_id": ObjectId("507f1f77bcf86cd799439012"),
            "is_personal": True
        }
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.study_plans_per_subject.find_one.return_value = mock_plan

        service = StudyPlanService()
        plan = service.get_study_plan(str(sample_id))
        self.assertIsNotNone(plan)
        self.assertEqual(plan["_id"], str(sample_id))
        self.assertTrue(plan["is_personal"]) 

if __name__ == '__main__':
    unittest.main()