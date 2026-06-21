import sys
import time
import logging
import psycopg.errors

from shared.db import DatabaseConnector, DatabaseInserter


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


class PostgresCollector:
    def __init__(self, connector, interval: int = 10):
        self.interval = interval

        self.connector = connector
        self.connection = None
        self.inserter = DatabaseInserter()

        self.serviceId = None
        self.serviceName = 'postgres'
        self.serviceType = 'database'

        self.stableSince = None

    def start(self) -> None:
        logging.info("PostgreSQL Collector started...")

        self.connection = self.connector.connect()
        self.stableSince = time.monotonic()
        
        with self.connection.transaction(): # Register service if not registered, update if necessary
            self.serviceId = self.inserter.registerService(self.connection, self.serviceName, self.serviceType)

        while True:
            heartbeat = self.getHeartbeat()
            if heartbeat:
                connections = self.getConnections()
                databaseSize = self.getDatabaseSize()

                with self.connection.transaction():
                    self.inserter.logHeartbeat(self.connection, self.serviceId, heartbeat)

                    if connections is not None:
                        self.inserter.logMetric(self.connection, self.serviceId, "active_connections", connections)

                    if databaseSize is not None:
                        self.inserter.logMetric(self.connection, self.serviceId, "database_size_bytes", databaseSize)
            else:
                logging.warning("Database connection failed, attempting to reconnect to database...")

                if self.connection:
                    self.connector.disconnect(self.connection)
                    self.connection = None
                self.connection = self.connector.connect()

            time.sleep(self.interval)

    def getHeartbeat(self) -> bool:
        connection = self.getConnection()

        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")

            return True
        except psycopg.Error as e:
            logging.error(f"Error checking database heartbeat: {e}")

            return False

    def getConnections(self) -> int | None:
        connection = self.getConnection()

        try:
            with connection.cursor() as cur:
                cur.execute("SELECT count(*) FROM pg_stat_activity")
                count = cur.fetchone()
                if count is None:
                    raise RuntimeError("Connection count query returned no row.")

            return count[0]
        except psycopg.Error as e:
            logging.error(f"Error checking database connections: {e}")

            return None
    
    def getDatabaseSize(self) -> int | None:
        connection = self.getConnection()

        try:
            with connection.cursor() as cur:
                cur.execute("SELECT pg_database_size(current_database())")
                size = cur.fetchone()
                if size is None:
                    raise RuntimeError("Database size query returned no row.")

            return size[0]
        except psycopg.Error as e:
            logging.error(f"Error checking database size: {e}")

            return None
        
    def getConnection(self) -> psycopg.Connection:
        if self.connection is None:
            raise RuntimeError("No active database connection.")
        return self.connection

    def stop(self) -> None:
        logging.info("Shutting down PostgreSQL Collector...")

        if self.connection:
            self.connector.disconnect(self.connection)
            self.connection = None


if __name__ == "__main__":
    initialDelay = 5
    maxDelay = 600 # 10 minutes
    stableThreshold = 300  # 5 minutes
    delay = initialDelay

    while True:
        collector = PostgresCollector(connector=DatabaseConnector())
        try:
            collector.start()

        except KeyboardInterrupt:
            logging.info("\nShutdown signal received...")
            break

        except Exception as e:
            logging.exception(f"An error occurred while running the PostgreSQL Collector: {e}")
            if collector.stableSince is not None and time.monotonic() - collector.stableSince >= stableThreshold:
                delay = initialDelay
                collector.stableSince = None

            logging.info(f"Attempting to restart collector in {delay} seconds...")

            time.sleep(delay)
            delay = min(delay * 2, maxDelay)

        finally:
            collector.stop()
