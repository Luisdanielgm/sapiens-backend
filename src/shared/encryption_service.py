import os
import base64
import binascii
from cryptography.fernet import Fernet
from typing import Optional, Dict, Any
import logging

class EncryptionService:
    """
    Servicio para encriptar y desencriptar API keys de usuarios.
    Utiliza Fernet (AES 128) para encriptación simétrica segura.
    """
    
    def __init__(self):
        self._fernet = None
        self._initialize_encryption_key()
    
    def _initialize_encryption_key(self):
        """Inicializa la clave de encriptación desde variable de entorno o genera una nueva."""
        try:
            # Intentar obtener clave desde variable de entorno
            encryption_key = os.getenv('ENCRYPTION_KEY')
            
            if encryption_key:
                # Validar que la clave tenga el formato correcto
                try:
                    self._fernet = Fernet(encryption_key.encode())
                    logging.info("Clave de encriptación cargada desde variable de entorno")
                except Exception as e:
                    logging.warning(f"Clave de encriptación inválida en variable de entorno: {e}")
                    self._generate_fallback_key()
            else:
                self._generate_fallback_key()
                
        except Exception as e:
            logging.error(f"Error inicializando encriptación: {e}")
            self._generate_fallback_key()
    
    def _generate_fallback_key(self):
        """Genera una clave de encriptación de respaldo."""
        try:
            key = Fernet.generate_key()
            self._fernet = Fernet(key)
            logging.warning("Usando clave de encriptación generada automáticamente. ")
            logging.warning("Para producción, configure ENCRYPTION_KEY en variables de entorno.")
            logging.info(f"Clave generada (guarde en ENCRYPTION_KEY): {key.decode()}")
        except Exception as e:
            logging.error(f"Error generando clave de respaldo: {e}")
            raise Exception("No se pudo inicializar el servicio de encriptación")
    
    def encrypt_api_key(self, api_key: str) -> Optional[str]:
        """
        Encripta una API key.
        
        Args:
            api_key: La API key en texto plano
            
        Returns:
            La API key encriptada en base64, o None si hay error
        """
        if not api_key or not isinstance(api_key, str):
            return None
            
        try:
            # Encriptar la API key
            encrypted_bytes = self._fernet.encrypt(api_key.encode('utf-8'))
            # Convertir a base64 para almacenamiento
            encrypted_b64 = base64.b64encode(encrypted_bytes).decode('utf-8')
            return encrypted_b64
            
        except Exception as e:
            logging.error(f"Error encriptando API key: {e}")
            return None
    
    def decrypt_api_key(self, encrypted_api_key: str) -> Optional[str]:
        """
        Desencripta una API key.
        
        Args:
            encrypted_api_key: La API key encriptada en base64
            
        Returns:
            La API key en texto plano, o None si hay error
        """
        if not encrypted_api_key or not isinstance(encrypted_api_key, str):
            return None
            
        try:
            # Decodificar desde base64
            encrypted_bytes = base64.b64decode(encrypted_api_key.encode('utf-8'))
            # Desencriptar
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            # Convertir a string
            api_key = decrypted_bytes.decode('utf-8')
            return api_key
            
        except binascii.Error as e:
            logging.error(f"Error decodificando base64 en API key: {e}")
            return None
        except Exception as e:
            logging.error(f"Error desencriptando API key: {e}")
            logging.error(f"Tipo de error: {type(e).__name__}")
            if "InvalidToken" in str(type(e)):
                logging.error("La clave de encriptación ha cambiado o los datos fueron encriptados con otra clave")
            return None
    
    def encrypt_api_keys_dict(self, api_keys: Dict[str, str]) -> Dict[str, str]:
        """
        Encripta un diccionario de API keys.
        
        Args:
            api_keys: Diccionario con provider -> api_key
            
        Returns:
            Diccionario con provider -> encrypted_api_key
        """
        if not api_keys or not isinstance(api_keys, dict):
            return {}
            
        encrypted_keys = {}
        for provider, api_key in api_keys.items():
            if api_key:  # Solo encriptar si la clave no está vacía
                encrypted_key = self.encrypt_api_key(api_key)
                if encrypted_key:
                    encrypted_keys[provider] = encrypted_key
                else:
                    logging.warning(f"No se pudo encriptar API key para {provider}")
            
        return encrypted_keys
    
    def decrypt_api_keys_dict(self, encrypted_api_keys: Dict[str, str]) -> Dict[str, str]:
        """
        Desencripta un diccionario de API keys encriptadas.
        
        Args:
            encrypted_api_keys: Diccionario con provider -> encrypted_api_key
            
        Returns:
            Diccionario con provider -> api_key
        """
        if not encrypted_api_keys or not isinstance(encrypted_api_keys, dict):
            return {}
            
        decrypted_keys = {}
        for provider, encrypted_key in encrypted_api_keys.items():
            if encrypted_key:  # Solo desencriptar si la clave no está vacía
                decrypted_key = self.decrypt_api_key(encrypted_key)
                if decrypted_key:
                    decrypted_keys[provider] = decrypted_key
                else:
                    logging.warning(f"No se pudo desencriptar API key para {provider}")
            
        return decrypted_keys
    
    def re_encrypt_with_new_key(self, old_encrypted_data: str, old_key: str) -> Optional[str]:
        """
        Re-encripta datos que fueron encriptados con una clave anterior.
        
        Args:
            old_encrypted_data: Datos encriptados con la clave anterior
            old_key: La clave de encriptación anterior
            
        Returns:
            Los datos re-encriptados con la clave actual, o None si hay error
        """
        try:
            # Crear instancia temporal con la clave anterior
            old_fernet = Fernet(old_key.encode())
            
            # Desencriptar con la clave anterior
            encrypted_bytes = base64.b64decode(old_encrypted_data.encode('utf-8'))
            decrypted_bytes = old_fernet.decrypt(encrypted_bytes)
            plain_text = decrypted_bytes.decode('utf-8')
            
            # Re-encriptar con la clave actual
            return self.encrypt_api_key(plain_text)
            
        except Exception as e:
            logging.error(f"Error re-encriptando datos: {e}")
            return None
    
    def get_current_key(self) -> str:
        """
        Obtiene la clave de encriptación actual.
        
        Returns:
            La clave de encriptación actual en formato string
        """
        if hasattr(self._fernet, '_encryption_key'):
            return base64.urlsafe_b64encode(self._fernet._encryption_key).decode()
        return ""

# Instancia global del servicio
encryption_service = EncryptionService()