from flask import Flask, jsonify, send_from_directory, request, session
from flask_cors import CORS
import os
import re
import logging
import threading
from datetime import datetime, timedelta
from config import DEBUG, SECRET_KEY, setup_logging
from routes.postgres_routes import postgres_bp
from routes.mongodb_routes import mongodb_bp
from routes.stock_routes import stock_bp

# Inicializar logging antes de cualquier otra cosa
setup_logging()
logger = logging.getLogger(__name__)

try:
    import requests as http_req
except ImportError:
    http_req = None

app = Flask(__name__)
app.config['DEBUG'] = DEBUG
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SESSION_COOKIE_SECURE'] = not DEBUG
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

CORS(app, supports_credentials=True, origins=['http://localhost:5000', 'http://127.0.0.1:5000'])

# ================================================
# Almacenamiento en memoria de visitantes
# ================================================
_visitor_log = []
_unique_ips = {}
_SKIP_PATHS = {'/favicon.ico', '/api/visitors', '/api/fingerprint'}


def _get_real_ip():
    for header in ('X-Forwarded-For', 'X-Real-IP', 'CF-Connecting-IP'):
        val = request.headers.get(header, '')
        if val:
            return val.split(',')[0].strip()
    return request.remote_addr or '0.0.0.0'


def _parse_ua(ua):
    ua_l = ua.lower()

    if 'iphone' in ua_l:
        device = '📱 iPhone'
    elif 'android' in ua_l and 'mobile' in ua_l:
        device = '📱 Android Móvil'
    elif 'android' in ua_l:
        device = '📟 Android Tablet'
    elif 'ipad' in ua_l:
        device = '📟 iPad'
    else:
        device = '🖥️  Desktop'

    if 'windows nt 10' in ua_l or 'windows nt 11' in ua_l:
        os_name = 'Windows 10/11'
    elif 'windows nt 6.3' in ua_l:
        os_name = 'Windows 8.1'
    elif 'windows nt 6.1' in ua_l:
        os_name = 'Windows 7'
    elif 'mac os x' in ua_l:
        os_name = 'macOS'
    elif 'android' in ua_l:
        v = re.search(r'android (\d+\.?\d*)', ua_l)
        os_name = f"Android {v.group(1)}" if v else 'Android'
    elif 'iphone os' in ua_l:
        v = re.search(r'iphone os (\d+_\d+)', ua_l)
        os_name = f"iOS {v.group(1).replace('_', '.')}" if v else 'iOS'
    elif 'cros' in ua_l:
        os_name = 'ChromeOS'
    elif 'linux' in ua_l:
        os_name = 'Linux'
    else:
        os_name = 'Desconocido'

    if 'edg/' in ua_l:
        browser = 'Microsoft Edge'
    elif 'opr/' in ua_l or 'opera' in ua_l:
        browser = 'Opera'
    elif 'chrome/' in ua_l:
        browser = 'Chrome'
    elif 'firefox/' in ua_l:
        browser = 'Firefox'
    elif 'safari/' in ua_l:
        browser = 'Safari'
    elif 'curl' in ua_l:
        browser = 'cURL'
    elif 'python' in ua_l:
        browser = 'Python/Bot'
    else:
        browser = 'Desconocido'

    return device, os_name, browser


def _geolocate_async(ip):
    if not http_req or ip in ('127.0.0.1', '::1'):
        return
    try:
        r = http_req.get(
            f'http://ip-api.com/json/{ip}',
            params={'fields': 'country,regionName,city,isp,org,lat,lon,timezone,mobile,proxy,hosting'},
            timeout=4
        )
        if r.status_code == 200 and ip in _unique_ips:
            _unique_ips[ip]['geo'] = r.json()
    except Exception:
        pass


