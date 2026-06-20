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
        delay = 5
        while True:
            if not all([self.dbUser, self.dbPassword, self.dbName, self.dbHost]):
                logging.error("Database connection parameters are not fully set. Please ensure POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, and POSTGRES_HOST environment variables are all set.")
                logging.info(f"Retrying database connection in {delay} seconds...")
                
                time.sleep(delay)
                delay = min(delay * 2, 300)
                continue

            try:
                connection = psycopg.connect(
                    host=self.dbHost,
                    dbname=self.dbName,
                    user=self.dbUser,
                    password=self.dbPassword
                )

                logging.info("Connected to PostgreSQL database successfully.")
                return connection
            except Exception as e:
                logging.error(f"Failed to connect to PostgreSQL database with exception: {e}\nRetrying in {delay} seconds...")
                
                time.sleep(delay)
                delay = min(delay * 2, 300)
    
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
        # I return -1 on failure for this method bc the service ID is needed for all other logging methods, 
        # so if registration fails we want to be able to easily check for that and avoid attempting to log 
        # anything else.
        try:
            cur = connection.cursor()
            cur.execute("""
                INSERT INTO metadata.service (service_name, service_type)
                VALUES (%s, %s)
                ON CONFLICT (service_name) DO UPDATE 
                SET service_name = EXCLUDED.service_name
                SET service_type = EXCLUDED.service_type
                RETURNING id
            """, (serviceName, serviceType))
            row = cur.fetchone()
            serviceId = row[0]
            connection.commit()

            logging.info(f"Service '{serviceName}' successfully registered with ID: {serviceId}")

            return serviceId
        except Exception as e:
            logging.error(f"Error registering service '{serviceName}': {e}")

            try:
                connection.rollback()

                logging.info("Successfully rolled back transaction after failed service registration.")
            except Exception as rollback_error:
                logging.error(f"Error rolling back transaction after failed service registration: {rollback_error}")
            
            return -1
    
    def logHeartbeat(self, connection, serviceId: int, active: bool) -> None:
        try:
            status = "active" if active == True else "inactive"
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO monitoring.heartbeat (service_id, status, timestamp)
                    VALUES (%s, %s, clock_timestamp())
                """, (serviceId, status))
                connection.commit()
        except Exception as e:
            logging.error(f"Error logging heartbeat for service ID {serviceId}: {e}")

            try:
                connection.rollback()

                logging.info("Successfully rolled back transaction after failed heartbeat log.")
            except Exception as rollback_error:
                logging.error(f"Error rolling back transaction after failed heartbeat log: {rollback_error}")
    
    def logMetric(self, connection, serviceId: int, metricName: str, metricValue: float) -> None:
        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO monitoring.metrics (service_id, metric_name, metric_value, timestamp)
                    VALUES (%s, %s, %s, clock_timestamp())
                """, (serviceId, metricName, metricValue))
                connection.commit()
        except Exception as e:
            logging.error(f"Error logging metric '{metricName}' for service ID {serviceId}: {e}")

            try:
                connection.rollback()

                logging.info("Successfully rolled back transaction after failed metric log.")
            except Exception as rollback_error:
                logging.error(f"Error rolling back transaction after failed metric log: {rollback_error}")

    def logEvent(self, connection, serviceId: int, eventType: str, eventMessage: str) -> None:
        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO events.service_event (service_id, event_type, message, timestamp)
                    VALUES (%s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (serviceId, eventType, eventMessage))
                connection.commit()
        except Exception as e:
            logging.error(f"Error logging event '{eventType}' for service ID {serviceId}: {e}")

            try:
                connection.rollback()

                logging.info("Successfully rolled back transaction after failed event log.")
            except Exception as rollback_error:
                logging.error(f"Error rolling back transaction after failed event log: {rollback_error}")

    def logLog(self, connection, serviceId: int, logLevel: str, logMessage: str) -> None:
        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO logs.service_log (service_id, level, message, timestamp)
                    VALUES (%s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (serviceId, logLevel, logMessage))
                connection.commit()
        except Exception as e:
            logging.error(f"Error logging message with level '{logLevel}' for service ID {serviceId}: {e}")

            try:
                connection.rollback()

                logging.info("Successfully rolled back transaction after failed log message.")
            except Exception as rollback_error:
                logging.error(f"Error rolling back transaction after failed log message: {rollback_error}")

    def logAccessEvent(self, connection, serviceId: int, targetType: str, eventType: str, ipAddress: str | None, username: str | None) -> None:
        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO security.access_event (service_id, target_type, event_type, ip_address, username, timestamp)
                    VALUES (%s, %s, %s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (serviceId, targetType, eventType, ipAddress, username))
                connection.commit()
        except Exception as e:
            logging.error(f"Error logging access event '{eventType}' for service ID {serviceId}: {e}")

            try:
                connection.rollback()

                logging.info("Successfully rolled back transaction after failed access event log.")
            except Exception as rollback_error:
                logging.error(f"Error rolling back transaction after failed access event log: {rollback_error}")

    def logSession(self, connection, serviceId: int, targetType: str, username: str | None, ipAddress: str | None) -> int:
        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO security.session (service_id, target_type, username, ip_address, started_at)
                    VALUES (%s, %s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (serviceId, targetType, username, ipAddress))
                sessionId = cur.fetchone()[0]
                connection.commit()

                return sessionId
        except Exception as e:
            logging.error(f"Error logging session for user '{username}' on service ID {serviceId}: {e}")

            try:
                connection.rollback()

                logging.info("Successfully rolled back transaction after failed session log.")
            except Exception as rollback_error:
                logging.error(f"Error rolling back transaction after failed session log: {rollback_error}")

            return -1

    def logAction(self, connection, sessionId: int, actionType: str | None, actionDescription: str | None) -> None:
        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO security.action (session_id, action_type, description, timestamp)
                    VALUES (%s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (sessionId, actionType, actionDescription))
                connection.commit()
        except Exception as e:
            logging.error(f"Error logging action '{actionType}' for session ID {sessionId}: {e}")

            try:
                connection.rollback()

                logging.info("Successfully rolled back transaction after failed action log.")
            except Exception as rollback_error:
                logging.error(f"Error rolling back transaction after failed action log: {rollback_error}")
