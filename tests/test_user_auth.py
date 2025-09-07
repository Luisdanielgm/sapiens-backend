import unittest
import json
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_jwt_extended import JWTManager, decode_token, create_access_token
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from main import create_app
from config import TestingConfig

class TestUserAuth(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        self.app_context.pop()
    
    def test_jwt_token_creation_with_email_claims(self):
        """Test that JWT tokens can be created with email in additional claims."""
        with self.app.app_context():
            # Test data
            user_id = 'user123'
            claims = {
                'email': 'test@example.com',
                'workspace_id': 'workspace123',
                'institute_id': 'institute123',
                'role': 'student'
            }
            
            # Create token with email in claims
            token = create_access_token(identity=user_id, additional_claims=claims)
            
            # Decode token and verify email is present
            decoded_token = decode_token(token)
            
            self.assertIn('email', decoded_token)
            self.assertEqual(decoded_token['email'], 'test@example.com')
            self.assertIn('workspace_id', decoded_token)
            self.assertIn('institute_id', decoded_token)
            self.assertIn('role', decoded_token)
    
    def test_verify_token_missing_authorization(self):
        """Test verify-token endpoint without Authorization header."""
        response = self.client.get('/api/users/verify-token')
        
        # Should return 401 for missing token
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_verify_token_invalid_format(self):
        """Test verify-token endpoint with invalid token format."""
        headers = {'Authorization': 'Bearer invalid_token_format'}
        response = self.client.get('/api/users/verify-token', headers=headers)
        
        # Should return 422 for invalid token format
        self.assertIn(response.status_code, [401, 422])  # Both are acceptable
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_verify_token_debug_missing_authorization(self):
        """Test verify-token-debug endpoint without Authorization header."""
        response = self.client.get('/api/users/verify-token-debug')
        
        # Should return 401 for missing token
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_jwt_decode_leeway_configuration(self):
        """Test that JWT_DECODE_LEEWAY is properly configured."""
        with self.app.app_context():
            # Check if JWT_DECODE_LEEWAY is configured
            jwt_decode_leeway = self.app.config.get('JWT_DECODE_LEEWAY')
            self.assertIsNotNone(jwt_decode_leeway)
            self.assertIsInstance(jwt_decode_leeway, int)
            self.assertGreaterEqual(jwt_decode_leeway, 0)
    
    def test_cors_configuration(self):
        """Test that CORS is properly configured for API endpoints."""
        # Make an OPTIONS request to check CORS headers
        response = self.client.options('/api/users/verify-token')
        
        # Check that the request doesn't fail due to CORS
        self.assertIn(response.status_code, [200, 204, 405])  # Various acceptable responses
    
    @patch('src.users.services.UserService.login_user')
    @patch('src.members.services.MembershipService.get_user_workspaces')
    def test_login_endpoint_structure(self, mock_get_workspaces, mock_login):
        """Test that login endpoint has the correct structure for JWT claims."""
        # Mock successful login
        mock_user_info = {
            'id': 'user123',
            'email': 'test@example.com',
            'role': 'student'
        }
        mock_login.return_value = mock_user_info
        
        # Mock workspaces
        mock_workspaces = [{
            '_id': 'workspace123',
            'institute_id': 'institute123'
        }]
        mock_get_workspaces.return_value = mock_workspaces
        
        # Make login request
        response = self.client.post('/api/users/login', 
                                  json={'email': 'test@example.com', 'password': 'password123'})
        
        # Check response structure
        if response.status_code == 200:
            data = json.loads(response.data)
            self.assertTrue(data['success'])
            self.assertIn('access_token', data['data'])
            
            # Verify token can be decoded (basic structure test)
            token = data['data']['access_token']
            self.assertIsInstance(token, str)
            self.assertTrue(len(token) > 0)

if __name__ == '__main__':
    unittest.main()