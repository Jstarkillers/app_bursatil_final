"""
Script para crear la base de datos comerciotech y las tablas necesarias en PostgreSQL.
Usa psycopg3 para compatibilidad con Python 3.14.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import psycopg
from werkzeug.security import generate_password_hash
from config import POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD

# ============================================
# Configuración
# ============================================
DB_NAME = 'comerciotech'  # Cambiado de 'dual_database' a 'comerciotech'

print("=" * 60)
print("  🚀 Creando Base de Datos ComercioTech")
print("=" * 60)

# ============================================
# 1. Crear la base de datos si no existe
# ============================================
print("\n[1/4] Verificando/Creando base de datos...")
try:
    conn = psycopg.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT,
        dbname='postgres', user=POSTGRES_USER,
        password=POSTGRES_PASSWORD, autocommit=True
    )
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
    if cur.fetchone():
        print(f"   ✓ La base de datos '{DB_NAME}' ya existe")
    else:
        cur.execute(f'CREATE DATABASE "{DB_NAME}"')
        print(f"   ✓ Base de datos '{DB_NAME}' creada")
    conn.close()
except Exception as e:
    print(f"   ✗ Error al crear la BD: {e}")
    sys.exit(1)

# ============================================
# 2. Crear tablas
# ============================================
print("\n[2/4] Creando tablas...")
try:
    conn2 = psycopg.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT,
        dbname=DB_NAME, user=POSTGRES_USER,
        password=POSTGRES_PASSWORD, autocommit=True
    )
    cur2 = conn2.cursor()

    # --- Tabla: usuarios ---
    cur2.execute("""
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
    cur2.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username)")
    cur2.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email)")
    print("   ✓ Tabla 'usuarios' creada")

    # --- Tabla: activos ---
    cur2.execute("""
        CREATE TABLE IF NOT EXISTS activos (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL UNIQUE,
            name VARCHAR(100),
            market VARCHAR(50) DEFAULT 'SNGO'
        )
    """)
    cur2.execute("CREATE INDEX IF NOT EXISTS idx_activos_symbol ON activos(symbol)")
    print("   ✓ Tabla 'activos' creada")

    # --- Tabla: transacciones ---
    cur2.execute("""
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
    cur2.execute("CREATE INDEX IF NOT EXISTS idx_transacciones_user_id ON transacciones(user_id)")
    cur2.execute("CREATE INDEX IF NOT EXISTS idx_transacciones_asset_id ON transacciones(asset_id)")
    print("   ✓ Tabla 'transacciones' creada")

    # --- Tabla: posiciones ---
    cur2.execute("""
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
    cur2.execute("CREATE INDEX IF NOT EXISTS idx_posiciones_user_id ON posiciones(user_id)")
    cur2.execute("CREATE INDEX IF NOT EXISTS idx_posiciones_asset_id ON posiciones(asset_id)")
    print("   ✓ Tabla 'posiciones' creada")

except Exception as e:
    print(f"   ✗ Error creando tablas: {e}")
    sys.exit(1)

# ============================================
# 3. Insertar activos (acciones disponibles)
# ============================================
print("\n[3/4] Insertando activos (acciones)...")
try:
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
    
    inserted = 0
    for symbol, name, market in activos:
        cur2.execute(
            """INSERT INTO activos (symbol, name, market)
               VALUES (%s, %s, %s)
               ON CONFLICT (symbol) DO NOTHING""",
            (symbol, name, market)
        )
        if cur2.rowcount:
            inserted += 1
    
    print(f"   ✓ {inserted} activos insertados")

except Exception as e:
    print(f"   ✗ Error insertando activos: {e}")

# ============================================
# 4. Insertar usuarios por defecto
# ============================================
print("\n[4/4] Insertando usuarios por defecto...")
try:
    DEFAULT_USERS = [
        ("admin", "admin@comerciotech.com", "admin123", "Administrador Sistema", "admin", 10000000),
        ("jgarcia", "juan.garcia@comerciotech.com", "password123", "Juan Garcia", "user", 10000000),
        ("mlopez", "maria.lopez@comerciotech.com", "password123", "Maria Lopez", "user", 10000000),
        ("crodriguez", "carlos.rodriguez@comerciotech.com", "password123", "Carlos Rodriguez", "user", 10000000),
        ("amartinez", "ana.martinez@comerciotech.com", "password123", "Ana Martinez", "user", 10000000),
        ("psanchez", "pedro.sanchez@comerciotech.com", "password123", "Pedro Sanchez", "user", 10000000),
    ]
    
    inserted = 0
    for username, email, password, full_name, role, balance in DEFAULT_USERS:
        ph = generate_password_hash(password)
        cur2.execute(
            """INSERT INTO usuarios (username, email, password_hash, full_name, role, balance)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (username) DO NOTHING""",
            (username, email, ph, full_name, role, balance)
        )
        if cur2.rowcount:
            inserted += 1
    
    print(f"   ✓ {inserted} usuarios insertados")
    
    # Mostrar usuarios disponibles
    cur2.execute("SELECT username, role, balance FROM usuarios ORDER BY id")
    rows = cur2.fetchall()
    
    print("\n" + "=" * 60)
    print("  📋 USUARIOS DISPONIBLES")
    print("=" * 60)
    print(f"  {'Usuario':<20} {'Contraseña':<15} {'Rol':<10} {'Saldo':>15}")
    print("  " + "-" * 60)
    for row in rows:
        pw = "admin123" if row[1] == "admin" else "password123"
        balance_str = f"${row[2]:,.0f}" if row[2] else "$0"
        print(f"  {row[0]:<20} {pw:<15} {row[1]:<10} {balance_str:>15}")
    
    conn2.close()
    
except Exception as e:
    print(f"   ✗ Error insertando usuarios: {e}")
    sys.exit(1)

# ============================================
# Resumen final
# ============================================
print("\n" + "=" * 60)
print("  ✅ INICIALIZACIÓN COMPLETADA")
print("=" * 60)
print(f"  📊 Base de datos: {DB_NAME}")
print(f"  📁 Tablas creadas: usuarios, activos, transacciones, posiciones")
print(f"  🏦 Activos disponibles: {len(activos)}")
print(f"  👥 Usuarios registrados: {len(DEFAULT_USERS)}")
print("\n  🌐 Inicia el servidor:")
print("     cd backend")
print("     python app.py")
print("\n  🔗 Abre en tu navegador:")
print("     http://localhost:5000")
print("=" * 60)