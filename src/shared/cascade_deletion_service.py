from datetime import datetime
from bson import ObjectId
from typing import List, Dict, Optional, Set
import logging
from pymongo import MongoClient
from src.shared.database import get_db

class CascadeDeletionService:
    """
    Servicio para manejar eliminación en cascada de entidades relacionadas.
    Previene datos huérfanos y mantiene la integridad referencial.
    """
    
    def __init__(self):
        self.db = get_db()
        self.logger = logging.getLogger(__name__)
        
        # Definir relaciones de dependencia
        self.dependencies = {
            # StudyPlan dependencies
            'study_plans': {
                'modules': 'study_plan_id',
                'study_plan_assignments': 'study_plan_id',
                'virtual_modules': 'study_plan_id'
            },
            
            # Module dependencies
            'modules': {
                'topics': 'module_id',
                'virtual_modules': 'module_id',
                'virtual_generation_tasks': 'module_id'
            },
            
            # Topic dependencies
            'topics': {
                'topic_contents': 'topic_id',
                'virtual_topics': 'topic_id',
                'evaluations': 'topic_ids',  # Array field
                'content_results': 'topic_id'  # Resultados ligados al tema (incluye virtual)
            },
            
            # VirtualModule dependencies
            'virtual_modules': {
                'virtual_topics': 'virtual_module_id',
                'virtual_generation_tasks': 'module_id'  # Same module_id
            },
            
            # VirtualTopic dependencies
            'virtual_topics': {
                'virtual_topic_contents': 'virtual_topic_id',
                'parallel_content_generation_tasks': 'virtual_topic_id'
            },
            
            # TopicContent dependencies
            'topic_contents': {
                'virtual_topic_contents': 'content_id',
                'content_results': 'content_id',
                'template_usage': 'content_id'
            },

            # VirtualTopicContent dependencies
            'virtual_topic_contents': {
                'content_results': 'virtual_content_id'
            },
            
            # Evaluation dependencies
            'evaluations': {
                'evaluation_submissions': 'evaluation_id',
                'evaluation_resources': 'evaluation_id',
                'content_results': 'evaluation_id'
            },
            
            # Student dependencies
            'students': {
                'virtual_modules': 'student_id',
                'virtual_topics': 'student_id',
                'virtual_topic_contents': 'student_id',
                'content_results': 'student_id',
                'evaluation_submissions': 'student_id',
                'student_performance': 'student_id'
            },
            
            # Educational structure dependencies
            'educational_programs': {
                'levels': 'program_id'
            },
            'levels': {
                'sections': 'level_id',
                'subjects': 'level_id',
                'academic_periods': 'level_id',
                'classes': 'level_id'
            },
            'sections': {
                'classes': 'section_id'
            },
            'subjects': {
                'classes': 'subject_id'
            },
            'academic_periods': {
                'classes': 'academic_period_id'
            },

            # Class dependencies
            'classes': {
                'class_members': 'class_id',
                'subperiods': 'class_id',
                'study_plan_assignments': 'class_id',
                'student_individual_content': 'class_id',
                'student_performance': 'class_id',
                'class_statistics': 'class_id',
                'evaluation_analytics': 'class_id'
            }
        }
    
    def delete_with_cascade(self, collection_name: str, entity_id: str, dry_run: bool = False) -> Dict:
        """
        Elimina una entidad y todas sus dependencias en cascada.
        
        Args:
            collection_name: Nombre de la colección
            entity_id: ID de la entidad a eliminar
            dry_run: Si es True, solo simula la eliminación sin ejecutarla
            
        Returns:
            Dict con el resumen de la operación
        """
        try:
            entity_id = ObjectId(entity_id)
            deletion_plan = self._build_deletion_plan(collection_name, entity_id)
            
            if dry_run:
                return {
                    'success': True,
                    'dry_run': True,
                    'deletion_plan': deletion_plan,
                    'total_entities': sum(len(entities) for entities in deletion_plan.values())
                }
            
            # Ejecutar eliminación en orden inverso de dependencias
            deleted_counts = {}
            total_deleted = 0
            
            # Ordenar colecciones por nivel de dependencia (hojas primero)
            ordered_collections = self._get_deletion_order(deletion_plan.keys())
            
            for collection in ordered_collections:
                if collection in deletion_plan and deletion_plan[collection]:
                    count = self._delete_entities(collection, deletion_plan[collection])
                    deleted_counts[collection] = count
                    total_deleted += count
                    
                    self.logger.info(f"Deleted {count} entities from {collection}")
            
            return {
                'success': True,
                'dry_run': False,
                'deleted_counts': deleted_counts,
                'total_deleted': total_deleted,
                'deletion_plan': deletion_plan
            }
            
        except Exception as e:
            self.logger.error(f"Error in cascade deletion: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_deletion_plan(self, collection_name: str, entity_id: ObjectId, 
                           visited: Optional[Set] = None) -> Dict[str, List[ObjectId]]:
        """
        Construye un plan de eliminación recursivo.
        """
        if visited is None:
            visited = set()
        
        # Evitar ciclos infinitos
        key = f"{collection_name}:{entity_id}"
        if key in visited:
            return {}
        visited.add(key)
        
        deletion_plan = {collection_name: [entity_id]}
        
        # Buscar dependencias
        if collection_name in self.dependencies:
            for dependent_collection, field_name in self.dependencies[collection_name].items():
                dependent_ids = self._find_dependent_entities(dependent_collection, field_name, entity_id)
                
                if dependent_ids:
                    # Agregar a plan actual
                    if dependent_collection not in deletion_plan:
                        deletion_plan[dependent_collection] = []
                    deletion_plan[dependent_collection].extend(dependent_ids)
                    
                    # Recursión para dependencias de dependencias
                    for dep_id in dependent_ids:
                        sub_plan = self._build_deletion_plan(dependent_collection, dep_id, visited)
                        for sub_collection, sub_ids in sub_plan.items():
                            if sub_collection not in deletion_plan:
                                deletion_plan[sub_collection] = []
                            deletion_plan[sub_collection].extend(sub_ids)
        
        # Remover duplicados
        for collection in deletion_plan:
            deletion_plan[collection] = list(set(deletion_plan[collection]))
        
        return deletion_plan
    
    def _find_dependent_entities(self, collection: str, field_name: str, parent_id: ObjectId) -> List[ObjectId]:
        """
        Encuentra entidades dependientes en una colección.
        """
        try:
            # Algunas colecciones pueden almacenar referencias como ObjectId o como string
            search_values = [parent_id]
            if isinstance(parent_id, ObjectId):
                search_values.append(str(parent_id))

            if field_name.endswith('_ids'):  # Array field
                query = {field_name: {"$in": search_values}}
            else:
                query = {field_name: {"$in": search_values}} if len(search_values) > 1 else {field_name: parent_id}

            cursor = self.db[collection].find(query, {'_id': 1})
            return [doc['_id'] for doc in cursor]
            
        except Exception as e:
            self.logger.warning(f"Error finding dependents in {collection}: {str(e)}")
            return []
    
    def _get_deletion_order(self, collections: List[str]) -> List[str]:
        """
        Ordena las colecciones para eliminación (dependientes primero).
        """
        # Orden básico: entidades más dependientes primero
        priority_order = [
            'content_results',
            'virtual_topic_contents',
            'parallel_content_generation_tasks',
            'virtual_topics',
            'virtual_generation_tasks',
            'virtual_modules',
            'evaluation_submissions',
            'evaluation_resources',
            'evaluation_analytics',
            'student_individual_content',
            'class_members',
            'subperiods',
            'student_performance',
            'class_statistics',
            'topic_contents',
            'evaluations',
            'topics',
            'modules',
            'study_plan_assignments',
            'classes',
            'sections',
            'subjects',
            'academic_periods',
            'levels',
            'educational_programs',
            'study_plans',
            'students'
        ]
        
        # Filtrar solo las colecciones que están en el plan
        ordered = [col for col in priority_order if col in collections]
        
        # Agregar cualquier colección no listada al final
        remaining = [col for col in collections if col not in ordered]
        ordered.extend(remaining)
        
        return ordered
    
    def _delete_entities(self, collection: str, entity_ids: List[ObjectId]) -> int:
        """
        Elimina entidades de una colección.
        """
        if not entity_ids:
            return 0
        
        try:
            result = self.db[collection].delete_many({'_id': {'$in': entity_ids}})
            return result.deleted_count
        except Exception as e:
            self.logger.error(f"Error deleting from {collection}: {str(e)}")
            return 0
    
    def cleanup_orphaned_data(self, collection_name: str, dry_run: bool = False) -> Dict:
        """
        Limpia datos huérfanos en una colección específica.
        """
        try:
            orphaned_ids = self._find_orphaned_entities(collection_name)
            
            if dry_run:
                return {
                    'success': True,
                    'dry_run': True,
                    'collection': collection_name,
                    'orphaned_count': len(orphaned_ids),
                    'orphaned_ids': [str(oid) for oid in orphaned_ids]
                }
            
            if orphaned_ids:
                deleted_count = self._delete_entities(collection_name, orphaned_ids)
                self.logger.info(f"Cleaned up {deleted_count} orphaned entities from {collection_name}")
                
                return {
                    'success': True,
                    'dry_run': False,
                    'collection': collection_name,
                    'deleted_count': deleted_count
                }
            else:
                return {
                    'success': True,
                    'dry_run': False,
                    'collection': collection_name,
                    'deleted_count': 0,
                    'message': 'No orphaned data found'
                }
                
        except Exception as e:
            self.logger.error(f"Error cleaning orphaned data in {collection_name}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _find_orphaned_entities(self, collection_name: str) -> List[ObjectId]:
        """
        Encuentra entidades huérfanas en una colección.
        """
        orphaned_ids = []
        
        # Buscar en dependencias inversas
        for parent_collection, dependencies in self.dependencies.items():
            if collection_name in dependencies:
                field_name = dependencies[collection_name]
                
                # Obtener todos los IDs de la colección hijo
                child_docs = list(self.db[collection_name].find({}, {'_id': 1, field_name: 1}))
                
                for child_doc in child_docs:
                    parent_id = child_doc.get(field_name)
                    if parent_id:
                        # Verificar si el padre existe
                        if field_name.endswith('_ids'):  # Array field
                            # Para campos array, verificar si el ID está en algún array
                            parent_exists = self.db[parent_collection].count_documents(
                                {field_name: parent_id}
                            ) > 0
                        else:
                            parent_exists = self.db[parent_collection].count_documents(
                                {'_id': parent_id}
                            ) > 0
                        
                        if not parent_exists:
                            orphaned_ids.append(child_doc['_id'])
        
        return orphaned_ids
    
    def get_dependency_report(self, collection_name: str, entity_id: str) -> Dict:
        """
        Genera un reporte de dependencias para una entidad.
        """
        try:
            entity_id = ObjectId(entity_id)
            deletion_plan = self._build_deletion_plan(collection_name, entity_id)
            
            report = {
                'entity': {
                    'collection': collection_name,
                    'id': str(entity_id)
                },
                'dependencies': {},
                'total_affected': 0
            }
            
            for collection, ids in deletion_plan.items():
                if collection != collection_name:  # Excluir la entidad principal
                    report['dependencies'][collection] = {
                        'count': len(ids),
                        'ids': [str(oid) for oid in ids]
                    }
                    report['total_affected'] += len(ids)
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating dependency report: {str(e)}")
            return {
                'error': str(e)
            }
