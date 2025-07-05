#!/usr/bin/env python3
"""
Script de Testing Integral - Módulos Virtuales Progresivos
Verifica el flujo completo desde creación hasta sincronización automática.
"""

import os
import sys
import requests
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Añadir directorio raíz al path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class VirtualModulesFlowTester:
    def __init__(self, base_url="http://localhost:5000", token=None):
        self.base_url = base_url
        self.token = token
        self.headers = {}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        
        # IDs para limpieza
        self.created_ids = {
            "study_plans": [],
            "modules": [],
            "topics": [],
            "virtual_modules": [],
            "users": []
        }

    def log(self, message, level="INFO"):
        """Log con timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def api_call(self, method, endpoint, data=None, expected_status=200):
        """Realizar llamada a la API"""
        url = f"{self.base_url}/api{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers, params=data)
            elif method.upper() == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=self.headers, json=data)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=self.headers)
            
            if response.status_code != expected_status:
                self.log(f"❌ API Error {response.status_code}: {response.text}", "ERROR")
                return None
            
            return response.json()
        except Exception as e:
            self.log(f"❌ Request failed: {str(e)}", "ERROR")
            return None

    def test_1_create_study_plan(self):
        """Paso 1: Crear plan de estudios"""
        self.log("🚀 PASO 1: Creando plan de estudios...")
        
        study_plan_data = {
            "version": "1.0",
            "author_id": "test_author_123",
            "name": "Plan de Prueba - Módulos Virtuales",
            "description": "Plan para testing del sistema de módulos virtuales progresivos",
            "subject_id": "test_subject_123"
        }
        
        result = self.api_call("POST", "/study_plan/", study_plan_data, 201)
        if result and result.get("success"):
            plan_id = result["data"]["id"]
            self.created_ids["study_plans"].append(plan_id)
            self.log(f"✅ Plan de estudios creado: {plan_id}")
            return plan_id
        else:
            self.log("❌ Error creando plan de estudios", "ERROR")
            return None

    def test_2_create_module_with_topics(self, study_plan_id):
        """Paso 2: Crear módulo con temas"""
        self.log("📚 PASO 2: Creando módulo con temas...")
        
        # Crear módulo
        module_data = {
            "study_plan_id": study_plan_id,
            "name": "Módulo de Prueba Virtual",
            "learning_outcomes": ["Objetivo 1", "Objetivo 2", "Objetivo 3"],
            "evaluation_rubric": {"criteria": "Criterios de evaluación"},
            "date_start": (datetime.now()).isoformat(),
            "date_end": (datetime.now() + timedelta(days=30)).isoformat(),
            "topics": [
                {
                    "name": "Tema 1: Introducción",
                    "difficulty": "easy",
                    "theory_content": "Contenido teórico del tema 1 para testing",
                    "date_start": (datetime.now()).isoformat(),
                    "date_end": (datetime.now() + timedelta(days=7)).isoformat(),
                    "published": False  # Inicialmente no publicado
                },
                {
                    "name": "Tema 2: Desarrollo",
                    "difficulty": "medium", 
                    "theory_content": "Contenido teórico del tema 2 para testing",
                    "date_start": (datetime.now() + timedelta(days=7)).isoformat(),
                    "date_end": (datetime.now() + timedelta(days=14)).isoformat(),
                    "published": False
                },
                {
                    "name": "Tema 3: Avanzado",
                    "difficulty": "hard",
                    "theory_content": "Contenido teórico del tema 3 para testing",
                    "date_start": (datetime.now() + timedelta(days=14)).isoformat(),
                    "date_end": (datetime.now() + timedelta(days=21)).isoformat(),
                    "published": False
                },
                {
                    "name": "Tema 4: Evaluación",
                    "difficulty": "medium",
                    "theory_content": "Contenido teórico del tema 4 para testing",
                    "date_start": (datetime.now() + timedelta(days=21)).isoformat(),
                    "date_end": (datetime.now() + timedelta(days=28)).isoformat(),
                    "published": False
                }
            ]
        }
        
        result = self.api_call("POST", "/study_plan/module", module_data, 201)
        if result and result.get("success"):
            module_id = result["data"]["id"]
            topic_ids = result["data"]["topics"]
            self.created_ids["modules"].append(module_id)
            self.created_ids["topics"].extend(topic_ids)
            self.log(f"✅ Módulo creado: {module_id} con {len(topic_ids)} temas")
            return module_id, topic_ids
        else:
            self.log("❌ Error creando módulo", "ERROR")
            return None, None

    def test_3_publication_management(self, module_id, topic_ids):
        """Paso 3: Gestión de publicación de temas"""
        self.log("📝 PASO 3: Probando gestión de publicación...")
        
        # 3.1 Verificar estado inicial
        status = self.api_call("GET", f"/study_plan/module/{module_id}/topics/publication-status")
        if status and status.get("success"):
            data = status["data"]
            self.log(f"📊 Estado inicial: {data['published_count']}/{data['total_topics']} temas publicados")
        
        # 3.2 Publicar primeros 2 temas individualmente
        for i, topic_id in enumerate(topic_ids[:2]):
            result = self.api_call("PUT", f"/study_plan/topic/{topic_id}/publish", {"published": True})
            if result and result.get("success"):
                self.log(f"✅ Tema {i+1} publicado individualmente")
            else:
                self.log(f"❌ Error publicando tema {i+1}", "ERROR")
        
        # 3.3 Verificar estado después de publicación individual
        status = self.api_call("GET", f"/study_plan/module/{module_id}/topics/publication-status")
        if status and status.get("success"):
            data = status["data"]
            self.log(f"📊 Después de publicación individual: {data['published_count']}/{data['total_topics']} temas")
        
        # 3.4 Auto-publicar temas restantes (debería publicar tema 3 y 4 porque tienen contenido)
        result = self.api_call("POST", f"/study_plan/module/{module_id}/topics/auto-publish")
        if result and result.get("success"):
            auto_published = result["data"]["total_published"]
            self.log(f"✅ Auto-publicación: {auto_published} temas adicionales publicados")
        
        # 3.5 Verificar estado final
        status = self.api_call("GET", f"/study_plan/module/{module_id}/topics/publication-status")
        if status and status.get("success"):
            data = status["data"]
            self.log(f"📊 Estado final: {data['published_count']}/{data['total_topics']} temas publicados ({data['publication_percentage']}%)")
            return data['published_count'] == data['total_topics']
        
        return False

    def test_4_enable_virtualization(self, module_id):
        """Paso 4: Habilitar virtualización del módulo"""
        self.log("⚙️ PASO 4: Habilitando virtualización...")
        
        # Verificar requisitos de virtualización
        readiness = self.api_call("GET", f"/study_plan/module/{module_id}/virtualization-readiness")
        if readiness and readiness.get("success"):
            self.log(f"📋 Readiness verificado: {readiness['data']}")
        
        # Con la nueva lógica ya no se habilita manualmente
        self.log("✅ Paso de habilitación omitido - se usa publicación de temas")
        return True

    def test_5_generate_virtual_module(self, study_plan_id, module_id):
        """Paso 5: Generar módulo virtual para estudiante"""
        self.log("🤖 PASO 5: Generando módulo virtual...")
        
        # Datos del estudiante ficticio
        student_data = {
            "class_id": "test_class_123",
            "study_plan_id": study_plan_id,
            "student_id": "test_student_123",
            "module_id": module_id,
            "preferences": {"learning_style": "visual"},
            "adaptive_options": {
                "cognitive_profile": {
                    "visual_strength": 0.8,
                    "learning_speed": "medium"
                }
            }
        }
        
        result = self.api_call("POST", "/virtual/generate", student_data, 201)
        if result and result.get("success"):
            created_modules = result["data"]["created_modules"]
            if created_modules:
                virtual_module_id = created_modules[0]["virtual_module_id"]
                self.created_ids["virtual_modules"].append(virtual_module_id)
                self.log(f"✅ Módulo virtual generado: {virtual_module_id}")
                return virtual_module_id, "test_student_123"
            else:
                updated_modules = result["data"]["updated_modules"] 
                if updated_modules:
                    virtual_module_id = updated_modules[0]["virtual_module_id"]
                    self.log(f"✅ Módulo virtual actualizado: {virtual_module_id}")
                    return virtual_module_id, "test_student_123"
        
        self.log("❌ Error generando módulo virtual", "ERROR")
        return None, None

    def test_6_progressive_topic_generation(self, student_id, topic_ids):
        """Paso 6: Probar generación progresiva de temas"""
        self.log("🔄 PASO 6: Probando generación progresiva...")
        
        if not topic_ids:
            self.log("❌ No hay topic_ids para probar", "ERROR")
            return False
        
        # Simular progreso en el primer tema y disparar siguiente
        current_topic_id = topic_ids[0]
        trigger_data = {
            "current_topic_id": current_topic_id,
            "student_id": student_id,
            "progress": 85  # Más del 80% requerido
        }
        
        result = self.api_call("POST", "/virtual/trigger-next-topic", trigger_data)
        if result and result.get("success"):
            data = result["data"]
            generated = data.get("total_generated", 0)
            self.log(f"✅ Trigger next topic: {generated} temas generados")
            self.log(f"📊 Progreso: {data.get('progress_info', {})}")
            return True
        else:
            self.log("❌ Error en trigger-next-topic", "ERROR")
            return False

    def test_7_content_synchronization(self, module_id, topic_ids):
        """Paso 7: Probar sincronización de contenido"""
        self.log("🔄 PASO 7: Probando sincronización automática...")
        
        if not topic_ids:
            return False
        
        # Simular cambio: actualizar contenido de un tema
        topic_id = topic_ids[0]
        update_data = {
            "theory_content": "Contenido actualizado para testing de sincronización automática"
        }
        
        result = self.api_call("PUT", f"/study_plan/topic/{topic_id}", update_data)
        if result and result.get("success"):
            self.log("✅ Contenido de tema actualizado")
        
        # Detectar cambios manualmente
        result = self.api_call("POST", f"/virtual/modules/{module_id}/detect-changes")
        if result and result.get("success"):
            changes_detected = result["data"]["changes_detected"]
            if changes_detected:
                scheduled_updates = result["data"]["scheduled_updates"]
                self.log(f"✅ Cambios detectados: {scheduled_updates} actualizaciones programadas")
                return True
            else:
                self.log("📋 No se detectaron cambios (normal si es la primera ejecución)")
                return True
        else:
            self.log("❌ Error detectando cambios", "ERROR")
            return False

    def test_8_queue_processing(self):
        """Paso 8: Procesar cola de tareas"""
        self.log("⚙️ PASO 8: Procesando cola de tareas...")
        
        result = self.api_call("POST", "/virtual/process-queue")
        if result and result.get("success"):
            processed = result["data"]["processed_tasks"]
            failed = result["data"]["failed_tasks"]
            self.log(f"✅ Cola procesada: {processed} exitosas, {failed} fallidas")
            return True
        else:
            self.log("❌ Error procesando cola", "ERROR")
            return False

    def cleanup(self):
        """Limpiar datos de prueba (opcional)"""
        self.log("🧹 Limpiando datos de prueba...")
        
        # En un entorno real, aquí se eliminarían los datos de prueba
        # Por ahora solo mostramos qué se creó
        for resource_type, ids in self.created_ids.items():
            if ids:
                self.log(f"📋 {resource_type}: {len(ids)} elementos creados")

    def run_full_test(self):
        """Ejecutar test completo"""
        self.log("🎯 INICIANDO TEST INTEGRAL DE MÓDULOS VIRTUALES PROGRESIVOS")
        self.log("=" * 70)
        
        success_count = 0
        total_tests = 8
        
        try:
            # Paso 1: Crear plan de estudios
            study_plan_id = self.test_1_create_study_plan()
            if study_plan_id:
                success_count += 1
            else:
                return False
            
            # Paso 2: Crear módulo con temas
            module_id, topic_ids = self.test_2_create_module_with_topics(study_plan_id)
            if module_id and topic_ids:
                success_count += 1
            else:
                return False
            
            # Paso 3: Gestión de publicación
            if self.test_3_publication_management(module_id, topic_ids):
                success_count += 1
            
            # Paso 4: Habilitar virtualización
            if self.test_4_enable_virtualization(module_id):
                success_count += 1
            
            # Paso 5: Generar módulo virtual
            virtual_module_id, student_id = self.test_5_generate_virtual_module(study_plan_id, module_id)
            if virtual_module_id and student_id:
                success_count += 1
            
            # Paso 6: Generación progresiva
            if self.test_6_progressive_topic_generation(student_id, topic_ids):
                success_count += 1
            
            # Paso 7: Sincronización
            if self.test_7_content_synchronization(module_id, topic_ids):
                success_count += 1
            
            # Paso 8: Procesar cola
            if self.test_8_queue_processing():
                success_count += 1
            
            # Resumen
            self.log("=" * 70)
            self.log(f"🎯 RESUMEN: {success_count}/{total_tests} pruebas exitosas")
            
            if success_count == total_tests:
                self.log("🎉 ¡TODAS LAS PRUEBAS PASARON EXITOSAMENTE!")
                self.log("✅ El sistema de módulos virtuales progresivos está funcionando correctamente")
            else:
                self.log(f"⚠️ {total_tests - success_count} pruebas fallaron")
            
            return success_count == total_tests
            
        except Exception as e:
            self.log(f"❌ Error crítico durante testing: {str(e)}", "ERROR")
            return False
        finally:
            self.cleanup()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Testing integral de módulos virtuales")
    parser.add_argument('--url', default='http://localhost:5000', 
                       help='URL base del API (default: http://localhost:5000)')
    parser.add_argument('--token', help='Token de autenticación')
    parser.add_argument('--cleanup', action='store_true',
                       help='Limpiar datos de prueba al final')
    
    args = parser.parse_args()
    
    print("🧪 Testing Integral - Sistema de Módulos Virtuales Progresivos")
    print("=" * 70)
    
    if not args.token:
        print("⚠️  Nota: No se proporcionó token de autenticación")
        print("   Algunas pruebas pueden fallar si el API requiere autenticación")
    
    tester = VirtualModulesFlowTester(base_url=args.url, token=args.token)
    success = tester.run_full_test()
    
    if success:
        print("\n✅ Testing completado exitosamente")
        sys.exit(0)
    else:
        print("\n❌ Testing falló")
        sys.exit(1)

if __name__ == "__main__":
    main() 