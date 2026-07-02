import time
import logging
import psycopg

from shared.db import DatabaseConnector, DatabaseInserter
from shared.runtime import runCollector, RuntimeConfig


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


class PostgresCollector:
    collectionIntervals = ("fast",)

    def __init__(self, connector):

        self.connector = connector
        self.connection: psycopg.Connection | None = None

        self.inserter = DatabaseInserter()

        self.serviceId: int | None = None
        self.serviceName = 'PostgreSQL'
        self.serviceType = 'database'

        self.lastSuccessfulHeartbeat: float | None = None

    def initialize(self) -> None:
        self.connection = self.connector.connect()
        connection = self.getConnection()

        with connection.transaction():
            self.serviceId = self.inserter.registerService(connection, self.serviceName, self.serviceType)

    def collectFast(self) -> None:
        if not self.getHeartbeat():
            raise RuntimeError("Database heartbeat check failed.")
        elif self.serviceId is None:
            raise RuntimeError("Service ID is not set.")
        
        self.lastSuccessfulHeartbeat = time.monotonic()
        
        connection = self.getConnection()
        serviceId = self.serviceId
        metrics = {
            "active_connections": self.getDatabaseConnections(),
            "database_size_bytes": self.getDatabaseSize()
        }

        with connection.transaction():
            self.inserter.logHeartbeat(connection, serviceId, True)

            for metricName, metricValue in metrics.items():
                if metricValue is not None:
                    self.inserter.logMetric(connection, serviceId, metricName, metricValue)

    def getConnection(self) -> psycopg.Connection:
        if self.connection is None:
            raise RuntimeError("No active database connection.")
        return self.connection

    def getHeartbeat(self) -> bool:
        connection = self.getConnection()

        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")

            return True
        except psycopg.Error as e:
            logging.error(f"Error checking database heartbeat: {e}")

            return False

    def getDatabaseConnections(self) -> int | None:
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

    def stop(self) -> None:
        if self.connection:
            self.connector.disconnect(self.connection)
            self.connection = None


if __name__ == "__main__":
    config = RuntimeConfig()
    runCollector(
        factory=lambda: PostgresCollector(DatabaseConnector()),
        collectorName="PostgreSQL",
        config=config
    )
