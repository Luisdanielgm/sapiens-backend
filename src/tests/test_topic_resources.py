import unittest
import json
from unittest.mock import patch, MagicMock
from bson import ObjectId

from src.study_plans.models import TopicResource
from src.study_plans.services import TopicResourceService


class TestTopicResource(unittest.TestCase):
    """Pruebas para el modelo y servicio de relación entre temas y recursos"""
    
    def setUp(self):
        """Configuración inicial para las pruebas"""
        self.topic_id = str(ObjectId())
        self.resource_id = str(ObjectId())
        self.user_id = str(ObjectId())
        
        # Crear un objeto de prueba
        self.test_topic_resource = TopicResource(
            topic_id=self.topic_id,
            resource_id=self.resource_id,
            relevance_score=0.8,
            recommended_for=["visual", "kinesthetic"],
            usage_context="primary",
            content_types=["video", "interactive"],
            created_by=self.user_id,
            status="active"
        )
        
        # Datos para la API
        self.link_data = {
            "relevance_score": 0.8,
            "recommended_for": ["visual", "kinesthetic"],
            "usage_context": "primary",
            "content_types": ["video", "interactive"]
        }
    
    def test_topic_resource_model(self):
        """Prueba la creación y serialización del modelo TopicResource"""
        # Verificar que el modelo se crea correctamente
        self.assertEqual(self.test_topic_resource.topic_id, self.topic_id)
        self.assertEqual(self.test_topic_resource.resource_id, self.resource_id)
        self.assertEqual(self.test_topic_resource.relevance_score, 0.8)
        self.assertEqual(self.test_topic_resource.recommended_for, ["visual", "kinesthetic"])
        
        # Verificar serialización
        dict_data = self.test_topic_resource.to_dict()
        self.assertEqual(dict_data["topic_id"], ObjectId(self.topic_id))
        self.assertEqual(dict_data["resource_id"], ObjectId(self.resource_id))
        self.assertEqual(dict_data["status"], "active")
    
    @patch("src.study_plans.services.TopicResourceService.collection")
    @patch("src.study_plans.services.TopicResourceService.db")
    def test_link_resource_to_topic(self, mock_db, mock_collection):
        """Prueba la vinculación de un recurso a un tema"""
        # Configurar los mocks
        mock_db.topics.find_one.return_value = {"_id": ObjectId(self.topic_id), "name": "Test Topic"}
        mock_db.resources.find_one.return_value = {"_id": ObjectId(self.resource_id), "name": "Test Resource"}
        mock_collection.find_one.return_value = None
        mock_collection.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        
        # Crear servicio y ejecutar método
        service = TopicResourceService()
        success, result = service.link_resource_to_topic(
            topic_id=self.topic_id,
            resource_id=self.resource_id,
            relevance_score=0.8,
            recommended_for=["visual", "kinesthetic"],
            usage_context="primary",
            content_types=["video", "interactive"],
            created_by=self.user_id
        )
        
        # Verificar resultado
        self.assertTrue(success)
        mock_collection.insert_one.assert_called_once()
        
        # Probar el caso donde ya existe la relación
        mock_collection.find_one.return_value = {
            "_id": ObjectId(),
            "topic_id": ObjectId(self.topic_id),
            "resource_id": ObjectId(self.resource_id),
            "relevance_score": 0.5
        }
        
        success, result = service.link_resource_to_topic(
            topic_id=self.topic_id,
            resource_id=self.resource_id,
            relevance_score=0.9,
            recommended_for=["visual"]
        )
        
        self.assertTrue(success)
        mock_collection.update_one.assert_called_once()
    
    @patch("src.study_plans.services.TopicResourceService.collection")
    @patch("src.study_plans.services.TopicResourceService.db")
    def test_unlink_resource_from_topic(self, mock_db, mock_collection):
        """Prueba desvinculación de un recurso de un tema"""
        # Configurar el mock
        mock_collection.update_one.return_value = MagicMock(modified_count=1)
        
        # Ejecutar método
        service = TopicResourceService()
        success, message = service.unlink_resource_from_topic(
            topic_id=self.topic_id,
            resource_id=self.resource_id
        )
        
        # Verificar resultado
        self.assertTrue(success)
        mock_collection.update_one.assert_called_once()
        
        # Caso donde no se encuentra la relación
        mock_collection.update_one.return_value = MagicMock(modified_count=0)
        success, message = service.unlink_resource_from_topic(
            topic_id=self.topic_id,
            resource_id=self.resource_id
        )
        
        self.assertFalse(success)
        self.assertIn("No se encontró", message)
    
    @patch("src.study_plans.services.TopicResourceService.collection")
    @patch("src.study_plans.services.TopicResourceService.db")
    def test_get_topic_resources(self, mock_db, mock_collection):
        """Prueba la obtención de recursos asociados a un tema"""
        # Configurar los mocks
        mock_topic_resources = [
            {
                "_id": ObjectId(),
                "topic_id": ObjectId(self.topic_id),
                "resource_id": ObjectId(self.resource_id),
                "relevance_score": 0.8,
                "recommended_for": ["visual", "kinesthetic"],
                "usage_context": "primary",
                "status": "active"
            }
        ]
        
        mock_resources = [
            {
                "_id": ObjectId(self.resource_id),
                "name": "Test Resource",
                "resource_type": "video",
                "url": "https://example.com/video.mp4",
                "created_by": ObjectId(self.user_id)
            }
        ]
        
        mock_collection.find.return_value = mock_topic_resources
        mock_db.resources.find.return_value = mock_resources
        
        # Ejecutar método
        service = TopicResourceService()
        resources = service.get_topic_resources(
            topic_id=self.topic_id,
            cognitive_profile={"learning_style": {"visual": 0.8, "verbal": 0.2}}
        )
        
        # Verificar resultado
        self.assertEqual(len(resources), 1)
        self.assertIn("profile_match", resources[0])
        self.assertIn("relevance_score", resources[0])
        self.assertEqual(resources[0]["name"], "Test Resource")
    
    @patch("src.study_plans.services.TopicResourceService.collection")
    @patch("src.study_plans.services.TopicResourceService.db")
    def test_get_resource_topics(self, mock_db, mock_collection):
        """Prueba la obtención de temas asociados a un recurso"""
        # Configurar los mocks
        mock_relationships = [
            {
                "_id": ObjectId(),
                "topic_id": ObjectId(self.topic_id),
                "resource_id": ObjectId(self.resource_id),
                "relevance_score": 0.8,
                "usage_context": "primary",
                "status": "active"
            }
        ]
        
        mock_topics = [
            {
                "_id": ObjectId(self.topic_id),
                "name": "Test Topic",
                "description": "Tema de prueba",
                "module_id": ObjectId(),
                "status": "active"
            }
        ]
        
        mock_collection.find.return_value = mock_relationships
        mock_db.topics.find.return_value = mock_topics
        mock_db.modules.find_one.return_value = {"name": "Test Module", "study_plan_id": ObjectId()}
        mock_db.study_plans_per_subject.find_one.return_value = {"name": "Test Study Plan"}
        
        # Ejecutar método
        service = TopicResourceService()
        topics = service.get_resource_topics(resource_id=self.resource_id)
        
        # Verificar resultado
        self.assertEqual(len(topics), 1)
        self.assertEqual(topics[0]["name"], "Test Topic")
        self.assertIn("module_name", topics[0])
        self.assertIn("relevance_score", topics[0])


if __name__ == "__main__":
    unittest.main() 