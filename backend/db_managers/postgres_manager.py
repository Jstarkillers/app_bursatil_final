import logging
import psycopg
import psycopg.rows
from werkzeug.security import generate_password_hash, check_password_hash
from config import (
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD,
    INITIAL_BALANCE, TRANSACTION_LIMIT_DEFAULT
)

logger = logging.getLogger(__name__)

try:
    from psycopg_pool import ConnectionPool as _ConnectionPool
    _POOL_AVAILABLE = True
except ImportError:
    _POOL_AVAILABLE = False
    logger.warning("psycopg_pool no disponible — se usarán conexiones individuales. "
                   "Instala con: pip install psycopg-pool")


class PostgresManager:
    """Gestor de PostgreSQL — Base de datos ComercioTech
    Tablas: usuarios, activos, transacciones, posiciones
    """

    def __init__(self):
        self.host = POSTGRES_HOST
        self.port = POSTGRES_PORT
        self.database = POSTGRES_DB
        self.user = POSTGRES_USER
        self.password = POSTGRES_PASSWORD
        self._conninfo = (
            f"host={self.host} port={self.port} dbname={self.database} "
            f"user={self.user} password={self.password}"
        )
        self._pool = None
        if _POOL_AVAILABLE:
            try:
                self._pool = _ConnectionPool(
                    conninfo=self._conninfo,
                    min_size=2,
                    max_size=10,
                    open=True
                )
                logger.info("Pool de conexiones PostgreSQL iniciado (min=2, max=10)")
            except Exception as e:
                logger.warning("No se pudo crear el pool de conexiones: %s. "
                               "Usando conexiones individuales.", e)
                self._pool = None

    def connect(self):
        """Conexión directa (fallback cuando el pool no está disponible)."""
        try:
            return psycopg.connect(
                host=self.host, port=self.port,
                dbname=self.database, user=self.user, password=self.password
            )
        except psycopg.Error as e:
            logger.error("Error al conectar a PostgreSQL: %s", e)
            return None

    def execute_query(self, query, params=None):
        """Ejecuta una consulta SELECT y retorna lista de dicts."""
        if self._pool:
            try:
                with self._pool.connection() as conn:
                    with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                        cursor.execute(query, params)
                        return [dict(row) for row in cursor.fetchall()]
            except Exception as e:
                logger.error("Error ejecutando query (pool): %s", e)
                return None

        # Fallback: conexión individual
        conn = self.connect()
        if not conn:
            return None
        try:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except psycopg.Error as e:
            logger.error("Error ejecutando query: %s", e)
            return None
        finally:
            conn.close()

    def execute_command(self, command, params=None):
        """Ejecuta INSERT / UPDATE / DELETE."""
        if self._pool:
            try:
                with self._pool.connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(command, params)
                return True
            except Exception as e:
                logger.error("Error ejecutando comando (pool): %s", e)
                return False

        conn = self.connect()
        if not conn:
            return False
        try:
            with conn.cursor() as cursor:
                cursor.execute(command, params)
            conn.commit()
            return True
        except psycopg.Error as e:
            logger.error("Error ejecutando comando: %s", e)
            conn.rollback()
            return False
        finally:
            conn.close()

    def execute_and_return_id(self, command, params=None):
        """Ejecuta un INSERT y retorna el ID generado."""
        if self._pool:
            try:
                with self._pool.connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(command, params)
                        cursor.execute("SELECT LASTVAL()")
                        return cursor.fetchone()[0]
            except Exception as e:
                logger.error("Error ejecutando comando con ID (pool): %s", e)
                return None

        conn = self.connect()
        if not conn:
            return None
        try:
            with conn.cursor() as cursor:
                cursor.execute(command, params)
                conn.commit()
                cursor.execute("SELECT LASTVAL()")
                return cursor.fetchone()[0]
        except psycopg.Error as e:
            logger.error("Error ejecutando comando con ID: %s", e)
            conn.rollback()
            return None
        finally:
            conn.close()

    # ========================================
    # Autenticación
    # ========================================

    def register_user(self, username, email, password, full_name,
                      balance=None, role='user'):
        if balance is None:
            balance = INITIAL_BALANCE
        password_hash = generate_password_hash(password)
        command = """
            INSERT INTO usuarios (username, email, password_hash, full_name, role, balance)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        return self.execute_command(command, (username, email, password_hash, full_name, role, balance))

    def login_user(self, username, password):
        query = "SELECT * FROM usuarios WHERE username = %s"
        results = self.execute_query(query, (username,))
        if results and len(results) > 0:
            user = results[0]
            if check_password_hash(user['password_hash'], password):
                user_data = dict(user)
                del user_data['password_hash']
                return user_data
        return None

    def user_exists(self, username, email):
        query = "SELECT id FROM usuarios WHERE username = %s OR email = %s"
        results = self.execute_query(query, (username, email))
        return results is not None and len(results) > 0

    # ========================================
    # Gestión de Usuarios
    # ========================================

    def get_all_users(self):
        query = """
            SELECT id, username, email, full_name, role, balance, created_at
            FROM usuarios ORDER BY id
        """
        return self.execute_query(query)

    def get_user_by_id(self, user_id):
        query = """
            SELECT id, username, email, full_name, role, balance, created_at
            FROM usuarios WHERE id = %s
        """
        results = self.execute_query(query, (user_id,))
        return results[0] if results else None

    def update_user(self, user_id, data):
        allowed_fields = ['username', 'email', 'full_name', 'role', 'balance']
        updates = []
        values = []

        for field in allowed_fields:
            if field in data:
                updates.append(f"{field} = %s")
                values.append(data[field])

        if not updates:
            return False

        values.append(user_id)
        query = f"UPDATE usuarios SET {', '.join(updates)} WHERE id = %s"
        return self.execute_command(query, values)

    def delete_user(self, user_id):
        command = "DELETE FROM usuarios WHERE id = %s"
        return self.execute_command(command, (user_id,))

    def get_user_count(self):
        query = "SELECT COUNT(*) as count FROM usuarios"
        results = self.execute_query(query)
        return results[0]['count'] if results else 0

    def get_user_balance(self, user_id):
        query = "SELECT balance FROM usuarios WHERE id = %s"
        results = self.execute_query(query, (user_id,))
        return results[0]['balance'] if results else None

    def update_user_balance(self, user_id, new_balance):
        command = "UPDATE usuarios SET balance = %s WHERE id = %s"
        return self.execute_command(command, (new_balance, user_id))

    # ========================================
    # Activos
    # ========================================

    def get_asset_by_symbol(self, symbol):
        query = "SELECT id, symbol, name, market FROM activos WHERE symbol = %s"
        results = self.execute_query(query, (symbol,))
        return results[0] if results else None

    def create_asset(self, symbol, name, market='SNGO'):
        command = """
            INSERT INTO activos (symbol, name, market)
            VALUES (%s, %s, %s)
            ON CONFLICT (symbol) DO NOTHING
        """
        return self.execute_command(command, (symbol, name, market))

    def get_all_activos(self):
        query = "SELECT id, symbol, name, market FROM activos ORDER BY symbol"
        return self.execute_query(query)

    # ========================================
    # Transacciones
    # ========================================

    def realizar_transaccion(self, user_id, symbol, transaction_type, quantity, price):
        """Compra o venta atómica con bloqueo FOR UPDATE sobre el balance."""
        if self._pool:
            try:
                with self._pool.connection() as conn:
                    return self._transaccion_inner(conn, user_id, symbol,
                                                   transaction_type, quantity, price)
            except Exception as e:
                logger.error("Error en transacción (pool): %s", e)
                return {'error': 'Error al procesar la transacción'}

        conn = self.connect()
        if not conn:
            return {'error': 'Error de conexión a la base de datos'}
        try:
            result = self._transaccion_inner(conn, user_id, symbol,
                                             transaction_type, quantity, price)
            if 'error' not in result:
                conn.commit()
            else:
                conn.rollback()
            return result
        except psycopg.Error as e:
            conn.rollback()
            logger.error("Error en transacción: %s", e)
            return {'error': f'Error al procesar la transacción: {str(e)}'}
        finally:
            conn.close()

    def _transaccion_inner(self, conn, user_id, symbol, transaction_type, quantity, price):
        """Lógica transaccional interna (reutilizada por pool y conexión directa)."""
        with conn.cursor() as cursor:
            # 1. Verificar/crear activo
            cursor.execute("SELECT id FROM activos WHERE symbol = %s", (symbol,))
            asset_result = cursor.fetchone()

            if not asset_result:
                cursor.execute(
                    "INSERT INTO activos (symbol, name, market) VALUES (%s, %s, %s)",
                    (symbol, symbol, 'SNGO')
                )
                cursor.execute("SELECT id FROM activos WHERE symbol = %s", (symbol,))
                asset_result = cursor.fetchone()

            asset_id = asset_result[0]
            total = quantity * price

            # 2. Obtener y bloquear balance
            cursor.execute(
                "SELECT balance FROM usuarios WHERE id = %s FOR UPDATE", (user_id,)
            )
            balance_result = cursor.fetchone()
            if not balance_result:
                return {'error': 'Usuario no encontrado'}

            current_balance = float(balance_result[0])

            if transaction_type == 'buy':
                if total > current_balance:
                    return {'error': f'Saldo insuficiente. Necesitas ${total:,.2f} CLP'}

                new_balance = current_balance - total
                cursor.execute(
                    "UPDATE usuarios SET balance = %s WHERE id = %s",
                    (new_balance, user_id)
                )
                cursor.execute(
                    """INSERT INTO posiciones (user_id, asset_id, quantity, average_price)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (user_id, asset_id) DO UPDATE
                       SET quantity = posiciones.quantity + EXCLUDED.quantity,
                           average_price = (
                               posiciones.average_price * posiciones.quantity +
                               EXCLUDED.average_price * EXCLUDED.quantity
                           ) / (posiciones.quantity + EXCLUDED.quantity),
                           updated_at = CURRENT_TIMESTAMP""",
                    (user_id, asset_id, quantity, price)
                )

            elif transaction_type == 'sell':
                cursor.execute(
                    "SELECT quantity, average_price FROM posiciones "
                    "WHERE user_id = %s AND asset_id = %s",
                    (user_id, asset_id)
                )
                position = cursor.fetchone()

                if not position or position[0] < quantity:
                    available = position[0] if position else 0
                    return {'error': f'No tienes suficientes acciones de {symbol}. '
                                     f'Disponibles: {available}'}

                new_balance = current_balance + total
                cursor.execute(
                    "UPDATE usuarios SET balance = %s WHERE id = %s",
                    (new_balance, user_id)
                )
                new_quantity = position[0] - quantity
                if new_quantity == 0:
                    cursor.execute(
                        "DELETE FROM posiciones WHERE user_id = %s AND asset_id = %s",
                        (user_id, asset_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE posiciones SET quantity = %s, updated_at = CURRENT_TIMESTAMP "
                        "WHERE user_id = %s AND asset_id = %s",
                        (new_quantity, user_id, asset_id)
                    )
            else:
                return {'error': 'Tipo de transacción inválido'}

            # 3. Registrar transacción
            cursor.execute(
                """INSERT INTO transacciones
                       (user_id, asset_id, transaction_type, quantity, price, total)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (user_id, asset_id, transaction_type, quantity, price, total)
            )
            transaction_id = cursor.fetchone()[0]

        return {
            'success': True,
            'message': f'{transaction_type.upper()} de {quantity} {symbol} completada',
            'new_balance': new_balance,
            'transaction_id': transaction_id
        }

    def get_user_transacciones(self, user_id, limit=None):
        if limit is None:
            limit = TRANSACTION_LIMIT_DEFAULT
        query = """
            SELECT t.id, t.transaction_type, t.quantity, t.price, t.total, t.created_at,
                   a.symbol, a.name
            FROM transacciones t
            JOIN activos a ON t.asset_id = a.id
            WHERE t.user_id = %s
            ORDER BY t.created_at DESC
            LIMIT %s
        """
        return self.execute_query(query, (user_id, limit))

    # ========================================
    # Posiciones
    # ========================================

    def get_user_posiciones(self, user_id):
        query = """
            SELECT p.id, p.quantity, p.average_price, p.updated_at,
                   a.symbol, a.name, a.market
            FROM posiciones p
            JOIN activos a ON p.asset_id = a.id
            WHERE p.user_id = %s
            ORDER BY a.symbol
        """
        return self.execute_query(query, (user_id,))

    # ========================================
    # Ranking
    # ========================================

    def get_ranking(self):
        query = f"""
            SELECT
                u.id,
                u.username,
                u.full_name,
                u.balance,
                COALESCE(SUM(p.quantity * p.average_price), 0) AS portfolio_value,
                u.balance + COALESCE(SUM(p.quantity * p.average_price), 0) AS total_value,
                (u.balance + COALESCE(SUM(p.quantity * p.average_price), 0))
                    - {INITIAL_BALANCE} AS pnl,
                ((u.balance + COALESCE(SUM(p.quantity * p.average_price), 0))
                    - {INITIAL_BALANCE}) / {INITIAL_BALANCE} * 100 AS pnl_percent
            FROM usuarios u
            LEFT JOIN posiciones p ON u.id = p.user_id
            GROUP BY u.id, u.username, u.full_name, u.balance
            ORDER BY total_value DESC
        """
        return self.execute_query(query)

    # ========================================
    # Estadísticas del sistema
    # ========================================

    def get_system_stats(self):
        query = """
            SELECT
                (SELECT COUNT(*) FROM usuarios)              AS total_users,
                (SELECT COUNT(*) FROM usuarios
                    WHERE role = 'admin')                    AS admin_count,
                (SELECT COUNT(*) FROM usuarios
                    WHERE role = 'user')                     AS user_count,
                (SELECT COUNT(*) FROM transacciones)         AS total_transactions,
                (SELECT COUNT(*) FROM activos)               AS total_assets,
                (SELECT SUM(balance) FROM usuarios)          AS total_balance
        """
        results = self.execute_query(query)
        return results[0] if results else None
