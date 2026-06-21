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
        self.connection = None
        self.inserter = DatabaseInserter()

        self.serviceId = None
        self.serviceName = 'postgres'
        self.serviceType = 'database'

        self.stableSince = None

    def start(self) -> None:
        logging.info("PostgreSQL Collector started...")

        self.connection = self.connector.connect()
        self.stableSince = time.time()
        
        with self.connection.transaction(): # Register service if not registered, update if necessary
            self.serviceId = self.inserter.registerService(self.connection, self.serviceName, self.serviceType)

        while True:
            heartbeat = self.getHeartbeat()
            if heartbeat:
                connections = self.getConnections()
                databaseSize = self.getDatabaseSize()

                with self.connection.transaction():
                    self.inserter.logHeartbeat(self.connection, self.serviceId, heartbeat)

                    if connections != -1: # Only log active connections if we were able to get a valid count
                        self.inserter.logMetric(self.connection, self.serviceId, "active_connections", connections)

                    if databaseSize != -1: # Only log database size if we were able to get a valid size
                        self.inserter.logMetric(self.connection, self.serviceId, "database_size_bytes", databaseSize)
            else:
                logging.warning("Database connection failed, attempting to reconnect to database...")

                if self.connection:
                    self.connector.disconnect(self.connection)
                    self.connection = None
                self.connection = self.connector.connect()

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

        except Exception:
            if collector.stableSince is not None and time.time() - collector.stableSince >= stableThreshold:
                delay = initialDelay
                collector.stableSince = None

            logging.info(f"Attempting to restart collector in {delay} seconds...")

            time.sleep(delay)
            delay = min(delay * 2, maxDelay)

        finally:
            collector.stop()
