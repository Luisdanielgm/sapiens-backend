import unittest
from unittest.mock import patch, MagicMock
from flask import Flask, request, jsonify
from bson import ObjectId
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.shared.decorators import (
    workspace_type_required,
    workspace_access_required,
    workspace_owner_required,
    workspace_role_required,
    workspace_data_isolation_required
)
from src.shared.middleware import validate_resource_access, apply_workspace_data_filters


class TestWorkspaceIntegration(unittest.TestCase):
    """Pruebas de integración para verificar el funcionamiento completo del sistema de workspaces"""
    
    def setUp(self):
        """Configuración inicial para las pruebas"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        self.test_user_id = "507f1f77bcf86cd799439011"
        self.test_institute_id = "507f1f77bcf86cd799439013"
        self.test_class_id = "507f1f77bcf86cd799439014"
        self.test_workspace_id = "507f1f77bcf86cd799439015"
    
    def test_individual_student_endpoint_access(self):
        """Prueba el acceso completo de un endpoint para estudiante individual"""
        with self.app.test_request_context():
            # Simular datos de workspace de estudiante individual
            request.current_workspace = {
                'workspace_id': self.test_workspace_id,
                'workspace_type': 'INDIVIDUAL_STUDENT',
                'user_id': ObjectId(self.test_user_id),
                'role': 'STUDENT'
            }
            request.user_id = self.test_user_id
            
            # Endpoint simulado con múltiples decoradores
            @workspace_type_required(['INDIVIDUAL_STUDENT'])
            @workspace_data_isolation_required
            def student_dashboard():
                # Verificar que se aplicaron los filtros de aislamiento
                filters = getattr(request, 'isolation_filters', {})
                return jsonify({
                    'message': 'Dashboard de estudiante',
                    'workspace_type': request.current_workspace['workspace_type'],
                    'filters_applied': bool(filters)
                })
            
            # Ejecutar endpoint
            response = student_dashboard()
            self.assertIsNotNone(response)
            
            # Verificar que se aplicaron filtros de aislamiento
            self.assertTrue(hasattr(request, 'isolation_filters'))
    
    def test_individual_teacher_endpoint_access(self):
        """Prueba el acceso completo de un endpoint para profesor individual"""
        with self.app.test_request_context():
            # Simular datos de workspace de profesor individual
            request.current_workspace = {
                'workspace_id': self.test_workspace_id,
                'workspace_type': 'INDIVIDUAL_TEACHER',
                'user_id': ObjectId(self.test_user_id),
                'class_id': ObjectId(self.test_class_id),
                'role': 'TEACHER'
            }
            request.user_id = self.test_user_id
            
            # Endpoint simulado con múltiples decoradores
            @workspace_type_required(['INDIVIDUAL_TEACHER'])
            @workspace_role_required(['TEACHER'])
            @workspace_data_isolation_required
            def teacher_classes():
                # Verificar que se aplicaron los filtros de aislamiento
                filters = getattr(request, 'isolation_filters', {})
                return jsonify({
                    'message': 'Clases del profesor',
                    'workspace_type': request.current_workspace['workspace_type'],
                    'class_id': str(request.current_workspace['class_id']),
                    'filters_applied': bool(filters)
                })
            
            # Ejecutar endpoint
            response = teacher_classes()
            self.assertIsNotNone(response)
            
            # Verificar que se aplicaron filtros de aislamiento
            self.assertTrue(hasattr(request, 'isolation_filters'))
            filters = request.isolation_filters
            self.assertIn('$or', filters)
    
    def test_institute_endpoint_access(self):
        """Prueba el acceso completo de un endpoint institucional"""
        with self.app.test_request_context():
            # Simular datos de workspace institucional
            request.current_workspace = {
                'workspace_id': self.test_workspace_id,
                'workspace_type': 'INSTITUTE',
                'institute_id': ObjectId(self.test_institute_id),
                'role': 'ADMIN'
            }
            request.user_id = self.test_user_id
            
            # Endpoint simulado con múltiples decoradores
            @workspace_type_required(['INSTITUTE'])
            @workspace_role_required(['ADMIN', 'TEACHER'])
            @workspace_data_isolation_required
            def institute_dashboard():
                # Verificar que se aplicaron los filtros de aislamiento
                filters = getattr(request, 'isolation_filters', {})
                return jsonify({
                    'message': 'Dashboard institucional',
                    'workspace_type': request.current_workspace['workspace_type'],
                    'institute_id': str(request.current_workspace['institute_id']),
                    'filters_applied': bool(filters)
                })
            
            # Ejecutar endpoint
            response = institute_dashboard()
            self.assertIsNotNone(response)
            
            # Verificar que se aplicaron filtros de aislamiento
            self.assertTrue(hasattr(request, 'isolation_filters'))
            filters = request.isolation_filters
            self.assertIn('institute_id', filters)
    
    def test_access_denied_wrong_workspace_type(self):
        """Prueba que se deniegue el acceso con workspace_type incorrecto"""
        with self.app.test_request_context():
            # Simular workspace de estudiante intentando acceder a endpoint de profesor
            request.current_workspace = {
                'workspace_id': self.test_workspace_id,
                'workspace_type': 'INDIVIDUAL_STUDENT',
                'user_id': ObjectId(self.test_user_id),
                'role': 'STUDENT'
            }
            request.user_id = self.test_user_id
            
            # Endpoint que requiere workspace de profesor
            @workspace_type_required(['INDIVIDUAL_TEACHER'])
            def teacher_only_endpoint():
                return jsonify({'message': 'Solo para profesores'})
            
            # Debería denegar acceso
            result = teacher_only_endpoint()
            self.assertEqual(result[1], 403)  # Status code 403
    
    def test_access_denied_wrong_role(self):
        """Prueba que se deniegue el acceso con rol incorrecto"""
        with self.app.test_request_context():
            # Simular workspace con rol de estudiante intentando acceder a endpoint de admin
            request.current_workspace = {
                'workspace_id': self.test_workspace_id,
                'workspace_type': 'INSTITUTE',
                'institute_id': ObjectId(self.test_institute_id),
                'role': 'STUDENT'
            }
            request.user_id = self.test_user_id
            
            # Endpoint que requiere rol de admin
            @workspace_role_required(['ADMIN'])
            def admin_only_endpoint():
                return jsonify({'message': 'Solo para administradores'})
            
            # Debería denegar acceso
            result = admin_only_endpoint()
            self.assertEqual(result[1], 403)  # Status code 403
    
    def test_data_isolation_filters_integration(self):
        """Prueba la integración completa de filtros de aislamiento de datos"""
        # Prueba para estudiante individual
        workspace_info = {
            'workspace_type': 'INDIVIDUAL_STUDENT',
            'user_id': self.test_user_id
        }
        
        base_query = {'status': 'active'}
        filtered_query = apply_workspace_data_filters(base_query, workspace_info, self.test_user_id)
        
        # Verificar que se aplicaron filtros correctos
        self.assertIn('$or', filtered_query)
        self.assertIn('status', filtered_query)
        
        # Prueba para profesor individual
        workspace_info = {
            'workspace_type': 'INDIVIDUAL_TEACHER',
            'class_id': self.test_class_id,
            'user_id': self.test_user_id
        }
        
        filtered_query = apply_workspace_data_filters(base_query, workspace_info, self.test_user_id)
        
        # Verificar que se aplicaron filtros correctos
        self.assertIn('$or', filtered_query)
        or_conditions = filtered_query['$or']
        self.assertTrue(any('class_id' in condition for condition in or_conditions))
        self.assertTrue(any('created_by' in condition for condition in or_conditions))
    
    def test_resource_access_validation_integration(self):
        """Prueba la validación de acceso a recursos de forma integrada"""
        # Estudiante individual accediendo a su propio recurso
        workspace_info = {
            'workspace_type': 'INDIVIDUAL_STUDENT',
            'user_id': self.test_user_id
        }
        
        own_resource = {
            'user_id': self.test_user_id,
            'title': 'Mi plan de estudio'
        }
        
        # Debería tener acceso
        has_access = validate_resource_access(own_resource, workspace_info, self.test_user_id)
        self.assertTrue(has_access)
        
        # Estudiante individual intentando acceder a recurso de otro
        other_resource = {
            'user_id': '507f1f77bcf86cd799439099',
            'title': 'Plan de otro estudiante'
        }
        
        # No debería tener acceso
        has_access = validate_resource_access(other_resource, workspace_info, self.test_user_id)
        self.assertFalse(has_access)
        
        # Profesor individual accediendo a recurso de su clase
        teacher_workspace = {
            'workspace_type': 'INDIVIDUAL_TEACHER',
            'class_id': self.test_class_id,
            'user_id': self.test_user_id
        }
        
        class_resource = {
            'class_id': self.test_class_id,
            'title': 'Contenido de mi clase'
        }
        
        # Debería tener acceso
        has_access = validate_resource_access(class_resource, teacher_workspace, self.test_user_id)
        self.assertTrue(has_access)


if __name__ == '__main__':
    unittest.main()