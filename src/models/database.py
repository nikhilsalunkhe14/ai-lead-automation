"""
Database Layer - MongoDB Connection and Operations
Professional database abstraction layer
"""

import os
import logging
from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, OperationFailure
from src.config.settings import settings

class DatabaseManager:
    """Professional database manager with connection pooling and error handling"""
    
    def __init__(self):
        self.client = None
        self.database = None
        self.collections = {}
        self._connected = False
    
    def connect(self):
        """Establish MongoDB connection with retry logic"""
        try:
            config = settings.get_database_config()
            
            self.client = MongoClient(
                config['uri'],
                serverSelectionTimeoutMS=config['timeout'],
                maxPoolSize=config['max_pool_size'],
                minPoolSize=config['min_pool_size'],
                retryWrites=True,
                w='majority'
            )
            
            # Test connection
            self.client.admin.command('ping')
            
            self.database = self.client[config['db_name']]
            self._connected = True
            
            logging.info(f"✅ Successfully connected to MongoDB: {config['db_name']}")
            return True
            
        except ConnectionFailure as e:
            logging.error(f"❌ MongoDB Connection Error: {e}")
            return False
        except ServerSelectionTimeoutError as e:
            logging.error(f"❌ MongoDB Timeout Error: {e}")
            return False
        except Exception as e:
            logging.error(f"❌ MongoDB Error: {e}")
            return False
    
    def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            self._connected = False
            logging.info("🔌 MongoDB connection closed")
    
    def is_connected(self):
        """Check if database is connected"""
        return self._connected
    
    def get_collection(self, collection_name):
        """Get or create a collection with error handling"""
        if not self._connected:
            logging.error("❌ Database not connected")
            return None
        
        try:
            if collection_name not in self.collections:
                self.collections[collection_name] = self.database[collection_name]
            return self.collections[collection_name]
        except Exception as e:
            logging.error(f"❌ Error accessing collection {collection_name}: {e}")
            return None
    
    def create_indexes(self):
        """Create database indexes for performance"""
        try:
            # Leads collection indexes
            leads_collection = self.get_collection('leads')
            if leads_collection:
                leads_collection.create_index([("email", 1)], unique=True)
                leads_collection.create_index([("created_at", -1)])
                leads_collection.create_index([("status", 1)])
            
            # Admins collection indexes
            admins_collection = self.get_collection('admins')
            if admins_collection:
                admins_collection.create_index([("username", 1)], unique=True)
                admins_collection.create_index([("email", 1)], unique=True)
                admins_collection.create_index([("created_at", -1)])
            
            # Chat history collection indexes
            chat_collection = self.get_collection('chat_history')
            if chat_collection:
                chat_collection.create_index([("session_id", 1)])
                chat_collection.create_index([("timestamp", -1)])
            
            # Summaries collection indexes
            summaries_collection = self.get_collection('summaries')
            if summaries_collection:
                summaries_collection.create_index([("lead_id", 1)])
                summaries_collection.create_index([("created_at", -1)])
            
            logging.info("✅ Database indexes created successfully")
            return True
            
        except Exception as e:
            logging.error(f"❌ Error creating indexes: {e}")
            return False
    
    def health_check(self):
        """Perform database health check"""
        try:
            if not self._connected:
                return False
            
            # Test database connectivity
            self.database.command('ping')
            
            # Test collection access
            test_collection = self.get_collection('health_check')
            test_collection.insert_one({'test': datetime.now(timezone.utc)})
            test_collection.delete_one({'test': {'$exists': True}})
            
            return True
            
        except Exception as e:
            logging.error(f"❌ Database health check failed: {e}")
            return False

# Global database manager instance
db_manager = DatabaseManager()

def init_database():
    """Initialize database connection"""
    success = db_manager.connect()
    if success:
        db_manager.create_indexes()
    return success

def get_db():
    """Get database manager instance"""
    return db_manager

def get_collection(collection_name):
    """Get collection from database manager"""
    return db_manager.get_collection(collection_name)
