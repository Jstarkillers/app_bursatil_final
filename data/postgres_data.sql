-- ============================================
-- Script de inicialización de PostgreSQL
-- Sistema de Bolsa en Línea - ComercioTech
-- Base de datos: comerciotech
-- ============================================

-- Conectar a la base de datos (ejecutar manualmente)
-- \c comerciotech;

-- ============================================
-- ELIMINAR TABLAS EXISTENTES (orden correcto por FK)
-- ============================================
DROP TABLE IF EXISTS transacciones CASCADE;
DROP TABLE IF EXISTS posiciones CASCADE;
DROP TABLE IF EXISTS activos CASCADE;
DROP TABLE IF EXISTS usuarios CASCADE;

-- ============================================
-- TABLA: usuarios
-- ============================================
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    full_name VARCHAR(100),
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'user')) DEFAULT 'user',
    balance NUMERIC(15,2) DEFAULT 10000000 CHECK (balance >= 0),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- TABLA: activos (catálogo de acciones)
-- ============================================
CREATE TABLE IF NOT EXISTS activos (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100),
    market VARCHAR(50) DEFAULT 'SNGO'
);

-- ============================================
-- TABLA: transacciones (historial de compras/ventas)
-- ============================================
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
);

-- ============================================
-- TABLA: posiciones (portfolio actual por usuario)
-- ============================================
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
);

-- ============================================
-- ÍNDICES (optimización de consultas)
-- ============================================

-- Usuarios
CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username);
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);

-- Transacciones
CREATE INDEX IF NOT EXISTS idx_transacciones_user_id ON transacciones(user_id);
CREATE INDEX IF NOT EXISTS idx_transacciones_asset_id ON transacciones(asset_id);
CREATE INDEX IF NOT EXISTS idx_transacciones_created_at ON transacciones(created_at);

-- Posiciones
CREATE INDEX IF NOT EXISTS idx_posiciones_user_id ON posiciones(user_id);
CREATE INDEX IF NOT EXISTS idx_posiciones_asset_id ON posiciones(asset_id);
CREATE INDEX IF NOT EXISTS idx_posiciones_user_asset ON posiciones(user_id, asset_id);

-- Activos
CREATE INDEX IF NOT EXISTS idx_activos_symbol ON activos(symbol);

-- ============================================
-- DATOS INICIALES
-- ============================================

-- Insertar activos (acciones)
INSERT INTO activos (symbol, name, market) VALUES
    ('SONDA.SN', 'Sonda IT', 'SNGO'),
    ('ENTEL.SN', 'Empresa Nacional de Telecomunicaciones', 'SNGO'),
    ('NUAM.SN', 'nuam exchange', 'SNGO'),
    ('SQM-B.SN', 'SQM', 'SNGO'),
    ('CHILE.SN', 'Banco de Chile', 'SNGO'),
    ('ENELAM.SN', 'Enel Americas', 'SNGO'),
    ('CENCOSUD.SN', 'Cencosud', 'SNGO'),
    ('LTM.SN', 'LATAM Airlines', 'SNGO'),
    ('BCI.SN', 'Banco BCI', 'SNGO'),
    ('FALABELLA.SN', 'Falabella', 'SNGO')
ON CONFLICT (symbol) DO NOTHING;

-- Insertar usuarios de prueba (contraseñas hasheadas con werkzeug)
-- Contraseña 'admin123' -> hash generado con generate_password_hash('admin123')
-- Contraseña 'password123' -> hash generado con generate_password_hash('password123')
-- NOTA: En producción, usar generate_password_hash() desde Python

-- Usuario administrador (password: admin123)
INSERT INTO usuarios (username, email, password_hash, full_name, role, balance) VALUES (
    'admin',
    'admin@comerciotech.com',
    'scrypt:32768:8:1$KJWqoXxL3uNk5ZxV$1e4f8a2b3c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b',
    'Administrador del Sistema',
    'admin',
    10000000
) ON CONFLICT (username) DO NOTHING;

-- Usuarios normales (password: password123)
INSERT INTO usuarios (username, email, password_hash, full_name, role, balance) VALUES
    ('jgarcia', 'juan.garcia@comerciotech.com', 'scrypt:32768:8:1$XyZ5aBcDeFgHiJkL$2e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2g3h4i', 'Juan García', 'user', 10000000),
    ('mlopez', 'maria.lopez@comerciotech.com', 'scrypt:32768:8:1$XyZ5aBcDeFgHiJkL$2e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2g3h4i', 'María López', 'user', 10000000),
    ('crodriguez', 'carlos.rodriguez@comerciotech.com', 'scrypt:32768:8:1$XyZ5aBcDeFgHiJkL$2e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2g3h4i', 'Carlos Rodríguez', 'user', 10000000)
ON CONFLICT (username) DO NOTHING;

-- ============================================
-- EJEMPLO DE TRANSACCIÓN (opcional, para pruebas)
-- ============================================

-- Ejemplo: Admin compra acciones de SONDA a $415.00
-- (Esto se hace desde la aplicación, este es solo un ejemplo)

-- SELECT * FROM usuarios;
-- SELECT * FROM activos;
-- SELECT * FROM transacciones;
-- SELECT * FROM posiciones;

-- ============================================
-- VERIFICACIÓN DE DATOS
-- ============================================

-- Ver cantidad de usuarios
SELECT 'Total usuarios:' AS info, COUNT(*) AS cantidad FROM usuarios
UNION ALL
SELECT 'Usuarios admin:', COUNT(*) FROM usuarios WHERE role = 'admin'
UNION ALL
SELECT 'Usuarios normales:', COUNT(*) FROM usuarios WHERE role = 'user';

-- Ver activos cargados
SELECT 'Total activos:' AS info, COUNT(*) AS cantidad FROM activos;

-- ============================================
-- NOTAS PARA EL DESARROLLADOR
-- ============================================
-- 1. Los hashes de contraseña son ejemplos. En producción, usar:
--    from werkzeug.security import generate_password_hash
--    hash = generate_password_hash('password123')
--
-- 2. Para insertar un usuario desde Python:
--    cursor.execute("INSERT INTO usuarios (username, email, password_hash, full_name, role, balance) VALUES (%s, %s, %s, %s, %s, %s)", 
--                   (username, email, password_hash, full_name, role, balance))
--
-- 3. La tabla posiciones se actualiza automáticamente al hacer transacciones
--
-- 4. Base de datos esperada: comerciotech
--    Crearla con: CREATE DATABASE comerciotech;