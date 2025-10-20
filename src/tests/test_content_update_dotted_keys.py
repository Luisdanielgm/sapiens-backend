import unittest
from unittest.mock import patch, MagicMock, call, ANY
from bson import ObjectId
import json
import sys
import os
from datetime import datetime

# Agregar path al sistema
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.content.services import ContentService


class TestContentUpdateWithDottedKeys(unittest.TestCase):
    """
    Tests para validar la actualización de contenido con claves punteadas (content.*)
    Verifica que la sanitización y validación se aplique consistentemente sin importar
    cómo se envíen los datos: raíz, anidados, o claves punteadas
    """

    def setUp(self):
        """Configuración inicial para las pruebas"""
        self.test_topic_id = str(ObjectId())
        self.test_user_id = str(ObjectId())
        self.test_content_id = str(ObjectId())

        # HTML de prueba
        self.dangerous_html = '<div><script>alert("xss")</script><p>Contenido válido</p></div>'
        self.sanitized_html = '<div><p>Contenido válido</p></div>'
        self.valid_html = '<div><h1>Título</h1><p>Contenido limpio</p></div>'

        # Narrativa y otros campos
        self.narrative_text = "Esta es la narrativa de la diapositiva"
        self.full_text = "Texto completo del contenido"
        self.slide_plan = "# Plan de Diapositivas\n\n- Diseño minimalista\n- Colores azul y blanco"
        self.template_snapshot = {
            "style": "modern",
            "colors": ["blue", "white"],
            "font": "sans-serif",
            "layout": "title-and-content"
        }

    @patch('src.shared.database.get_db')
    @patch('src.content.services.ContentTypeService.get_content_type')
    @patch('src.content.services.ContentService.validate_slide_html_content')
    @patch('src.content.services.ContentService.sanitize_slide_html_content')
    @patch('src.content.services.ContentService.validate_template_snapshot')
    def test_update_with_root_fields(self, mock_validate_template, mock_sanitize_html,
                                   mock_validate_html, mock_get_content_type, mock_get_db):
        """
        Test 1: Actualización con campos a nivel raíz
        Verifica que los campos raíz se validen, saniticen y muevan a content.*
        """
        # Setup de mocks
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_collection = mock_db.topic_contents
        mock_get_content_type.return_value = {"code": "slide", "name": "Slide", "status": "active"}
        mock_validate_html.return_value = (True, "HTML válido")
        mock_sanitize_html.return_value = self.sanitized_html
        mock_validate_template.return_value = (True, "Template válido")

        service = ContentService()

        # Override the service's collection to use our mock
        service.collection = mock_collection

        # Mockear get_content method
        existing_content = {
            "_id": self.test_content_id,
            "topic_id": self.test_topic_id,
            "content_type": "slide",
            "order": 1,
            "content": {
                "full_text": self.full_text
            },
            "status": "skeleton",
            "creator_id": self.test_user_id
        }
        service.get_content = MagicMock(return_value=existing_content)
        mock_collection.find_one.return_value = existing_content
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        # Mock para que coincida con el filtro ObjectId
        def mock_update_one(filter_query, update_data):
            if filter_query.get("_id") == ObjectId(self.test_content_id):
                return MagicMock(modified_count=1)
            return MagicMock(modified_count=0)

        mock_collection.update_one.side_effect = mock_update_one

        # Payload con campos a nivel raíz
        update_data = {
            "content_html": self.dangerous_html,
            "narrative_text": self.narrative_text,
            "template_snapshot": self.template_snapshot,
            "creator_id": self.test_user_id
        }

        success, message = service.update_content(self.test_content_id, update_data)

        # Verificaciones
        self.assertTrue(success, f"Expected success but got: {message}")

        # Verificar que se llamaron las validaciones (pueden llamarse multiple veces)
        mock_validate_html.assert_any_call(self.dangerous_html)
        mock_sanitize_html.assert_any_call(self.dangerous_html)
        mock_validate_template.assert_any_call(self.template_snapshot)

        # Verificar que update_one fue llamado con campos correctos
        update_call = mock_collection.update_one.call_args
        update_set = update_call[0][1]['$set']

        # Verificar que los campos están en content.* (no a nivel raíz)
        self.assertIn('content.content_html', update_set)
        self.assertIn('content.narrative_text', update_set)
        self.assertIn('content.template_snapshot', update_set)

        # Verificar que NO están a nivel raíz
        self.assertNotIn('content_html', update_set)
        self.assertNotIn('narrative_text', update_set)
        self.assertNotIn('template_snapshot', update_set)

        # Verificar valores sanitizados
        self.assertEqual(update_set['content.content_html'], self.sanitized_html)
        self.assertEqual(update_set['content.narrative_text'], self.narrative_text)
        self.assertEqual(update_set['content.template_snapshot'], self.template_snapshot)

        # Verificar que se estableció render_engine
        self.assertEqual(update_set['render_engine'], 'raw_html')

        # Verificar status actualizado
        self.assertEqual(update_set['status'], 'narrative_ready')

    @patch('src.shared.database.get_db')
    @patch('src.content.services.ContentTypeService.get_content_type')
    @patch('src.content.services.ContentService.validate_slide_html_content')
    @patch('src.content.services.ContentService.sanitize_slide_html_content')
    @patch('src.content.services.ContentService.validate_template_snapshot')
    def test_update_with_nested_content_dict(self, mock_validate_template, mock_sanitize_html,
                                            mock_validate_html, mock_get_content_type, mock_get_db):
        """
        Test 2: Actualización con diccionario content anidado
        Verifica que los campos anidados en content se validen y saniticen correctamente
        """
        # Setup de mocks
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_collection = mock_db.topic_contents
        mock_get_content_type.return_value = {"code": "slide", "name": "Slide", "status": "active"}
        mock_validate_html.return_value = (True, "HTML válido")
        mock_sanitize_html.return_value = self.sanitized_html
        mock_validate_template.return_value = (True, "Template válido")

        service = ContentService()

        # Override the service's collection to use our mock
        service.collection = mock_collection

        # Mockear get_content method
        existing_content = {
            "_id": self.test_content_id,
            "topic_id": self.test_topic_id,
            "content_type": "slide",
            "order": 1,
            "content": {
                "full_text": self.full_text
            },
            "status": "skeleton",
            "creator_id": self.test_user_id
        }
        service.get_content = MagicMock(return_value=existing_content)
        mock_collection.find_one.return_value = existing_content
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        # Mock para que coincida con el filtro ObjectId
        def mock_update_one(filter_query, update_data):
            if filter_query.get("_id") == ObjectId(self.test_content_id):
                return MagicMock(modified_count=1)
            return MagicMock(modified_count=0)

        mock_collection.update_one.side_effect = mock_update_one

        # Payload con content anidado
        update_data = {
            "content": {
                "content_html": self.dangerous_html,
                "narrative_text": self.narrative_text,
                "template_snapshot": self.template_snapshot
            },
            "creator_id": self.test_user_id
        }

        success, message = service.update_content(self.test_content_id, update_data)

        # Verificaciones
        self.assertTrue(success, f"Expected success but got: {message}")

        # Verificar que se llamaron las validaciones (pueden llamarse multiple veces)
        mock_validate_html.assert_any_call(self.dangerous_html)
        mock_sanitize_html.assert_any_call(self.dangerous_html)
        mock_validate_template.assert_any_call(self.template_snapshot)

        # Verificar que update_one fue llamado con campos correctos
        update_call = mock_collection.update_one.call_args
        update_set = update_call[0][1]['$set']

        # Verificar que los campos están en content.*
        self.assertIn('content.content_html', update_set)
        self.assertIn('content.narrative_text', update_set)
        self.assertIn('content.template_snapshot', update_set)

        # Verificar que NO están a nivel raíz
        self.assertNotIn('content_html', update_set)
        self.assertNotIn('narrative_text', update_set)
        self.assertNotIn('template_snapshot', update_set)
        self.assertNotIn('content', update_set)  # El diccionario content completo no debe estar

        # Verificar valores sanitizados
        self.assertEqual(update_set['content.content_html'], self.sanitized_html)
        self.assertEqual(update_set['content.narrative_text'], self.narrative_text)
        self.assertEqual(update_set['content.template_snapshot'], self.template_snapshot)

        # Verificar que se estableció render_engine
        self.assertEqual(update_set['render_engine'], 'raw_html')

    @patch('src.shared.database.get_db')
    @patch('src.content.services.ContentTypeService.get_content_type')
    @patch('src.content.services.ContentService.validate_slide_html_content')
    @patch('src.content.services.ContentService.sanitize_slide_html_content')
    @patch('src.content.services.ContentService.validate_template_snapshot')
    def test_update_with_dotted_keys_only(self, mock_validate_template, mock_sanitize_html,
                                        mock_validate_html, mock_get_content_type, mock_get_db):
        """
        Test 3: Actualización con claves punteadas únicamente
        Verifica que las claves content.* se extraigan, validen y saniticen correctamente
        """
        # Setup de mocks
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_collection = mock_db.topic_contents
        mock_get_content_type.return_value = {"code": "slide", "name": "Slide", "status": "active"}
        mock_validate_html.return_value = (True, "HTML válido")
        mock_sanitize_html.return_value = self.sanitized_html
        mock_validate_template.return_value = (True, "Template válido")

        service = ContentService()

        # Override the service's collection to use our mock
        service.collection = mock_collection

        # Mockear get_content method
        existing_content = {
            "_id": self.test_content_id,
            "topic_id": self.test_topic_id,
            "content_type": "slide",
            "order": 1,
            "content": {
                "full_text": self.full_text
            },
            "status": "skeleton",
            "creator_id": self.test_user_id
        }
        service.get_content = MagicMock(return_value=existing_content)
        mock_collection.find_one.return_value = existing_content
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        # Mock para que coincida con el filtro ObjectId
        def mock_update_one(filter_query, update_data):
            if filter_query.get("_id") == ObjectId(self.test_content_id):
                return MagicMock(modified_count=1)
            return MagicMock(modified_count=0)

        mock_collection.update_one.side_effect = mock_update_one

        # Payload con claves punteadas únicamente
        update_data = {
            "content.content_html": self.dangerous_html,
            "content.narrative_text": self.narrative_text,
            "content.template_snapshot": self.template_snapshot,
            "creator_id": self.test_user_id
        }

        success, message = service.update_content(self.test_content_id, update_data)

        # Verificaciones
        self.assertTrue(success, f"Expected success but got: {message}")

        # Verificar que se llamaron las validaciones (pueden llamarse multiple veces)
        mock_validate_html.assert_any_call(self.dangerous_html)
        mock_sanitize_html.assert_any_call(self.dangerous_html)
        mock_validate_template.assert_any_call(self.template_snapshot)

        # Verificar que update_one fue llamado con campos correctos
        update_call = mock_collection.update_one.call_args
        update_set = update_call[0][1]['$set']

        # Verificar que los campos están en content.*
        self.assertIn('content.content_html', update_set)
        self.assertIn('content.narrative_text', update_set)
        self.assertIn('content.template_snapshot', update_set)

        # Verificar valores sanitizados
        self.assertEqual(update_set['content.content_html'], self.sanitized_html)
        self.assertEqual(update_set['content.narrative_text'], self.narrative_text)
        self.assertEqual(update_set['content.template_snapshot'], self.template_snapshot)

        # Verificar que se estableció render_engine
        self.assertEqual(update_set['render_engine'], 'raw_html')

    @patch('src.shared.database.get_db')
    @patch('src.content.services.ContentTypeService.get_content_type')
    @patch('src.content.services.ContentService.validate_slide_html_content')
    def test_update_html_validation_failure(self, mock_validate_html, mock_get_content_type, mock_get_db):
        """
        Test 4: Fallo en validación de HTML
        Verifica que se rechace HTML inválido sin importar cómo se envíe
        """
        # Setup de mocks
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_collection = mock_db.topic_contents
        mock_get_content_type.return_value = {"code": "slide", "name": "Slide", "status": "active"}
        mock_validate_html.return_value = (False, "HTML contiene contenido inválido")

        service = ContentService()

        # Override the service's collection to use our mock
        service.collection = mock_collection

        # Mockear get_content method
        existing_content = {
            "_id": self.test_content_id,
            "topic_id": self.test_topic_id,
            "content_type": "slide",
            "order": 1,
            "content": {"full_text": self.full_text},
            "status": "skeleton",
            "creator_id": self.test_user_id
        }
        service.get_content = MagicMock(return_value=existing_content)
        mock_collection.find_one.return_value = existing_content

        # Test 4.1: HTML inválido con clave raíz
        update_data_root = {
            "content_html": "html_inválido",
            "creator_id": self.test_user_id
        }

        success, message = service.update_content(self.test_content_id, update_data_root)
        self.assertFalse(success, "Expected failure with invalid HTML via root key")
        self.assertIn("content_html inválido", message)

        # Test 4.2: HTML inválido con content anidado
        update_data_nested = {
            "content": {
                "content_html": "html_inválido"
            },
            "creator_id": self.test_user_id
        }

        success, message = service.update_content(self.test_content_id, update_data_nested)
        self.assertFalse(success, "Expected failure with invalid HTML via nested content")
        self.assertIn("content_html inválido", message)

        # Test 4.3: HTML inválido con clave punteada
        update_data_dotted = {
            "content.content_html": "html_inválido",
            "creator_id": self.test_user_id
        }

        success, message = service.update_content(self.test_content_id, update_data_dotted)
        self.assertFalse(success, "Expected failure with invalid HTML via dotted key")
        self.assertIn("content_html inválido", message)

    @patch('src.shared.database.get_db')
    @patch('src.content.services.ContentTypeService.get_content_type')
    @patch('src.content.services.ContentService.validate_template_snapshot')
    def test_update_template_validation_failure(self, mock_validate_template, mock_get_content_type, mock_get_db):
        """
        Test 5: Fallo en validación de template_snapshot
        Verifica que se rechace template_snapshot inválido sin importar cómo se envíe
        """
        # Setup de mocks
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_collection = mock_db.topic_contents
        mock_get_content_type.return_value = {"code": "slide", "name": "Slide", "status": "active"}
        mock_validate_template.return_value = (False, "Template snapshot inválido")

        service = ContentService()

        # Override the service's collection to use our mock
        service.collection = mock_collection

        # Mockear get_content method
        existing_content = {
            "_id": self.test_content_id,
            "topic_id": self.test_topic_id,
            "content_type": "slide",
            "order": 1,
            "content": {"full_text": self.full_text},
            "status": "skeleton",
            "creator_id": self.test_user_id
        }
        service.get_content = MagicMock(return_value=existing_content)
        mock_collection.find_one.return_value = existing_content

        # Test con template inválido via clave punteada
        invalid_template = {"invalid": "template"}
        update_data = {
            "content.template_snapshot": invalid_template,
            "creator_id": self.test_user_id
        }

        success, message = service.update_content(self.test_content_id, update_data)
        self.assertFalse(success, "Expected failure with invalid template snapshot")
        self.assertIn("template_snapshot inválido", message)

    @patch('src.shared.database.get_db')
    @patch('src.content.services.ContentTypeService.get_content_type')
    def test_update_type_validation(self, mock_get_content_type, mock_get_db):
        """
        Test 6: Validación de tipos de datos
        Verifica que se validen tipos de narrative_text y full_text
        """
        # Setup de mocks
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_collection = mock_db.topic_contents
        mock_get_content_type.return_value = {"code": "slide", "name": "Slide", "status": "active"}

        service = ContentService()

        # Override the service's collection to use our mock
        service.collection = mock_collection

        # Mockear get_content method
        existing_content = {
            "_id": self.test_content_id,
            "topic_id": self.test_topic_id,
            "content_type": "slide",
            "order": 1,
            "content": {"full_text": self.full_text},
            "status": "skeleton",
            "creator_id": self.test_user_id
        }
        service.get_content = MagicMock(return_value=existing_content)
        mock_collection.find_one.return_value = existing_content

        # Test 6.1: narrative_text con tipo inválido via clave punteada
        update_data_narrative = {
            "content.narrative_text": 123,  # Debe ser string
            "creator_id": self.test_user_id
        }

        success, message = service.update_content(self.test_content_id, update_data_narrative)
        self.assertFalse(success, "Expected failure with non-string narrative_text")
        self.assertIn("debe ser una cadena de texto", message)

        # Test 6.2: full_text con tipo inválido via clave punteada
        update_data_full_text = {
            "content.full_text": ["no", "es", "string"],  # Debe ser string
            "creator_id": self.test_user_id
        }

        success, message = service.update_content(self.test_content_id, update_data_full_text)
        self.assertFalse(success, "Expected failure with non-string full_text")
        self.assertIn("debe ser una cadena de texto", message)

    @patch('src.shared.database.get_db')
    @patch('src.content.services.ContentTypeService.get_content_type')
    @patch('src.content.services.ContentService.validate_slide_html_content')
    @patch('src.content.services.ContentService.sanitize_slide_html_content')
    def test_update_mixed_sources_precedence(self, mock_sanitize_html, mock_validate_html,
                                            mock_get_content_type, mock_get_db):
        """
        Test 7: Mezcla de fuentes y precedencia
        Verifica que cuando hay múltiples fuentes, las claves punteadas tienen precedencia
        """
        # Setup de mocks
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_collection = mock_db.topic_contents
        mock_get_content_type.return_value = {"code": "slide", "name": "Slide", "status": "active"}
        mock_validate_html.return_value = (True, "HTML válido")
        mock_sanitize_html.return_value = self.sanitized_html

        service = ContentService()

        # Override the service's collection to use our mock
        service.collection = mock_collection

        # Mockear get_content method
        existing_content = {
            "_id": self.test_content_id,
            "topic_id": self.test_topic_id,
            "content_type": "slide",
            "order": 1,
            "content": {"full_text": self.full_text},
            "status": "skeleton",
            "creator_id": self.test_user_id
        }
        service.get_content = MagicMock(return_value=existing_content)
        mock_collection.find_one.return_value = existing_content
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        # Mock para que coincida con el filtro ObjectId
        def mock_update_one(filter_query, update_data):
            if filter_query.get("_id") == ObjectId(self.test_content_id):
                return MagicMock(modified_count=1)
            return MagicMock(modified_count=0)

        mock_collection.update_one.side_effect = mock_update_one

        # Payload con mezcla de fuentes - la clave punteada debe tener precedencia
        update_data = {
            "content": {
                "content_html": "<div>HTML anidado</div>",
                "narrative_text": "Narrativa anidada"
            },
            "content_html": "<div>HTML raíz</div>",
            "content.content_html": self.dangerous_html,  # Debe tener precedencia
            "content.narrative_text": "Narrativa punteada",  # Debe tener precedencia
            "creator_id": self.test_user_id
        }

        success, message = service.update_content(self.test_content_id, update_data)
        self.assertTrue(success, f"Expected success but got: {message}")

        # Verificar que se usó el valor de la clave punteada (puede haber validación múltiple pero la clave punteada tiene precedencia)
        mock_validate_html.assert_any_call(self.dangerous_html)
        mock_sanitize_html.assert_any_call(self.dangerous_html)

        # Verificar valores finales en update_set
        update_call = mock_collection.update_one.call_args
        update_set = update_call[0][1]['$set']

        # La clave punteada debe tener precedencia sobre las otras fuentes
        self.assertEqual(update_set['content.content_html'], self.sanitized_html)
        self.assertEqual(update_set['content.narrative_text'], "Narrativa punteada")

    def tearDown(self):
        """Limpieza opcional después de cada test"""
        pass


if __name__ == "__main__":
    unittest.main()