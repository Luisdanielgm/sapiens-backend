from datetime import datetime
from bson import ObjectId

# translations
{
    "_id": ObjectId,
    "español": str,
    "traduccion": str,  # Texto en la lengua originaria
    "dialecto": str,
    "language_pair": str,  # ej: "español-pemon", "español-warao"
    "type_data": str,
    "created_at": datetime,
    "updated_at": datetime
} 