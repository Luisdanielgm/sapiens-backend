from typing import Tuple, List, Dict, Optional, Union
from bson import ObjectId
from datetime import datetime
import logging
import json
import requests
import os
import io
import re
import base64
from urllib.parse import urlparse
import PyPDF2
from PIL import Image
import pytesseract
import numpy as np
import pandas as pd
from pdf2image import convert_from_path

from src.shared.database import get_db
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from src.shared.utils import ensure_json_serializable
from .models import ProcessedPDF, WebSearchResult, DiagramTemplate, GeneratedDiagram, SearchProvider

class PDFProcessingService(VerificationBaseService):
    """
    Servicio para procesamiento de archivos PDF.
    """
    def __init__(self):
        super().__init__(collection_name="processed_pdfs")
        
        # Determinar si estamos en un entorno serverless
        self.is_serverless = os.environ.get("VERCEL") == "1" or os.environ.get("SERVERLESS") == "1"
        
        # Si estamos en un entorno local, intentar crear el directorio
        # En entornos serverless, usaremos un enfoque basado en memoria
        if not self.is_serverless:
            # Directorio para almacenar imágenes extraídas en entornos locales
            self.image_extract_dir = os.path.join(os.environ.get("UPLOAD_FOLDER", "uploads"), "extracted_images")
            try:
                os.makedirs(self.image_extract_dir, exist_ok=True)
                logging.info(f"Directorio creado: {self.image_extract_dir}")
            except Exception as e:
                logging.warning(f"No se pudo crear el directorio: {str(e)}. Usando almacenamiento en memoria.")
                self.is_serverless = True
        
        # En entornos serverless, no usamos el sistema de archivos
        if self.is_serverless:
            self.image_extract_dir = None
            logging.info("Ejecutando en modo serverless: usando almacenamiento en memoria para archivos temporales")
        
    def process_pdf(self, file_path: str, title: str, original_filename: str, creator_id: str = None) -> Tuple[bool, str]:
        """
        Procesa un archivo PDF para extraer su contenido.
        
        Args:
            file_path: Ruta al archivo PDF
            title: Título para el PDF procesado
            original_filename: Nombre original del archivo
            creator_id: ID del usuario que subió el archivo
            
        Returns:
            Tupla con estado y mensaje/ID
        """
        try:
            # Verificar que el archivo existe
            if not os.path.exists(file_path):
                return False, "El archivo no existe"
            
            # Verificar que el archivo sea accesible
            try:
                with open(file_path, 'rb') as test_file:
                    pass
            except Exception as e:
                logging.error(f"Error al acceder al archivo: {str(e)}")
                return False, f"No se puede acceder al archivo: {str(e)}"
                
            # Obtener tamaño del archivo
            file_size = os.path.getsize(file_path)
            
            # Extraer texto usando PyPDF2
            extracted_text = self._extract_text_from_pdf(file_path)
            
            # Extraer imágenes del PDF
            extracted_images = self._extract_images_from_pdf(file_path, os.path.basename(file_path))
            
            # Extraer tablas del PDF (versión básica)
            extracted_tables = self._extract_tables_from_pdf(file_path)
            
            # Extraer metadatos
            metadata = self._extract_pdf_metadata(file_path)
            
            # En entornos serverless, no guardamos la ruta del archivo
            if self.is_serverless:
                stored_file_path = None
            else:
                stored_file_path = file_path
            
            # Crear objeto de PDF procesado
            pdf_dict = {
                "title": title,
                "file_path": stored_file_path,
                "original_filename": original_filename,
                "file_size": file_size,
                "extracted_text": extracted_text,
                "extracted_images": extracted_images,
                "extracted_tables": extracted_tables,
                "metadata": metadata,
                "creator_id": ObjectId(creator_id) if creator_id else None,
                "tags": self._generate_tags_from_content(extracted_text),
                "processed_at": datetime.now(),
                "status": "active"
            }
            
            # Guardar en la base de datos
            result = self.collection.insert_one(pdf_dict)
            
            return True, str(result.inserted_id)
        except Exception as e:
            logging.error(f"Error al procesar PDF: {str(e)}")
            return False, str(e)
    
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extrae el texto de un archivo PDF.
        
        Args:
            file_path: Ruta al archivo PDF
            
        Returns:
            Texto extraído del PDF
        """
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Obtener número de páginas
                num_pages = len(pdf_reader.pages)
                
                # Extraer texto de cada página
                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n\n"
                    
            return text
        except Exception as e:
            logging.error(f"Error al extraer texto del PDF: {str(e)}")
            return ""
    
    def _extract_images_from_pdf(self, file_path: str, base_filename: str) -> List[Dict]:
        """
        Extrae imágenes de un archivo PDF.
        
        Args:
            file_path: Ruta al archivo PDF
            base_filename: Nombre base para guardar las imágenes
            
        Returns:
            Lista de diccionarios con información de las imágenes extraídas
        """
        try:
            images = []
            # Convertir páginas del PDF a imágenes
            pdf_pages = convert_from_path(file_path, 300)
            
            for i, page in enumerate(pdf_pages):
                # Generar nombre para la imagen
                image_filename = f"{base_filename.split('.')[0]}_page_{i+1}.jpg"
                
                # Procesamiento de la imagen según el entorno
                if self.is_serverless:
                    # En serverless: convertir a base64 y almacenar en memoria
                    img_byte_arr = io.BytesIO()
                    page.save(img_byte_arr, format='JPEG')
                    img_byte_arr.seek(0)
                    
                    # Convertir a base64 para almacenamiento
                    base64_encoded = base64.b64encode(img_byte_arr.read()).decode('utf-8')
                    image_path = f"data:image/jpeg;base64,{base64_encoded}"
                    
                    # Analizar texto en la imagen usando OCR
                    ocr_text = pytesseract.image_to_string(page)
                    
                    # Añadir información de la imagen
                    images.append({
                        "filename": image_filename,
                        "path": None,  # No hay ruta en el sistema de archivos
                        "base64_data": image_path,
                        "page_number": i + 1,
                        "width": page.width,
                        "height": page.height,
                        "ocr_text": ocr_text,
                        "type": "page_image"
                    })
                else:
                    # En entorno local: guardar en el sistema de archivos
                    image_path = os.path.join(self.image_extract_dir, image_filename)
                    page.save(image_path, "JPEG")
                    
                    # Analizar texto en la imagen usando OCR
                    ocr_text = pytesseract.image_to_string(page)
                    
                    # Añadir información de la imagen
                    images.append({
                        "filename": image_filename,
                        "path": image_path,
                        "page_number": i + 1,
                        "width": page.width,
                        "height": page.height,
                        "ocr_text": ocr_text,
                        "type": "page_image"
                    })
                
            return images
        except Exception as e:
            logging.error(f"Error al extraer imágenes del PDF: {str(e)}")
            return []
    
    def _extract_tables_from_pdf(self, file_path: str) -> List[Dict]:
        """
        Extrae tablas de un archivo PDF.
        NOTA: Esta implementación es básica y puede no detectar todas las tablas.
        Para una implementación más robusta, considerar el uso de bibliotecas como 
        tabula-py o camelot-py.
        
        Args:
            file_path: Ruta al archivo PDF
            
        Returns:
            Lista de diccionarios con tablas extraídas
        """
        try:
            tables = []
            
            # En entornos serverless, usamos un enfoque más ligero
            if self.is_serverless:
                # Extraer texto usando PyPDF2 (más ligero que convertir a imágenes)
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    
                    # Obtener número de páginas
                    num_pages = len(pdf_reader.pages)
                    
                    # Extraer tablas de cada página usando patrones de texto
                    for page_num in range(num_pages):
                        page = pdf_reader.pages[page_num]
                        text = page.extract_text()
                        lines = text.split('\n')
                        
                        # Buscar patrones que podrían indicar tablas
                        table_data = self._detect_tables_from_text(lines)
                        
                        if table_data:
                            tables.append({
                                "page_number": page_num + 1,
                                "data": table_data,
                                "rows": len(table_data),
                                "columns": len(table_data[0]) if table_data else 0
                            })
            else:
                # Método original para entornos locales
                # Convertir páginas del PDF a imágenes para procesamiento
                pdf_pages = convert_from_path(file_path, 300)
                
                for i, page in enumerate(pdf_pages):
                    # Método simple para detectar posibles tablas basado en patrones de texto
                    ocr_text = pytesseract.image_to_string(page)
                    lines = ocr_text.split('\n')
                    
                    # Buscar patrones que podrían indicar tablas (múltiples líneas con delimitadores consistentes)
                    table_data = self._detect_tables_from_text(lines)
                    
                    if table_data:
                        tables.append({
                            "page_number": i + 1,
                            "data": table_data,
                            "rows": len(table_data),
                            "columns": len(table_data[0]) if table_data else 0
                        })
                
            return tables
        except Exception as e:
            logging.error(f"Error al extraer tablas del PDF: {str(e)}")
            return []
    
    def _detect_tables_from_text(self, lines: List[str]) -> List[List[str]]:
        """
        Detecta tablas a partir de líneas de texto.
        Método simple basado en patrones consistentes de espaciado.
        
        Args:
            lines: Líneas de texto
            
        Returns:
            Lista de listas representando filas y columnas
        """
        potential_table_data = []
        in_table = False
        
        for line in lines:
            # Eliminar espacios extras
            clean_line = re.sub(r'\s+', ' ', line).strip()
            
            # Ignorar líneas vacías
            if not clean_line:
                continue
                
            # Detectar líneas con múltiples palabras separadas por espacios consistentes
            parts = clean_line.split(' ')
            if len(parts) >= 3:  # Asumimos que una tabla tiene al menos 3 columnas
                # Si encontramos una línea con estructura tabular, comenzamos a capturar
                in_table = True
                potential_table_data.append(parts)
            elif in_table and len(potential_table_data) > 0:
                # Si estábamos en una tabla y encontramos una línea que no parece tabular,
                # verificamos si tenemos suficientes filas para confirmar que es una tabla
                if len(potential_table_data) >= 3:  # Mínimo 3 filas para considerar una tabla
                    return potential_table_data
                else:
                    # Reiniciar si no hay suficientes filas
                    potential_table_data = []
                    in_table = False
        
        # Verificar si terminamos en medio de una tabla
        if in_table and len(potential_table_data) >= 3:
            return potential_table_data
            
        return []
    
    def _extract_pdf_metadata(self, file_path: str) -> Dict:
        """
        Extrae metadatos de un archivo PDF.
        
        Args:
            file_path: Ruta al archivo PDF
            
        Returns:
            Diccionario con metadatos
        """
        try:
            metadata = {}
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                info = pdf_reader.metadata
                
                # Convertir a diccionario serializable
                if info:
                    for key in info:
                        value = info[key]
                        # Asegurar que el valor es serializable
                        metadata[key] = str(value)
                
                # Añadir información adicional
                metadata["page_count"] = len(pdf_reader.pages)
                
            return metadata
        except Exception as e:
            logging.error(f"Error al extraer metadatos del PDF: {str(e)}")
            return {}
    
    def _generate_tags_from_content(self, content: str) -> List[str]:
        """
        Genera etiquetas automáticamente basadas en el contenido del PDF.
        
        Args:
            content: Texto extraído del PDF
            
        Returns:
            Lista de etiquetas generadas
        """
        try:
            # Lista básica de palabras a ignorar (stop words)
            stop_words = set(['el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'a', 
                              'de', 'del', 'en', 'con', 'por', 'para', 'es', 'son', 'al', 'e', 'u'])
            
            # Limpiar y dividir el texto
            words = re.findall(r'\b[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}\b', content.lower())
            
            # Filtrar stop words y contar frecuencia
            word_counts = {}
            for word in words:
                if word not in stop_words:
                    word_counts[word] = word_counts.get(word, 0) + 1
            
            # Seleccionar las 10 palabras más frecuentes como etiquetas
            sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
            tags = [word for word, count in sorted_words[:10]]
            
            return tags
        except Exception as e:
            logging.error(f"Error al generar etiquetas: {str(e)}")
            return []
            
    def get_processed_pdf(self, pdf_id: str) -> Optional[Dict]:
        """
        Obtiene un PDF procesado por su ID.
        
        Args:
            pdf_id: ID del PDF procesado
            
        Returns:
            Diccionario con datos del PDF o None si no existe
        """
        try:
            pdf = self.collection.find_one({"_id": ObjectId(pdf_id)})
            if not pdf:
                return None
                
            # Actualizar contador de accesos y timestamp
            self.collection.update_one(
                {"_id": ObjectId(pdf_id)},
                {
                    "$inc": {"access_count": 1},
                    "$set": {"last_accessed": datetime.now()}
                }
            )
            
            # Convertir ObjectId a str para serialización
            pdf = ensure_json_serializable(pdf)
                
            return pdf
        except Exception as e:
            logging.error(f"Error al obtener PDF procesado: {str(e)}")
            return None
            
    def extract_pdf_for_topic(self, pdf_id: str, topic_id: str) -> Tuple[bool, Optional[str]]:
        """
        Extrae contenido relevante de un PDF para un tema específico.
        
        Args:
            pdf_id: ID del PDF procesado
            topic_id: ID del tema
            
        Returns:
            Tupla con estado y contenido extraído
        """
        try:
            # Obtener el PDF procesado
            pdf = self.get_processed_pdf(pdf_id)
            if not pdf:
                return False, None
                
            # Obtener el tema
            topic = get_db().topics.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                return False, None
            
            # Convertir a formato serializable
            topic = ensure_json_serializable(topic)
                
            # Extraer palabras clave del tema
            keywords = []
            keywords.append(topic.get("name", ""))
            
            # Añadir palabras del contenido teórico
            if "theory_content" in topic and topic["theory_content"]:
                # Extraer palabras significativas del contenido teórico
                words = re.findall(r'\b[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}\b', topic["theory_content"].lower())
                # Filtrar y añadir las más relevantes (hasta 5)
                stop_words = set(['el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'a', 
                                  'de', 'del', 'en', 'con', 'por', 'para', 'es', 'son', 'al', 'e', 'u'])
                filtered_words = [w for w in words if w not in stop_words]
                word_counts = {}
                for word in filtered_words:
                    word_counts[word] = word_counts.get(word, 0) + 1
                sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
                additional_keywords = [word for word, count in sorted_words[:5]]
                keywords.extend(additional_keywords)
            
            # Extraer contenido relevante basado en palabras clave
            extracted_text = pdf.get("extracted_text", "")
            paragraphs = extracted_text.split('\n\n')
            
            # Filtrar párrafos relevantes
            relevant_paragraphs = []
            for paragraph in paragraphs:
                paragraph = paragraph.strip()
                if not paragraph:
                    continue
                    
                # Calcular puntuación de relevancia
                relevance_score = 0
                for keyword in keywords:
                    if keyword.lower() in paragraph.lower():
                        relevance_score += 1
                
                if relevance_score > 0:
                    relevant_paragraphs.append({
                        "text": paragraph,
                        "score": relevance_score
                    })
            
            # Ordenar por relevancia y concatenar
            relevant_paragraphs.sort(key=lambda x: x["score"], reverse=True)
            result_paragraphs = [p["text"] for p in relevant_paragraphs[:5]]  # Tomar los 5 párrafos más relevantes
            
            if not result_paragraphs:
                # Si no encontramos párrafos relevantes, devolver primeros párrafos
                result_paragraphs = [p for p in paragraphs if p.strip()][:3]
                
            result_text = "\n\n".join(result_paragraphs)
            
            return True, result_text
        except Exception as e:
            logging.error(f"Error al extraer contenido de PDF para tema: {str(e)}")
            return False, None

    def generate_pdf_summary(self, pdf_id: str, max_length: int = 500, focus_areas: List[str] = None) -> Tuple[bool, Union[str, Dict]]:
        """
        Genera un resumen del contenido de un PDF procesado.
        
        Args:
            pdf_id: ID del PDF procesado
            max_length: Longitud máxima del resumen en palabras
            focus_areas: Áreas específicas en las que enfocarse
            
        Returns:
            Tuple with success flag and summary text or error message
        """
        try:
            # Obtener el PDF procesado
            pdf = self.get_processed_pdf(pdf_id)
            if not pdf:
                return False, "PDF no encontrado"
            
            # Obtener el texto extraído
            extracted_text = pdf.get("extracted_text", "")
            if not extracted_text:
                return False, "El PDF no contiene texto extraído"
            
            # Obtener metadata
            metadata = pdf.get("metadata", {})
            title = pdf.get("title", "")
            
            # Aplicar NLP para obtener resumen
            # Esta implementación utiliza un algoritmo de extracción simple,
            # pero podría mejorarse con un modelo de IA más sofisticado
            summary = self._extract_summary(extracted_text, max_length, focus_areas)
            
            # Guardar el resumen generado en la base de datos
            summary_data = {
                "pdf_id": ObjectId(pdf_id),
                "summary": summary,
                "max_length": max_length,
                "focus_areas": focus_areas,
                "created_at": datetime.now()
            }
            
            # Almacenar en colección de resúmenes
            self.db.pdf_summaries.insert_one(summary_data)
            
            # Actualizar el PDF para indicar que tiene resumen
            self.collection.update_one(
                {"_id": ObjectId(pdf_id)},
                {"$set": {"has_summary": True, "updated_at": datetime.now()}}
            )
            
            return True, summary
        except Exception as e:
            logging.error(f"Error al generar resumen de PDF: {str(e)}")
            return False, str(e)
        
    def _extract_summary(self, text: str, max_length: int = 500, focus_areas: List[str] = None) -> str:
        """
        Extrae un resumen del texto utilizando técnicas de NLP.
        
        Args:
            text: Texto completo para resumir
            max_length: Longitud máxima del resumen en palabras
            focus_areas: Áreas específicas en las que enfocarse
            
        Returns:
            Texto resumido
        """
        try:
            # Dividir el texto en párrafos y oraciones
            paragraphs = text.split('\n\n')
            all_sentences = []
            
            for paragraph in paragraphs:
                # Omitir párrafos vacíos
                if not paragraph.strip():
                    continue
                    
                # Dividir en oraciones
                sentences = re.split(r'(?<=[.!?])\s+', paragraph.strip())
                all_sentences.extend(sentences)
                
            # Eliminar oraciones vacías o demasiado cortas
            all_sentences = [s for s in all_sentences if len(s.split()) > 3]
            
            # Calcular puntuación para cada oración
            sentence_scores = {}
            
            # Palabras a ignorar (stop words)
            stop_words = set(['el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'a', 
                               'de', 'del', 'en', 'con', 'por', 'para', 'es', 'son', 'al', 'e', 'u'])
            
            # Calcular frecuencia de palabras
            word_frequencies = {}
            for sentence in all_sentences:
                for word in sentence.lower().split():
                    word = word.strip('.,!?()[]{}:;"\'-')
                    if word and word not in stop_words and len(word) > 1:
                        if word in word_frequencies:
                            word_frequencies[word] += 1
                        else:
                            word_frequencies[word] = 1
            
            # Normalizar frecuencias
            max_frequency = max(word_frequencies.values()) if word_frequencies else 1
            for word in word_frequencies:
                word_frequencies[word] = word_frequencies[word] / max_frequency
            
            # Calcular puntuación para cada oración
            for sentence in all_sentences:
                sentence_scores[sentence] = 0
                words = sentence.lower().split()
                
                # Mayor peso a oraciones al inicio del documento
                position_weight = 1.5 if all_sentences.index(sentence) < len(all_sentences) * 0.2 else 1.0
                
                # Mayor peso si incluye áreas de enfoque
                focus_weight = 1.0
                if focus_areas:
                    if any(area.lower() in sentence.lower() for area in focus_areas):
                        focus_weight = 2.0
                        
                # Calcular puntuación basada en frecuencia de palabras
                for word in words:
                    word = word.strip('.,!?()[]{}:;"\'-')
                    if word in word_frequencies:
                        sentence_scores[sentence] += word_frequencies[word]
                        
                # Aplicar pesos
                sentence_scores[sentence] *= position_weight * focus_weight
                
                # Normalizar por longitud de la oración para no favorecer oraciones muy largas
                if len(words) > 0:
                    sentence_scores[sentence] /= len(words)
            
            # Seleccionar mejores oraciones
            sorted_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)
            
            # Determinar número de oraciones para el resumen
            summary_sentences_count = min(len(sorted_sentences), max(3, len(sorted_sentences) // 10))
            
            # Limitar por longitud máxima
            total_words = 0
            summary_sentences = []
            
            for sentence, score in sorted_sentences:
                words_count = len(sentence.split())
                if total_words + words_count <= max_length:
                    summary_sentences.append(sentence)
                    total_words += words_count
                else:
                    break
                    
            # Reordenar las oraciones según su posición original
            ordered_summary = []
            for sentence in all_sentences:
                if sentence in summary_sentences:
                    ordered_summary.append(sentence)
                    
            # Unir oraciones en un resumen cohesivo
            summary = ' '.join(ordered_summary)
            
            return summary
        except Exception as e:
            logging.error(f"Error en extracción de resumen: {str(e)}")
            return "No se pudo generar un resumen debido a un error."

class WebSearchService(VerificationBaseService):
    """
    Servicio para búsqueda de recursos en la web.
    """
    def __init__(self):
        super().__init__(collection_name="web_search_results")
        self.providers_collection = get_db().search_providers
        
    def get_active_providers(self) -> List[Dict]:
        """
        Obtiene los proveedores de búsqueda activos.
        
        Returns:
            Lista de proveedores de búsqueda
        """
        try:
            providers = list(self.providers_collection.find({"is_active": True}))
            
            # Convertir ObjectId a str para serialización
            for provider in providers:
                if "_id" in provider:
                    provider["_id"] = str(provider["_id"])
                    
            return providers
        except Exception as e:
            logging.error(f"Error al obtener proveedores de búsqueda: {str(e)}")
            return []
            
    def search_web(self, query: str, result_type: str = None, max_results: int = 10, topic_id: str = None) -> List[Dict]:
        """
        Realiza una búsqueda en la web utilizando el proveedor configurado.
        
        Args:
            query: Consulta de búsqueda
            result_type: Tipo de resultado (webpage, image, video, pdf, audio)
            max_results: Número máximo de resultados
            topic_id: ID del tema relacionado (opcional)
            
        Returns:
            Lista de resultados de búsqueda
        """
        try:
            # Obtener proveedores activos
            providers = self.get_active_providers()
            if not providers:
                logging.warning("No hay proveedores de búsqueda activos")
                return []
                
            # Por ahora, usamos el primer proveedor disponible
            provider = providers[0]
            
            if provider.get("provider_type") == "serp_api":
                return self._search_with_serp_api(provider, query, result_type, max_results, topic_id)
            elif provider.get("provider_type") == "google_cse":
                return self._search_with_google_cse(provider, query, result_type, max_results, topic_id)
            else:
                logging.warning(f"Tipo de proveedor no soportado: {provider.get('provider_type')}")
                return []
        except Exception as e:
            logging.error(f"Error al buscar en la web: {str(e)}")
            return []
    
    def _search_with_serp_api(self, provider: Dict, query: str, result_type: str, max_results: int, topic_id: str = None) -> List[Dict]:
        """
        Realiza una búsqueda utilizando SerpAPI.
        
        Args:
            provider: Configuración del proveedor
            query: Consulta de búsqueda
            result_type: Tipo de resultado 
            max_results: Número máximo de resultados
            topic_id: ID del tema relacionado (opcional)
            
        Returns:
            Lista de resultados de búsqueda
        """
        api_key = provider.get("api_key")
        if not api_key:
            logging.error("API key no configurada para SerpAPI")
            return []
            
        # Determinar el tipo de búsqueda
        search_type = "search"  # Búsqueda web por defecto
        if result_type == "image":
            search_type = "images"
        elif result_type == "video":
            search_type = "videos"
        elif result_type == "news":
            search_type = "news"
            
        # Construir la URL de la API
        base_url = "https://serpapi.com/search.json"
        params = {
            "q": query,
            "api_key": api_key,
            "num": min(max_results, 10)  # SerpAPI limita a 10 resultados por página en plan gratuito
        }
        
        # Si es una búsqueda específica, añadir parámetros
        if search_type != "search":
            params["tbm"] = search_type
        
        try:
            # Realizar la petición
            response = requests.get(base_url, params=params)
            response.raise_for_status()  # Lanzar excepción si hay error HTTP
            
            search_results = response.json()
            
            # Procesar resultados según el tipo
            results = []
            
            # Resultados de búsqueda web
            if search_type == "search" and "organic_results" in search_results:
                for item in search_results["organic_results"][:max_results]:
                    result = WebSearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        result_type="webpage",
                        topic_id=topic_id,
                        metadata={
                            "position": item.get("position"),
                            "displayed_link": item.get("displayed_link"),
                            "source": "serp_api_google"
                        },
                        relevance_score=1.0 - (item.get("position", 1) / 10.0)
                    )
                    
                    # Guardar en la base de datos
                    saved_result = self.collection.insert_one(result.to_dict())
                    
                    # Convertir a formato JSON serializable
                    result_dict = ensure_json_serializable(result.to_dict())
                    result_dict["_id"] = str(saved_result.inserted_id)
                    results.append(result_dict)
            
            # Resultados de imágenes
            elif search_type == "images" and "images_results" in search_results:
                for item in search_results["images_results"][:max_results]:
                    result = WebSearchResult(
                        title=item.get("title", ""),
                        url=item.get("original", item.get("link", "")),
                        snippet=item.get("snippet", ""),
                        result_type="image",
                        topic_id=topic_id,
                        metadata={
                            "thumbnail": item.get("thumbnail"),
                            "source": item.get("source"),
                            "source_website": item.get("source_website"),
                            "width": item.get("width"),
                            "height": item.get("height"),
                            "image_type": item.get("image_type")
                        },
                        relevance_score=1.0 - (item.get("position", 1) / 20.0)
                    )
                    
                    # Guardar en la base de datos
                    saved_result = self.collection.insert_one(result.to_dict())
                    
                    # Convertir a formato JSON serializable
                    result_dict = ensure_json_serializable(result.to_dict())
                    result_dict["_id"] = str(saved_result.inserted_id)
                    results.append(result_dict)
            
            # Resultados de videos
            elif search_type == "videos" and "video_results" in search_results:
                for item in search_results["video_results"][:max_results]:
                    result = WebSearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        result_type="video",
                        topic_id=topic_id,
                        metadata={
                            "thumbnail": item.get("thumbnail"),
                            "source": item.get("source"),
                            "duration": item.get("duration"),
                            "platform": item.get("platform", "unknown")
                        },
                        relevance_score=1.0 - (item.get("position", 1) / 10.0)
                    )
                    
                    # Guardar en la base de datos
                    saved_result = self.collection.insert_one(result.to_dict())
                    
                    # Convertir a formato JSON serializable
                    result_dict = ensure_json_serializable(result.to_dict())
                    result_dict["_id"] = str(saved_result.inserted_id)
                    results.append(result_dict)
                    
            # Actualizar contador de uso del proveedor
            self.providers_collection.update_one(
                {"_id": ObjectId(provider.get("_id"))},
                {
                    "$inc": {"usage_count": 1},
                    "$set": {"last_used": datetime.now()}
                }
            )
                    
            return results
        except requests.exceptions.RequestException as e:
            logging.error(f"Error en la petición a SerpAPI: {str(e)}")
            return []
        except json.JSONDecodeError as e:
            logging.error(f"Error al decodificar respuesta JSON: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Error inesperado en búsqueda SerpAPI: {str(e)}")
            return []
            
    def _search_with_google_cse(self, provider: Dict, query: str, result_type: str, max_results: int, topic_id: str = None) -> List[Dict]:
        """
        Realiza una búsqueda utilizando Google Custom Search API.
        
        Args:
            provider: Configuración del proveedor
            query: Consulta de búsqueda
            result_type: Tipo de resultado 
            max_results: Número máximo de resultados
            topic_id: ID del tema relacionado (opcional)
            
        Returns:
            Lista de resultados de búsqueda
        """
        api_key = provider.get("api_key")
        cx = provider.get("config", {}).get("cx")
        
        if not api_key or not cx:
            logging.error("API key o CX no configurados para Google CSE")
            return []
            
        # Construir la URL de la API
        base_url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "q": query,
            "key": api_key,
            "cx": cx,
            "num": min(max_results, 10)  # Google CSE limita a 10 resultados por página
        }
        
        # Si es búsqueda de imágenes, añadir parámetro
        if result_type == "image":
            params["searchType"] = "image"
            
        try:
            # Realizar la petición
            response = requests.get(base_url, params=params)
            response.raise_for_status()  # Lanzar excepción si hay error HTTP
            
            search_results = response.json()
            
            results = []
            if "items" in search_results:
                for i, item in enumerate(search_results["items"]):
                    # Determinar tipo de resultado
                    if "image" in item.get("pagemap", {}):
                        result_item_type = "image"
                    elif "videoobject" in item.get("pagemap", {}):
                        result_item_type = "video"
                    elif "document" in item.get("pagemap", {}) and item.get("link", "").endswith(".pdf"):
                        result_item_type = "pdf"
                    else:
                        result_item_type = "webpage"
                    
                    # Crear objeto de resultado
                    result = WebSearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        result_type=result_item_type,
                        topic_id=topic_id,
                        metadata={
                            "display_link": item.get("displayLink"),
                            "html_snippet": item.get("htmlSnippet"),
                            "pagemap": item.get("pagemap", {}),
                            "source": "google_cse"
                        },
                        relevance_score=0.9 - (i * 0.05)
                    )
                    
                    # Guardar en la base de datos
                    saved_result = self.collection.insert_one(result.to_dict())
                    
                    # Convertir a formato JSON serializable
                    result_dict = ensure_json_serializable(result.to_dict())
                    result_dict["_id"] = str(saved_result.inserted_id)
                    results.append(result_dict)
                    
            # Actualizar contador de uso del proveedor
            self.providers_collection.update_one(
                {"_id": ObjectId(provider.get("_id"))},
                {
                    "$inc": {"usage_count": 1},
                    "$set": {"last_used": datetime.now()}
                }
            )
                    
            return results
        except requests.exceptions.RequestException as e:
            logging.error(f"Error en la petición a Google CSE: {str(e)}")
            return []
        except json.JSONDecodeError as e:
            logging.error(f"Error al decodificar respuesta JSON: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Error inesperado en búsqueda Google CSE: {str(e)}")
            return []
            
    def save_search_result(self, result_id: str) -> Tuple[bool, str]:
        """
        Marca un resultado de búsqueda como guardado.
        
        Args:
            result_id: ID del resultado de búsqueda
            
        Returns:
            Tupla con estado y mensaje
        """
        try:
            # Marcar como guardado
            result = self.collection.update_one(
                {"_id": ObjectId(result_id)},
                {"$set": {"is_saved": True}}
            )
            
            if result.modified_count > 0:
                return True, "Resultado guardado exitosamente"
            return False, "No se pudo guardar el resultado"
        except Exception as e:
            logging.error(f"Error al guardar resultado de búsqueda: {str(e)}")
            return False, str(e)

class DiagramService(VerificationBaseService):
    """
    Servicio para generación y gestión de diagramas.
    """
    def __init__(self):
        super().__init__(collection_name="generated_diagrams")
        self.templates_collection = get_db().diagram_templates
        # Directorio para almacenar imágenes generadas
        self.diagrams_dir = os.path.join(os.environ.get("UPLOAD_FOLDER", "uploads"), "diagrams")
        os.makedirs(self.diagrams_dir, exist_ok=True)
        
    def list_templates(self, template_type: str = None) -> List[Dict]:
        """
        Lista las plantillas de diagramas disponibles.
        
        Args:
            template_type: Tipo de plantilla para filtrar (opcional)
            
        Returns:
            Lista de plantillas
        """
        try:
            filter_query = {"status": "active"}
            if template_type:
                filter_query["template_type"] = template_type
                
            templates = list(self.templates_collection.find(filter_query))
            
            # Convertir ObjectId a str para serialización
            for template in templates:
                if "_id" in template:
                    template["_id"] = str(template["_id"])
                    
            return templates
        except Exception as e:
            logging.error(f"Error al listar plantillas de diagramas: {str(e)}")
            return []
            
    def create_template(self, template_data: dict) -> Tuple[bool, str]:
        """
        Crea una nueva plantilla de diagrama.
        
        Args:
            template_data: Datos de la plantilla
            
        Returns:
            Tupla con estado y mensaje/ID
        """
        try:
            # Verificar si ya existe una plantilla con el mismo nombre
            existing = self.templates_collection.find_one({"name": template_data.get("name")})
            if existing:
                return False, "Ya existe una plantilla con ese nombre"
                
            # Crear la plantilla
            template = DiagramTemplate(**template_data)
            result = self.templates_collection.insert_one(template.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            logging.error(f"Error al crear plantilla de diagrama: {str(e)}")
            return False, str(e)
            
    def generate_diagram(self, diagram_data: dict) -> Tuple[bool, str]:
        """
        Genera un nuevo diagrama.
        
        Args:
            diagram_data: Datos del diagrama
            
        Returns:
            Tupla con estado y mensaje/ID
        """
        try:
            # Si se especifica una plantilla, validar que existe y aplicarla
            template_id = diagram_data.get("template_id")
            if template_id:
                template = self.templates_collection.find_one({"_id": ObjectId(template_id)})
                if not template:
                    return False, "Plantilla no encontrada"
                
                # Aplicar plantilla (reemplazando variables en el contenido)
                content = self._apply_template(template, diagram_data)
                diagram_data["content"] = content
            
            # Generar imagen del diagrama
            diagram_type = diagram_data.get("diagram_type")
            content = diagram_data.get("content")
            
            # Generar el diagrama según el tipo
            image_url = None
            if diagram_type == "flowchart" or diagram_type == "graph":
                image_url = self._generate_graphviz_diagram(content, diagram_data.get("title"))
            elif diagram_type == "sequence" or diagram_type == "uml":
                image_url = self._generate_plantuml_diagram(content, diagram_data.get("title"))
            elif diagram_type == "mindmap":
                image_url = self._generate_mindmap_diagram(content, diagram_data.get("title"))
            elif diagram_type == "mermaid":
                image_url = self._generate_mermaid_diagram(content, diagram_data.get("title"))
            
            # Añadir URL de la imagen si se generó
            if image_url:
                diagram_data["image_url"] = image_url
            
            # Crear el diagrama en la base de datos
            diagram = GeneratedDiagram(**diagram_data)
            result = self.collection.insert_one(diagram.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            logging.error(f"Error al generar diagrama: {str(e)}")
            return False, str(e)
    
    def _apply_template(self, template: Dict, diagram_data: Dict) -> str:
        """
        Aplica una plantilla a un diagrama, reemplazando variables.
        
        Args:
            template: Plantilla de diagrama
            diagram_data: Datos del diagrama
            
        Returns:
            Contenido del diagrama con variables reemplazadas
        """
        # Obtener el código base de la plantilla
        template_code = template.get("sample_code", "")
        
        # Obtener variables de la plantilla
        template_schema = template.get("template_schema", {})
        variables = template_schema.get("variables", [])
        
        # Reemplazar variables en el código
        content = template_code
        for var in variables:
            var_name = var.get("name")
            var_placeholder = f"{{${var_name}}}"
            
            # Buscar el valor en los datos del diagrama
            if "metadata" in diagram_data and var_name in diagram_data["metadata"]:
                value = diagram_data["metadata"][var_name]
                content = content.replace(var_placeholder, str(value))
        
        return content
    
    def _generate_graphviz_diagram(self, content: str, title: str) -> Optional[str]:
        """
        Genera un diagrama usando Graphviz.
        
        Args:
            content: Contenido DOT del diagrama
            title: Título del diagrama
            
        Returns:
            URL de la imagen generada o None si falla
        """
        try:
            import graphviz
            
            # Sanitizar título para usar como nombre de archivo
            safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
            filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Crear objeto Graphviz
            dot = graphviz.Source(content)
            
            # Renderizar el diagrama
            output_path = os.path.join(self.diagrams_dir, filename)
            rendered_file = dot.render(output_path, format='png', cleanup=True)
            
            # Devolver ruta relativa para acceso web
            rel_path = os.path.relpath(rendered_file, os.environ.get("UPLOAD_FOLDER", "uploads"))
            return f"/uploads/{rel_path}"
        except Exception as e:
            logging.error(f"Error al generar diagrama Graphviz: {str(e)}")
            return None
    
    def _generate_plantuml_diagram(self, content: str, title: str) -> Optional[str]:
        """
        Genera un diagrama usando PlantUML.
        
        Args:
            content: Contenido PlantUML del diagrama
            title: Título del diagrama
            
        Returns:
            URL de la imagen generada o None si falla
        """
        try:
            # Sanitizar título para usar como nombre de archivo
            safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
            filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            output_path = os.path.join(self.diagrams_dir, filename)
            
            # Preparar contenido PlantUML
            if not content.startswith('@startuml'):
                content = f"@startuml\n{content}\n@enduml"
            
            # Codificar contenido para PlantUML server
            encoded = base64.b64encode(content.encode('utf-8'))
            plantuml_url = f"http://www.plantuml.com/plantuml/png/{encoded.decode('utf-8')}"
            
            # Descargar imagen generada
            response = requests.get(plantuml_url)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                # Devolver ruta relativa para acceso web
                rel_path = os.path.relpath(output_path, os.environ.get("UPLOAD_FOLDER", "uploads"))
                return f"/uploads/{rel_path}"
            else:
                logging.error(f"Error al descargar imagen PlantUML: {response.status_code}")
                return None
        except Exception as e:
            logging.error(f"Error al generar diagrama PlantUML: {str(e)}")
            return None
    
    def _generate_mindmap_diagram(self, content: str, title: str) -> Optional[str]:
        """
        Genera un diagrama de mapa mental.
        
        Args:
            content: Contenido del mapa mental (formato específico)
            title: Título del diagrama
            
        Returns:
            URL de la imagen generada o None si falla
        """
        try:
            # Convertir a formato PlantUML para mapas mentales
            plantuml_content = "@startmindmap\n"
            plantuml_content += f"* {title}\n"
            
            # Procesar líneas del contenido
            for line in content.strip().split("\n"):
                plantuml_content += line + "\n"
                
            plantuml_content += "@endmindmap"
            
            # Usar método de PlantUML para generar
            return self._generate_plantuml_diagram(plantuml_content, title)
        except Exception as e:
            logging.error(f"Error al generar mapa mental: {str(e)}")
            return None
    
    def _generate_mermaid_diagram(self, content: str, title: str) -> Optional[str]:
        """
        Genera un diagrama usando Mermaid.
        
        Args:
            content: Contenido Mermaid del diagrama
            title: Título del diagrama
            
        Returns:
            URL de la imagen generada o None si falla
        """
        try:
            # Sanitizar título para usar como nombre de archivo
            safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
            filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            output_path = os.path.join(self.diagrams_dir, filename)
            
            # Usar Puppeteer para renderizar Mermaid
            # En un entorno real, se podría usar un servicio como mermaid.ink o implementar
            # un servicio interno con Puppeteer/Chrome headless
            
            # Por ahora, usaremos mermaid.ink (servicio público)
            payload = {
                "code": content,
                "mermaid": {"theme": "default"},
                "updateEditor": True,
                "autoSync": True
            }
            
            json_payload = json.dumps(payload)
            encoded_payload = base64.urlsafe_b64encode(json_payload.encode()).decode()
            mermaid_url = f"https://mermaid.ink/img/{encoded_payload}"
            
            # Descargar imagen generada
            response = requests.get(mermaid_url)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                # Devolver ruta relativa para acceso web
                rel_path = os.path.relpath(output_path, os.environ.get("UPLOAD_FOLDER", "uploads"))
                return f"/uploads/{rel_path}"
            else:
                logging.error(f"Error al descargar imagen Mermaid: {response.status_code}")
                return None
        except Exception as e:
            logging.error(f"Error al generar diagrama Mermaid: {str(e)}")
            return None
            
    def get_diagram(self, diagram_id: str) -> Optional[Dict]:
        """
        Obtiene un diagrama por su ID.
        
        Args:
            diagram_id: ID del diagrama
            
        Returns:
            Diccionario con datos del diagrama o None si no existe
        """
        try:
            diagram = self.collection.find_one({"_id": ObjectId(diagram_id)})
            if not diagram:
                return None
                
            # Convertir a formato serializable
            diagram = ensure_json_serializable(diagram)
                    
            return diagram
        except Exception as e:
            logging.error(f"Error al obtener diagrama: {str(e)}")
            return None

class SearchProviderService(VerificationBaseService):
    """
    Servicio para gestionar proveedores de búsqueda.
    """
    def __init__(self):
        super().__init__(collection_name="search_providers")
        
    def list_providers(self, active_only: bool = True) -> List[Dict]:
        """
        Lista los proveedores de búsqueda.
        
        Args:
            active_only: Si solo se devuelven los proveedores activos
            
        Returns:
            Lista de proveedores
        """
        try:
            filter_query = {}
            if active_only:
                filter_query["status"] = "active"
                
            providers = list(self.collection.find(filter_query))
            
            # Convertir a formato serializable
            for provider in providers:
                provider = ensure_json_serializable(provider)
                
                # Ocultar claves API en respuesta 
                if "api_key" in provider:
                    provider["api_key"] = "***" + provider["api_key"][-4:] if provider["api_key"] else ""
                    
            return providers
        except Exception as e:
            logging.error(f"Error al listar proveedores de búsqueda: {str(e)}")
            return []
            
    def create_provider(self, provider_data: dict) -> Tuple[bool, str]:
        """
        Crea un nuevo proveedor de búsqueda.
        
        Args:
            provider_data: Datos del proveedor
            
        Returns:
            Tupla con estado y mensaje/ID
        """
        try:
            # Verificar si ya existe un proveedor con el mismo nombre
            existing = self.collection.find_one({"name": provider_data.get("name")})
            if existing:
                return False, "Ya existe un proveedor con ese nombre"
                
            # Validar datos del proveedor
            provider_type = provider_data.get("provider_type")
            if provider_type not in ["google_cse", "serp_api"]:
                return False, "Tipo de proveedor no válido"
                
            if not provider_data.get("api_key"):
                return False, "Clave API requerida"
                
            # Para Google CSE, validar ID del motor de búsqueda
            if provider_type == "google_cse" and not provider_data.get("search_engine_id"):
                return False, "ID del motor de búsqueda requerido para Google CSE"
                
            # Crear el proveedor
            provider = SearchProvider(**provider_data)
            result = self.collection.insert_one(provider.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            logging.error(f"Error al crear proveedor de búsqueda: {str(e)}")
            return False, str(e)
            
    def update_provider(self, provider_id: str, update_data: dict) -> Tuple[bool, str]:
        """
        Actualiza un proveedor de búsqueda.
        
        Args:
            provider_id: ID del proveedor
            update_data: Datos a actualizar
            
        Returns:
            Tupla con estado y mensaje
        """
        try:
            # Verificar que el proveedor existe
            provider = self.collection.find_one({"_id": ObjectId(provider_id)})
            if not provider:
                return False, "Proveedor no encontrado"
                
            # Si actualizamos nombre, verificar que no exista otro con ese nombre
            if "name" in update_data and update_data["name"] != provider["name"]:
                existing = self.collection.find_one({"name": update_data["name"]})
                if existing:
                    return False, "Ya existe un proveedor con ese nombre"
            
            # Si actualizamos tipo, validar
            if "provider_type" in update_data:
                if update_data["provider_type"] not in ["google_cse", "serp_api"]:
                    return False, "Tipo de proveedor no válido"
                    
                # Si cambiamos a Google CSE, verificar que tengamos search_engine_id
                if update_data["provider_type"] == "google_cse":
                    search_engine_id = update_data.get("search_engine_id") or provider.get("search_engine_id")
                    if not search_engine_id:
                        return False, "ID del motor de búsqueda requerido para Google CSE"
            
            # Actualizar el proveedor
            self.collection.update_one(
                {"_id": ObjectId(provider_id)},
                {"$set": update_data}
            )
            
            return True, "Proveedor actualizado correctamente"
        except Exception as e:
            logging.error(f"Error al actualizar proveedor de búsqueda: {str(e)}")
            return False, str(e)
            
    def delete_provider(self, provider_id: str) -> Tuple[bool, str]:
        """
        Elimina un proveedor de búsqueda.
        
        Args:
            provider_id: ID del proveedor
            
        Returns:
            Tupla con estado y mensaje
        """
        try:
            # Verificar que el proveedor existe
            provider = self.collection.find_one({"_id": ObjectId(provider_id)})
            if not provider:
                return False, "Proveedor no encontrado"
                
            # Eliminar el proveedor (cambiar estado a deleted)
            self.collection.update_one(
                {"_id": ObjectId(provider_id)},
                {"$set": {"status": "deleted"}}
            )
            
            return True, "Proveedor eliminado correctamente"
        except Exception as e:
            logging.error(f"Error al eliminar proveedor de búsqueda: {str(e)}")
            return False, str(e)
            
    def test_provider(self, provider_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Prueba un proveedor de búsqueda.
        
        Args:
            provider_id: ID del proveedor
            
        Returns:
            Tupla con estado, mensaje y resultados (opcional)
        """
        try:
            # Obtener el proveedor
            provider = self.collection.find_one({"_id": ObjectId(provider_id)})
            if not provider:
                return False, "Proveedor no encontrado", None
                
            # Prueba real del proveedor
            provider_type = provider.get("provider_type")
            api_key = provider.get("api_key")
            
            if provider_type == "serp_api":
                # Prueba de SerpAPI
                test_url = f"https://serpapi.com/account?api_key={api_key}"
                response = requests.get(test_url)
                
                if response.status_code == 200:
                    data = response.json()
                    # Validar si hay acceso y obtener límites
                    if "plan_searches_left" in data:
                        return True, "Conexión exitosa", {
                            "searches_left": data.get("plan_searches_left"),
                            "plan_name": data.get("plan_name")
                        }
                    else:
                        return False, "No se pudo verificar el plan", None
                else:
                    return False, f"Error en conexión: {response.status_code}", None
                    
            elif provider_type == "google_cse":
                # Prueba de Google CSE
                search_engine_id = provider.get("search_engine_id")
                if not search_engine_id:
                    return False, "ID del motor de búsqueda no configurado", None
                    
                test_url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={search_engine_id}&q=test"
                response = requests.get(test_url)
                
                if response.status_code == 200:
                    return True, "Conexión exitosa", {
                        "search_engine_id": search_engine_id,
                    }
                else:
                    error_data = response.json() if response.headers.get("content-type") == "application/json" else {}
                    error_message = error_data.get("error", {}).get("message", f"Error {response.status_code}")
                    return False, f"Error en conexión: {error_message}", None
            
            return False, "Tipo de proveedor no soportado", None
            
        except Exception as e:
            logging.error(f"Error al probar proveedor de búsqueda: {str(e)}")
            return False, str(e), None 