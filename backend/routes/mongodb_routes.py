from flask import Blueprint, jsonify, request
from db_managers.mongodb_manager import MongoDBManager
from decorators import login_required, admin_required

mongodb_bp = Blueprint('mongodb', __name__, url_prefix='/api/mongodb')
mongo_manager = MongoDBManager()


# ============================================
# Colecciones disponibles
# Base de datos: comerciotech
# Colecciones: stock_quotes, stock_history
# ============================================

@mongodb_bp.route('/collections', methods=['GET'])
def get_collections():
    """Obtiene todas las colecciones disponibles"""
    collections = mongo_manager.get_collections()
    if collections is None:
        return jsonify({'error': 'No se pudo conectar a MongoDB'}), 500
    return jsonify({'success': True, 'data': collections}), 200


# ============================================
# Endpoints específicos para stock_quotes
# ============================================

@mongodb_bp.route('/stock_quotes', methods=['GET'])
def get_all_quotes():
    """Obtiene todas las cotizaciones actuales"""
    documents = mongo_manager.get_all_documents('stock_quotes')
    if documents is None:
        return jsonify({'error': 'Error al obtener cotizaciones'}), 500
    return jsonify({'success': True, 'data': documents}), 200


@mongodb_bp.route('/stock_quotes/<symbol>', methods=['GET'])
def get_quote_by_symbol(symbol):
    """Obtiene una cotización por símbolo"""
    symbol = symbol.upper()
    documents = mongo_manager.search_documents('stock_quotes', {'symbol': symbol})
    if documents and len(documents) > 0:
        return jsonify({'success': True, 'data': documents[0]}), 200
    return jsonify({'error': 'Cotización no encontrada'}), 404


@mongodb_bp.route('/stock_quotes', methods=['POST'])
@admin_required
def create_quote():
    """Crea una nueva cotización (solo admin)"""
    data = request.get_json()
    
    required = ['symbol', 'price']
    if not all(k in data for k in required):
        return jsonify({'error': 'Faltan campos requeridos: symbol, price'}), 400
    
    # Verificar si ya existe
    existing = mongo_manager.search_documents('stock_quotes', {'symbol': data['symbol'].upper()})
    if existing and len(existing) > 0:
        return jsonify({'error': 'El símbolo ya existe'}), 409
    
    data['symbol'] = data['symbol'].upper()
    doc_id = mongo_manager.insert_document('stock_quotes', data)
    if doc_id:
        return jsonify({'success': True, 'message': 'Cotización creada', 'id': doc_id}), 201
    return jsonify({'error': 'Error al crear cotización'}), 500


@mongodb_bp.route('/stock_quotes/<symbol>', methods=['PUT'])
@admin_required
def update_quote(symbol):
    """Actualiza una cotización (solo admin)"""
    data = request.get_json()
    symbol = symbol.upper()
    
    # Buscar el documento por símbolo
    existing = mongo_manager.search_documents('stock_quotes', {'symbol': symbol})
    if not existing or len(existing) == 0:
        return jsonify({'error': 'Cotización no encontrada'}), 404
    
    doc_id = existing[0]['_id']
    success = mongo_manager.update_document('stock_quotes', doc_id, data)
    if success:
        return jsonify({'success': True, 'message': 'Cotización actualizada'}), 200
    return jsonify({'error': 'Error al actualizar cotización'}), 500


@mongodb_bp.route('/stock_quotes/<symbol>', methods=['DELETE'])
@admin_required
def delete_quote(symbol):
    """Elimina una cotización (solo admin)"""
    symbol = symbol.upper()
    
    existing = mongo_manager.search_documents('stock_quotes', {'symbol': symbol})
    if not existing or len(existing) == 0:
        return jsonify({'error': 'Cotización no encontrada'}), 404
    
    doc_id = existing[0]['_id']
    success = mongo_manager.delete_document('stock_quotes', doc_id)
    if success:
        return jsonify({'success': True, 'message': 'Cotización eliminada'}), 200
    return jsonify({'error': 'Error al eliminar cotización'}), 500


# ============================================
# Endpoints específicos para stock_history
# ============================================

@mongodb_bp.route('/stock_history', methods=['GET'])
def get_all_history():
    """Obtiene todo el historial de precios"""
    limit = request.args.get('limit', 100, type=int)
    documents = mongo_manager.get_all_documents('stock_history', limit=limit)
    if documents is None:
        return jsonify({'error': 'Error al obtener historial'}), 500
    return jsonify({'success': True, 'data': documents}), 200


@mongodb_bp.route('/stock_history/<symbol>', methods=['GET'])
def get_history_by_symbol(symbol):
    """Obtiene el historial de un símbolo específico"""
    symbol = symbol.upper()
    limit = request.args.get('limit', 50, type=int)
    
    # Buscar con orden descendente por fecha
    collection = mongo_manager.get_collection('stock_history')
    if collection is None:
        return jsonify({'error': 'Error al conectar a MongoDB'}), 500
    
    cursor = collection.find({'symbol': symbol}).sort('updated_at', -1).limit(limit)
    documents = list(cursor)
    
    for doc in documents:
        doc['_id'] = str(doc['_id'])
    
    return jsonify({'success': True, 'data': documents}), 200


