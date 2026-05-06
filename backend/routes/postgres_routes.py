from flask import Blueprint, jsonify, request, session
from db_managers.postgres_manager import PostgresManager
from db_managers.mongodb_manager import MongoDBManager
from decorators import login_required, admin_required
import logging

logger = logging.getLogger(__name__)

postgres_bp = Blueprint('postgres', __name__, url_prefix='/api/postgres')
pg_manager = PostgresManager()
mongo_manager = MongoDBManager()


# ============================================
# Autenticación
# ============================================

@postgres_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    required = ['username', 'email', 'password', 'full_name']
    if not all(k in data for k in required):
        return jsonify({'error': 'Faltan campos requeridos: username, email, password, full_name'}), 400

    if len(data['password']) < 6:
        return jsonify({'error': 'La contraseña debe tener al menos 6 caracteres'}), 400

    if pg_manager.user_exists(data['username'], data['email']):
        return jsonify({'error': 'El usuario o email ya está registrado'}), 409

    from config import INITIAL_BALANCE
    success = pg_manager.register_user(
        data['username'], data['email'],
        data['password'], data['full_name'],
        balance=INITIAL_BALANCE
    )

    if success:
        return jsonify({'success': True, 'message': 'Usuario registrado correctamente'}), 201
    return jsonify({'error': 'Error al registrar usuario'}), 500


@postgres_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not all(k in data for k in ['username', 'password']):
        return jsonify({'error': 'Faltan credenciales'}), 400

    user = pg_manager.login_user(data['username'], data['password'])

    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        session['full_name'] = user['full_name']
        session.permanent = True

        user_data = {
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'full_name': user['full_name'],
            'role': user['role'],
            'balance': float(user['balance']) if user.get('balance') else 0
        }
        return jsonify({'success': True, 'data': user_data, 'message': 'Inicio de sesión exitoso'}), 200

    return jsonify({'error': 'Usuario o contraseña incorrectos'}), 401


@postgres_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Sesión cerrada'}), 200


@postgres_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    user = pg_manager.get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return jsonify({'error': 'Usuario no encontrado'}), 404
    return jsonify({'success': True, 'data': user}), 200


# ============================================
# Gestión de Usuarios (solo admin)
# ============================================

@postgres_bp.route('/usuarios', methods=['GET'])
@admin_required
def get_usuarios():
    users = pg_manager.get_all_users()
    if users is None:
        return jsonify({'error': 'No se pudo conectar a PostgreSQL'}), 500
    return jsonify({'success': True, 'data': users}), 200


@postgres_bp.route('/usuarios', methods=['POST'])
@admin_required
def create_usuario():
    data = request.get_json()

    required = ['username', 'email', 'password', 'full_name']
    if not all(k in data for k in required):
        return jsonify({'error': 'Faltan campos requeridos'}), 400

    if pg_manager.user_exists(data['username'], data['email']):
        return jsonify({'error': 'El usuario o email ya existe'}), 409

    from config import INITIAL_BALANCE
    balance = data.get('balance', INITIAL_BALANCE)
    role = data.get('role', 'user')

    success = pg_manager.register_user(
        data['username'], data['email'],
        data['password'], data['full_name'],
        balance=balance,
        role=role
    )

    if success:
        return jsonify({'success': True, 'message': 'Usuario creado correctamente'}), 201
    return jsonify({'error': 'Error al crear usuario'}), 500


@postgres_bp.route('/usuarios/<int:user_id>', methods=['GET'])
@admin_required
def get_usuario(user_id):
    user = pg_manager.get_user_by_id(user_id)
    if user is None:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    return jsonify({'success': True, 'data': user}), 200


@postgres_bp.route('/usuarios/<int:user_id>', methods=['PUT'])
@admin_required
def update_usuario(user_id):
    data = request.get_json()
    success = pg_manager.update_user(user_id, data)
    if success:
        return jsonify({'success': True, 'message': 'Usuario actualizado'}), 200
    return jsonify({'error': 'Error al actualizar usuario'}), 500


