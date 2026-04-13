import sys
import time
import logging

from shared.db import DatabaseConnector, DatabaseInserter


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


class PostgresCollector:
    def __init__(self, connector, interval: int = 10):
        self.interval = interval

        self.connector = connector
        self.connection = connector.connection
        self.inserter = DatabaseInserter()

        self.serviceId = None
        self.serviceName = 'postgres'
        self.serviceType = 'database'

    def start(self) -> None:
        logging.info("PostgreSQL Collector started. Registering service in metadata...")

        self.serviceId = self.inserter.registerService(self.connector, self.serviceName, self.serviceType)
        if self.serviceId == -1: # I used -1 as an error code for failed registration, allowing collector to handle resolve/shutdown logic
            return

        while True:
            # Checks connection before attempting to log anything, attempting to reconnect on failure.
            if self.connector.checkConnection():
                self.inserter.logHeartbeat(self.connector.connection, self.serviceId, self.getHeartbeat())

                if self.getConnections() != -1: # Only log active connections if we were able to get a valid count
                    self.inserter.logMetric(self.connector.connection, self.serviceId, "active_connections", self.getConnections())

                if self.getDatabaseSize() != -1: # Only log database size if we were able to get a valid size
                    self.inserter.logMetric(self.connector.connection, self.serviceId, "database_size_bytes", self.getDatabaseSize())
            else:
                logging.warning("Heartbeat failed, attempting to reconnect to database...")
                self.connector.connect()
                self.connection = self.connector.connection

            time.sleep(self.interval)

    def getHeartbeat(self) -> bool:
        try:
            with self.connection.cursor() as cur:
                cur.execute("SELECT 1")

            return True
        except Exception as e:
            logging.error(f"Error checking database heartbeat: {e}")

            return False

    def getConnections(self) -> int:
        try:
            with self.connection.cursor() as cur:
                cur.execute("SELECT count(*) FROM pg_stat_activity")
                count = cur.fetchone()[0]

            return count
        except Exception as e:
            logging.error(f"Error checking database connections: {e}")

            return -1
    
    def getDatabaseSize(self) -> int:
        try:
            with self.connection.cursor() as cur:
                cur.execute("SELECT pg_database_size(current_database())")
                size = cur.fetchone()[0]

            return size
        except Exception as e:
            logging.error(f"Error checking database size: {e}")

            return -1

    def stop(self) -> None:
        logging.info("Shutting down PostgreSQL Collector...")

        if self.connection:
            self.connection.close()

        sys.exit(0)


if __name__ == "__main__":
    try:
        db_connector = DatabaseConnector()
        db_connector.connect()
    except Exception as e:
        logging.error(f"Critical Error: Could not connect to database on startup: {e}")
        sys.exit(1)

    collector = None
    try:
        collector = PostgresCollector(connector=db_connector)
        collector.start()
    except KeyboardInterrupt:
        logging.info("\nShutdown signal received...")
    finally:
        if collector:
            collector.stop()
        else:
            logging.error("Collector failed to initialize, shutting down...")
            sys.exit(1)
