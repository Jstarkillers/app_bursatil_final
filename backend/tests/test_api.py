"""
Tests básicos de la API NEXO BOLSA.
Ejecutar desde el directorio /backend con:
    pytest tests/ -v
"""
import sys
import os
import pytest

# Agregar backend al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app as flask_app


@pytest.fixture
def app():
    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
        'SESSION_COOKIE_SECURE': False,
    })
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# ============================================================
# Health check
# ============================================================

def test_health_ok(client):
    r = client.get('/api/health')
    assert r.status_code == 200
    data = r.get_json()
    assert data['status'] == 'ok'


# ============================================================
# Autenticación
# ============================================================

def test_login_missing_fields(client):
    r = client.post('/api/postgres/login',
                    json={'username': 'alguien'},
                    content_type='application/json')
    assert r.status_code == 400
    assert 'error' in r.get_json()


def test_login_wrong_credentials(client):
    r = client.post('/api/postgres/login',
                    json={'username': 'noexiste', 'password': 'mal'},
                    content_type='application/json')
    assert r.status_code == 401


def test_register_short_password(client):
    r = client.post('/api/postgres/register',
                    json={
                        'username': 'test_u',
                        'email': 'test@test.cl',
                        'password': '123',
                        'full_name': 'Test User'
                    },
                    content_type='application/json')
    assert r.status_code == 400
    assert 'contraseña' in r.get_json().get('error', '').lower()


def test_register_missing_fields(client):
    r = client.post('/api/postgres/register',
                    json={'username': 'test_u'},
                    content_type='application/json')
    assert r.status_code == 400


# ============================================================
# Endpoints protegidos sin sesión → 401
# ============================================================

def test_me_unauthenticated(client):
    r = client.get('/api/postgres/me')
    assert r.status_code == 401


def test_logout_unauthenticated(client):
    r = client.post('/api/postgres/logout')
    assert r.status_code == 401


def test_transaccion_unauthenticated(client):
    r = client.post('/api/postgres/transaccion',
                    json={'symbol': 'SONDA.SN', 'transaction_type': 'buy', 'quantity': 1},
                    content_type='application/json')
    assert r.status_code == 401


def test_balance_unauthenticated(client):
    r = client.get('/api/postgres/usuarios/1/balance')
    assert r.status_code == 401


def test_posiciones_unauthenticated(client):
    r = client.get('/api/postgres/usuarios/1/posiciones')
    assert r.status_code == 401


# ============================================================
# Endpoints de admin sin sesión → 401
# ============================================================

def test_usuarios_unauthenticated(client):
    r = client.get('/api/postgres/usuarios')
    assert r.status_code == 401


def test_delete_usuario_unauthenticated(client):
    r = client.delete('/api/postgres/usuarios/1')
    assert r.status_code == 401


# ============================================================
# Validación de transacción (sin sesión → 401, con sesión inválida → 400)
# ============================================================

def test_transaccion_invalid_type(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 9999
        sess['username'] = 'testuser'
        sess['role'] = 'user'

    r = client.post('/api/postgres/transaccion',
                    json={'symbol': 'SONDA.SN', 'transaction_type': 'hold', 'quantity': 1},
                    content_type='application/json')
    assert r.status_code == 400
    assert 'buy' in r.get_json().get('error', '')


def test_transaccion_invalid_quantity(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 9999
        sess['username'] = 'testuser'
        sess['role'] = 'user'

    r = client.post('/api/postgres/transaccion',
                    json={'symbol': 'SONDA.SN', 'transaction_type': 'buy', 'quantity': -5},
                    content_type='application/json')
    assert r.status_code == 400


def test_transaccion_missing_fields(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 9999
        sess['username'] = 'testuser'
        sess['role'] = 'user'

    r = client.post('/api/postgres/transaccion',
                    json={'symbol': 'SONDA.SN'},
                    content_type='application/json')
    assert r.status_code == 400


# ============================================================
# Endpoints públicos
# ============================================================

def test_activos_public(client):
    r = client.get('/api/postgres/activos')
    assert r.status_code == 200
    assert 'data' in r.get_json()


def test_ranking_public(client):
    r = client.get('/api/postgres/ranking')
    assert r.status_code == 200
    assert 'data' in r.get_json()


def test_stats_public(client):
    r = client.get('/api/postgres/stats')
    assert r.status_code == 200


def test_mongodb_quotes_public(client):
    r = client.get('/api/mongodb/stock_quotes')
    assert r.status_code in (200, 500)


def test_stocks_symbols_public(client):
    r = client.get('/api/stocks/symbols')
    assert r.status_code == 200
    data = r.get_json()
    assert 'data' in data
    assert len(data['data']) > 0


def test_visitors_restricted(client):
    r = client.get('/api/visitors')
    assert r.status_code == 403
