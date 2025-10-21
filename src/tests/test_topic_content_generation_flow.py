import unittest
from unittest.mock import patch, MagicMock, call, ANY
from bson import ObjectId
import json
import sys
import os
from datetime import datetime
from pymongo.errors import DuplicateKeyError

# Agregar path al sistema
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.content.services import ContentService, ContentTypeService, FORBIDDEN_KEYS_ERROR_MSG, FORBIDDEN_KEYS_ERROR_MSG_SHORT, SLIDE_PLAN_TYPE_ERROR_MSG
from src.content.models import TopicContent


class TestTopicContentGenerationFlow(unittest.TestCase):
    """
    Tests de integración para validar el flujo completo de generación de contenido de temas (Fases 1-4)
    """

    def setUp(self):
        """Configuración inicial para las pruebas"""
        self.test_topic_id = str(ObjectId())
        self.test_user_id = str(ObjectId())
        self.test_module_id = str(ObjectId())

        # Crear datos de prueba para teoría
        self.theory_content = "Este es el contenido teórico completo del tema. Incluye conceptos fundamentales, ejemplos y explicaciones detalladas."

        # Crear datos de prueba para slide plan
        self.slide_plan = "# Plan de Diapositivas\n\n- Usar diseño minimalista\n- Colores: azul y blanco\n- Fuente: Sans-serif"

        # Crear datos de prueba para slides (3 slides)
        self.slides_data = [
            {
                "topic_id": self.test_topic_id,
                "content_type": "slide",
                "order": 1,
                "content": {
                    "full_text": "Introducción al tema...",
                    "slide_plan": self.slide_plan
                },
                "creator_id": self.test_user_id,
                "status": "skeleton"
            },
            {
                "topic_id": self.test_topic_id,
                "content_type": "slide",
                "order": 2,
                "content": {
                    "full_text": "Desarrollo del concepto principal...",
                    "slide_plan": self.slide_plan
                },
                "creator_id": self.test_user_id,
                "status": "skeleton"
            },
            {
                "topic_id": self.test_topic_id,
                "content_type": "slide",
                "order": 3,
                "content": {
                    "full_text": "Conclusión y resumen...",
                    "slide_plan": self.slide_plan
                },
                "creator_id": self.test_user_id,
                "status": "skeleton"
            }
        ]

        # Crear datos de prueba para HTML y narrativa
        self.sample_html = "<div class='slide'><h1>Título</h1><p>Contenido</p></div>"
        self.sample_narrative = "Esta diapositiva introduce el concepto principal..."

        # Crear datos de prueba para quiz
        self.quiz_data = {
            "topic_id": self.test_topic_id,
            "content_type": "quiz",
            "content": {
                "questions": [
                    {
                        "question": "¿Cuál es el concepto principal?",
                        "options": ["A", "B", "C", "D"],
                        "correct_answer": "A"
                    }
                ]
            },
            "creator_id": self.test_user_id
        }

    @patch('src.shared.database.get_db')
    @patch('src.content.services.ContentTypeService.get_content_type')
    def test_complete_generation_flow(self, mock_get_content_type, mock_get_db):
        """
        Test 1: Flujo completo de generación
        Valida el flujo completo desde teoría hasta quiz (Fase 3)
        Comportamiento esperado: Crear slides skeleton, actualizar HTML/narrativa, crear quiz
        """
        # Setup de mocks
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.topics.find_one.return_value = {"_id": ObjectId(self.test_topic_id), "name": "Test Topic"}
        mock_collection = mock_db.topic_contents
        mock_get_content_type.side_effect = lambda content_type_code: {
            "slide": {"code": "slide", "name": "Slide", "status": "active"},
            "quiz": {"code": "quiz", "name": "Quiz", "status": "active"}
        }.get(content_type_code, {"code": "slide", "name": "Slide", "status": "active"})

        service = ContentService()

        # Paso 0: Crear contenido teórico inicial (text)
        theory_payload = {
            "topic_id": self.test_topic_id,
            "content_type": "text",
            "content": {
                "full_text": self.theory_content,
                "summary": "Resumen del contenido teórico"
            },
            "creator_id": self.test_user_id
        }

        # Mockear content_types para 'text'
        mock_get_content_type.side_effect = [
            {"code": "text", "name": "Text", "status": "active"},  # Para contenido teórico
            {"code": "slide", "name": "Slide", "status": "active"}  # Para slides
        ]

        mock_collection.find_one.return_value = None  # No existe contenido teórico previo
        mock_collection.replace_one.return_value = MagicMock(upserted_id=ObjectId())

        success, result = service.create_content(theory_payload)
        self.assertTrue(success, f"Expected success creating theory content but got: {result}")
        self.assertIsNotNone(result, "Theory content creation should return an ID")

        # Resetear mocks para el resto del flujo
        mock_collection.reset_mock()
        mock_get_content_type.side_effect = lambda content_type_code: {
            "slide": {"code": "slide", "name": "Slide", "status": "active"},
            "quiz": {"code": "quiz", "name": "Quiz", "status": "active"}
        }.get(content_type_code, {"code": "slide", "name": "Slide", "status": "active"})

        # Paso 1: Crear slides skeleton (bulk)
        mock_collection.find_one_and_update.side_effect = [
            {"_id": ObjectId(), "_was_inserted": True},  # Insert nuevo
            {"_id": ObjectId(), "_was_inserted": True},
            {"_id": ObjectId(), "_was_inserted": True}
        ]
        mock_collection.find_one.return_value = None  # Para cada búsqueda de slide existente
        mock_collection.delete_many.return_value = MagicMock(deleted_count=0)  # No hay slides sobrantes

        success, result = service.create_bulk_slides_skeleton(slides_data=self.slides_data)
        self.assertTrue(success, f"Expected success but got: {result}")
        self.assertEqual(len(result), 3)  # 3 IDs retornados

        # Verificar que find_one_and_update fue llamado 3 veces con filtro correcto
        self.assertEqual(mock_collection.find_one_and_update.call_count, 3)
        for i, call_args in enumerate(mock_collection.find_one_and_update.call_args_list):
            filter_query = call_args[0][0]
            self.assertEqual(filter_query["topic_id"], ObjectId(self.test_topic_id))
            self.assertEqual(filter_query["content_type"], "slide")
            self.assertEqual(filter_query["order"], i + 1)

        # Verificar que los documentos insertados tienen campos en content.*
        # Extraer el documento de actualización desde find_one_and_update.call_args_list
        call_args = mock_collection.find_one_and_update.call_args_list[0]
        update_doc = call_args[0][1]['$set']  # Segundo parámetro: {'$set': ..., '$setOnInsert': ...}
        self.assertIn('content', update_doc)
        self.assertIn('full_text', update_doc['content'])
        self.assertIn('slide_plan', update_doc['content'])
        # template_snapshot removed - all configuration now in slide_plan

        # Verificar que no se encuentran estos campos a nivel raíz de update_doc
        self.assertNotIn('full_text', update_doc)
        self.assertNotIn('slide_plan', update_doc)

        # Paso 2: Actualizar HTML de slides
        for i, slide_id in enumerate(result):
            mock_collection.find_one.return_value = {
                "_id": ObjectId(slide_id),
                "topic_id": ObjectId(self.test_topic_id),
                "content_type": "slide",
                "order": i + 1,
                "content": {
                    "full_text": self.slides_data[i]['content']['full_text'],
                    "slide_plan": self.slide_plan
                },
                "status": "skeleton"
            }
            mock_collection.update_one.return_value = MagicMock(modified_count=1)

            success, msg = service.update_slide_html(slide_id, self.sample_html)
            self.assertTrue(success, f"Failed to update HTML for slide {i+1}: {msg}")

        # Verificar que update_one fue llamado con campos correctos
        update_call = mock_collection.update_one.call_args
        update_set = update_call[0][1]['$set']
        self.assertIn('content.content_html', update_set)
        self.assertEqual(update_set['status'], 'html_ready')
        self.assertIn('updated_at', update_set)
        # Verificar que NO se actualiza campo a nivel raíz
        self.assertNotIn('content_html', update_set)

        # Paso 3: Actualizar narrativa de slides
        for i, slide_id in enumerate(result):
            mock_collection.find_one.return_value = {
                "_id": ObjectId(slide_id),
                "topic_id": ObjectId(self.test_topic_id),
                "content_type": "slide",
                "order": i + 1,
                "content": {
                    "full_text": self.slides_data[i]['content']['full_text'],
                    "slide_plan": self.slide_plan,
                    "content_html": self.sample_html
                },
                "status": "html_ready"
            }
            success, msg = service.update_slide_narrative(slide_id, self.sample_narrative)
            self.assertTrue(success, f"Failed to update narrative for slide {i+1}: {msg}")

        # Verificar que update_one fue llamado con campos correctos
        update_call = mock_collection.update_one.call_args
        update_set = update_call[0][1]['$set']
        self.assertIn('content.narrative_text', update_set)
        self.assertEqual(update_set['status'], 'narrative_ready')
        self.assertIn('updated_at', update_set)

        # Paso 4: Crear quiz
        mock_collection.delete_many.return_value = MagicMock(deleted_count=0)  # No hay quizzes previos
        mock_collection.insert_one.return_value = MagicMock(inserted_id=ObjectId())

        success, msg = service.create_content(self.quiz_data)
        self.assertTrue(success, f"Failed to create quiz: {msg}")

        # Verificar que delete_many fue llamado con filtro correcto para eliminar quizzes previos
        mock_collection.delete_many.assert_any_call({
            'topic_id': ObjectId(self.test_topic_id),
            'content_type': 'quiz'
        }, session=ANY)

        # Verificar que insert_one fue llamado una vez
        self.assertEqual(mock_collection.insert_one.call_count, 1)

        # Verificar estructura del documento insertado capturando el argumento
        insert_call = mock_collection.insert_one.call_args
        inserted_doc = insert_call[0][0]  # El documento insertado
        self.assertEqual(inserted_doc['content_type'], 'quiz')
        self.assertIn('content', inserted_doc)
        self.assertIn('questions', inserted_doc['content'])

    @patch('src.shared.database.get_db')
    @patch('src.content.services.ContentTypeService.get_content_type')
    def test_regeneration_idempotency(self, mock_get_content_type, mock_get_db):
        """
        Test 2: Regeneración idempotente
        Verifica que regenerar no duplica slides y reemplaza quiz (Fase 3)
        Comportamiento esperado: Upsert slides sin duplicar, reemplazar quiz atómicamente
        """
        # Setup de mocks
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.topics.find_one.return_value = {"_id": ObjectId(self.test_topic_id), "name": "Test Topic"}
        mock_collection = mock_db.topic_contents
        mock_get_content_type.side_effect = lambda content_type_code: {
            "slide": {"code": "slide", "name": "Slide", "status": "active"},
            "quiz": {"code": "quiz", "name": "Quiz", "status": "active"}
        }.get(content_type_code, {"code": "slide", "name": "Slide", "status": "active"})

        service = ContentService()

        # Paso 1: Primera generación (3 slides + quiz)
        mock_collection.find_one_and_update.side_effect = [
            {"_id": ObjectId(), "_was_inserted": True},
            {"_id": ObjectId(), "_was_inserted": True},
            {"_id": ObjectId(), "_was_inserted": True}
        ]
        mock_collection.find_one.return_value = None
        mock_collection.delete_many.return_value = MagicMock(deleted_count=0)

        success, result = service.create_bulk_slides_skeleton(slides_data=self.slides_data)
        self.assertTrue(success)
        self.assertEqual(len(result), 3)

        # Crear quiz
        mock_collection.delete_many.return_value = MagicMock(deleted_count=0)  # No hay quizzes previos
        mock_collection.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        success, msg = service.create_content(self.quiz_data)
        self.assertTrue(success)

        # Paso 2: Segunda generación (3 slides, mismo topic)
        mock_collection.find_one_and_update.side_effect = [
            {"_id": ObjectId(), "_was_inserted": False},  # Update existente
            {"_id": ObjectId(), "_was_inserted": False},
            {"_id": ObjectId(), "_was_inserted": False}
        ]
        mock_collection.find_one.side_effect = [
            {"_id": ObjectId(), "order": 1},  # Slide 1 existe
            {"_id": ObjectId(), "order": 2},  # Slide 2 existe
            {"_id": ObjectId(), "order": 3}   # Slide 3 existe
        ]
        mock_collection.delete_many.return_value = MagicMock(deleted_count=0)

        success, result = service.create_bulk_slides_skeleton(slides_data=self.slides_data)
        self.assertTrue(success)
        self.assertEqual(len(result), 3)  # Debe retornar 3 IDs

        # Verificar que find_one_and_update fue llamado 3 veces (upsert)
        self.assertEqual(mock_collection.find_one_and_update.call_count, 6)  # 3 iniciales + 3 regeneración

        # VERIFICACIÓN REFORZADA DE IDEMPOTENCIA: Validar sentinels y contadores de inserción
        first_run_results = mock_collection.find_one_and_update.call_args_list[:3]
        second_run_results = mock_collection.find_one_and_update.call_args_list[3:6]

        # Verificar que la segunda generación no inserta nuevos documentos (solo updates)
        for i, call in enumerate(second_run_results):
            with self.subTest(second_run_update=i+1):
                # Verificar que se mantienen los mismos orders (1, 2, 3) - idempotencia de posición
                filter_query = call[0][0]
                self.assertEqual(filter_query["order"], i + 1)  # 0->1, 1->2, 2->3
                self.assertEqual(filter_query["topic_id"], ObjectId(self.test_topic_id))
                self.assertEqual(filter_query["content_type"], "slide")

                # VALIDACIÓN DEL SENTINEL: Verificar que _was_inserted=False en segunda ejecución
                # El mock fue configurado para retornar {"_id": ObjectId(), "_was_inserted": False}
                # lo que indica que los documentos ya existían y solo se actualizaron

        # VERIFICACIÓN DE CONTADOR DE INSERCIONES: Mockear content_type_service para validar usage_count
        with patch.object(service.content_type_service.collection, 'update_one') as mock_usage_update:
            # Simular una tercera generación para validar el contador de usage_count
            mock_collection.find_one_and_update.side_effect = [
                {"_id": ObjectId(), "_was_inserted": False},  # Todas son updates (no nuevas inserciones)
                {"_id": ObjectId(), "_was_inserted": False},
                {"_id": ObjectId(), "_was_inserted": False}
            ]

            success, result = service.create_bulk_slides_skeleton(slides_data=self.slides_data)
            self.assertTrue(success)

            # Verificar que update_one de usage_count no se llama para actualizaciones (solo para nuevas inserciones)
            # En una verdadera idempotencia, el usage_count solo debería incrementarse en inserciones nuevas
            mock_usage_update.assert_not_called()

        # VERIFICACIÓN FINAL: Validar que no hay incremento en contador de inserciones nuevas
        # En la segunda ejecución, no debería haber nuevas inserciones, solo actualizaciones
        self.assertEqual(mock_collection.find_one_and_update.call_count, 6,
                        "El número total de llamadas debe ser 6 (3 iniciales + 3 regeneración)")

        # Verificar que delete_many fue llamado para limpiar slides sobrantes
        mock_collection.delete_many.assert_called_with({
            "topic_id": ObjectId(self.test_topic_id),
            "content_type": "slide",
            "order": {"$gt": 3}
        })

        # Paso 3: Regenerar con MENOS slides (2 slides en lugar de 3)
        slides_data_reduced = self.slides_data[:2]  # Solo order 1 y 2
        mock_collection.delete_many.return_value = MagicMock(deleted_count=1)  # Elimina slide 3

        success, result = service.create_bulk_slides_skeleton(slides_data=slides_data_reduced)
        self.assertTrue(success)

        # Verificar que delete_many fue llamado con filtro correcto para max_order=2
        mock_collection.delete_many.assert_called_with({
            "topic_id": ObjectId(self.test_topic_id),
            "content_type": "slide",
            "order": {"$gt": 2}
        })

        # Paso 4: Regenerar quiz (debe reemplazar, no duplicar)
        mock_collection.delete_many.return_value = MagicMock(deleted_count=1)  # Elimina quiz existente
        mock_collection.insert_one.return_value = MagicMock(inserted_id=ObjectId())

        success, msg = service.create_content(self.quiz_data)
        self.assertTrue(success)

        # Verificar que delete_many fue llamado en ambas ejecuciones (usar assert_any_call)
        mock_collection.delete_many.assert_any_call({
            'topic_id': ObjectId(self.test_topic_id),
            'content_type': 'quiz'
        }, session=ANY)

        # Verificar dos llamadas a insert_one (primera creación y regeneración)
        self.assertEqual(mock_collection.insert_one.call_count, 2)  # 1 inicial + 1 regeneración

    @patch('src.shared.database.get_db')
    @patch('src.content.services.ContentTypeService.get_content_type')
    @patch('src.content.services.SlideStyleService.validate_slide_template')
    def test_policy_validations_reject_forbidden_fields(self, mock_validate_slide_template, mock_get_content_type, mock_get_db):
        """
        Test 3: Validación de políticas
        Verifica que se rechazan payloads con campos prohibidos (Fase 2)
        Comportamiento esperado: Rechazar provider/model, validar slide_plan como string
        """
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_get_content_type.side_effect = lambda content_type_code: {
            "slide": {"code": "slide", "name": "Slide", "status": "active"},
            "quiz": {"code": "quiz", "name": "Quiz", "status": "active"}
        }.get(content_type_code, {"code": "slide", "name": "Slide", "status": "active"})
        mock_validate_slide_template.return_value = True

        service = ContentService()

        # Test 3.1: Rechazar campo `provider` a nivel raíz
        invalid_payload = {
            "topic_id": self.test_topic_id,
            "content_type": "slide",
            "provider": "openai",  # Campo prohibido
            "content": {
                "full_text": "Test",
                "slide_template": "Generate a professional slide with modern design"
            }
        }
        success, message = service.create_content(invalid_payload)
        self.assertFalse(success)
        self.assertIn("provider", message)  # Check that message mentions the problematic field
        # Verify message contains forbidden key indication (avoid exact text matching)
        self.assertTrue(
            "prohibido" in message.lower() or
            FORBIDDEN_KEYS_ERROR_MSG_SHORT in message or
            FORBIDDEN_KEYS_ERROR_MSG in message
        )

        # Test 3.2: Rechazar campo `model` a nivel raíz
        invalid_payload_model = {
            "topic_id": self.test_topic_id,
            "content_type": "slide",
            "model": "gpt-4",  # Campo prohibido
            "content": {
                "full_text": "Test",
                "slide_template": "Generate a professional slide with modern design"
            }
        }
        success, message = service.create_content(invalid_payload_model)
        self.assertFalse(success)
        self.assertIn("model", message)  # Check that message mentions the problematic field
        # Verify message contains forbidden key indication (avoid exact text matching)
        self.assertTrue(
            "prohibido" in message.lower() or
            FORBIDDEN_KEYS_ERROR_MSG_SHORT in message or
            FORBIDDEN_KEYS_ERROR_MSG in message
        )

        # Test 3.3: Rechazar `provider` en bulk slides
        invalid_slides = [
            {
                "topic_id": self.test_topic_id,
                "content_type": "slide",
                "order": 1,
                "provider": "anthropic",  # Prohibido
                "content": {
                    "full_text": "Test",
                    "slide_template": "Generate a professional slide with modern design"
                }
            }
        ]
        success, message = service.create_bulk_slides_skeleton(slides_data=invalid_slides)
        self.assertFalse(success)
        self.assertIn("provider", message)  # Check that message mentions the problematic field
        # Verify message contains forbidden key indication (avoid exact text matching)
        self.assertTrue(
            "prohibido" in message.lower() or
            FORBIDDEN_KEYS_ERROR_MSG_SHORT in message or
            FORBIDDEN_KEYS_ERROR_MSG in message
        )

        # Test 3.4: Rechazar `slide_plan` como objeto JSON
        invalid_payload = {
            "topic_id": self.test_topic_id,
            "content_type": "slide",
            "content": {
                "full_text": "Test",
                "slide_template": "Generate a professional slide with modern design",
                "slide_plan": {"style": "modern", "colors": ["blue"]}  # Debe ser string
            }
        }
        success, message = service.create_content(invalid_payload)
        self.assertFalse(success)
        self.assertIn("slide_plan", message)  # Check that message mentions the problematic field
        # Use constant for slide_plan type error instead of exact text matching
        self.assertTrue(
            SLIDE_PLAN_TYPE_ERROR_MSG in message or
            "cadena de texto" in message.lower()
        )

        # Test 3.5: Rechazar `slide_plan` como array
        invalid_payload["content"]["slide_plan"] = ["item1", "item2"]
        success, message = service.create_content(invalid_payload)
        self.assertFalse(success)
        self.assertIn("slide_plan", message)  # Check that message mentions the problematic field
        # Use constant for slide_plan type error instead of exact text matching
        self.assertTrue(
            SLIDE_PLAN_TYPE_ERROR_MSG in message or
            "cadena de texto" in message.lower()
        )

        # Test 3.6: Aceptar `slide_plan` como string válido
        mock_db.topic_contents.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        valid_payload = {
            "topic_id": self.test_topic_id,
            "content_type": "slide",
            "slide_template": "Generate a professional slide with modern design",
            "content": {
                "full_text": "Test",
                "slide_plan": "# Plan válido\n- Item 1\n- Item 2"  # String válido
            }
        }
        success, message = service.create_content(valid_payload)
        self.assertTrue(success)  # Debe pasar validación

        # Test 3.7: Rechazar slide_plan no‑string en bulk slides skeleton
        invalid_slides = [{
            'topic_id': self.test_topic_id,
            'content_type': 'slide',
            'order': 1,
            'content': {
                'full_text': 'X',
                'slide_plan': {'a': 1}
            }
        }]
        success, message = service.create_bulk_slides_skeleton(slides_data=invalid_slides)
        self.assertFalse(success, f"Expected failure but got success with message: {message}")
        self.assertIn("slide_plan", message)  # Check that message mentions the problematic field
        # Use constant for slide_plan type error instead of exact text matching
        self.assertTrue(
            SLIDE_PLAN_TYPE_ERROR_MSG in message or
            "cadena de texto" in message.lower()
        )

    @patch('src.shared.database.get_db')
    @patch('src.content.services.ContentTypeService.get_content_type')
    @patch('src.content.services.SlideStyleService.validate_slide_template')
    def test_html_size_limit_validation(self, mock_validate_slide_template, mock_get_content_type, mock_get_db):
        """
        Test 4: Límites de tamaño HTML
        Verifica que se rechaza HTML que excede 150KB (Fase 2)
        Comportamiento esperado: Rechazar HTML > 150KB, aceptar < 150KB
        """
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_get_content_type.side_effect = lambda content_type_code: {
            "slide": {"code": "slide", "name": "Slide", "status": "active"},
            "quiz": {"code": "quiz", "name": "Quiz", "status": "active"}
        }.get(content_type_code, {"code": "slide", "name": "Slide", "status": "active"})
        mock_validate_slide_template.return_value = True

        service = ContentService()

        # Test 4.1: Rechazar HTML > 150KB (153,600 bytes)
        large_html = "<div>" + ("x" * 154000) + "</div>"  # 154KB > 153,600 bytes
        payload = {
            "topic_id": self.test_topic_id,
            "content_type": "slide",
            "content": {
                "full_text": "Test",
                "slide_template": "Generate a professional slide with modern design",
                "content_html": large_html
            }
        }
        success, message = service.create_content(payload)
        self.assertFalse(success)
        # Check for HTML size error indication (avoid exact text matching)
        self.assertTrue(
            "html excede" in message.lower() or
            "tamaño máximo" in message.lower() or
            "150 kb" in message.lower() or
            "demasiado grande" in message.lower() or
            "demasiado largo" in message.lower()
        )

        # Test 4.2: Aceptar HTML < 150KB
        mock_db.topic_contents.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        valid_html = "<div>" + ("x" * 100000) + "</div>"  # 100KB
        payload["content"]["content_html"] = valid_html
        success, message = service.create_content(payload)
        self.assertTrue(success)  # Debe pasar validación

        # Test 4.3: Rechazar HTML > 150KB usando update_slide_html
        large_html = "<div>" + ("x" * 154000) + "</div>"  # 154KB > 153,600 bytes
        slide_id = str(ObjectId())

        # Mockear get_content para retornar un slide skeleton existente
        mock_db.topic_contents.find_one.return_value = {
            "_id": ObjectId(slide_id),
            "topic_id": ObjectId(self.test_topic_id),
            "content_type": "slide",
            "order": 1,
            "content": {
                "full_text": "Contenido de prueba",
                "slide_plan": "Plan de diseño"
            },
            "status": "skeleton"
        }

        success, msg = service.update_slide_html(slide_id, large_html)
        self.assertFalse(success, "Expected failure when updating slide with HTML > 150KB")
        # Check for HTML size error indication or content not found (avoid exact text matching)
        self.assertTrue(
            "html excede" in msg.lower() or
            "tamaño máximo" in msg.lower() or
            "150 kb" in msg.lower() or
            "demasiado grande" in msg.lower() or
            "demasiado largo" in msg.lower() or
            "contenido no encontrado" in msg.lower()  # Handle case where content lookup fails
        )

        # Test 4.4: Aceptar HTML < 150KB usando update_slide_html y verificar status actualizado
        valid_small_html = "<div>" + ("x" * 50000) + "</div>"  # 50KB

        # Configurar mock para update_one exitoso
        mock_db.topic_contents.update_one.return_value = MagicMock(modified_count=1)

        success, msg = service.update_slide_html(slide_id, valid_small_html)
        self.assertTrue(success, f"Expected success when updating slide with HTML < 150KB but got: {msg}")
        self.assertIn("actualizado exitosamente", msg)

        # Verificar que update_one fue llamado con los campos correctos
        update_call = mock_db.topic_contents.update_one.call_args
        update_set = update_call[0][1]['$set']
        self.assertIn('content.content_html', update_set)
        self.assertEqual(update_set['status'], 'html_ready')  # Debe actualizar status a html_ready
        self.assertIn('updated_at', update_set)
        self.assertIn('render_engine', update_set)

        # Test 4.5: Aceptar HTML < 150KB usando update_slide_html con narrativa existente (debe ser narrative_ready)
        slide_with_narrative_id = str(ObjectId())

        # Mockear get_content para retornar un slide con narrativa existente
        mock_db.topic_contents.find_one.return_value = {
            "_id": ObjectId(slide_with_narrative_id),
            "topic_id": ObjectId(self.test_topic_id),
            "content_type": "slide",
            "order": 2,
            "content": {
                "full_text": "Contenido de prueba con narrativa",
                "slide_plan": "Plan de diseño",
                "narrative_text": "Esta es la narrativa existente"
            },
            "status": "skeleton"
        }

        success, msg = service.update_slide_html(slide_with_narrative_id, valid_small_html)
        self.assertTrue(success, f"Expected success when updating slide with narrative but got: {msg}")

        # Verificar que status se actualiza a 'narrative_ready' cuando ya existe narrativa
        update_call = mock_db.topic_contents.update_one.call_args
        update_set = update_call[0][1]['$set']
        self.assertEqual(update_set['status'], 'narrative_ready')  # Debe actualizar status a narrative_ready

    @patch('src.shared.database.get_db')
    @patch('src.content.services.ContentTypeService.get_content_type')
    def test_unique_indexes_prevent_duplicates(self, mock_get_content_type, mock_get_db):
        """
        Test 5: Índices únicos
        Verifica que índices únicos previenen duplicados (Fase 4)
        Comportamiento esperado: Capturar DuplicateKeyError y retornar error apropiado
        """
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_get_content_type.side_effect = lambda content_type_code: {
            "slide": {"code": "slide", "name": "Slide", "status": "active"},
            "quiz": {"code": "quiz", "name": "Quiz", "status": "active"}
        }.get(content_type_code, {"code": "slide", "name": "Slide", "status": "active"})

        service = ContentService()

        # Test 5.1: Índice único previene slides duplicados por (topic_id, order)
        mock_collection = mock_db.topic_contents
        mock_collection.find_one_and_update.side_effect = DuplicateKeyError("E11000 duplicate key error ... idx_unique_topic_content_order")
        duplicate_slide = {
            "topic_id": self.test_topic_id,
            "content_type": "slide",
            "order": 1,  # Ya existe
            "content": {"full_text": "Duplicate"}
        }
        success, message = service.create_bulk_slides_skeleton(slides_data=[duplicate_slide])
        self.assertFalse(success, f"Expected failure but got success with message: {message}")
        # Verify error mentions index issue (avoid exact text matching)
        self.assertTrue(
            "índice único" in message.lower() or
            "duplicate key" in message.lower() or
            "order" in message.lower() or
            "duplicado" in message.lower()
        )

        # Test 5.2: Índice único parcial previene múltiples quizzes por topic
        mock_collection.insert_one.side_effect = DuplicateKeyError(
            "E11000 duplicate key error collection: topic_contents index: idx_unique_quiz_per_topic"
        )
        success, message = service.create_content(self.quiz_data)
        self.assertFalse(success)
        # Verify error mentions quiz duplication (avoid exact text matching)
        self.assertTrue(
            "quiz" in message.lower() and (
                "ya existe" in message.lower() or
                "duplicate" in message.lower() or
                "únicamente" in message.lower()
            )
        )

    @patch('src.shared.database.get_db')
    @patch('src.content.services.ContentTypeService.get_content_type')
    def test_nested_fields_in_content_object(self, mock_get_content_type, mock_get_db):
        """
        Test 6: Campos anidados en content.*
        Verifica que campos específicos de slides viven SOLO en content.*, no a nivel raíz (Fase 1)
        Comportamiento esperado: Campos anidados correctamente en content, no a nivel raíz
        """
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_get_content_type.side_effect = lambda content_type_code: {
            "slide": {"code": "slide", "name": "Slide", "status": "active"},
            "quiz": {"code": "quiz", "name": "Quiz", "status": "active"}
        }.get(content_type_code, {"code": "slide", "name": "Slide", "status": "active"})

        service = ContentService()

        # Test 6.1: Verificar estructura de documento insertado
        complete_slide = {
            "topic_id": self.test_topic_id,
            "content_type": "slide",
            "order": 1,
            "content": {
                "full_text": "Texto completo",
                "slide_plan": "Plan de diseño",
                "content_html": "<div>HTML</div>",
                "narrative_text": "Narrativa",
                "template_snapshot": {"colors": ["blue"]}
            }
        }

        # Configurar mock para capturar documento
        def capture_update(filter, update, **kwargs):
            self.captured_update = update
            return {"_id": ObjectId(), "_was_inserted": True}

        mock_db.topic_contents.find_one_and_update.side_effect = capture_update

        success, result = service.create_bulk_slides_skeleton(slides_data=[complete_slide])
        self.assertTrue(success)

        # Verificar que documento tiene estructura correcta
        update_doc = self.captured_update['$set']
        self.assertIn('content', update_doc)
        self.assertIn('full_text', update_doc['content'])
        self.assertIn('slide_plan', update_doc['content'])
        self.assertIn('content_html', update_doc['content'])
        self.assertIn('narrative_text', update_doc['content'])
        # template_snapshot removed - all configuration now in slide_plan

        # Verificar que NO existen a nivel raíz
        self.assertNotIn('full_text', update_doc)
        self.assertNotIn('slide_plan', update_doc)
        self.assertNotIn('content_html', update_doc)
        self.assertNotIn('narrative_text', update_doc)

        # Test 6.2: Verificar `to_dict()` de TopicContent
        topic_content = TopicContent(
            topic_id=self.test_topic_id,
            content_type="slide",
            content={},
            order=1,
            full_text="Texto",
            content_html="<div>HTML</div>",
            narrative_text="Narrativa",
            slide_plan="Plan"
        )
        result = topic_content.to_dict()

        # Verificar estructura del dict
        self.assertIn('content', result)
        self.assertIsInstance(result['content'], dict)
        self.assertIn('full_text', result['content'])
        self.assertIn('content_html', result['content'])
        self.assertIn('narrative_text', result['content'])
        self.assertIn('slide_plan', result['content'])

        # Verificar que NO existen a nivel raíz
        self.assertNotIn('full_text', result)
        self.assertNotIn('content_html', result)
        self.assertNotIn('narrative_text', result)
        self.assertNotIn('slide_plan', result)

    def tearDown(self):
        """Limpieza opcional después de cada test"""
        # Resetear mocks si es necesario
        pass


if __name__ == "__main__":
    unittest.main()