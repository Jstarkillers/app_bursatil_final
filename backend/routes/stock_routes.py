from flask import Blueprint, jsonify, request
from db_managers.mongodb_manager import MongoDBManager
import requests as http_requests
from datetime import datetime, timedelta
import config

stock_bp = Blueprint('stocks', __name__, url_prefix='/api/stocks')
mongo_manager = MongoDBManager()

# ============================================
# Acciones de monitoreo de la Bolsa de Santiago
# Base de datos: comerciotech
# Colecciones: stock_quotes (actual), stock_history (histórico)
# ============================================

STOCK_SYMBOLS = [
    'BSANTANDER', 'CFIETFUSA', 'CFINASDAQ', 'CHILE', 'ENELGXCH',
    'ENTEL', 'SONDA', 'CGE', 'MOLYMET', 'EISA'
]

STOCK_NAMES = {
    'BSANTANDER': 'Banco Santander',
    'CFIETFUSA': 'ETF USA',
    'CFINASDAQ': 'ETF NASDAQ',
    'CHILE': 'Banco de Chile',
    'ENELGXCH': 'Enel Generación Chile',
    'ENTEL': 'Entel Chile',
    'SONDA': 'Sonda IT',
    'CGE': 'CGE',
    'MOLYMET': 'Molymet',
    'EISA': 'EISA'
}


@stock_bp.route('', methods=['GET'])
def get_stocks():
    """Obtiene todas las acciones almacenadas en MongoDB (stock_quotes)"""
    documents = mongo_manager.get_all_documents('stock_quotes')
    if documents is None:
        return jsonify({'error': 'Error al obtener datos de acciones'}), 500
    return jsonify({'success': True, 'data': documents}), 200


@stock_bp.route('/history', methods=['GET'])
def get_stock_history():
    """Obtiene el historial completo de todas las acciones"""
    symbol = request.args.get('symbol')
    limit = int(request.args.get('limit', 100))
    
    if symbol:
        query = {'symbol': symbol.upper()}
    else:
        query = {}
    
    documents = mongo_manager.search_documents('stock_history', query, limit=limit)
    if documents is None:
        return jsonify({'error': 'Error al obtener historial'}), 500
    return jsonify({'success': True, 'data': documents}), 200


@stock_bp.route('/sync', methods=['POST'])
def fetch_stocks():
    """Obtiene datos de acciones desde la Bolsa de Santiago y los guarda en MongoDB
       - Actualiza stock_quotes (precios actuales)
       - Guarda histórico en stock_history
    """
    updated = []
    errors = []
    history_saved = 0

    # Validar tiempo desde la última actualización (30 minutos)
    collection = mongo_manager.get_collection('stock_quotes')
    if collection is not None:
        latest_doc = collection.find_one(sort=[("updated_at", -1)])
        if latest_doc and "updated_at" in latest_doc:
            try:
                last_update = datetime.fromisoformat(latest_doc["updated_at"])
                if datetime.utcnow() - last_update < timedelta(minutes=30):
                    return jsonify({
                        'success': False,
                        'message': f"Consulta bloqueada: Espera 30 minutos (Última: {last_update.strftime('%H:%M:%S')})"
                    }), 429
            except ValueError:
                pass

    headers = {
        "Ocp-Apim-Subscription-Key": config.BOLSA_API_KEY,
        "Accept": "application/json"
    }
    base_url = config.BOLSA_API_BASE_URL

    try:
        # Llamadas a la API de la Bolsa de Santiago
        res_inst = http_requests.get(f"{base_url}/Instrumentos", headers=headers, timeout=10)
        res_punt = http_requests.get(f"{base_url}/Puntas", headers=headers, timeout=10)

        if res_inst.status_code != 200 or res_punt.status_code != 200:
            return jsonify({
                'success': False,
                'message': 'Error de autenticación o respuesta de la API de la Bolsa.'
            }), 500

        instrumentos = res_inst.json()
        puntas = res_punt.json()

        puntas_dict = {p.get("NEMO"): p for p in puntas if isinstance(p, dict)}
        now_iso = datetime.utcnow().isoformat()

        for inst in instrumentos:
            if not isinstance(inst, dict):
                continue
            symbol = inst.get("NEMO")

            if symbol not in STOCK_SYMBOLS:
                continue

            punta = puntas_dict.get(symbol, {})

            # Obtener precio
            price = inst.get("PRE_ULT_TR", 0)
            if price == 0:
                price = punta.get("PRECIO_COMPRA", 0)

            if price == 0:
                errors.append({"symbol": symbol, "error": "No se pudo obtener precio"})
                continue

            # Buscar documento anterior para calcular cambio
            previous_doc = None
            if collection is not None:
                previous_doc = collection.find_one({"symbol": symbol})

            prev_close = previous_doc.get("price", price) if previous_doc else price
            change = round(float(price) - float(prev_close), 2)
            change_pct = round((change / float(prev_close)) * 100, 2) if prev_close != 0 else 0

            # Documento para stock_quotes (actual)
            stock_doc = {
                "symbol": symbol,
                "name": STOCK_NAMES.get(symbol, symbol),
                "price": round(float(price), 2),
                "previous_close": round(float(prev_close), 2),
                "change": change,
                "change_percent": change_pct,
                "day_high": round(float(price), 2),
                "day_low": round(float(price), 2),
                "wk52_high": round(float(price), 2),
                "wk52_low": round(float(price), 2),
                "volume": punta.get("VOLUMEN", 0),
                "currency": "CLP",
                "exchange": "SNGO",
                "market_state": "REGULAR",
                "updated_at": now_iso,
                "source": "Bolsa de Santiago API"
            }

            # Guardar en stock_quotes (actualizar o insertar)
            if collection is not None:
                collection.update_one(
                    {"symbol": symbol},
                    {"$set": stock_doc},
                    upsert=True
                )
                updated.append(symbol)

            # Guardar en stock_history (histórico)
            history_doc = {
                "symbol": symbol,
                "name": STOCK_NAMES.get(symbol, symbol),
                "price": round(float(price), 2),
                "previous_close": round(float(prev_close), 2),
                "change": change,
                "change_percent": change_pct,
                "day_high": round(float(price), 2),
                "day_low": round(float(price), 2),
                "wk52_high": round(float(price), 2),
                "wk52_low": round(float(price), 2),
                "updated_at": now_iso,
            }

            history_collection = mongo_manager.get_collection('stock_history')
            if history_collection is not None:
                history_collection.insert_one(history_doc)
                history_saved += 1

    except http_requests.exceptions.Timeout:
        errors.append({"symbol": "ALL", "error": "Timeout al conectar con la API"})
    except http_requests.exceptions.ConnectionError:
        errors.append({"symbol": "ALL", "error": "Error de conexión con la API"})
    except Exception as e:
        errors.append({"symbol": "ALL", "error": f"Error general: {str(e)}"})

    return jsonify({
        'success': len(updated) > 0,
        'updated': updated,
        'history_saved': history_saved,
        'errors': errors,
        'message': f'{len(updated)} acciones actualizadas, {history_saved} registros históricos guardados'
    }), 200


