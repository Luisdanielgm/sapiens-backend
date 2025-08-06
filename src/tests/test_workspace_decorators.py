import unittest
from unittest.mock import patch, MagicMock, Mock
from flask import Flask, request, jsonify
from bson import ObjectId
import sys
import os

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.shared.decorators import (
    workspace_type_required,
    workspace_access_required,
    workspace_owner_required,
    workspace_role_required,
    workspace_data_isolation_required
)
from src.shared.middleware import (
    validate_resource_access,
    apply_workspace_data_filters,
    get_current_workspace_info
)


class TestWorkspaceDecorators(unittest.TestCase):
    """Pruebas para los decoradores de workspace implementados"""
    
    def setUp(self):
        """Configuración inicial para las pruebas"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Mock data
        self.test_user_id = "507f1f77bcf86cd799439011"
        self.test_workspace_id = "507f1f77bcf86cd799439012"
        self.test_institute_id = "507f1f77bcf86cd799439013"
        self.test_class_id = "507f1f77bcf86cd799439014"
    
    def test_workspace_type_required_individual_student(self):
        """Prueba el decorador workspace_type_required para estudiantes individuales"""
        with self.app.test_request_context():
            # Simular workspace de estudiante individual
            request.current_workspace = {
                'workspace_type': 'INDIVIDUAL_STUDENT',
                'user_id': ObjectId(self.test_user_id)
            }
            
            @workspace_type_required(['INDIVIDUAL'])
            def test_endpoint():
                return jsonify({'success': True})
            
            # Debería permitir acceso
            result = test_endpoint()
            self.assertIsNotNone(result)
    
    def test_workspace_type_required_denied(self):
        """Prueba que el decorador deniegue acceso a tipos no permitidos"""
        with self.app.test_request_context():
            # Simular workspace institucional
            request.current_workspace = {
                'workspace_type': 'INSTITUTE',
                'institute_id': ObjectId(self.test_institute_id)
            }
            
            @workspace_type_required(['INDIVIDUAL'])
            def test_endpoint():
                return jsonify({'success': True})
            
            # Debería denegar acceso
            result = test_endpoint()
            self.assertEqual(result[1], 403)  # Status code 403
    
    def test_workspace_role_required_owner(self):
        """Prueba el decorador workspace_role_required para propietarios"""
        with self.app.test_request_context():
            # Simular workspace con rol de propietario
            request.current_workspace = {
                'workspace_type': 'INDIVIDUAL_STUDENT',
                'role': 'OWNER',
                'user_id': ObjectId(self.test_user_id)
            }
            
            @workspace_role_required(['OWNER'])
            def test_endpoint():
                return jsonify({'success': True})
            
            # Debería permitir acceso
            result = test_endpoint()
            self.assertIsNotNone(result)
    
    def test_workspace_role_required_denied(self):
        """Prueba que el decorador deniegue acceso a roles no permitidos"""
        with self.app.test_request_context():
            # Simular workspace con rol de estudiante
            request.current_workspace = {
                'workspace_type': 'INSTITUTE',
                'role': 'STUDENT',
                'user_id': ObjectId(self.test_user_id)
            }
            
            @workspace_role_required(['ADMIN', 'TEACHER'])
            def test_endpoint():
                return jsonify({'success': True})
            
            # Debería denegar acceso
            result = test_endpoint()
            self.assertEqual(result[1], 403)  # Status code 403
    
    def test_workspace_data_isolation_individual_student(self):
        """Prueba el aislamiento de datos para estudiantes individuales"""
        with self.app.test_request_context():
            # Simular workspace de estudiante individual
            request.current_workspace = {
                'workspace_type': 'INDIVIDUAL_STUDENT',
                'user_id': ObjectId(self.test_user_id)
            }
            request.user_id = self.test_user_id
            
            @workspace_data_isolation_required
            def test_endpoint():
                # Verificar que se agregaron los filtros de aislamiento
                filters = getattr(request, 'isolation_filters', {})
                return jsonify({'filters': str(filters)})
            
            result = test_endpoint()
            self.assertIsNotNone(result)
            # Verificar que se agregaron filtros para el usuario
            self.assertTrue(hasattr(request, 'isolation_filters'))
    
    def test_workspace_data_isolation_individual_teacher(self):
        """Prueba el aislamiento de datos para profesores individuales"""
        with self.app.test_request_context():
            # Simular workspace de profesor individual
            request.current_workspace = {
                'workspace_type': 'INDIVIDUAL_TEACHER',
                'class_id': ObjectId(self.test_class_id),
                'user_id': ObjectId(self.test_user_id)
            }
            request.user_id = self.test_user_id
            
            @workspace_data_isolation_required
            def test_endpoint():
                # Verificar que se agregaron los filtros de aislamiento
                filters = getattr(request, 'isolation_filters', {})
                return jsonify({'filters': str(filters)})
            
            result = test_endpoint()
            self.assertIsNotNone(result)
            # Verificar que se agregaron filtros para la clase
            self.assertTrue(hasattr(request, 'isolation_filters'))
            filters = request.isolation_filters
            # Los filtros deben estar en formato $or
            self.assertIn('$or', filters)
            or_conditions = filters['$or']
            # Verificar que incluye filtros para class_id y created_by
            self.assertTrue(any('class_id' in condition for condition in or_conditions))
            self.assertTrue(any('created_by' in condition for condition in or_conditions))


class TestWorkspaceMiddleware(unittest.TestCase):
    """Pruebas para el middleware de workspace implementado"""
    
    def setUp(self):
        """Configuración inicial para las pruebas"""
        self.test_user_id = "507f1f77bcf86cd799439011"
        self.test_institute_id = "507f1f77bcf86cd799439013"
        self.test_class_id = "507f1f77bcf86cd799439014"
    
    def test_validate_resource_access_individual_student(self):
        """Prueba la validación de acceso para estudiantes individuales"""
        workspace_info = {
            'workspace_type': 'INDIVIDUAL_STUDENT',
            'user_id': self.test_user_id
        }
        
        # Recurso propio del estudiante
        resource_data = {
            'user_id': self.test_user_id,
            'title': 'Mi plan de estudio'
        }
        
        # Debería tener acceso
        has_access = validate_resource_access(resource_data, workspace_info, self.test_user_id)
        self.assertTrue(has_access)
        
        # Recurso de otro estudiante
        other_resource = {
            'user_id': '507f1f77bcf86cd799439099',
            'title': 'Plan de otro estudiante'
        }
        
        # No debería tener acceso
        has_access = validate_resource_access(other_resource, workspace_info, self.test_user_id)
        self.assertFalse(has_access)
    
    def test_validate_resource_access_individual_teacher(self):
        """Prueba la validación de acceso para profesores individuales"""
        workspace_info = {
            'workspace_type': 'INDIVIDUAL_TEACHER',
            'class_id': self.test_class_id,
            'user_id': self.test_user_id
        }
        
        # Recurso creado por el profesor
        resource_data = {
            'created_by': self.test_user_id,
            'title': 'Mi clase'
        }
        
        # Debería tener acceso
        has_access = validate_resource_access(resource_data, workspace_info, self.test_user_id)
        self.assertTrue(has_access)
        
        # Recurso de su clase personal
        class_resource = {
            'class_id': self.test_class_id,
            'title': 'Contenido de mi clase'
        }
        
        # Debería tener acceso
        has_access = validate_resource_access(class_resource, workspace_info, self.test_user_id)
        self.assertTrue(has_access)
    
    def test_validate_resource_access_institute(self):
        """Prueba la validación de acceso para workspaces institucionales"""
        workspace_info = {
            'workspace_type': 'INSTITUTE',
            'institute_id': self.test_institute_id
        }
        
        # Recurso del mismo instituto
        resource_data = {
            'institute_id': self.test_institute_id,
            'title': 'Recurso institucional'
        }
        
        # Debería tener acceso
        has_access = validate_resource_access(resource_data, workspace_info, self.test_user_id)
        self.assertTrue(has_access)
        
        # Recurso de otro instituto
        other_resource = {
            'institute_id': '507f1f77bcf86cd799439099',
            'title': 'Recurso de otro instituto'
        }
        
        # No debería tener acceso
        has_access = validate_resource_access(other_resource, workspace_info, self.test_user_id)
        self.assertFalse(has_access)
    
    def test_apply_workspace_data_filters_individual_student(self):
        """Prueba la aplicación de filtros para estudiantes individuales"""
        workspace_info = {
            'workspace_type': 'INDIVIDUAL_STUDENT',
            'user_id': self.test_user_id
        }
        
        base_query = {'status': 'active'}
        
        # Aplicar filtros
        filtered_query = apply_workspace_data_filters(base_query, workspace_info, self.test_user_id)
        
        # Verificar que se agregaron filtros de usuario
        self.assertIn('$or', filtered_query)
        self.assertIn({'user_id': ObjectId(self.test_user_id)}, filtered_query['$or'])
        self.assertIn({'student_id': ObjectId(self.test_user_id)}, filtered_query['$or'])
    
    def test_apply_workspace_data_filters_individual_teacher(self):
        """Prueba la aplicación de filtros para profesores individuales"""
        workspace_info = {
            'workspace_type': 'INDIVIDUAL_TEACHER',
            'class_id': self.test_class_id,
            'user_id': self.test_user_id
        }
        
        base_query = {'status': 'active'}
        
        # Aplicar filtros
        filtered_query = apply_workspace_data_filters(base_query, workspace_info, self.test_user_id)
        
        # Verificar que se agregaron filtros apropiados
        self.assertIn('$or', filtered_query)
        or_conditions = filtered_query['$or']
        
        # Verificar condiciones específicas
        self.assertIn({'created_by': ObjectId(self.test_user_id)}, or_conditions)
        self.assertIn({'user_id': ObjectId(self.test_user_id)}, or_conditions)
        self.assertIn({'class_id': ObjectId(self.test_class_id)}, or_conditions)
    
    def test_apply_workspace_data_filters_institute(self):
        """Prueba la aplicación de filtros para workspaces institucionales"""
        workspace_info = {
            'workspace_type': 'INSTITUTE',
            'institute_id': self.test_institute_id
        }
        
        base_query = {'status': 'active'}
        
        # Aplicar filtros
        filtered_query = apply_workspace_data_filters(base_query, workspace_info, self.test_user_id)
        
        # Verificar que se agregó filtro de instituto
        self.assertIn('institute_id', filtered_query)
        self.assertEqual(filtered_query['institute_id'], ObjectId(self.test_institute_id))


if __name__ == '__main__':
    unittest.main()