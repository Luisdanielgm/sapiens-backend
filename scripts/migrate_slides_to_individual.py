#!/usr/bin/env python3
"""
Script de migración de datos legacy: Convierte contenidos tipo 'slides' únicos
a múltiples contenidos tipo 'slide' individuales.

Este script:
1. Busca todos los TopicContent con content_type="slides"
2. Analiza su estructura de contenido
3. Crea múltiples TopicContent con content_type="slide" individuales
4. Mantiene el slide_template y otros metadatos
5. Establece el orden secuencial correcto
6. Marca el contenido legacy como migrado

Uso:
    python scripts/migrate_slides_to_individual.py [--dry-run] [--topic-id TOPIC_ID]
"""

import sys
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from bson import ObjectId
import argparse

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.shared.database import get_database
from src.content.models import TopicContent, ContentTypes
from src.content.services import ContentService
from src.content.slide_style_service import SlideStyleService

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration_slides.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SlideMigrationService:
    """Servicio para migrar contenidos tipo 'slides' a 'slide' individuales"""
    
    def __init__(self, db):
        self.db = db
        self.collection = db.topic_contents
        self.content_service = ContentService(db)
        self.slide_style_service = SlideStyleService(db)
        
        # Estadísticas de migración
        self.stats = {
            'total_slides_found': 0,
            'successfully_migrated': 0,
            'failed_migrations': 0,
            'individual_slides_created': 0,
            'errors': []
        }
    
    def find_legacy_slides_content(self, topic_id: Optional[str] = None) -> List[Dict]:
        """
        Encuentra todos los contenidos tipo 'slides' que necesitan migración.
        
        Args:
            topic_id: ID específico del tema (opcional)
            
        Returns:
            Lista de documentos TopicContent tipo 'slides'
        """
        query = {
            "content_type": ContentTypes.SLIDES,
            "status": {"$in": ["draft", "active", "published"]},
            "migrated_to_individual_slides": {"$ne": True}  # No migrados previamente
        }
        
        if topic_id:
            query["topic_id"] = ObjectId(topic_id)
        
        legacy_slides = list(self.collection.find(query))
        self.stats['total_slides_found'] = len(legacy_slides)
        
        logger.info(f"Encontrados {len(legacy_slides)} contenidos tipo 'slides' para migrar")
        return legacy_slides
    
    def parse_slides_content(self, slides_content: Dict) -> List[Dict]:
        """
        Parsea el contenido tipo 'slides' y extrae las diapositivas individuales.
        
        Args:
            slides_content: Documento TopicContent tipo 'slides'
            
        Returns:
            Lista de estructuras de diapositivas individuales
        """
        content = slides_content.get('content', '')
        individual_slides = []
        
        try:
            # Si el contenido es un string JSON, parsearlo
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    # Si no es JSON válido, tratarlo como texto plano
                    content = {'text': content}
            
            # Caso 1: Contenido es una lista de diapositivas
            if isinstance(content, list):
                for i, slide_data in enumerate(content):
                    individual_slides.append({
                        'order': i,
                        'title': slide_data.get('title', f'Diapositiva {i + 1}'),
                        'content': slide_data,
                        'slide_template': slides_content.get('slide_template', {})
                    })
            
            # Caso 2: Contenido es un objeto con múltiples secciones
            elif isinstance(content, dict):
                # Buscar patrones comunes de estructura
                if 'slides' in content and isinstance(content['slides'], list):
                    # Estructura: {"slides": [{...}, {...}]}
                    for i, slide_data in enumerate(content['slides']):
                        individual_slides.append({
                            'order': i,
                            'title': slide_data.get('title', f'Diapositiva {i + 1}'),
                            'content': slide_data,
                            'slide_template': slides_content.get('slide_template', {})
                        })
                
                elif 'sections' in content and isinstance(content['sections'], list):
                    # Estructura: {"sections": [{...}, {...}]}
                    for i, section in enumerate(content['sections']):
                        individual_slides.append({
                            'order': i,
                            'title': section.get('title', f'Sección {i + 1}'),
                            'content': {
                                'title': section.get('title', f'Sección {i + 1}'),
                                'full_text': section.get('content', section.get('text', '')),
                                'narrative_text': section.get('narrative', section.get('description', ''))
                            },
                            'slide_template': slides_content.get('slide_template', {})
                        })
                
                else:
                    # Contenido como una sola diapositiva
                    individual_slides.append({
                        'order': 0,
                        'title': content.get('title', 'Presentación'),
                        'content': content,
                        'slide_template': slides_content.get('slide_template', {})
                    })
            
            # Caso 3: Contenido es texto plano - dividir por párrafos o secciones
            else:
                content_str = str(content)
                # Intentar dividir por títulos o secciones
                sections = self._split_text_into_sections(content_str)
                
                for i, section in enumerate(sections):
                    individual_slides.append({
                        'order': i,
                        'title': section.get('title', f'Diapositiva {i + 1}'),
                        'content': {
                            'title': section.get('title', f'Diapositiva {i + 1}'),
                            'full_text': section.get('content', ''),
                            'narrative_text': section.get('content', '')
                        },
                        'slide_template': slides_content.get('slide_template', {})
                    })
            
            logger.info(f"Parseadas {len(individual_slides)} diapositivas del contenido {slides_content['_id']}")
            return individual_slides
            
        except Exception as e:
            logger.error(f"Error parseando contenido {slides_content['_id']}: {str(e)}")
            self.stats['errors'].append(f"Parse error en {slides_content['_id']}: {str(e)}")
            return []
    
    def _split_text_into_sections(self, text: str) -> List[Dict]:
        """
        Divide texto plano en secciones basándose en patrones comunes.
        
        Args:
            text: Texto a dividir
            
        Returns:
            Lista de secciones con título y contenido
        """
        sections = []
        
        # Dividir por títulos numerados (1., 2., etc.)
        import re
        title_pattern = r'^(\d+\.\s*[^\n]+)'
        parts = re.split(title_pattern, text, flags=re.MULTILINE)
        
        if len(parts) > 1:
            # Hay títulos numerados
            for i in range(1, len(parts), 2):
                if i + 1 < len(parts):
                    title = parts[i].strip()
                    content = parts[i + 1].strip()
                    sections.append({
                        'title': title,
                        'content': content
                    })
        else:
            # Dividir por párrafos largos
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            
            if len(paragraphs) > 1:
                for i, paragraph in enumerate(paragraphs):
                    # Usar la primera línea como título si es corta
                    lines = paragraph.split('\n')
                    if len(lines) > 1 and len(lines[0]) < 100:
                        title = lines[0]
                        content = '\n'.join(lines[1:])
                    else:
                        title = f"Sección {i + 1}"
                        content = paragraph
                    
                    sections.append({
                        'title': title,
                        'content': content
                    })
            else:
                # Una sola sección
                sections.append({
                    'title': "Presentación",
                    'content': text
                })
        
        return sections
    
    def create_individual_slide(self, topic_id: str, slide_data: Dict, 
                               original_content: Dict) -> Tuple[bool, Optional[str]]:
        """
        Crea un TopicContent individual tipo 'slide'.
        
        Args:
            topic_id: ID del tema
            slide_data: Datos de la diapositiva individual
            original_content: Contenido original tipo 'slides'
            
        Returns:
            Tuple (éxito, content_id o mensaje de error)
        """
        try:
            # Preparar datos del contenido
            content_data = {
                'content': slide_data['content'],
                'slide_template': slide_data['slide_template'],
                'order': slide_data['order'],
                'parent_content_id': None,  # Es una diapositiva principal
                'migrated_from_slides': str(original_content['_id']),
                'migration_timestamp': datetime.utcnow()
            }
            
            # Heredar metadatos del contenido original
            if 'learning_methodologies' in original_content:
                content_data['learning_methodologies'] = original_content['learning_methodologies']
            
            if 'adaptation_options' in original_content:
                content_data['adaptation_options'] = original_content['adaptation_options']
            
            if 'resources' in original_content:
                content_data['resources'] = original_content['resources']
            
            if 'web_resources' in original_content:
                content_data['web_resources'] = original_content['web_resources']
            
            # Crear el contenido usando ContentService
            success, result = self.content_service.create_content(
                topic_id=topic_id,
                content_type=ContentTypes.SLIDE,
                content_data=content_data
            )
            
            if success:
                logger.info(f"Creada diapositiva individual: {result}")
                self.stats['individual_slides_created'] += 1
                return True, result
            else:
                logger.error(f"Error creando diapositiva: {result}")
                self.stats['errors'].append(f"Error creando slide: {result}")
                return False, result
                
        except Exception as e:
            error_msg = f"Excepción creando diapositiva: {str(e)}"
            logger.error(error_msg)
            self.stats['errors'].append(error_msg)
            return False, error_msg
    
    def mark_as_migrated(self, slides_content_id: ObjectId) -> bool:
        """
        Marca el contenido tipo 'slides' original como migrado.
        
        Args:
            slides_content_id: ID del contenido original
            
        Returns:
            True si se marcó exitosamente
        """
        try:
            result = self.collection.update_one(
                {"_id": slides_content_id},
                {
                    "$set": {
                        "migrated_to_individual_slides": True,
                        "migration_timestamp": datetime.utcnow(),
                        "status": "migrated"  # Cambiar status para no mostrarlo
                    }
                }
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error marcando como migrado {slides_content_id}: {str(e)}")
            return False
    
    def migrate_slides_content(self, slides_content: Dict, dry_run: bool = False) -> bool:
        """
        Migra un contenido tipo 'slides' específico.
        
        Args:
            slides_content: Documento TopicContent tipo 'slides'
            dry_run: Si True, solo simula la migración
            
        Returns:
            True si la migración fue exitosa
        """
        content_id = slides_content['_id']
        topic_id = str(slides_content['topic_id'])
        
        logger.info(f"Migrando contenido {content_id} del tema {topic_id}")
        
        # Parsear las diapositivas individuales
        individual_slides = self.parse_slides_content(slides_content)
        
        if not individual_slides:
            logger.warning(f"No se pudieron extraer diapositivas del contenido {content_id}")
            return False
        
        if dry_run:
            logger.info(f"[DRY RUN] Se crearían {len(individual_slides)} diapositivas individuales")
            for i, slide in enumerate(individual_slides):
                logger.info(f"[DRY RUN] Diapositiva {i}: {slide['title']}")
            return True
        
        # Crear las diapositivas individuales
        created_slides = []
        for slide_data in individual_slides:
            success, result = self.create_individual_slide(topic_id, slide_data, slides_content)
            
            if success:
                created_slides.append(result)
            else:
                # Si falla una diapositiva, revertir las creadas
                logger.error(f"Fallo creando diapositiva, revirtiendo migración de {content_id}")
                self._cleanup_created_slides(created_slides)
                return False
        
        # Marcar el contenido original como migrado
        if self.mark_as_migrated(content_id):
            logger.info(f"Migración exitosa: {content_id} -> {len(created_slides)} diapositivas")
            self.stats['successfully_migrated'] += 1
            return True
        else:
            logger.error(f"Error marcando como migrado {content_id}")
            self._cleanup_created_slides(created_slides)
            return False
    
    def _cleanup_created_slides(self, slide_ids: List[str]):
        """
        Limpia diapositivas creadas en caso de error.
        
        Args:
            slide_ids: Lista de IDs de diapositivas a eliminar
        """
        for slide_id in slide_ids:
            try:
                self.collection.delete_one({"_id": ObjectId(slide_id)})
                logger.info(f"Eliminada diapositiva {slide_id} por rollback")
            except Exception as e:
                logger.error(f"Error eliminando diapositiva {slide_id}: {str(e)}")
    
    def run_migration(self, topic_id: Optional[str] = None, dry_run: bool = False) -> Dict:
        """
        Ejecuta la migración completa.
        
        Args:
            topic_id: ID específico del tema (opcional)
            dry_run: Si True, solo simula la migración
            
        Returns:
            Estadísticas de la migración
        """
        logger.info(f"Iniciando migración de slides {'(DRY RUN)' if dry_run else ''}")
        
        # Encontrar contenidos legacy
        legacy_slides = self.find_legacy_slides_content(topic_id)
        
        if not legacy_slides:
            logger.info("No se encontraron contenidos tipo 'slides' para migrar")
            return self.stats
        
        # Migrar cada contenido
        for slides_content in legacy_slides:
            try:
                success = self.migrate_slides_content(slides_content, dry_run)
                if not success:
                    self.stats['failed_migrations'] += 1
            except Exception as e:
                logger.error(f"Error migrando {slides_content['_id']}: {str(e)}")
                self.stats['failed_migrations'] += 1
                self.stats['errors'].append(f"Migration error {slides_content['_id']}: {str(e)}")
        
        # Mostrar estadísticas finales
        logger.info("=== ESTADÍSTICAS DE MIGRACIÓN ===")
        logger.info(f"Total contenidos encontrados: {self.stats['total_slides_found']}")
        logger.info(f"Migraciones exitosas: {self.stats['successfully_migrated']}")
        logger.info(f"Migraciones fallidas: {self.stats['failed_migrations']}")
        logger.info(f"Diapositivas individuales creadas: {self.stats['individual_slides_created']}")
        
        if self.stats['errors']:
            logger.warning(f"Errores encontrados: {len(self.stats['errors'])}")
            for error in self.stats['errors']:
                logger.warning(f"  - {error}")
        
        return self.stats

def main():
    """Función principal del script"""
    parser = argparse.ArgumentParser(
        description='Migra contenidos tipo "slides" a múltiples "slide" individuales'
    )
    parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='Simula la migración sin hacer cambios reales'
    )
    parser.add_argument(
        '--topic-id', 
        type=str, 
        help='ID específico del tema a migrar (opcional)'
    )
    parser.add_argument(
        '--verbose', 
        action='store_true', 
        help='Mostrar información detallada'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Conectar a la base de datos
        db = get_database()
        
        # Crear servicio de migración
        migration_service = SlideMigrationService(db)
        
        # Ejecutar migración
        stats = migration_service.run_migration(
            topic_id=args.topic_id,
            dry_run=args.dry_run
        )
        
        # Determinar código de salida
        if stats['failed_migrations'] > 0:
            logger.error("La migración completó con errores")
            sys.exit(1)
        else:
            logger.info("Migración completada exitosamente")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Error fatal en la migración: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()