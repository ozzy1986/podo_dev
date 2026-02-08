"""
Database initialization module.
Exposes common repositories for ease of use.
"""

from database.repository import BaseRepository
from database.users import UserRepository

# Initialize repositories
users = UserRepository()

# Backward compatibility for existing code that uses the singleton Database class
# We will keep the old db.py for now but alias it or eventually deprecate it
# For now, this file exposes the NEW repository-based access
