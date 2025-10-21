#!/usr/bin/env python3
"""
Simple test to verify that the create_bulk_slides API endpoint returns both
content_ids and slide_ids fields for backward compatibility.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add path to system
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

class TestSlideIdsBackwardCompatibility(unittest.TestCase):
    """
    Test backward compatibility for slide_ids -> content_ids field renaming
    """

    @patch('src.shared.database.get_db')
    @patch('src.content.services.ContentTypeService.get_content_type')
    def test_create_bulk_slides_response_format(self, mock_get_content_type, mock_get_db):
        """
        Test that create_bulk_slides endpoint returns both content_ids and slide_ids
        """
        # Mock the Flask app and request context
        with patch('src.content.routes.request') as mock_request:
            mock_request.json = {
                "slides": [
                    {
                        "topic_id": "507f1f77bcf86cd799439011",
                        "content_type": "slide",
                        "order": 1,
                        "content": {
                            "full_text": "Test slide content"
                        }
                    }
                ]
            }
            mock_request.user_id = "test_user_id"

            # Mock database operations
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_db.topics.find_one.return_value = {"_id": "507f1f77bcf86cd799439011", "name": "Test Topic"}

            # Mock content type service
            mock_get_content_type.return_value = {"code": "slide", "name": "Slide", "status": "active"}

            # Mock the service method
            with patch('src.content.routes.content_service.create_bulk_slides_skeleton') as mock_service:
                mock_service.return_value = (True, ["507f1f77bcf86cd799439012"])

                # Import after patching
                from src.content.routes import create_bulk_slides

                # Call the endpoint
                response = create_bulk_slides()

                # Get the response data - Flask endpoints can return Response objects or tuples
                if hasattr(response, 'get_json'):
                    response_data = response.get_json()
                elif isinstance(response, tuple) and len(response) > 0:
                    response_data = response[0].get_json()
                else:
                    self.fail("Unexpected response type from create_bulk_slides endpoint")

                # Verify that both fields are present
                self.assertIn("content_ids", response_data.get("data", {}), "Response should contain 'content_ids' field")
                self.assertIn("slide_ids", response_data.get("data", {}), "Response should contain deprecated 'slide_ids' field for backward compatibility")

                # Verify both fields have the same value
                data = response_data.get("data", {})
                self.assertEqual(data["content_ids"], data["slide_ids"], "Both content_ids and slide_ids should have identical values")

                # Verify deprecation headers are present
                self.assertTrue(hasattr(response, 'headers'), "Response should have headers attribute")
                self.assertIn('Deprecation', response.headers, "Response should have Deprecation header")
                self.assertIn('Sunset', response.headers, "Response should have Sunset header")
                self.assertIn('Warning', response.headers, "Response should have Warning header")

if __name__ == "__main__":
    unittest.main()