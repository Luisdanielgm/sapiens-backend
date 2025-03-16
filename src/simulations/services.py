from typing import Tuple, List, Dict, Optional
from bson import ObjectId
from datetime import datetime

from src.shared.database import get_db
from src.shared.constants import STATUS
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
import logging
from .models import Simulation, VirtualSimulation, SimulationResult

class SimulationService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="simulations")

    def check_topic_exists(self, topic_id: str) -> bool:
        """
        Verifica si un tema existe.
        
        Args:
            topic_id: ID del tema a verificar
            
        Returns:
            bool: True si el tema existe, False en caso contrario
        """
        try:
            topic = get_db().topics.find_one({"_id": ObjectId(topic_id)})
            return topic is not None
        except Exception:
            return False
            
    def check_simulation_exists(self, simulation_id: str) -> bool:
        """
        Verifica si una simulación existe.
        
        Args:
            simulation_id: ID de la simulación a verificar
            
        Returns:
            bool: True si la simulación existe, False en caso contrario
        """
        try:
            simulation = self.collection.find_one({"_id": ObjectId(simulation_id)})
            return simulation is not None
        except Exception:
            return False

    def create_simulation(self, simulation_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que el tema existe
            if not self.check_topic_exists(simulation_data['topic_id']):
                return False, "Tema no encontrado"

            simulation = Simulation(**simulation_data)
            result = self.collection.insert_one(simulation.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_simulation(self, simulation_id: str) -> Optional[Dict]:
        try:
            simulation = self.collection.find_one({"_id": ObjectId(simulation_id)})
            if not simulation:
                return None
            
            # Convertir ObjectId a string
            simulation["_id"] = str(simulation["_id"])
            simulation["topic_id"] = str(simulation["topic_id"])
            if simulation.get("creator_id"):
                simulation["creator_id"] = str(simulation["creator_id"])
            
            return simulation
        except Exception as e:
            logging.error(f"Error al obtener simulación: {str(e)}")
            return None

    def update_simulation(self, simulation_id: str, update_data: dict) -> Tuple[bool, str]:
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(simulation_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Simulación actualizada con éxito"
            return False, "No se realizaron cambios o simulación no encontrada"
        except Exception as e:
            logging.error(f"Error al actualizar simulación: {str(e)}")
            return False, str(e)

    def delete_simulation(self, simulation_id: str) -> Tuple[bool, str]:
        try:
            # Primero, obtener todas las simulaciones virtuales que dependen de esta simulación
            virtual_simulations = list(get_db().virtual_simulations.find(
                {"simulation_id": ObjectId(simulation_id)}
            ))
            
            # Eliminar todos los resultados de simulaciones virtuales
            v_sim_ids = [v_sim["_id"] for v_sim in virtual_simulations]
            deleted_results = 0
            
            if v_sim_ids:
                results_deletion = get_db().simulation_results.delete_many(
                    {"virtual_simulation_id": {"$in": v_sim_ids}}
                )
                deleted_results = results_deletion.deleted_count
            
            # Eliminar todas las simulaciones virtuales
            v_sims_deletion = get_db().virtual_simulations.delete_many(
                {"simulation_id": ObjectId(simulation_id)}
            )
            deleted_v_sims = v_sims_deletion.deleted_count
            
            # Ahora eliminar la simulación
            result = self.collection.delete_one({"_id": ObjectId(simulation_id)})
            
            if result.deleted_count > 0:
                return True, f"Simulación eliminada con éxito: {deleted_v_sims} simulaciones virtuales y {deleted_results} resultados eliminados"
            return False, "Simulación no encontrada"
        except Exception as e:
            logging.error(f"Error al eliminar simulación: {str(e)}")
            return False, str(e)

    def get_simulations_by_topic(self, topic_id: str) -> List[Dict]:
        try:
            simulations = list(self.collection.find({"topic_id": ObjectId(topic_id)}))
            # Convertir ObjectId a string
            for simulation in simulations:
                simulation["_id"] = str(simulation["_id"])
                simulation["topic_id"] = str(simulation["topic_id"])
                if simulation.get("creator_id"):
                    simulation["creator_id"] = str(simulation["creator_id"])
            return simulations
        except Exception as e:
            logging.error(f"Error al obtener simulaciones: {str(e)}")
            return []

    def toggle_evaluation_mode(self, simulation_id: str) -> Tuple[bool, str]:
        try:
            # Obtener el estado actual
            simulation = self.collection.find_one({"_id": ObjectId(simulation_id)})
            if not simulation:
                return False, "Simulación no encontrada"
            
            current_status = simulation.get("is_evaluation", False)
            
            # Cambiar al estado opuesto
            result = self.collection.update_one(
                {"_id": ObjectId(simulation_id)},
                {"$set": {"is_evaluation": not current_status}}
            )
            
            if result.modified_count > 0:
                new_status = "evaluación" if not current_status else "recurso de aprendizaje"
                return True, f"Simulación actualizada como {new_status}"
            return False, "No se realizaron cambios"
        except Exception as e:
            logging.error(f"Error al cambiar modo de evaluación: {str(e)}")
            return False, str(e)

    def delete_all_topic_simulations(self, topic_id: str) -> Tuple[int, int, int]:
        """
        Elimina todas las simulaciones asociadas a un tema y sus dependencias.
        Retorna la cantidad de simulaciones, simulaciones virtuales y resultados eliminados.
        """
        try:
            # Obtener todas las simulaciones asociadas al tema
            simulations = list(self.collection.find({"topic_id": ObjectId(topic_id)}))
            sim_ids = [sim["_id"] for sim in simulations]
            
            # Obtener todas las simulaciones virtuales asociadas
            v_sims = []
            v_sim_ids = []
            if sim_ids:
                v_sims = list(get_db().virtual_simulations.find({"simulation_id": {"$in": sim_ids}}))
                v_sim_ids = [v_sim["_id"] for v_sim in v_sims]
            
            # Eliminar resultados de simulaciones virtuales
            results_deleted = 0
            if v_sim_ids:
                results = get_db().simulation_results.delete_many({"virtual_simulation_id": {"$in": v_sim_ids}})
                results_deleted = results.deleted_count
                
            # Eliminar simulaciones virtuales
            v_sims_deleted = 0
            if sim_ids:
                v_sims_result = get_db().virtual_simulations.delete_many({"simulation_id": {"$in": sim_ids}})
                v_sims_deleted = v_sims_result.deleted_count
                
            # Eliminar simulaciones
            sims_deleted = 0
            if sim_ids:
                sims_result = self.collection.delete_many({"_id": {"$in": sim_ids}})
                sims_deleted = sims_result.deleted_count
                
            return sims_deleted, v_sims_deleted, results_deleted
        except Exception as e:
            logging.error(f"Error al eliminar simulaciones del tema: {str(e)}")
            return 0, 0, 0

class VirtualSimulationService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="virtual_simulations")

    def check_simulation_exists(self, simulation_id: str) -> bool:
        """
        Verifica si una simulación existe.
        
        Args:
            simulation_id: ID de la simulación a verificar
            
        Returns:
            bool: True si la simulación existe, False en caso contrario
        """
        try:
            simulation = get_db().simulations.find_one({"_id": ObjectId(simulation_id)})
            return simulation is not None
        except Exception:
            return False
            
    def check_virtual_simulation_exists(self, virtual_simulation_id: str) -> bool:
        """
        Verifica si una simulación virtual existe.
        
        Args:
            virtual_simulation_id: ID de la simulación virtual a verificar
            
        Returns:
            bool: True si la simulación virtual existe, False en caso contrario
        """
        try:
            simulation = self.collection.find_one({"_id": ObjectId(virtual_simulation_id)})
            return simulation is not None
        except Exception:
            return False

    def create_virtual_simulation(self, virtual_simulation_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que la simulación base existe
            simulation = get_db().simulations.find_one(
                {"_id": ObjectId(virtual_simulation_data['simulation_id'])}
            )
            if not simulation:
                return False, "Simulación base no encontrada"

            # Verificar que el tema virtual existe
            virtual_topic = get_db().virtual_topics.find_one(
                {"_id": ObjectId(virtual_simulation_data['virtual_topic_id'])}
            )
            if not virtual_topic:
                return False, "Tema virtual no encontrado"

            # Verificar que el estudiante existe
            student = get_db().users.find_one(
                {"_id": ObjectId(virtual_simulation_data['student_id']), "role": "student"}
            )
            if not student:
                return False, "Estudiante no encontrado"

            # Si no se proporciona código personalizado, usar el de la simulación base
            if 'code' not in virtual_simulation_data or not virtual_simulation_data['code']:
                virtual_simulation_data['code'] = simulation.get('code', '')

            virtual_simulation = VirtualSimulation(**virtual_simulation_data)
            result = self.collection.insert_one(virtual_simulation.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            logging.error(f"Error al crear simulación virtual: {str(e)}")
            return False, str(e)

    def get_virtual_simulation(self, virtual_simulation_id: str) -> Optional[Dict]:
        try:
            virtual_simulation = self.collection.find_one({"_id": ObjectId(virtual_simulation_id)})
            if not virtual_simulation:
                return None
            
            # Convertir ObjectId a string
            virtual_simulation["_id"] = str(virtual_simulation["_id"])
            virtual_simulation["simulation_id"] = str(virtual_simulation["simulation_id"])
            virtual_simulation["virtual_topic_id"] = str(virtual_simulation["virtual_topic_id"])
            virtual_simulation["student_id"] = str(virtual_simulation["student_id"])
            
            return virtual_simulation
        except Exception as e:
            logging.error(f"Error al obtener simulación virtual: {str(e)}")
            return None

    def update_virtual_simulation(self, virtual_simulation_id: str, update_data: dict) -> Tuple[bool, str]:
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(virtual_simulation_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Simulación virtual actualizada con éxito"
            return False, "No se realizaron cambios o simulación virtual no encontrada"
        except Exception as e:
            logging.error(f"Error al actualizar simulación virtual: {str(e)}")
            return False, str(e)

    def get_student_simulations(self, student_id: str) -> List[Dict]:
        try:
            virtual_simulations = list(self.collection.find({"student_id": ObjectId(student_id)}))
            
            # Agregar información de la simulación base
            for virtual_simulation in virtual_simulations:
                simulation = get_db().simulations.find_one({"_id": virtual_simulation["simulation_id"]})
                if simulation:
                    virtual_simulation["simulation_details"] = {
                        "_id": str(simulation["_id"]),
                        "title": simulation["title"],
                        "description": simulation["description"],
                        "simulation_type": simulation["simulation_type"],
                        "complexity": simulation["complexity"],
                        "is_evaluation": simulation.get("is_evaluation", False)
                    }
                
                # Convertir ObjectId a string
                virtual_simulation["_id"] = str(virtual_simulation["_id"])
                virtual_simulation["simulation_id"] = str(virtual_simulation["simulation_id"])
                virtual_simulation["virtual_topic_id"] = str(virtual_simulation["virtual_topic_id"])
                virtual_simulation["student_id"] = str(virtual_simulation["student_id"])
            
            return virtual_simulations
        except Exception as e:
            logging.error(f"Error al obtener simulaciones del estudiante: {str(e)}")
            return []

    def update_simulation_progress(self, virtual_simulation_id: str, completion_status: str, time_spent: int, interactions: int) -> Tuple[bool, str]:
        try:
            # Obtener registro actual para actualizar incrementalmente
            virtual_simulation = self.collection.find_one({"_id": ObjectId(virtual_simulation_id)})
            if not virtual_simulation:
                return False, "Simulación virtual no encontrada"
                
            current_time = virtual_simulation.get("time_spent", 0)
            current_interactions = virtual_simulation.get("interactions", 0)
            
            update_data = {
                "last_used": datetime.now(),
                "completion_status": completion_status,
                "time_spent": current_time + time_spent,
                "interactions": current_interactions + interactions
            }
            
            result = self.collection.update_one(
                {"_id": ObjectId(virtual_simulation_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Progreso de la simulación actualizado con éxito"
            return False, "No se realizaron cambios"
        except Exception as e:
            logging.error(f"Error al actualizar progreso de la simulación: {str(e)}")
            return False, str(e)

class SimulationResultService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="simulation_results")
        
    def check_virtual_simulation_exists(self, virtual_simulation_id: str) -> bool:
        """
        Verifica si una simulación virtual existe.
        
        Args:
            virtual_simulation_id: ID de la simulación virtual a verificar
            
        Returns:
            bool: True si la simulación virtual existe, False en caso contrario
        """
        try:
            simulation = get_db().virtual_simulations.find_one({"_id": ObjectId(virtual_simulation_id)})
            return simulation is not None
        except Exception:
            return False
            
    def check_result_exists(self, result_id: str) -> bool:
        """
        Verifica si un resultado existe.
        
        Args:
            result_id: ID del resultado a verificar
            
        Returns:
            bool: True si el resultado existe, False en caso contrario
        """
        try:
            result = self.collection.find_one({"_id": ObjectId(result_id)})
            return result is not None
        except Exception:
            return False
            
    def save_result(self, result_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que la simulación virtual existe
            virtual_simulation = get_db().virtual_simulations.find_one(
                {"_id": ObjectId(result_data['virtual_simulation_id'])}
            )
            if not virtual_simulation:
                return False, "Simulación virtual no encontrada"
                
            simulation_result = SimulationResult(**result_data)
            result = self.collection.insert_one(simulation_result.to_dict())
            
            # Actualizar el estado de la simulación virtual
            get_db().virtual_simulations.update_one(
                {"_id": ObjectId(result_data['virtual_simulation_id'])},
                {"$set": {"completion_status": "completed"}}
            )
            
            return True, str(result.inserted_id)
        except Exception as e:
            print(f"Error al guardar resultado de simulación: {str(e)}")
            return False, str(e)
            
    def get_student_results(self, student_id: str) -> List[Dict]:
        try:
            results = list(self.collection.find({"student_id": ObjectId(student_id)}))
            
            # Convertir ObjectId a string
            for result in results:
                result["_id"] = str(result["_id"])
                result["virtual_simulation_id"] = str(result["virtual_simulation_id"])
                result["student_id"] = str(result["student_id"])
                
                # Agregar detalles de la simulación
                virtual_sim = get_db().virtual_simulations.find_one({"_id": ObjectId(result["virtual_simulation_id"])})
                if virtual_sim:
                    sim = get_db().simulations.find_one({"_id": virtual_sim["simulation_id"]})
                    if sim:
                        result["simulation_info"] = {
                            "title": sim["title"],
                            "type": sim["simulation_type"]
                        }
            
            return results
        except Exception as e:
            print(f"Error al obtener resultados del estudiante: {str(e)}")
            return []
            
    def get_result(self, result_id: str) -> Optional[Dict]:
        try:
            result = self.collection.find_one({"_id": ObjectId(result_id)})
            if not result:
                return None
                
            # Convertir ObjectId a string
            result["_id"] = str(result["_id"])
            result["virtual_simulation_id"] = str(result["virtual_simulation_id"])
            result["student_id"] = str(result["student_id"])
            
            return result
        except Exception as e:
            print(f"Error al obtener resultado: {str(e)}")
            return None
