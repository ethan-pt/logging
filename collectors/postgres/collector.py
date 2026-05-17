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
        logging.info("PostgreSQL Collector started...")
        try:
            self.connector.connect()
            self.serviceId = self.inserter.registerService(self.connection, self.serviceName, self.serviceType)
            if self.serviceId == -1:
                return

        except Exception as e:
            logging.error(f"Failed to connect to database: {e}")
            return

        while True:
            # Checks connection before attempting to log anything, attempting to reconnect on failure.
            if self.connector.checkConnection(self.connection):
                self.inserter.logHeartbeat(self.connection, self.serviceId, self.getHeartbeat())

                connections = self.getConnections()
                if connections != -1: # Only log active connections if we were able to get a valid count
                    self.inserter.logMetric(self.connection, self.serviceId, "active_connections", connections)

                databaseSize = self.getDatabaseSize()
                if databaseSize != -1: # Only log database size if we were able to get a valid size
                    self.inserter.logMetric(self.connection, self.serviceId, "database_size_bytes", databaseSize)
            else:
                logging.warning("Heartbeat failed, attempting to reconnect to database...")
                self.connector.disconnect(self.connection)
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
            self.connector.disconnect(self.connection)

        sys.exit(0)


if __name__ == "__main__":
    delay = 5
    while True:
        collector = None
        try:
            collector = PostgresCollector(connector=DatabaseConnector())
            collector.start()

        except KeyboardInterrupt:
            logging.info("\nShutdown signal received...")
            if collector:
                collector.stop()
            else:
                logging.error("Collector failed to initialize, shutting down...")
                sys.exit(1)

        except Exception as e:
            logging.error(f"Collector encountered an error: {e}")
            logging.info(f"Attempting to restart collector in {delay} seconds...")

            time.sleep(delay)
            delay = min(delay * 2, 600) # Exponential backoff with a max delay of 10 minutes

        else:
            delay = 5
