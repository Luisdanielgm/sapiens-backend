from flask import Blueprint

topic_resources_bp = Blueprint('topic_resources', __name__)

from . import routes 