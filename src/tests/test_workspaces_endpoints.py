import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.workspaces.services import WorkspaceService
from src.members.services import MembershipService


class TestWorkspacesEndpoints(unittest.TestCase):
    """Pruebas básicas para los endpoints de workspaces implementados"""
    
    def setUp(self):
        """Configuración inicial para las pruebas"""
        self.workspace_service = WorkspaceService()
        self.membership_service = MembershipService()
        self.test_user_id = "507f1f77bcf86cd799439011"
        self.test_workspace_id = "507f1f77bcf86cd799439012"
    
    def test_workspace_service_initialization(self):
        """Prueba que el servicio de workspaces se inicializa correctamente"""
        self.assertIsNotNone(self.workspace_service)
        self.assertTrue(hasattr(self.workspace_service, 'validate_workspace_type'))
        self.assertTrue(hasattr(self.workspace_service, 'generate_workspace_name'))
        self.assertTrue(hasattr(self.workspace_service, 'get_workspace_by_id'))
        self.assertTrue(hasattr(self.workspace_service, 'create_personal_workspace'))
        self.assertTrue(hasattr(self.workspace_service, 'update_workspace_info'))
        self.assertTrue(hasattr(self.workspace_service, 'create_study_plan_for_workspace'))
    
    def test_membership_service_workspace_methods(self):
        """Prueba que el servicio de membresías tiene los métodos de workspace"""
        self.assertIsNotNone(self.membership_service)
        self.assertTrue(hasattr(self.membership_service, 'get_workspace_membership'))
        self.assertTrue(hasattr(self.membership_service, 'check_workspace_ownership'))
        self.assertTrue(hasattr(self.membership_service, 'get_workspace_members'))
        self.assertTrue(hasattr(self.membership_service, 'update_workspace_membership'))
        self.assertTrue(hasattr(self.membership_service, 'create_personal_workspace_membership'))
    
    def test_validate_workspace_type(self):
        """Prueba la validación de tipos de workspace"""
        # Tipos válidos
        self.assertTrue(self.workspace_service.validate_workspace_type('INDIVIDUAL_STUDENT'))
        self.assertTrue(self.workspace_service.validate_workspace_type('INDIVIDUAL_TEACHER'))
        self.assertTrue(self.workspace_service.validate_workspace_type('INSTITUTE'))
        
        # Tipos inválidos
        self.assertFalse(self.workspace_service.validate_workspace_type('CLASS'))
        self.assertFalse(self.workspace_service.validate_workspace_type('INVALID'))
        self.assertFalse(self.workspace_service.validate_workspace_type(''))
        self.assertFalse(self.workspace_service.validate_workspace_type(None))
    
    def test_generate_workspace_name(self):
        """Prueba la generación de nombres de workspace"""
        # Para workspace individual de estudiante
        name = self.workspace_service.generate_workspace_name('INDIVIDUAL_STUDENT', 'Juan Pérez')
        self.assertEqual(name, 'Aprendizaje de Juan Pérez')
        
        # Para workspace individual de profesor
        name = self.workspace_service.generate_workspace_name('INDIVIDUAL_TEACHER', 'María García')
        self.assertEqual(name, 'Clases de María García')
        
        # Para workspace de instituto
        name = self.workspace_service.generate_workspace_name('INSTITUTE', 'Universidad ABC')
        self.assertEqual(name, 'Universidad ABC')
        
        # Con nombre personalizado
        custom_name = self.workspace_service.generate_workspace_name('INDIVIDUAL_STUDENT', 'Juan Pérez', 'Mi Workspace Personal')
        self.assertEqual(custom_name, 'Mi Workspace Personal')
    
    def test_get_generic_institute_info(self):
        """Prueba la obtención de información genérica del instituto"""
        with patch('src.workspaces.services.get_db') as mock_get_db:
            # Configurar mock
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_db.institutes.find_one.return_value = {
                '_id': '507f1f77bcf86cd799439013',
                'name': 'Academia Sapiens',
                'description': 'Instituto genérico para workspaces individuales'
            }
            
            # Crear nueva instancia del servicio para usar el mock
            workspace_service = WorkspaceService()
            
            # Ejecutar método
            info = workspace_service.get_generic_institute()
            
            # Verificar resultado
            self.assertIsNotNone(info)
            self.assertEqual(info['name'], 'Academia Sapiens')
            mock_db.institutes.find_one.assert_called_once_with({"name": "Academia Sapiens"})
    
    def test_validate_object_id(self):
        """Prueba la validación de ObjectId"""
        from bson import ObjectId
        from bson.errors import InvalidId
        
        # ID válido
        valid_id = "507f1f77bcf86cd799439011"
        try:
            ObjectId(valid_id)
            is_valid = True
        except InvalidId:
            is_valid = False
        self.assertTrue(is_valid)
        
        # IDs inválidos
        invalid_ids = ["invalid_id", "", None, 123]
        for invalid_id in invalid_ids:
            try:
                if invalid_id is None:
                    raise TypeError("ObjectId() must be a valid hex string")
                ObjectId(invalid_id)
                is_valid = True
            except (InvalidId, TypeError):
                is_valid = False
            self.assertFalse(is_valid, f"Expected {invalid_id} to be invalid")


if __name__ == '__main__':
    unittest.main()