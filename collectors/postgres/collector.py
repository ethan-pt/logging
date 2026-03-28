import sys
import psycopg
import os
import time
import logging

from shared.db import DatabaseConnector


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


class PostgresCollector:
    def __init__(self, connector, interval: int = 10):
        self.interval = interval

        self.connector = connector
        self.connection = connector.connection

        self.serviceId = None
        self.serviceName = 'postgres'
        self.serviceType = 'database'

    def start(self) -> None:
        logging.info("PostgreSQL Collector started. Registering service in metadata...")

        try:
            cur = self.connection.cursor()
            cur.execute("""
                INSERT INTO metadata.service (service_name, service_type)
                VALUES (%s, %s)
                ON CONFLICT (service_name) DO UPDATE 
                SET service_name = EXCLUDED.service_name
                RETURNING id
            """, (self.serviceName, self.serviceType))
            row = cur.fetchone()
            self.serviceId = row[0]
            self.connection.commit()

            logging.info(f"Service registered with ID: {self.serviceId}")
        except Exception as e:
            logging.error(f"Error registering service: {e}")
            sys.exit(1)

        while True:
            # Logs heartbeat, attempting to reconnect if it fails. 
            if self.checkHeartbeat():
                with self.connection.cursor() as cur:
                    cur.execute("""
                        INSERT INTO monitoring.heartbeat (service_id, status, timestamp)
                        VALUES (%s, %s, clock_timestamp())
                        RETURNING id
                    """, (self.serviceId, "active"))

                    heartbeatId = cur.fetchone()[0]
                    if heartbeatId % 5 == 0:
                        logging.info("Committing heartbeat buffer to database...")

                        self.connection.commit()
            else:
                self.connector.connect()
                self.connection = self.connector.connection
            
            # Logs active connections to database, attempting to reconnect if it fails.
            activeConnections = self.checkConnections()
            if activeConnections is not None:
                with self.connection.cursor() as cur:
                    cur.execute("""
                        INSERT INTO monitoring.metrics (service_id, metric_name, metric_value, timestamp)
                        VALUES (%s, %s, %s, clock_timestamp())
                        RETURNING id
                    """, (self.serviceId, "active_connections", activeConnections))

                    connectionsId = cur.fetchone()[0]
                    if connectionsId % 5 == 0:
                        logging.info("Committing connections buffer to database...")

                        self.connection.commit()
            else:
                self.connector.connect()
                self.connection = self.connector.connection

            # Logs database size, attempting to reconnect if it fails.
            databaseSize = self.checkDatabaseSize()
            if databaseSize is not None:
                with self.connection.cursor() as cur:
                    cur.execute("""
                        INSERT INTO monitoring.metrics (service_id, metric_name, metric_value, timestamp)
                        VALUES (%s, %s, %s, clock_timestamp())
                        RETURNING id
                    """, (self.serviceId, "database_size_bytes", databaseSize))

                    sizeId = cur.fetchone()[0]
                    if sizeId % 5 == 0:
                        logging.info("Committing database size buffer to database...")

                        self.connection.commit()
            else:
                self.connector.connect()
                self.connection = self.connector.connection

            time.sleep(self.interval)

    def checkHeartbeat(self):
        try:
            with self.connection.cursor() as cur:
                cur.execute("SELECT 1")

            return True
        except Exception as e:
            logging.error(f"Error checking database heartbeat: {e}")

            return False

    def checkConnections(self) -> int:
        try:
            with self.connection.cursor() as cur:
                cur.execute("SELECT count(*) FROM pg_stat_activity")
                count = cur.fetchone()[0]

            return count
        except Exception as e:
            logging.error(f"Error checking database connections: {e}")

            return -1
    
    def checkDatabaseSize(self) -> int:
        try:
            with self.connection.cursor() as cur:
                cur.execute("SELECT pg_database_size(current_database())")
                size = cur.fetchone()[0]

            return size
        except Exception as e:
            logging.error(f"Error checking database size: {e}")

            return -1

    def stop(self) -> None:
        if self.connection:
            self.connection.close()

        sys.exit(0)


if __name__ == "__main__":
    try:
        db_connector = DatabaseConnector()
        db_connector.connect()

        collector = PostgresCollector(connector=db_connector)
    except Exception as e:
        logging.error(f"Critical Error: Could not connect to database on startup: {e}")
        sys.exit(1)

    try:
        collector.start()
    except KeyboardInterrupt:
        logging.info("\nShutdown signal received...")
    finally:
        collector.stop()
