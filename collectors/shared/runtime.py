import logging
import time

from dataclasses import dataclass
from typing import Protocol
from collections.abc import Callable


class Collector(Protocol):
    def initialize(self) -> None: ...
    def collect(self) -> None: ...
    def stop(self) -> None: ...


@dataclass(frozen=True)
class RuntimeConfig:
    interval: float = 10
    initialDelay: float = 5
    maxDelay: float = 600
    stableThreshold: float = 300

    def __post_init__(self) -> None:
        if self.interval <= 0:
            raise ValueError("Collection interval must be positive.")

        if self.initialDelay <= 0:
            raise ValueError("Initial delay must be positive.")
        
        if self.maxDelay < self.initialDelay:
            raise ValueError("Max delay cannot be less than initial delay.")
        
        if self.stableThreshold < 0:
            raise ValueError("Stable threshold cannot be negative.")


def waitForNextRun(nextRun: float, interval: float) -> float:
    nextRun += interval
    now = time.monotonic()

    if now > nextRun:
        missedIntervals = int((now - nextRun) // interval) + 1
        nextRun += interval * missedIntervals

        logging.warning(f"Collection exceeded deadline. Skipping {missedIntervals} intervals.")

    time.sleep(max(0, nextRun - time.monotonic()))
    return nextRun


def runCollector(factory: Callable[[], Collector], collectorName: str, config: RuntimeConfig) -> None:
    nextRestartDelay = config.initialDelay

    while True:
        collector = factory()
        stableSince: float | None = None
        currentRestartDelay: float | None = None

        try:
            logging.info(f"{collectorName} collector started. Running initialization...")

            collector.initialize()

            stableSince = time.monotonic()
            nextRun = time.monotonic()

            while True:
                collector.collect()
                nextRun = waitForNextRun(nextRun, config.interval)

        except KeyboardInterrupt:
            logging.info(f"{collectorName} collector stopped by user.")
            break

        except SystemExit:
            logging.info(f"{collectorName} collector container stopped.")
            break

        except Exception:
            logging.exception(f"An error occurred while running the {collectorName} collector.")

            if (stableSince is not None) and ((time.monotonic() - stableSince) >= config.stableThreshold):
                nextRestartDelay = config.initialDelay

            currentRestartDelay = nextRestartDelay
            nextRestartDelay = min(nextRestartDelay * 2, config.maxDelay)

        finally:
            logging.info(f"{collectorName} collector shutting down...")
            
            try:
                collector.stop()
            except Exception:
                logging.exception(f"An error occurred while stopping the {collectorName} collector.")

        if currentRestartDelay is not None:
            logging.info(f"Restarting {collectorName} collector in {currentRestartDelay} seconds...")
            time.sleep(currentRestartDelay)
        