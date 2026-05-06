import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from config import MONGODB_URI, MONGODB_DB
from bson.objectid import ObjectId
from datetime import datetime

logger = logging.getLogger(__name__)


class MongoDBManager:
    """Gestor de MongoDB — Base de datos ComercioTech
    Colecciones: stock_quotes, stock_history
    """

    def __init__(self):
        self.uri = MONGODB_URI
        self.db_name = MONGODB_DB
        self._client = None

    def connect(self):
        try:
            client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            self._client = client
            return client
        except ConnectionFailure as e:
            logger.error("Error al conectar a MongoDB: %s", e)
            self._client = None
            return None

    def get_database(self):
        try:
            client = self.connect()
            if client is None:
                return None
            return client[self.db_name]
        except Exception as e:
            logger.error("Error obteniendo base de datos: %s", e)
            return None

    def get_collection(self, collection_name):
        try:
            db = self.get_database()
            if db is None:
                return None
            return db[collection_name]
        except Exception as e:
            logger.error("Error obteniendo colección '%s': %s", collection_name, e)
            return None

    def get_all_documents(self, collection_name, limit=1000):
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                return None
            documents = list(collection.find().limit(limit))
            for doc in documents:
                doc['_id'] = str(doc['_id'])
            return documents
        except Exception as e:
            logger.error("Error obteniendo documentos de '%s': %s", collection_name, e)
            return None

    def get_document_by_id(self, collection_name, doc_id):
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                return None
            doc = collection.find_one({'_id': ObjectId(doc_id)})
            if doc:
                doc['_id'] = str(doc['_id'])
            return doc
        except Exception as e:
            logger.error("Error obteniendo documento por ID: %s", e)
            return None

    def get_document_by_symbol(self, collection_name, symbol):
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                return None
            doc = collection.find_one({'symbol': symbol})
            if doc:
                doc['_id'] = str(doc['_id'])
            return doc
        except Exception as e:
            logger.error("Error obteniendo documento por símbolo '%s': %s", symbol, e)
            return None

    def insert_document(self, collection_name, document):
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                return None
            if 'created_at' not in document:
                document['created_at'] = datetime.utcnow().isoformat()
            result = collection.insert_one(document)
            return str(result.inserted_id)
        except Exception as e:
            logger.error("Error insertando documento en '%s': %s", collection_name, e)
            return None

    def update_document(self, collection_name, doc_id, update_data):
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                return False
            update_data['updated_at'] = datetime.utcnow().isoformat()
            result = collection.update_one(
                {'_id': ObjectId(doc_id)},
                {'$set': update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error("Error actualizando documento: %s", e)
            return False

    def update_document_by_symbol(self, collection_name, symbol, update_data):
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                return False
            update_data['updated_at'] = datetime.utcnow().isoformat()
            result = collection.update_one(
                {'symbol': symbol},
                {'$set': update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error("Error actualizando documento por símbolo '%s': %s", symbol, e)
            return False

    def upsert_document_by_symbol(self, collection_name, symbol, document):
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                return None
            document['updated_at'] = datetime.utcnow().isoformat()
            result = collection.update_one(
                {'symbol': symbol},
                {'$set': document},
                upsert=True
            )
            return result.upserted_id is not None or result.modified_count > 0
        except Exception as e:
            logger.error("Error en upsert para símbolo '%s': %s", symbol, e)
            return False

    def delete_document(self, collection_name, doc_id):
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                return False
            result = collection.delete_one({'_id': ObjectId(doc_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error("Error eliminando documento: %s", e)
            return False

    def delete_document_by_symbol(self, collection_name, symbol):
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                return False
            result = collection.delete_one({'symbol': symbol})
            return result.deleted_count > 0
        except Exception as e:
            logger.error("Error eliminando documento por símbolo '%s': %s", symbol, e)
            return False

    def search_documents(self, collection_name, query, limit=100, sort=None):
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                return None
            cursor = collection.find(query)
            if sort:
                cursor = cursor.sort(sort)
            cursor = cursor.limit(limit)
            documents = list(cursor)
            for doc in documents:
                doc['_id'] = str(doc['_id'])
            return documents
        except Exception as e:
            logger.error("Error buscando documentos en '%s': %s", collection_name, e)
            return None

    def get_collections(self):
        try:
            db = self.get_database()
            if db is None:
                return None
            return db.list_collection_names()
        except Exception as e:
            logger.error("Error obteniendo colecciones: %s", e)
            return None

    def get_collection_stats(self, collection_name):
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                return None
            return {
                'name': collection_name,
                'count': collection.count_documents({}),
                'db_name': self.db_name
            }
        except Exception as e:
            logger.error("Error obteniendo estadísticas de '%s': %s", collection_name, e)
            return None

    def get_latest_quote(self, symbol):
        """Obtiene la cotización más reciente de un símbolo desde stock_quotes."""
        try:
            collection = self.get_collection('stock_quotes')
            if collection is None:
                return None
            doc = collection.find_one({'symbol': symbol})
            if doc:
                doc['_id'] = str(doc['_id'])
            return doc
        except Exception as e:
            logger.error("Error obteniendo cotización para '%s': %s", symbol, e)
            return None

    def save_historical_price(self, symbol, name, price, previous_close,
                              change, change_percent):
        try:
            history_collection = self.get_collection('stock_history')
            if history_collection is None:
                return None
            history_doc = {
                'symbol': symbol,
                'name': name,
                'price': price,
                'previous_close': previous_close,
                'change': change,
                'change_percent': change_percent,
                'updated_at': datetime.utcnow().isoformat()
            }
            result = history_collection.insert_one(history_doc)
            return str(result.inserted_id)
        except Exception as e:
            logger.error("Error guardando histórico de '%s': %s", symbol, e)
            return None

    def get_stock_history(self, symbol, limit=100):
        try:
            collection = self.get_collection('stock_history')
            if collection is None:
                return None
            cursor = collection.find({'symbol': symbol}).sort('updated_at', -1).limit(limit)
            documents = list(cursor)
            for doc in documents:
                doc['_id'] = str(doc['_id'])
            return documents
        except Exception as e:
            logger.error("Error obteniendo historial de '%s': %s", symbol, e)
            return None
