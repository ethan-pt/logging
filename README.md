# Homelab Logging System

Ideally provides a robust and versatile logging and data collection system tailored for my homelab. It gathers diverse data types from various sources, providing a centralized platform for personal monitoring, analysis, and experimentation. It's designed to be as modular as possible while remaining lightweight and mostly hands-off, which ideal for my use case.

## Data Collection Capabilities

The system is structured to collect a wide array of data for personal insights, as outlined by its PostgreSQL schema:

- **Monitoring Data:** Captures system metrics (e.g., performance, resource usage) and service heartbeats to track the health and operational status of homelab infrastructure.
- **Event Data:** Records significant service-related events, offering a timeline of activities and state changes within applications.
- **Log Data:** Centralizes application logs with various severity levels (e.g., info, warning, error), aiding in debugging and operational understanding within a personal environment.
- **Security Data:** Gathers detailed security-related information, including access events, user session tracking, and specific actions performed within sessions. This supports auditing and custom security analysis.
- **Metadata:** Manages metadata about services to provide context and facilitate organization of collected data.

The collected data is intended to be used with external visualization and analysis tools (such as Grafana, not yet integrated) to facilitate:

- Real-time performance monitoring of personal systems.
- Historical data analysis to identify trends and anomalies relevant to homelab operations.
- Security event tracking and custom auditing.
- Informing future hardware and software upgrade decisions for a personal server.
- Tracking specific data from game servers and other experimental setups.
- General tinkering and understanding the operational dynamics within a personal homelab.

## Planned Features

This project is a personal endeavor under active development. Future enhancements and data collectors are planned to expand its capabilities for my specific needs. This section will be updated with a detailed roadmap as the project evolves.

- [ ] Extended collecting for all the things I need collected
- [ ] Alerts for when bad things happen (email? smoke signals?)
- [ ] Data culling/consolidating of some sort (averaging time periods as they get further back?) to avoid filling my poor old HDD :(
- [ ] Support for fully (or at least mostly (I'll settle for somewhat)) automated inclusion of templated containers (Minecraft servers generated with mcgen tool)
