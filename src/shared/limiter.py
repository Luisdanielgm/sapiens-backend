from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Inicializar limiter
# Usamos get_remote_address para identificar al cliente por IP
# storage_uri="memory://" es el valor por defecto, adecuado para despliegues de una sola instancia
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "200 per hour"],
    storage_uri="memory://"
)