@stock_bp.route('/<symbol>', methods=['GET'])
def get_stock(symbol):
    """Obtiene datos de una acción específica desde MongoDB"""
    documents = mongo_manager.search_documents('stock_quotes', {'symbol': symbol.upper()})
    if documents and len(documents) > 0:
        return jsonify({'success': True, 'data': documents[0]}), 200
    return jsonify({'error': 'Acción no encontrada'}), 404


@stock_bp.route('/<symbol>/history', methods=['GET'])
def get_stock_history_by_symbol(symbol):
    """Obtiene el historial de una acción específica"""
    limit = int(request.args.get('limit', 100))
    documents = mongo_manager.search_documents(
        'stock_history',
        {'symbol': symbol.upper()},
        limit=limit,
        sort=[('updated_at', -1)]
    )
    if documents is None:
        return jsonify({'error': 'Error al obtener historial'}), 500
    return jsonify({'success': True, 'data': documents}), 200


@stock_bp.route('/symbols', methods=['GET'])
def get_symbols():
    """Retorna la lista de símbolos disponibles"""
    return jsonify({
        'success': True,
        'data': [{'symbol': s, 'name': STOCK_NAMES[s]} for s in STOCK_SYMBOLS]
    }), 200


@stock_bp.route('/sync/status', methods=['GET'])
def sync_status():
    """Retorna el estado de la última sincronización y cuánto falta para la próxima"""
    collection = mongo_manager.get_collection('stock_quotes')
    last_update = None
    can_sync_now = True
    minutes_remaining = 0

    if collection is not None:
        latest_doc = collection.find_one(sort=[("updated_at", -1)])
        if latest_doc and "updated_at" in latest_doc:
            try:
                last_update = datetime.fromisoformat(latest_doc["updated_at"])
                elapsed = datetime.utcnow() - last_update
                if elapsed < timedelta(minutes=30):
                    can_sync_now = False
                    minutes_remaining = int((timedelta(minutes=30) - elapsed).total_seconds() / 60)
            except ValueError:
                pass

    return jsonify({
        'success': True,
        'last_sync': last_update.isoformat() if last_update else None,
        'next_sync': (last_update + timedelta(minutes=30)).isoformat() if last_update else None,
        'minutes_remaining': minutes_remaining,
        'can_sync_now': can_sync_now
    }), 200