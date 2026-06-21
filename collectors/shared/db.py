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
    def __init__(self):
        self.dbUser = os.getenv("POSTGRES_USER")
        self.dbPassword = os.getenv("POSTGRES_PASSWORD")
        self.dbName = os.getenv("POSTGRES_DB")
        self.dbHost = os.getenv("POSTGRES_HOST")

    def connect(self) -> psycopg.Connection:
        if not all([self.dbUser, self.dbPassword, self.dbName, self.dbHost]):
            raise ValueError("Database connection parameters are not fully set.")

        connection = psycopg.connect(
            host=self.dbHost,
            dbname=self.dbName,
            user=self.dbUser,
            password=self.dbPassword,
            autocommit=True
        )

        logging.info("Connected to PostgreSQL database successfully.")
        return connection

    def checkConnection(self, connection) -> bool:
        if not connection:
            logging.warning("Attempted to check connection, but no active connection found.")

            return False
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")

                return True
        except Exception as e:
            logging.error(f"Database connection check failed with exception: {e}")
            return False
    
    def disconnect(self, connection) -> None: #TODO: Add additional cleanup (commit buffered inserts, etc) if needed before shutdown
        try:
            connection.close()
            logging.info("Disconnected from PostgreSQL database successfully.")
        except Exception as e:
            logging.error(f"Error disconnecting from PostgreSQL database: {e}")
        

class DatabaseInserter:
    def registerService(self, connection, serviceName: str, serviceType: str) -> int:
        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO metadata.service (service_name, service_type)
                    VALUES (%s, %s)
                    ON CONFLICT (service_name) DO UPDATE 
                    SET service_name = EXCLUDED.service_name,
                        service_type = EXCLUDED.service_type
                    RETURNING id
                """, (serviceName, serviceType))
                serviceId = cur.fetchone()[0]
                logging.debug(f"Successfully connected to database and registered service {serviceName} with ID: {serviceId}")
                return serviceId
        except Exception as e:
            logging.exception(f"Error registering service '{serviceName}': {e}")
            raise
    
    def logHeartbeat(self, connection, serviceId: int, active: bool) -> None:
        status = "active" if active == True else "inactive"
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO monitoring.heartbeat (service_id, status, timestamp)
                VALUES (%s, %s, clock_timestamp())
            """, (serviceId, status))

    def logMetric(self, connection, serviceId: int, metricName: str, metricValue: float) -> None:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO monitoring.metrics (service_id, metric_name, metric_value, timestamp)
                VALUES (%s, %s, %s, clock_timestamp())
            """, (serviceId, metricName, metricValue))

    def logEvent(self, connection, serviceId: int, eventType: str, eventMessage: str) -> None:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO events.service_event (service_id, event_type, message, timestamp)
                VALUES (%s, %s, %s, clock_timestamp())
                RETURNING id
            """, (serviceId, eventType, eventMessage))
            return cur.fetchone()[0]

    def logLog(self, connection, serviceId: int, logLevel: str, logMessage: str) -> None:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO logs.service_log (service_id, level, message, timestamp)
                VALUES (%s, %s, %s, clock_timestamp())
                RETURNING id
            """, (serviceId, logLevel, logMessage))

    def logAccessEvent(self, connection, serviceId: int, targetType: str, eventType: str, ipAddress: str | None, username: str | None) -> None:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO security.access_event (service_id, target_type, event_type, ip_address, username, timestamp)
                VALUES (%s, %s, %s, %s, %s, clock_timestamp())
                RETURNING id
            """, (serviceId, targetType, eventType, ipAddress, username))

    def logSession(self, connection, serviceId: int, targetType: str, username: str | None, ipAddress: str | None) -> int:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO security.session (service_id, target_type, username, ip_address, started_at)
                VALUES (%s, %s, %s, %s, clock_timestamp())
                RETURNING id
            """, (serviceId, targetType, username, ipAddress))
            sessionId = cur.fetchone()[0]
            return sessionId

    def logAction(self, connection, sessionId: int, actionType: str | None, actionDescription: str | None) -> None:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO security.action (session_id, action_type, description, timestamp)
                VALUES (%s, %s, %s, clock_timestamp())
                RETURNING id
            """, (sessionId, actionType, actionDescription))
