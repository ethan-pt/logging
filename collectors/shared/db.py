import os
import sys
import time
import psycopg


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

                print("Connected to PostgreSQL database successfully.")
                return 
            except Exception as e:
                print(f"Failed to connect to PostgreSQL database with exception: {e}\nRetrying in 5 seconds... ({i + 1}/{self.retries})")
                time.sleep(5)
        
        print("Exceeded maximum retries. Shutting down...")
        sys.exit(1)