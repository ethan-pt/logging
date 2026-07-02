import logging
import time

from dataclasses import dataclass
from typing import Literal, Protocol
from collections.abc import Callable


CollectionIntervalName = Literal["fast", "medium", "slow"]

INTERVAL_METHODS = {
    "fast": "collectFast",
    "medium": "collectMedium",
    "slow": "collectSlow",
}


class Collector(Protocol):
    def initialize(self) -> None: ...
    def stop(self) -> None: ...


@dataclass(frozen=True)
class RuntimeConfig:
    fastInterval: float = 10
    mediumInterval: float = 60
    slowInterval: float = 300
    initialDelay: float = 5
    maxDelay: float = 600
    stableThreshold: float = 300

    def __post_init__(self) -> None:
        if self.fastInterval <= 0:
            raise ValueError("Fast collection interval must be positive.")

        if self.mediumInterval <= 0:
            raise ValueError("Medium collection interval must be positive.")

        if self.slowInterval <= 0:
            raise ValueError("Slow collection interval must be positive.")

        if self.fastInterval > self.mediumInterval:
            raise ValueError("Fast collection interval cannot be greater than medium collection interval.")

        if self.mediumInterval > self.slowInterval:
            raise ValueError("Medium collection interval cannot be greater than slow collection interval.")

        if self.initialDelay <= 0:
            raise ValueError("Initial delay must be positive.")

        if self.maxDelay < self.initialDelay:
            raise ValueError("Max delay cannot be less than initial delay.")

        if self.stableThreshold < 0:
            raise ValueError("Stable threshold cannot be negative.")


@dataclass
class CollectionSchedule:
    name: CollectionIntervalName
    seconds: float
    run: Callable[[], None]
    nextRun: float | None = None


def getIntervalSeconds(intervalName: CollectionIntervalName, config: RuntimeConfig) -> float:
    if intervalName == "fast":
        return config.fastInterval

    if intervalName == "medium":
        return config.mediumInterval

    if intervalName == "slow":
        return config.slowInterval

    raise ValueError(f"Unknown collection interval: {intervalName}")


def validateCollector(collector: Collector) -> None:
    collectorClass = collector.__class__.__name__

    requiredMethods = ("initialize", "stop")
    missingMethods = [methodName for methodName in requiredMethods if not callable(getattr(collector, methodName, None))]
    if missingMethods:
        missingMethodList = ", ".join(missingMethods)
        raise TypeError(f"{collectorClass} is missing required collector method(s): {missingMethodList}")

    collectionIntervals = getattr(collector, "collectionIntervals", None)
    if collectionIntervals is None:
        raise AttributeError(f"{collectorClass} is missing required attribute: collectionIntervals")
    elif not isinstance(collectionIntervals, tuple):
        raise TypeError(f"{collectorClass}.collectionIntervals must be a tuple.")
    elif not collectionIntervals:
        raise ValueError(f"{collectorClass}.collectionIntervals cannot be empty.")

    for intervalName in collectionIntervals:
        if intervalName not in INTERVAL_METHODS:
            validIntervalList = ", ".join(INTERVAL_METHODS)
            raise ValueError(
                f"{collectorClass}.collectionIntervals contains invalid interval name: {intervalName}.\n"
                f"Valid interval names are: {validIntervalList}"
            )
        methodName = INTERVAL_METHODS[intervalName]
        if not callable(getattr(collector, methodName, None)):
            raise AttributeError(f"{collectorClass} is missing required method for interval '{intervalName}': {methodName}")


def getCollectionSchedules(collector: Collector, config: RuntimeConfig) -> list[CollectionSchedule]:
    schedules: list[CollectionSchedule] = []

    collectionIntervals = getattr(collector, "collectionIntervals")
    for intervalName in collectionIntervals:
        methodName = INTERVAL_METHODS[intervalName]
        seconds = getIntervalSeconds(intervalName, config)
        run = getattr(collector, methodName)

        schedules.append(CollectionSchedule(intervalName, seconds, run))

    return schedules


def getNextRun(nextRun: float, seconds: float, intervalName: str) -> float:
    nextRun += seconds
    now = time.monotonic()

    if now > nextRun:
        missedIntervals = int((now - nextRun) // seconds) + 1
        nextRun += seconds * missedIntervals

        logging.warning(f"{intervalName.capitalize()} collection exceeded deadline. Skipping {missedIntervals} intervals.")

    return nextRun


def runInitialCollection(schedules: list[CollectionSchedule]) -> None:
    for schedule in schedules:
        logging.info(f"Running initial {schedule.name} collection...")
        schedule.run()
        schedule.nextRun = time.monotonic() + schedule.seconds


def runDueCollections(schedules: list[CollectionSchedule]) -> None:
    now = time.monotonic()

    for schedule in schedules:
        if schedule.nextRun is None:
            raise RuntimeError(f"{schedule.name.capitalize()} collection interval has not been scheduled.")

        if schedule.nextRun <= now:
            logging.debug(f"Running scheduled {schedule.name} collection...")
            schedule.run()
            schedule.nextRun = getNextRun(schedule.nextRun, schedule.seconds, schedule.name)


def sleepUntilNextCollection(schedules: list[CollectionSchedule]) -> None:
    nextRuns = [schedule.nextRun for schedule in schedules if schedule.nextRun is not None]

    if not nextRuns:
        raise RuntimeError("No collection intervals have been scheduled.")

    time.sleep(max(0, min(nextRuns) - time.monotonic()))


def runCollector(factory: Callable[[], Collector], collectorName: str, config: RuntimeConfig) -> None:
    nextRestartDelay = config.initialDelay

    while True:
        collector = factory()
        stableSince: float | None = None
        currentRestartDelay: float | None = None

        try:
            logging.info(f"{collectorName} collector started.")

            logging.info("Validating...")
            validateCollector(collector)
            logging.info("Initializing...")
            collector.initialize()

            stableSince = time.monotonic()
            schedules = getCollectionSchedules(collector, config)
            runInitialCollection(schedules)

            while True:
                runDueCollections(schedules)
                sleepUntilNextCollection(schedules)

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