@mongodb_bp.route('/stock_history', methods=['POST'])
@admin_required
def create_history_record():
    """Crea un registro histórico (solo admin)"""
    data = request.get_json()
    
    required = ['symbol', 'price']
    if not all(k in data for k in required):
        return jsonify({'error': 'Faltan campos requeridos: symbol, price'}), 400
    
    data['symbol'] = data['symbol'].upper()
    doc_id = mongo_manager.insert_document('stock_history', data)
    if doc_id:
        return jsonify({'success': True, 'message': 'Registro histórico creado', 'id': doc_id}), 201
    return jsonify({'error': 'Error al crear registro histórico'}), 500


# ============================================
# Endpoints genéricos (con protección)
# ============================================

@mongodb_bp.route('/<collection>/documents', methods=['GET'])
@admin_required
def get_documents(collection):
    """Obtiene todos los documentos de una colección (solo admin)"""
    # Restringir colecciones sensibles
    if collection not in ['stock_quotes', 'stock_history']:
        return jsonify({'error': 'Colección no accesible'}), 403
    
    documents = mongo_manager.get_all_documents(collection)
    if documents is None:
        return jsonify({'error': 'Error al obtener documentos'}), 500
    return jsonify({'success': True, 'data': documents}), 200


@mongodb_bp.route('/<collection>/documents/<doc_id>', methods=['GET'])
@admin_required
def get_document(collection, doc_id):
    """Obtiene un documento específico (solo admin)"""
    if collection not in ['stock_quotes', 'stock_history']:
        return jsonify({'error': 'Colección no accesible'}), 403
    
    document = mongo_manager.get_document_by_id(collection, doc_id)
    if document is None:
        return jsonify({'error': 'Documento no encontrado'}), 404
    return jsonify({'success': True, 'data': document}), 200


@mongodb_bp.route('/<collection>/documents', methods=['POST'])
@admin_required
def create_document(collection):
    """Crea un nuevo documento (solo admin)"""
    if collection not in ['stock_quotes', 'stock_history']:
        return jsonify({'error': 'Colección no accesible'}), 403
    
    data = request.get_json()
    
    doc_id = mongo_manager.insert_document(collection, data)
    if doc_id:
        return jsonify({'success': True, 'message': 'Documento creado', 'id': doc_id}), 201
    return jsonify({'error': 'Error al crear documento'}), 500


@mongodb_bp.route('/<collection>/documents/<doc_id>', methods=['PUT'])
@admin_required
def update_document(collection, doc_id):
    """Actualiza un documento (solo admin)"""
    if collection not in ['stock_quotes', 'stock_history']:
        return jsonify({'error': 'Colección no accesible'}), 403
    
    data = request.get_json()
    
    success = mongo_manager.update_document(collection, doc_id, data)
    if success:
        return jsonify({'success': True, 'message': 'Documento actualizado'}), 200
    return jsonify({'error': 'Error al actualizar documento'}), 500


@mongodb_bp.route('/<collection>/documents/<doc_id>', methods=['DELETE'])
@admin_required
def delete_document(collection, doc_id):
    """Elimina un documento (solo admin)"""
    if collection not in ['stock_quotes', 'stock_history']:
        return jsonify({'error': 'Colección no accesible'}), 403
    
    success = mongo_manager.delete_document(collection, doc_id)
    if success:
        return jsonify({'success': True, 'message': 'Documento eliminado'}), 200
    return jsonify({'error': 'Error al eliminar documento'}), 500


@mongodb_bp.route('/<collection>/search', methods=['POST'])
@admin_required
def search_documents(collection):
    """Busca documentos con filtros (solo admin)"""
    if collection not in ['stock_quotes', 'stock_history']:
        return jsonify({'error': 'Colección no accesible'}), 403
    
    query = request.get_json()
    
    documents = mongo_manager.search_documents(collection, query)
    if documents is None:
        return jsonify({'error': 'Error al buscar documentos'}), 500
    return jsonify({'success': True, 'data': documents}), 200


# ============================================
# Endpoint de estadísticas de MongoDB
# ============================================

@mongodb_bp.route('/stats', methods=['GET'])
def get_stats():
    """Obtiene estadísticas de MongoDB"""
    stats = {
        'collections': {},
        'total_documents': 0
    }
    
    for collection_name in ['stock_quotes', 'stock_history']:
        collection = mongo_manager.get_collection(collection_name)
        if collection is not None:
            count = collection.count_documents({})
            stats['collections'][collection_name] = count
            stats['total_documents'] += count
    
    return jsonify({'success': True, 'data': stats}), 200