"""
Script para inicializar ambas bases de datos con datos de prueba.
- PostgreSQL: Tablas: usuarios, activos, transacciones, posiciones
- MongoDB: Colecciones: stock_quotes, stock_history
"""
import sys
import os

# Agregar el directorio backend al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import psycopg
from werkzeug.security import generate_password_hash
from pymongo import MongoClient
from datetime import datetime, timedelta
from config import (
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD,
    MONGODB_URI, MONGODB_DB
)

# ============================================
# Configuración
# ============================================
DB_NAME = POSTGRES_DB  # Debe ser 'comerciotech'


def seed_postgres():
    """Inicializa PostgreSQL con todas las tablas y datos de prueba"""
    print("\n🐘 Inicializando PostgreSQL...")
    print(f"   Base de datos: {DB_NAME}")

    try:
        conn = psycopg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            dbname=DB_NAME,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            autocommit=True
        )
        cur = conn.cursor()

        # ========================================
        # 1. Crear tabla: usuarios
        # ========================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                email VARCHAR(100) NOT NULL UNIQUE,
                password_hash VARCHAR(256) NOT NULL,
                full_name VARCHAR(100),
                role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'user')) DEFAULT 'user',
                balance NUMERIC(15,2) DEFAULT 10000000 CHECK (balance >= 0),
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email)")
        print("   ✓ Tabla 'usuarios' creada/verificada")

        # ========================================
        # 2. Crear tabla: activos
        # ========================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activos (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20) NOT NULL UNIQUE,
                name VARCHAR(100),
                market VARCHAR(50) DEFAULT 'SNGO'
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_activos_symbol ON activos(symbol)")
        print("   ✓ Tabla 'activos' creada/verificada")

        # ========================================
        # 3. Crear tabla: transacciones
        # ========================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transacciones (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                asset_id INTEGER NOT NULL,
                transaction_type VARCHAR(10) NOT NULL CHECK (transaction_type IN ('buy', 'sell')),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                price NUMERIC(15,2) NOT NULL CHECK (price > 0),
                total NUMERIC(15,2) NOT NULL CHECK (total > 0),
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_transacciones_user
                    FOREIGN KEY (user_id) REFERENCES usuarios(id)
                    ON DELETE CASCADE,

                CONSTRAINT fk_transacciones_asset
                    FOREIGN KEY (asset_id) REFERENCES activos(id)
                    ON DELETE RESTRICT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_transacciones_user_id ON transacciones(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_transacciones_asset_id ON transacciones(asset_id)")
        print("   ✓ Tabla 'transacciones' creada/verificada")

        # ========================================
        # 4. Crear tabla: posiciones
        # ========================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS posiciones (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                asset_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity >= 0),
                average_price NUMERIC(15,2) NOT NULL CHECK (average_price >= 0),
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_posiciones_user
                    FOREIGN KEY (user_id) REFERENCES usuarios(id)
                    ON DELETE CASCADE,

                CONSTRAINT fk_posiciones_asset
                    FOREIGN KEY (asset_id) REFERENCES activos(id)
                    ON DELETE RESTRICT,

                CONSTRAINT unique_user_asset
                    UNIQUE (user_id, asset_id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_posiciones_user_id ON posiciones(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_posiciones_asset_id ON posiciones(asset_id)")
        print("   ✓ Tabla 'posiciones' creada/verificada")

        # ========================================
        # 5. Insertar activos (acciones disponibles)
        # ========================================
        activos = [
            ("SONDA.SN", "Sonda IT", "SNGO"),
            ("ENTEL.SN", "Empresa Nacional de Telecomunicaciones", "SNGO"),
            ("NUAM.SN", "nuam exchange", "SNGO"),
            ("SQM-B.SN", "SQM", "SNGO"),
            ("CHILE.SN", "Banco de Chile", "SNGO"),
            ("ENELAM.SN", "Enel Americas", "SNGO"),
            ("CENCOSUD.SN", "Cencosud", "SNGO"),
            ("LTM.SN", "LATAM Airlines", "SNGO"),
            ("BCI.SN", "Banco BCI", "SNGO"),
            ("FALABELLA.SN", "Falabella", "SNGO"),
        ]

        activos_insertados = 0
        for symbol, name, market in activos:
            cur.execute(
                """INSERT INTO activos (symbol, name, market)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (symbol) DO NOTHING""",
                (symbol, name, market)
            )
            if cur.rowcount:
                activos_insertados += 1
        print(f"   ✓ {activos_insertados} activos insertados")

        # ========================================
        # 6. Insertar usuarios de prueba
        # ========================================
        users = [
            ("admin", "admin@comerciotech.com", "admin123", "Administrador Sistema", "admin", 10000000),
            ("jgarcia", "juan.garcia@comerciotech.com", "password123", "Juan García", "user", 10000000),
            ("mlopez", "maria.lopez@comerciotech.com", "password123", "María López", "user", 10000000),
            ("crodriguez", "carlos.rodriguez@comerciotech.com", "password123", "Carlos Rodríguez", "user", 10000000),
            ("amartinez", "ana.martinez@comerciotech.com", "password123", "Ana Martínez", "user", 10000000),
            ("psanchez", "pedro.sanchez@comerciotech.com", "password123", "Pedro Sánchez", "user", 10000000),
        ]

        usuarios_insertados = 0
        for username, email, password, full_name, role, balance in users:
            password_hash = generate_password_hash(password)
            cur.execute(
                """INSERT INTO usuarios (username, email, password_hash, full_name, role, balance) 
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (username) DO NOTHING""",
                (username, email, password_hash, full_name, role, balance)
            )
            if cur.rowcount:
                usuarios_insertados += 1

        # Mostrar usuarios insertados
        cur.execute("SELECT COUNT(*) FROM usuarios")
        count = cur.fetchone()[0]
        print(f"   ✓ {count} usuarios en la tabla (${usuarios_insertados} nuevos)")

        print("\n   📋 Credenciales de prueba:")
        print("     ┌─────────────────┬─────────────────┬───────────┐")
        print("     │ Usuario         │ Contraseña      │ Rol       │")
        print("     ├─────────────────┼─────────────────┼───────────┤")
        print("     │ admin           │ admin123        │ admin     │")
        print("     │ jgarcia         │ password123     │ user      │")
        print("     │ mlopez          │ password123     │ user      │")
        print("     │ crodriguez      │ password123     │ user      │")
        print("     │ amartinez       │ password123     │ user      │")
        print("     │ psanchez        │ password123     │ user      │")
        print("     └─────────────────┴─────────────────┴───────────┘")

        conn.close()
        print("\n   ✓ PostgreSQL inicializado correctamente")
        return True

    except Exception as e:
        print(f"   ✗ Error con PostgreSQL: {e}")
        return False


def seed_mongodb():
    """Inicializa MongoDB con datos de acciones de la bolsa"""
    print("\n🍃 Inicializando MongoDB...")
    print(f"   Base de datos: {MONGODB_DB}")

    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client[MONGODB_DB]

        # Limpiar colecciones existentes
        db.drop_collection('stock_quotes')
        db.drop_collection('stock_history')
        print("   ✓ Colecciones limpiadas: stock_quotes, stock_history")

        now_iso = datetime.utcnow().isoformat()

        # ========================================
        # Datos de acciones chilenas
        # ========================================
        stocks = [
            {
                "symbol": "SONDA.SN",
                "name": "Sonda IT",
                "price": 415.00,
                "previous_close": 410.50,
                "change": 4.50,
                "change_percent": 1.10,
                "volume": 1250000,
                "currency": "CLP",
                "exchange": "SNGO",
                "market_state": "REGULAR",
                "updated_at": now_iso,
                "source": "Datos de prueba"
            },
            {
                "symbol": "ENTEL.SN",
                "name": "Empresa Nacional de Telecomunicaciones",
                "price": 3200.00,
                "previous_close": 3250.00,
                "change": -50.00,
                "change_percent": -1.54,
                "volume": 850000,
                "currency": "CLP",
                "exchange": "SNGO",
                "market_state": "REGULAR",
                "updated_at": now_iso,
                "source": "Datos de prueba"
            },
            {
                "symbol": "NUAM.SN",
                "name": "nuam exchange",
                "price": 125.00,
                "previous_close": 123.00,
                "change": 2.00,
                "change_percent": 1.63,
                "volume": 3200000,
                "currency": "CLP",
                "exchange": "SNGO",
                "market_state": "REGULAR",
                "updated_at": now_iso,
                "source": "Datos de prueba"
            },
            {
                "symbol": "SQM-B.SN",
                "name": "SQM",
                "price": 42500.00,
                "previous_close": 41800.00,
                "change": 700.00,
                "change_percent": 1.67,
                "volume": 2100000,
                "currency": "CLP",
                "exchange": "SNGO",
                "market_state": "REGULAR",
                "updated_at": now_iso,
                "source": "Datos de prueba"
            },
            {
                "symbol": "CHILE.SN",
                "name": "Banco de Chile",
                "price": 105.50,
                "previous_close": 105.00,
                "change": 0.50,
                "change_percent": 0.48,
                "volume": 15600000,
                "currency": "CLP",
                "exchange": "SNGO",
                "market_state": "REGULAR",
                "updated_at": now_iso,
                "source": "Datos de prueba"
            },
            {
                "symbol": "ENELAM.SN",
                "name": "Enel Americas",
                "price": 102.00,
                "previous_close": 104.50,
                "change": -2.50,
                "change_percent": -2.39,
                "volume": 8900000,
                "currency": "CLP",
                "exchange": "SNGO",
                "market_state": "REGULAR",
                "updated_at": now_iso,
                "source": "Datos de prueba"
            },
            {
                "symbol": "CENCOSUD.SN",
                "name": "Cencosud",
                "price": 1680.00,
                "previous_close": 1650.00,
                "change": 30.00,
                "change_percent": 1.82,
                "volume": 3400000,
                "currency": "CLP",
                "exchange": "SNGO",
                "market_state": "REGULAR",
                "updated_at": now_iso,
                "source": "Datos de prueba"
            },
            {
                "symbol": "LTM.SN",
                "name": "LATAM Airlines",
                "price": 12.50,
                "previous_close": 12.10,
                "change": 0.40,
                "change_percent": 3.31,
                "volume": 45000000,
                "currency": "CLP",
                "exchange": "SNGO",
                "market_state": "REGULAR",
                "updated_at": now_iso,
                "source": "Datos de prueba"
            },
            {
                "symbol": "BCI.SN",
                "name": "Banco BCI",
                "price": 25400.00,
                "previous_close": 25600.00,
                "change": -200.00,
                "change_percent": -0.78,
                "volume": 1100000,
                "currency": "CLP",
                "exchange": "SNGO",
                "market_state": "REGULAR",
                "updated_at": now_iso,
                "source": "Datos de prueba"
            },
            {
                "symbol": "FALABELLA.SN",
                "name": "Falabella",
                "price": 2150.00,
                "previous_close": 2100.00,
                "change": 50.00,
                "change_percent": 2.38,
                "volume": 2800000,
                "currency": "CLP",
                "exchange": "SNGO",
                "market_state": "REGULAR",
                "updated_at": now_iso,
                "source": "Datos de prueba"
            }
        ]

        # Insertar en stock_quotes
        result = db['stock_quotes'].insert_many(stocks)
        print(f"   ✓ {len(result.inserted_ids)} acciones insertadas en stock_quotes")

        # ========================================
        # Crear historial de precios (últimos 30 días simulados)
        # ========================================
        history_count = 0
        for stock in stocks:
            symbol = stock['symbol']
            name = stock['name']
            base_price = stock['price']
            
            # Generar 30 registros históricos (1 por día)
            for day in range(30, 0, -1):
                date = datetime.utcnow() - timedelta(days=day)
                # Variación aleatoria del precio (±5%)
                import random
                variation = 1 + (random.random() - 0.5) * 0.1
                historical_price = round(base_price * variation, 2)
                historical_prev = round(historical_price * (1 + (random.random() - 0.5) * 0.05), 2)
                historical_change = round(historical_price - historical_prev, 2)
                historical_change_pct = round((historical_change / historical_prev) * 100, 2) if historical_prev != 0 else 0
                
                history_doc = {
                    "symbol": symbol,
                    "name": name,
                    "price": historical_price,
                    "previous_close": historical_prev,
                    "change": historical_change,
                    "change_percent": historical_change_pct,
                    "day_high": round(historical_price * 1.02, 2),
                    "day_low": round(historical_price * 0.98, 2),
                    "wk52_high": round(historical_price * 1.15, 2),
                    "wk52_low": round(historical_price * 0.85, 2),
                    "updated_at": date.isoformat()
                }
                db['stock_history'].insert_one(history_doc)
                history_count += 1
        
        print(f"   ✓ {history_count} registros históricos insertados en stock_history")
        print("\n   📊 Acciones disponibles:")
        symbols_list = [s['symbol'] for s in stocks]
        print(f"     {', '.join(symbols_list)}")

        client.close()
        print("\n   ✓ MongoDB inicializado correctamente")
        return True

    except Exception as e:
        print(f"   ✗ Error con MongoDB: {e}")
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Inicializando Sistema ComercioTech - Dual Database")
    print("=" * 60)
    print(f"📊 PostgreSQL DB: {DB_NAME}")
    print(f"🍃 MongoDB DB: {MONGODB_DB}")
    print("=" * 60)

    pg_ok = seed_postgres()
    mongo_ok = seed_mongodb()

    print("\n" + "=" * 60)
    print("📊 Resumen de inicialización:")
    print(f"   PostgreSQL: {'✓ OK' if pg_ok else '✗ ERROR'}")
    print(f"   MongoDB:    {'✓ OK' if mongo_ok else '✗ ERROR'}")
    print("=" * 60)

    if pg_ok and mongo_ok:
        print("\n✅ Ambas bases de datos inicializadas correctamente!")
        print("\n🚀 Para iniciar el servidor:")
        print("   cd backend")
        print("   python app.py")
        print("\n🌐 Abre en tu navegador:")
        print("   http://localhost:5000")
        print("\n🔑 Credenciales de acceso:")
        print("   Usuario: admin")
        print("   Contraseña: admin123")
    else:
        print("\n⚠️  Algunas bases de datos no pudieron ser inicializadas")
        print("   Verifica que PostgreSQL y MongoDB estén corriendo")