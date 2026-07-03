# Homelab Logging System

A centralized logging and observability(soon™) platform for all kinds of data from and about my homelab Ubuntu Server and any other project I buid that interacts with it. The idea is that it's as modular and reliable as possible so I can easily integrate new projects with minimal maintenance and monitor processes, their performance, analyze security stuff, and more efficiently plan for future hardware upgrades depending on how this all grows.

## Data Collection

The system is structured to collect all kinds of data in a modular way, ideally storing most, if not all of the data I might create with the processes I have running at any given point in time

- **Monitoring Data:** Captures system metrics (e.g., performance, resource usage) and service heartbeats to track the health and operational status of homelab infrastructure.
- **Event Data:** Records significant service-related events, offering a timeline of activities and state changes within applications.
- **Log Data:** Centralizes application logs with various severity levels (e.g., info, warning, error)
- **Security Data:** Gathers detailed security-related information, including access events, user session tracking, and specific actions performed within sessions
- **Metadata:** Manages metadata about services to provide context and facilitate organization of collected data.

## Tech Used

- PostgreSQL
- Docker/Docker Compose
- psycopg3
- Python
- SQL

## Planned Features

As of writing, this project is very much still in active development. Here's what I'm probably working on right now.

- [ ] Extended collecting for all the things I need collected
- [ ] Alerts for when bad things happen (email? smoke signals?)
- [x] Only attempt to log other data if heartbeat is successful
- [ ] Data culling/consolidating of some sort (averaging metric across time periods as they get older, just delete most of the rest of it once it's not likely to be relevant) to avoid filling my poor old HDD :(
- [ ] Use something like Grafana for data vis, Alloy for log collection, and Loki for log storage
- [ ] Support for fully (or at least mostly (I'll settle for somewhat)) automated inclusion of templated containers (Minecraft servers generated with mcman tool, etc.)
