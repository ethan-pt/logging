import time
import logging
import psycopg

from typing import LiteralString

from shared.db import DatabaseConnector, DatabaseInserter
from shared.runtime import runCollector, RuntimeConfig


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


class PostgresCollector:
    collectionIntervals = ("fast", "medium", "slow")

    def __init__(self, connector):
        self.connector = connector
        self.connection: psycopg.Connection | None = None

        self.inserter = DatabaseInserter()

        self.serviceId: int | None = None
        self.serviceName = 'PostgreSQL'
        self.serviceType = 'database'

    def initialize(self) -> None:
        self.connection = self.connector.connect()
        connection = self.getConnection()

        with connection.transaction():
            self.serviceId = self.inserter.registerService(connection, self.serviceName, self.serviceType)

    def collectFast(self) -> None:
        heartbeatStart = time.monotonic()

        if not self.getHeartbeat():
            raise RuntimeError("Database heartbeat check failed.")

        heartbeatLatencyMs = (time.monotonic() - heartbeatStart) * 1000
        connection = self.getConnection()
        serviceId = self.getServiceId()
        metrics = {
            "heartbeat_latency_ms": heartbeatLatencyMs,
            **self.getConnectionMetrics(),
            "database_size_bytes": self.getDatabaseSize(),
        }

        with connection.transaction():
            self.inserter.logHeartbeat(connection, serviceId, True)

        self.logMetrics(metrics)

    def collectMedium(self) -> None:
        metrics: dict[str, float | int | None] = {}

        databaseStats = self.fetchOne("""
            SELECT
                xact_commit,
                xact_rollback,
                deadlocks,
                temp_files,
                temp_bytes
            FROM pg_stat_database
            WHERE datname = current_database()
        """, "database activity stats")

        if databaseStats is None:
            metrics.update({
                "transactions_committed_total": None,
                "transactions_rolled_back_total": None,
                "deadlocks_total": None,
                "temp_files_total": None,
                "temp_bytes_total": None,
            })
        else:
            metrics.update({
                "transactions_committed_total": databaseStats[0],
                "transactions_rolled_back_total": databaseStats[1],
                "deadlocks_total": databaseStats[2],
                "temp_files_total": databaseStats[3],
                "temp_bytes_total": databaseStats[4],
            })

        transactionAges = self.fetchOne("""
            SELECT
                EXTRACT(EPOCH FROM max(now() - xact_start))::double precision,
                EXTRACT(EPOCH FROM max(now() - xact_start)
                    FILTER (WHERE state IN ('idle in transaction', 'idle in transaction (aborted)')))::double precision
            FROM pg_stat_activity
            WHERE xact_start IS NOT NULL
              AND pid <> pg_backend_pid()
        """, "transaction age stats")

        if transactionAges is None:
            metrics.update({
                "longest_transaction_age_seconds": None,
                "oldest_idle_transaction_age_seconds": None,
            })
        else:
            metrics.update({
                "longest_transaction_age_seconds": transactionAges[0],
                "oldest_idle_transaction_age_seconds": transactionAges[1],
            })

        self.logMetrics(metrics)

    def collectSlow(self) -> None:
        metrics: dict[str, float | int | None] = {}

        maxConnectionsRow = self.fetchOne(
            "SELECT current_setting('max_connections')::int",
            "max connections"
        )
        maxConnections = None if maxConnectionsRow is None else maxConnectionsRow[0]
        connectionMetrics = self.getConnectionMetrics()

        metrics["connections_max"] = maxConnections
        metrics["server_connections_used_percent"] = self.getUsagePercent(
            connectionMetrics["server_connections_total"],
            maxConnections
        )
        metrics["database_connections_used_percent"] = self.getUsagePercent(
            connectionMetrics["database_connections_total"],
            maxConnections
        )

        tableStats = self.fetchOne("""
            SELECT
                COALESCE(sum(n_live_tup), 0),
                COALESCE(sum(n_dead_tup), 0),
                count(*) FILTER (
                    WHERE n_dead_tup > (
                        current_setting('autovacuum_vacuum_threshold')::double precision
                        + current_setting('autovacuum_vacuum_scale_factor')::double precision * n_live_tup
                    )
                ),
                EXTRACT(EPOCH FROM max(now() - last_autovacuum))::double precision,
                count(*) FILTER (WHERE last_autovacuum IS NULL)
            FROM pg_stat_user_tables
        """, "table maintenance stats")

        if tableStats is None:
            metrics.update({
                "table_live_rows_total": None,
                "table_dead_rows_total": None,
                "tables_needing_vacuum": None,
                "oldest_last_autovacuum_age_seconds": None,
                "tables_never_autovacuumed": None,
            })
        else:
            metrics.update({
                "table_live_rows_total": tableStats[0],
                "table_dead_rows_total": tableStats[1],
                "tables_needing_vacuum": tableStats[2],
                "oldest_last_autovacuum_age_seconds": tableStats[3],
                "tables_never_autovacuumed": tableStats[4],
            })

        self.logMetrics(metrics)

    def getServiceId(self) -> int:
        if self.serviceId is None:
            raise RuntimeError("Service ID is not set.")

        return self.serviceId

    def getConnection(self) -> psycopg.Connection:
        if self.connection is None:
            raise RuntimeError("No active database connection.")
        return self.connection

    def fetchOne(self, query: LiteralString, metricGroup: str) -> tuple | None:
        connection = self.getConnection()

        try:
            with connection.cursor() as cur:
                cur.execute(query)
                row = cur.fetchone()

                if row is None:
                    logging.error(f"{metricGroup} query returned no row.")
                    return None

                return row
        except psycopg.Error as e:
            logging.error(f"Error collecting {metricGroup}: {e}")

            return None

    def logMetrics(self, metrics: dict[str, float | int | None]) -> None:
        filteredMetrics = {
            metricName: metricValue
            for metricName, metricValue in metrics.items()
            if metricValue is not None
        }

        if not filteredMetrics:
            return

        connection = self.getConnection()
        serviceId = self.getServiceId()

        with connection.transaction():
            for metricName, metricValue in filteredMetrics.items():
                self.inserter.logMetric(connection, serviceId, metricName, metricValue)

    def getHeartbeat(self) -> bool:
        connection = self.getConnection()

        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")

            return True
        except psycopg.Error as e:
            logging.error(f"Error checking database heartbeat: {e}")

            return False

    def getConnectionMetrics(self) -> dict[str, int | None]:
        metricNames = (
            "server_connections_total",
            "server_connections_active",
            "server_connections_idle",
            "server_connections_idle_in_transaction",
            "server_connections_waiting_on_lock",
            "database_connections_total",
            "database_connections_active",
            "database_connections_idle",
            "database_connections_idle_in_transaction",
            "database_connections_waiting_on_lock",
        )
        row = self.fetchOne("""
            SELECT
                count(*),
                count(*) FILTER (WHERE state = 'active'),
                count(*) FILTER (WHERE state = 'idle'),
                count(*) FILTER (WHERE state IN ('idle in transaction', 'idle in transaction (aborted)')),
                count(*) FILTER (WHERE wait_event_type = 'Lock'),
                count(*) FILTER (WHERE datname = current_database()),
                count(*) FILTER (WHERE datname = current_database() AND state = 'active'),
                count(*) FILTER (WHERE datname = current_database() AND state = 'idle'),
                count(*) FILTER (
                    WHERE datname = current_database()
                      AND state IN ('idle in transaction', 'idle in transaction (aborted)')
                ),
                count(*) FILTER (WHERE datname = current_database() AND wait_event_type = 'Lock')
            FROM pg_stat_activity
        """, "connection stats")

        if row is None:
            return dict.fromkeys(metricNames, None)

        return dict(zip(metricNames, row))

    def getDatabaseSize(self) -> int | None:
        row = self.fetchOne("SELECT pg_database_size(current_database())", "database size")

        if row is None:
            return None

        return row[0]

    def getUsagePercent(self, connectionCount: int | None, maxConnections: int | None) -> float | None:
        if connectionCount is None or maxConnections is None or maxConnections == 0:
            return None

        return (connectionCount / maxConnections) * 100

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
