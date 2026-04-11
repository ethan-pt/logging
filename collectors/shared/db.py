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
    def __init__(self, retries=5):
        self.retries = retries

        self.dbUser = os.getenv("POSTGRES_USER")
        self.dbPassword = os.getenv("POSTGRES_PASSWORD")
        self.dbName = os.getenv("POSTGRES_DB")
        self.dbHost = os.getenv("POSTGRES_HOST")

        self.connection = None

    def connect(self) -> None:
        for i in range(self.retries):
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
                logging.error(f"Failed to connect to PostgreSQL database with exception: {e}\nRetrying in 5 seconds... ({i + 1}/{self.retries})")
                
                time.sleep(5)
        
        logging.error("Exceeded maximum retries. Shutting down...")
        sys.exit(1)
    
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
    def registerService(self, connector, serviceName: str, serviceType: str) -> int:
        if not connector.checkConnection():
            logging.error("Cannot register service because database connection is not active.")
        
        try:
            cur = connector.connection.cursor()
            cur.execute("""
                INSERT INTO metadata.service (service_name, service_type)
                VALUES (%s, %s)
                ON CONFLICT (service_name) DO UPDATE 
                SET service_name = EXCLUDED.service_name
                RETURNING id
            """, (serviceName, serviceType))
            row = cur.fetchone()
            serviceId = row[0]
            connector.connection.commit()

            logging.info(f"Service '{serviceName}' successfully registered with ID: {serviceId}")

            return serviceId
        except Exception as e:
            logging.error(f"Error registering service '{serviceName}': {e}")
            
            return -1
    
    def logHeartbeat(self, connector, serviceId: int, active: float) -> None:
        if not connector.checkConnection():
            logging.error("Cannot log heartbeat because database connection is not active.")
        
        try:
            status = "active" if active == True else "inactive"
            with connector.connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO monitoring.heartbeat (service_id, status, timestamp)
                    VALUES (%s, %s, clock_timestamp())
                    RETURNING id
                """, (serviceId, status))

                heartbeatId = cur.fetchone()[0]
                if heartbeatId % 5 == 0:
                    logging.info("Committing heartbeat buffer to database...")

                    connector.connection.commit()
        except Exception as e:
            logging.error(f"Error logging heartbeat for service ID {serviceId}: {e}")
    
    def logMetric(self, connector, serviceId: int, metricName: str, metricValue: float) -> None:
        if not connector.checkConnection():
            logging.error("Cannot log metric because database connection is not active.")

        try:
            with connector.connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO monitoring.metrics (service_id, metric_name, metric_value, timestamp)
                    VALUES (%s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (serviceId, metricName, metricValue))

                metricId = cur.fetchone()[0]
                if metricId % 5 == 0:
                    logging.info("Committing metrics buffer to database...")

                    connector.connection.commit()
        except Exception as e:
            logging.error(f"Error logging metric '{metricName}' for service ID {serviceId}: {e}")
    
    def logEvent(self, connector, serviceId: int, eventType: str, eventMessage: str) -> None:
        if not connector.checkConnection():
            logging.error("Cannot log event because database connection is not active.")

        try:
            with connector.connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO monitoring.events (service_id, event_type, event_message, timestamp)
                    VALUES (%s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (serviceId, eventType, eventMessage))
                connector.connection.commit()
        except Exception as e:
            logging.error(f"Error logging event '{eventType}' for service ID {serviceId}: {e}")

    def logLog(self, connector, serviceId: int, logLevel: str, logMessage: str) -> None:
        if not connector.checkConnection():
            logging.error("Cannot log message because database connection is not active.")

        try:
            with connector.connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO monitoring.logs (service_id, log_level, log_message, timestamp)
                    VALUES (%s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (serviceId, logLevel, logMessage))
                connector.connection.commit()
        except Exception as e:
            logging.error(f"Error logging message with level '{logLevel}' for service ID {serviceId}: {e}")
    
    def logAccessEvent(self, connector, serviceId: int, targetType: str, eventType: str, ipAddress: str | None, username: str | None) -> None:
        if not connector.checkConnection():
            logging.error("Cannot log access event because database connection is not active.")

        try:
            with connector.connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO monitoring.access_events (service_id, target_type, event_type, ip_address, username, timestamp)
                    VALUES (%s, %s, %s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (serviceId, targetType, eventType, ipAddress, username))
                connector.connection.commit()
        except Exception as e:
            logging.error(f"Error logging access event '{eventType}' for service ID {serviceId}: {e}")

    def logSession(self, connector, serviceId: int, targetType: str, username: str | None, ipAddress: str | None) -> None:
        if not connector.checkConnection():
            logging.error("Cannot log session because database connection is not active.")

        try:
            with connector.connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO monitoring.sessions (service_id, target_type, username, ip_address, timestamp)
                    VALUES (%s, %s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (serviceId, targetType, username, ipAddress))
                connector.connection.commit()
        except Exception as e:
            logging.error(f"Error logging session for user '{username}' on service ID {serviceId}: {e}")

    def logAction(self, connector, sessionId: int, actionType: str | None, actionDescription: str | None) -> None:
        if not connector.checkConnection():
            logging.error("Cannot log action because database connection is not active.")

        try:
            with connector.connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO monitoring.actions (session_id, action_type, action_description, timestamp)
                    VALUES (%s, %s, %s, clock_timestamp())
                    RETURNING id
                """, (sessionId, actionType, actionDescription))
                connector.connection.commit()
        except Exception as e:
            logging.error(f"Error logging action '{actionType}' for session ID {sessionId}: {e}")   
