#!/usr/bin/env python3

import sys
import os
import requests

# Agregar backend al path para poder importar los managers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from db_managers.postgres_manager import PostgresManager
from db_managers.mongodb_manager import MongoDBManager

pm = PostgresManager()
mongo = MongoDBManager()

API_URL = "http://localhost:8000"


# =========================
# USUARIOS PostgreSQL (CRUD)
# =========================

def crear_usuario():
    print("\n--- Crear Usuario ---")
    username = input("Username: ")
    email = input("Email: ")
    password = input("Password: ")
    full_name = input("Nombre completo: ")

    if pm.user_exists(username, email):
        print("❌ Usuario o email ya existe")
        return

    if pm.register_user(username, email, password, full_name):
        print("✅ Usuario creado correctamente")
    else:
        print("❌ Error al crear usuario")


def ver_usuarios():
    print("\n--- Lista de Usuarios ---")
    usuarios = pm.get_all_users()

    if not usuarios:
        print("No hay usuarios")
        return

    for u in usuarios:
        print(f"[{u['id']}] {u['username']} | {u['email']} | Balance: {u['balance']}")


def actualizar_usuario():
    print("\n--- Actualizar Usuario ---")
    user_id = int(input("ID Usuario: "))

    data = {}
    if input("Cambiar username? (s/n): ") == "s":
        data["username"] = input("Nuevo username: ")
    if input("Cambiar email? (s/n): ") == "s":
        data["email"] = input("Nuevo email: ")
    if input("Cambiar nombre? (s/n): ") == "s":
        data["full_name"] = input("Nuevo nombre completo: ")
    if input("Cambiar rol? (s/n): ") == "s":
        data["role"] = input("Nuevo rol /user/admin): ")
    if input("Cambiar balance? (s/n): ") == "s":
        data["balance"] = float(input("Nuevo saldo: "))

    if not data:
        print("⚠️ Sin cambios")
        return

    if pm.update_user(user_id, data):
        print("✅ Usuario actualizado")
    else:
        print("❌ Error")


def eliminar_usuario():
    print("\n--- Eliminar Usuario ---")
    user_id = int(input("ID Usuario: "))

    if input("Confirmar (s/n): ") != "s":
        return

    if pm.delete_user(user_id):
        print("✅ Eliminado")
    else:
        print("❌ Error")


def ver_usuario_por_id():
    print("\n--- Buscar Usuario ---")
    user_id = int(input("ID Usuario: "))
    user = pm.get_user_by_id(user_id)

    if not user:
        print("No encontrado")
        return

    print("\nUsuario:")
    for k, v in user.items():
        print(f"{k}: {v}")


# =========================
# TRANSACCIONES
# =========================

def ejecutar_transaccion():
    print("\n--- Nueva Transacción ---")
    user_id = int(input("ID Usuario: "))
    symbol = input("Símbolo: ").upper()
    tipo = input("Tipo (buy/sell): ").lower()
    quantity = int(input("Cantidad: "))
    price = float(input("Precio: "))

    result = pm.realizar_transaccion(user_id, symbol, tipo, quantity, price)

    if 'error' in result:
        print(f"❌ {result['error']}")
    else:
        print("✅ Transacción OK")
        print(f"Nuevo balance: {result['new_balance']}")


def ver_posiciones():
    print("\n--- Posiciones ---")
    user_id = int(input("ID Usuario: "))
    posiciones = pm.get_user_posiciones(user_id)

    if not posiciones:
        print("Sin posiciones")
        return

    for p in posiciones:
        print(f"{p['symbol']} | Cantidad: {p['quantity']} | Precio Promedio: {p['average_price']}")


# =========================
# STOCKS (TIEMPO REAL)
# =========================

def actualizar_cotizaciones():
    print("\n--- Actualizando desde API ---")

    try:
        res = requests.post(f"{API_URL}/api/stocks/sync")

        data = res.json()

        if res.status_code == 200:
            print("✅ Sync OK")
            print(f"Actualizados: {len(data.get('updated', []))}")
        else:
            print("⚠️", data.get("message"))

    except Exception as e:
        print("❌ Error conexión:", e)


def ver_cotizaciones_api():
    print("\n--- Cotizaciones (API) ---")

    try:
        res = requests.get(f"{API_URL}/api/stocks")

        data = res.json().get("data", [])

        for d in data:
            print(f"{d['symbol']} | ${d['price']} | {d['change_percent']}%")

    except:
        print("❌ Error API")


def ver_cotizaciones_mongo():
    print("\n--- Cotizaciones (MongoDB) ---")

    docs = mongo.get_all_documents("stock_quotes", limit=20)

    if not docs:
        print("⚠️ No hay datos (usa opción actualizar)")
        return

    for d in docs:
        print(f"{d.get('symbol')} | {d.get('price')}")


def ver_historial():
    print("\n--- Historial de Precios ---")
    symbol = input("Símbolo: ").upper()
    docs = mongo.get_stock_history(symbol, 10)

    if not docs:
        print("Sin historial")
        return

    for d in docs:
        print(f"{d['updated_at']} | Precio: {d['price']}")


# =========================
# MENÚ
# =========================

def menu():
    while True:
        print("\n=== COMERCIOTECH CLI ===")
        print("1. Crear usuario")
        print("2. Ver usuarios")
        print("3. Ver usuario por ID")
        print("4. Actualizar usuario")
        print("5. Eliminar usuario")
        print("6. Ejecutar transacción")
        print("7. Ver posiciones")
        print("8. 🔄 Actualizar cotizaciones (API)")
        print("9. 📊 Ver cotizaciones (API)")
        print("10. 📦 Ver cotizaciones (Mongo)")
        print("11. 📈 Ver historial")
        print("0. Salir")

        op = input("Opción: ")

        if op == "1": crear_usuario()
        elif op == "2": ver_usuarios()
        elif op == "3": ver_usuario_por_id()
        elif op == "4": actualizar_usuario()
        elif op == "5": eliminar_usuario()
        elif op == "6": ejecutar_transaccion()
        elif op == "7": ver_posiciones()
        elif op == "8": actualizar_cotizaciones()
        elif op == "9": ver_cotizaciones_api()
        elif op == "10": ver_cotizaciones_mongo()
        elif op == "11": ver_historial()
        elif op == "0":
            print("Adios 👋")
            break
        else:
            print("❌ Opción inválida")


if __name__ == "__main__":
    menu()