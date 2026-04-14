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

        self.connection = None

    def connect(self) -> None:
        try:
            self.connection = psycopg.connect(
                host=self.dbHost,
                dbname=self.dbName,
                user=self.dbUser,
                password=self.dbPassword
            )

            logging.info("Connected to PostgreSQL database successfully.")
            return 
        except Exception as e:
            logging.error(f"Failed to connect to PostgreSQL database with exception: {e}")
    
    def checkConnection(self) -> bool:
        if not self.connection:
            logging.warning("Attempted to check connection, but no active connection found.")

            return False
        try:
            with self.connection.cursor() as cur:
                cur.execute("SELECT 1")

                return True
        except Exception as e:
            logging.error(f"Database connection check failed with exception: {e}")
            return False
        

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
                RETURNING id
            """, (serviceName, serviceType))
            row = cur.fetchone()
            serviceId = row[0]
            connection.commit()

            logging.info(f"Service '{serviceName}' successfully registered with ID: {serviceId}")

            return serviceId
        except Exception as e:
            logging.error(f"Error registering service '{serviceName}': {e}")
            
            return -1
    
    def logHeartbeat(self, connection, serviceId: int, active: bool) -> None:
        try:
            status = "active" if active == True else "inactive"
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO monitoring.heartbeat (service_id, status, timestamp)
                    VALUES (%s, %s, clock_timestamp())
                """, (serviceId, status))

                counter = 0
                if counter % 5 == 0:
                    logging.info("Committing heartbeat buffer to database...")

                    connection.commit()
                    counter = 0
                else:
                    counter += 1
        except Exception as e:
            logging.error(f"Error logging heartbeat for service ID {serviceId}: {e}")
    
    def logMetric(self, connection, serviceId: int, metricName: str, metricValue: float) -> None:
        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO monitoring.metrics (service_id, metric_name, metric_value, timestamp)
                    VALUES (%s, %s, %s, clock_timestamp())
                """, (serviceId, metricName, metricValue))

                counter = 0
                if counter % 5 == 0:
                    logging.info("Committing metrics buffer to database...")

                    connection.commit()
                    counter = 0
                else:
                    counter += 1
        except Exception as e:
            logging.error(f"Error logging metric '{metricName}' for service ID {serviceId}: {e}")
    
    def logEvent(self, connection, serviceId: int, eventType: str, eventMessage: str) -> None:
        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO events.service_event (service_id, event_type, event_message, timestamp)
                    VALUES (%s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (serviceId, eventType, eventMessage))
                connection.commit()
        except Exception as e:
            logging.error(f"Error logging event '{eventType}' for service ID {serviceId}: {e}")

    def logLog(self, connection, serviceId: int, logLevel: str, logMessage: str) -> None:
        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO logs.service_log (service_id, log_level, log_message, timestamp)
                    VALUES (%s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (serviceId, logLevel, logMessage))
                connection.commit()
        except Exception as e:
            logging.error(f"Error logging message with level '{logLevel}' for service ID {serviceId}: {e}")

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

    def logSession(self, connection, serviceId: int, targetType: str, username: str | None, ipAddress: str | None) -> None:
        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO security.session (service_id, target_type, username, ip_address, timestamp)
                    VALUES (%s, %s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (serviceId, targetType, username, ipAddress))
                connection.commit()
        except Exception as e:
            logging.error(f"Error logging session for user '{username}' on service ID {serviceId}: {e}")

    def logAction(self, connection, sessionId: int, actionType: str | None, actionDescription: str | None) -> None:
        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO security.action (session_id, action_type, action_description, timestamp)
                    VALUES (%s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (sessionId, actionType, actionDescription))
                connection.commit()
        except Exception as e:
            logging.error(f"Error logging action '{actionType}' for session ID {sessionId}: {e}")   