# ================================================
# Middleware: registrar cada request
# ================================================
@app.before_request
def track_visitor():
    path = request.path
    if any(path.startswith(s) for s in _SKIP_PATHS):
        return

    ip = _get_real_ip()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ua = request.headers.get('User-Agent', 'Desconocido')[:200]
    device, os_name, browser = _parse_ua(ua)

    lang = request.headers.get('Accept-Language', '-')[:60]
    referer = request.headers.get('Referer', '-')[:120]
    dnt = request.headers.get('DNT', '-')
    via = request.headers.get('Via', '-')

    entry = {
        'ip': ip, 'timestamp': now_str, 'method': request.method,
        'path': path, 'device': device, 'os': os_name, 'browser': browser,
        'language': lang, 'referer': referer, 'dnt': dnt, 'via': via,
        'user_agent': ua,
    }
    _visitor_log.append(entry)

    if ip not in _unique_ips:
        _unique_ips[ip] = {
            'first_seen': now_str, 'last_seen': now_str, 'hits': 1,
            'device': device, 'os': os_name, 'browser': browser,
            'language': lang, 'via': via, 'user_agent': ua,
            'geo': {}, 'fingerprint': {},
        }
        threading.Thread(target=_geolocate_async, args=(ip,), daemon=True).start()
    else:
        rec = _unique_ips[ip]
        rec['last_seen'] = now_str
        rec['hits'] += 1
        rec['device'] = device
        rec['os'] = os_name
        rec['browser'] = browser
        rec['language'] = lang


# ================================================
# Endpoint: fingerprint
# ================================================
@app.route('/api/fingerprint', methods=['POST'])
def receive_fingerprint():
    ip = _get_real_ip()
    data = request.get_json(silent=True) or {}
    fp = {
        'webrtc_ips': data.get('webrtc_ips', 'N/A'),
        'audio_hash': data.get('audio_hash', 'N/A'),
        'plugins': data.get('plugins', 'N/A'),
        'languages': data.get('languages', '-'),
        'screen': data.get('screen', '-'),
        'timezone': data.get('timezone', '-'),
        'platform': data.get('platform', '-'),
        'touch': data.get('touch', False),
        'isBrave': data.get('isBrave', False),
        'dnt': data.get('doNotTrack', '0'),
        'webgl_vendor': data.get('webglVendor', '-'),
        'webgl_renderer': data.get('webglRenderer', '-'),
        'canvas_hash': data.get('canvasHash', '-'),
        'memory_gb': data.get('memoryGB', '-'),
        'cpu_cores': data.get('cpuCores', '-'),
        'received_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    if ip in _unique_ips:
        _unique_ips[ip]['fingerprint'] = fp
    return jsonify({'ok': True}), 200


# ================================================
# Endpoint: visitantes (solo localhost)
# ================================================
@app.route('/api/visitors', methods=['GET'])
def get_visitors():
    caller_ip = _get_real_ip()
    if caller_ip not in ('127.0.0.1', '::1'):
        return jsonify({'error': 'Acceso restringido al servidor local'}), 403

    visitors = [
        {'ip': ip, **data}
        for ip, data in sorted(_unique_ips.items(), key=lambda x: x[1]['hits'], reverse=True)
    ]
    return jsonify({
        'total_requests': len(_visitor_log),
        'unique_ips': len(_unique_ips),
        'visitors': visitors,
        'recent_log': _visitor_log[-100:],
    }), 200


# ================================================
# Blueprints y archivos estáticos
# ================================================
app.register_blueprint(postgres_bp)
app.register_blueprint(mongodb_bp)
app.register_blueprint(stock_bp)


@app.route('/')
def serve_index():
    frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    return send_from_directory(frontend_path, 'index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    return send_from_directory(frontend_path, filename)


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'message': 'Servidor activo',
        'database': 'comerciotech',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.errorhandler(404)
def not_found(_e):
    return jsonify({'error': 'Recurso no encontrado'}), 404


@app.errorhandler(500)
def internal_error(e):
    logger.error("Error interno del servidor: %s", e)
    return jsonify({'error': 'Error interno del servidor'}), 500


if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("Servidor NEXO BOLSA - ComercioTech")
    logger.info("=" * 50)
    logger.info("PostgreSQL DB: comerciotech")
    logger.info("MongoDB DB:    comerciotech")
    logger.info("Puerto:        5000")
    logger.info("Debug mode:    %s", DEBUG)
    logger.info("=" * 50)
    logger.info("Servidor iniciado. Accede en: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=DEBUG)
