from flask import Flask, jsonify, request
from flask_cors import CORS
from database.db_user import verify_user_exists, register_user, search_users_by_partial_email, delete_student, get_user_by_email
from database.db_classrom import invite_user_to_classroom, accept_invitation, reject_invitation, get_user_pending_invitations, get_teacher_classrooms, get_classroom_students, get_student_classrooms
from bson import ObjectId
from functools import wraps
from database.cognitive_profile import get_cognitive_profile
from database.statistics import get_teacher_statistics, get_student_statistics

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://localhost:3000", "https://portal-hubnews.vercel.app"]}}, supports_credentials=True)

def serialize_doc(doc):
    return {k: str(v) if isinstance(v, ObjectId) else v for k, v in doc.items()}

def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return decorated_function

@app.route('/')
def index():
    return jsonify({"message": "Hello, World!"}), 200



@app.route('/users/check', methods=['POST'])
def verify_user_endpoint():
    data = request.get_json()
    email = data.get('email')
    name = data.get('name')
    picture = data.get('picture')

    if not email or not name or not picture:
        return jsonify({'error': 'Missing required fields'}), 400

    user_exists = verify_user_exists(email)

    return jsonify({'userExists': user_exists}), 200

@app.route('/users/register', methods=['POST'])
def register_user_endpoint():
    data = request.get_json()
    email = data.get('email')
    name = data.get('name')
    picture = data.get('picture')
    birth_date = data.get('birthDate')
    classroom_name = data.get('classroomName')
    role = data.get('role')

    if not email or not name or not picture or not birth_date or not role or not classroom_name:
        return jsonify({'error': 'Missing required fields'}), 400

    result = register_user(email, name, picture, birth_date, role, classroom_name)

    if result:
        return jsonify({'message': 'User registered successfully'}), 200
    else:
        return jsonify({'error': 'Failed to register user'}), 500

    
@app.route('/users/search', methods=['GET'])
@handle_errors
def search_users():
    partial_email = request.args.get('email')
    if not partial_email or '@' not in partial_email:
        return jsonify({"error": "Correo electrónico inválido"}), 400

    suggestions = search_users_by_partial_email(partial_email)
    return jsonify({"suggestions": suggestions}), 200

@app.route('/user/invite', methods=['POST'])
@handle_errors
def invite_user_endpoint():
    data = request.json
    email = data.get('email')
    classroom_id = data.get('classroomId')
    invitee_email = data.get('inviteeEmail')

    if not all([email, classroom_id, invitee_email]):
        return jsonify({"error": "Faltan parámetros requeridos"}), 400

    try:
        success, message = invite_user_to_classroom(email, classroom_id, invitee_email)
        if success:
            return jsonify({"message": message}), 200
        else:
            return jsonify({"error": message}), 400
    except Exception as e:
        return jsonify({"error": f"Error al enviar la invitación: {str(e)}"}), 500


@app.route('/user/invitations', methods=['GET'])
@handle_errors
def get_user_invitations():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del usuario"}), 400

    try:
        invitations = get_user_pending_invitations(email)
        return jsonify({"invitations": invitations}), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener invitaciones: {str(e)}"}), 500

@app.route('/invitations/accept', methods=['POST'])
@handle_errors
def accept_classroom_invitation():
    data = request.json
    email = data.get('email')
    invitation_id = data.get('invitation_id')

    if not email or not invitation_id:
        return jsonify({"error": "Se requieren email e invitation_id"}), 400

    try:
        success = accept_invitation(email, invitation_id)
        if success:
            return jsonify({"message": "Invitación aceptada exitosamente"}), 200
        else:
            return jsonify({"error": "No se pudo aceptar la invitación"}), 400
    except Exception as e:
        return jsonify({"error": f"Error al aceptar la invitación: {str(e)}"}), 500

@app.route('/invitations/reject', methods=['POST'])
@handle_errors
def reject_classroom_invitation():
    data = request.json
    email = data.get('email')
    invitation_id = data.get('invitation_id')

    if not email or not invitation_id:
        return jsonify({"error": "Se requieren email e invitation_id"}), 400

    try:
        success = reject_invitation(email, invitation_id)
        if success:
            return jsonify({"message": "Invitación rechazada exitosamente"}), 200
        else:
            return jsonify({"error": "No se pudo rechazar la invitación"}), 400
    except Exception as e:
        return jsonify({"error": f"Error al rechazar la invitación: {str(e)}"}), 500
    

@app.route('/teacher/classrooms', methods=['GET'])
@handle_errors
def get_teacher_classrooms_endpoint():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del profesor"}), 400

    try:
        classrooms = get_teacher_classrooms(email)
        return jsonify({"classrooms": classrooms}), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener los salones: {str(e)}"}), 500

@app.route('/classroom/students', methods=['GET'])
@handle_errors
def get_classroom_students_endpoint():
    try:
        classroom_id = request.args.get('classroomId')
        result = get_classroom_students(classroom_id)
        if result["success"]:
            return jsonify({
                "students": result["students"],
                "count": result["count"]
            }), 200
        else:
            return jsonify({"error": result["error"]}), 400
    except Exception as e:
        return jsonify({"error": f"Error al obtener estudiantes: {str(e)}"}), 500

@app.route('/user/cognitive-profile', methods=['GET'])
@handle_errors
def get_user_cognitive_profile():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del usuario"}), 400

    try:
        profile = get_cognitive_profile(email)
        if profile:
            return jsonify({"profile": profile}), 200
        else:
            return jsonify({"error": "No se encontró el perfil cognitivo"}), 404
    except Exception as e:
        return jsonify({"error": f"Error al obtener el perfil cognitivo: {str(e)}"}), 500

@app.route('/student/delete', methods=['DELETE'])
@handle_errors
def delete_student_endpoint():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del estudiante"}), 400

    success, message = delete_student(email)
    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 400

@app.route('/user/info', methods=['GET'])
@handle_errors
def get_user_info():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del usuario"}), 400

    try:
        user = get_user_by_email(email)
        if user:
            # Serializamos el documento para manejar el ObjectId
            user_data = serialize_doc(user)
            return jsonify({"user": user_data}), 200
        else:
            return jsonify({"error": "Usuario no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": f"Error al obtener información del usuario: {str(e)}"}), 500

@app.route('/statistics/teacher', methods=['GET'])
@handle_errors
def get_teacher_stats():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del profesor"}), 400

    try:
        stats = get_teacher_statistics(email)
        if stats:
            return jsonify({"statistics": stats}), 200
        else:
            return jsonify({"error": "No se pudieron obtener las estadísticas"}), 404
    except Exception as e:
        return jsonify({"error": f"Error al obtener estadísticas: {str(e)}"}), 500

@app.route('/statistics/student', methods=['GET'])
@handle_errors
def get_student_stats():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del estudiante"}), 400

    try:
        stats = get_student_statistics(email)
        if stats:
            return jsonify({"statistics": stats}), 200
        else:
            return jsonify({"error": "No se pudieron obtener las estadísticas"}), 404
    except Exception as e:
        return jsonify({"error": f"Error al obtener estadísticas: {str(e)}"}), 500

@app.route('/student/classrooms', methods=['GET'])
@handle_errors
def get_student_classrooms_endpoint():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del estudiante"}), 400

    try:
        classrooms = get_student_classrooms(email)
        return jsonify({
            "classrooms": classrooms,
            "count": len(classrooms)
        }), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener los salones: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