@postgres_bp.route('/usuarios/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_usuario(user_id):
    if session.get('user_id') == user_id:
        return jsonify({'error': 'No puedes eliminar tu propia cuenta'}), 403

    success = pg_manager.delete_user(user_id)
    if success:
        return jsonify({'success': True, 'message': 'Usuario eliminado'}), 200
    return jsonify({'error': 'Error al eliminar usuario'}), 500


# ============================================
# Balance del usuario
# ============================================

@postgres_bp.route('/usuarios/<int:user_id>/balance', methods=['GET'])
@login_required
def get_balance(user_id):
    if session['user_id'] != user_id and session.get('role') != 'admin':
        return jsonify({'error': 'No autorizado'}), 403

    balance = pg_manager.get_user_balance(user_id)
    if balance is None:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    return jsonify({'success': True, 'balance': float(balance)}), 200


# ============================================
# Activos (acciones disponibles)
# ============================================

@postgres_bp.route('/activos', methods=['GET'])
def get_activos():
    activos = pg_manager.get_all_activos()
    return jsonify({'success': True, 'data': activos}), 200


# ============================================
# Transacciones (comprar/vender)
# ============================================

def _get_market_price(symbol):
    """
    Obtiene el precio actual desde MongoDB (fuente autoritativa).
    Intenta primero sin sufijo .SN, luego con el símbolo original.
    Retorna None si no hay precio en MongoDB (modo simulación).
    """
    mongo_symbol = symbol.upper().replace('.SN', '')
    quote = mongo_manager.get_latest_quote(mongo_symbol)
    if not quote:
        quote = mongo_manager.get_latest_quote(symbol.upper())
    if quote and quote.get('price'):
        return float(quote['price'])
    return None


@postgres_bp.route('/transaccion', methods=['POST'])
@login_required
def realizar_transaccion():
    data = request.get_json()

    required = ['symbol', 'transaction_type', 'quantity']
    if not all(k in data for k in required):
        return jsonify({'error': 'Faltan campos requeridos: symbol, transaction_type, quantity'}), 400

    transaction_type = data['transaction_type']
    if transaction_type not in ['buy', 'sell']:
        return jsonify({'error': 'transaction_type debe ser "buy" o "sell"'}), 400

    try:
        quantity = int(data['quantity'])
    except (ValueError, TypeError):
        return jsonify({'error': 'La cantidad debe ser un número entero'}), 400

    if quantity <= 0:
        return jsonify({'error': 'La cantidad debe ser mayor a 0'}), 400

    user_id = session['user_id']
    symbol = data['symbol']

    # Buscar precio en MongoDB (fuente autoritativa, previene manipulación de precios)
    price = _get_market_price(symbol)

    if price is not None:
        # Precio real de MongoDB — ignorar precio del cliente
        logger.info("Transacción %s %s×%s a precio de mercado $%.2f (user_id=%s)",
                    transaction_type, quantity, symbol, price, user_id)
    else:
        # MongoDB sin datos aún (modo simulación) — usar precio del cliente como fallback
        client_price = data.get('price')
        if not client_price:
            return jsonify({'error': f'No hay precio disponible para {symbol}. Sincroniza los datos de mercado primero o usa el modo simulación.'}), 400
        try:
            price = float(client_price)
        except (ValueError, TypeError):
            return jsonify({'error': 'Precio inválido'}), 400
        if price <= 0:
            return jsonify({'error': 'El precio debe ser mayor a 0'}), 400
        logger.info("Transacción %s %s×%s a precio simulado $%.2f (user_id=%s)",
                    transaction_type, quantity, symbol, price, user_id)

    result = pg_manager.realizar_transaccion(user_id, symbol, transaction_type, quantity, price)

    if result.get('error'):
        return jsonify({'error': result['error']}), 400

    return jsonify({
        'success': True,
        'message': result['message'],
        'new_balance': float(result['new_balance']),
        'transaction_id': result.get('transaction_id'),
        'price_used': price
    }), 200


@postgres_bp.route('/usuarios/<int:user_id>/transacciones', methods=['GET'])
@login_required
def get_transacciones(user_id):
    if session['user_id'] != user_id and session.get('role') != 'admin':
        return jsonify({'error': 'No autorizado'}), 403

    limit = request.args.get('limit', 50, type=int)
    transacciones = pg_manager.get_user_transacciones(user_id, limit)
    return jsonify({'success': True, 'data': transacciones}), 200


# ============================================
# Posiciones (portafolio)
# ============================================

@postgres_bp.route('/usuarios/<int:user_id>/posiciones', methods=['GET'])
@login_required
def get_posiciones(user_id):
    if session['user_id'] != user_id and session.get('role') != 'admin':
        return jsonify({'error': 'No autorizado'}), 403

    posiciones = pg_manager.get_user_posiciones(user_id)
    return jsonify({'success': True, 'data': posiciones}), 200


# ============================================
# Ranking
# ============================================

@postgres_bp.route('/ranking', methods=['GET'])
def get_ranking():
    ranking = pg_manager.get_ranking()
    if 'user_id' in session:
        for r in ranking:
            r['is_me'] = r.get('id') == session['user_id']
    return jsonify({'success': True, 'data': ranking}), 200


# ============================================
# Estadísticas
# ============================================

@postgres_bp.route('/stats', methods=['GET'])
def get_stats():
    stats = pg_manager.get_system_stats()
    return jsonify({'success': True, 'data': stats}), 200
