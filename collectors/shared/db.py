import os
import sys
import time
import psycopg
import logging


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


class DatabaseConnector:
    def __init__(self, retries=5):
        self.retries = retries

        self.dbUser = os.getenv("POSTGRES_USER")
        self.dbPassword = os.getenv("POSTGRES_PASSWORD")
        self.dbName = os.getenv("POSTGRES_DB")
        self.dbHost = os.getenv("POSTGRES_HOST")

        self.connection = None

    def connect(self):
        for i in range(self.retries):
            try:
                self.connection = psycopg.connect(
                    host=self.dbHost,
                    dbname=self.dbName,
                    user=self.dbUser,
                    password=self.dbPassword
                )

                logging.info("Connected to PostgreSQL database successfully.")
                return 
            except Exception as e:
                logging.error(f"Failed to connect to PostgreSQL database with exception: {e}\nRetrying in 5 seconds... ({i + 1}/{self.retries})")
                
                time.sleep(5)
        
        logging.error("Exceeded maximum retries. Shutting down...")
        sys.exit(1)
    
    def checkConnection(self):
        try:
            with self.connection.cursor() as cur:
                cur.execute("SELECT 1")

                return True
        except Exception as e:
            logging.error(f"Database connection check failed with exception: {e}")
            return False