import os
import psycopg
import logging


class DatabaseConnector:
    def __init__(self, connectTimeout: int = 10, statementTimeoutMs: int = 2000):
        self.dbUser = os.getenv("POSTGRES_USER")
        self.dbPassword = os.getenv("POSTGRES_PASSWORD")
        self.dbName = os.getenv("POSTGRES_DB")
        self.dbHost = os.getenv("POSTGRES_HOST")

        self.connectTimeout = connectTimeout
        self.statementTimeoutMs = statementTimeoutMs

    def connect(self) -> psycopg.Connection:
        if not all([self.dbUser, self.dbPassword, self.dbName, self.dbHost]):
            raise ValueError("Database connection parameters are not fully set.")

        connection = psycopg.connect(
            host=self.dbHost,
            dbname=self.dbName,
            user=self.dbUser,
            password=self.dbPassword,
            autocommit=True,
            connect_timeout=self.connectTimeout,
            options=f"-c statement_timeout={self.statementTimeoutMs}"
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
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO metadata.service (service_name, service_type)
                VALUES (%s, %s)
                ON CONFLICT (service_name) DO UPDATE 
                SET service_name = EXCLUDED.service_name,
                    service_type = EXCLUDED.service_type
                RETURNING id
            """, (serviceName, serviceType))
            row = cur.fetchone()

            if row is None:
                raise RuntimeError("Service registration returned no ID")
            logging.debug(f"Successfully connected to database and registered service {serviceName} with ID: {row[0]}")
            
            return row[0]
    
    def logHeartbeat(self, connection, serviceId: int, active: bool) -> None:
        status = "active" if active == True else "inactive"
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO monitoring.heartbeat (service_id, status)
                VALUES (%s, %s)
            """, (serviceId, status))

    def logMetric(self, connection, serviceId: int, metricName: str, metricValue: float) -> None:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO monitoring.metrics (service_id, metric_name, metric_value)
                VALUES (%s, %s, %s)
            """, (serviceId, metricName, metricValue))

    def logEvent(self, connection, serviceId: int, eventType: str, eventMessage: str) -> None:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO events.service_event (service_id, event_type, message)
                VALUES (%s, %s, %s)
            """, (serviceId, eventType, eventMessage))

    def logLog(self, connection, serviceId: int, logLevel: str, logMessage: str) -> None:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO logs.service_log (service_id, level, message)
                VALUES (%s, %s, %s)
            """, (serviceId, logLevel, logMessage))

    def logAccessEvent(self, connection, serviceId: int | None, targetType: str, eventType: str, ipAddress: str | None, username: str | None) -> None:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO security.access_event (service_id, target_type, event_type, ip_address, username)
                VALUES (%s, %s, %s, %s, %s)
            """, (serviceId, targetType, eventType, ipAddress, username))

    def logSession(self, connection, serviceId: int | None, targetType: str, username: str | None, ipAddress: str | None) -> int:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO security.session (service_id, target_type, username, ip_address)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (serviceId, targetType, username, ipAddress))
            row = cur.fetchone()

            if row is None:
                raise RuntimeError("Session ID query returned no row.")
            
            return row[0]

    def logAction(self, connection, sessionId: int, actionType: str | None, actionDescription: str | None) -> None:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO security.action (session_id, action_type, description)
                VALUES (%s, %s, %s)
            """, (sessionId, actionType, actionDescription))
