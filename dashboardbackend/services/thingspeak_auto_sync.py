import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.database import get_db
from models.models import TankSensorData, TankSensorDataCreate

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ThingSpeakAutoSync:
    """Automated ThingSpeak data synchronization service"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False

        # Default configuration
        self.config = {
            "channel_id": 3290207,
            "api_key": "VFSNJB4V3DAZMBL5",
            "tank_id": "tank_001",  # Default tank ID - should be configurable
            "polling_interval_seconds": 30,  # Poll every 30 seconds
            "field1_name": "water_level_cm",  # Distance -> water_level_cm
            "field2_name": "temperature_c",   # Temperature -> temperature_c
            "max_results_per_poll": 10,
            "enabled": False
        }

        # Track last processed entry to avoid duplicates
        self.last_processed_entry_id = 0

    def update_config(self, **kwargs):
        """Update configuration parameters"""
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
                logger.info(f"Config updated: {key} = {value}")

        # Restart scheduler if interval changed and running
        if self.is_running and "polling_interval_seconds" in kwargs:
            self.restart_scheduler()

    def start(self):
        """Start the auto-sync scheduler"""
        if not self.config["enabled"]:
            logger.info("Auto-sync is disabled. Enable it first.")
            return False

        if not self.is_running:
            # Add the polling job
            self.scheduler.add_job(
                self._sync_data,
                IntervalTrigger(
                    seconds=self.config["polling_interval_seconds"]),
                id="thingspeak_sync",
                max_instances=1,
                replace_existing=True
            )

            self.scheduler.start()
            self.is_running = True
            logger.info(
                f"ThingSpeak auto-sync started - polling every {self.config['polling_interval_seconds']} seconds")
            return True
        else:
            logger.info("Auto-sync is already running")
            return False

    def stop(self):
        """Stop the auto-sync scheduler"""
        if self.is_running:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("ThingSpeak auto-sync stopped")
            return True
        else:
            logger.info("Auto-sync is not running")
            return False

    def restart_scheduler(self):
        """Restart the scheduler with updated configuration"""
        if self.is_running:
            self.stop()
            self.start()

    def enable(self):
        """Enable auto-sync"""
        self.config["enabled"] = True
        logger.info("Auto-sync enabled")

    def disable(self):
        """Disable auto-sync and stop if running"""
        self.config["enabled"] = False
        if self.is_running:
            self.stop()
        logger.info("Auto-sync disabled")

    async def _fetch_thingspeak_data(self) -> Optional[dict]:
        """Fetch latest data from ThingSpeak"""
        try:
            params = {
                "results": self.config["max_results_per_poll"],
                "api_key": self.config["api_key"]
            }

            base_url = f"https://api.thingspeak.com/channels/{self.config['channel_id']}/feeds.json"
            url = f"{base_url}?{urlencode(params)}"

            # Use asyncio to run the synchronous urlopen in a thread
            loop = asyncio.get_event_loop()
            response_data = await loop.run_in_executor(None, self._make_request, url)

            return json.loads(response_data)

        except Exception as e:
            logger.error(f"Error fetching ThingSpeak data: {e}")
            return None

    def _make_request(self, url: str) -> str:
        """Make HTTP request (synchronous helper for async execution)"""
        with urlopen(url, timeout=10) as response:
            return response.read().decode("utf-8")

    async def _sync_data(self):
        """Main sync function called by scheduler"""
        try:
            logger.info(" Checking ThingSpeak for new data...")

            # Fetch data from ThingSpeak
            thingspeak_data = await self._fetch_thingspeak_data()
            if not thingspeak_data:
                logger.warning("Failed to fetch ThingSpeak data")
                return

            feeds = thingspeak_data.get("feeds", [])
            if not feeds:
                logger.info("No data feeds found")
                return

            # Filter for new entries only
            new_feeds = [
                feed for feed in feeds
                if int(feed.get("entry_id", 0)) > self.last_processed_entry_id
            ]

            if not new_feeds:
                logger.info("No new data entries found")
                return

            logger.info(f" Found {len(new_feeds)} new entries to process")

            # Store new data
            stored_count = await self._store_feeds(new_feeds)

            # Update last processed entry ID
            if new_feeds:
                latest_entry_id = max(int(feed.get("entry_id", 0))
                                      for feed in new_feeds)
                self.last_processed_entry_id = latest_entry_id
                logger.info(
                    f" Processed {stored_count} new entries. Latest entry ID: {latest_entry_id}")

        except Exception as e:
            logger.error(f"Error in sync operation: {e}")

    async def _store_feeds(self, feeds: list) -> int:
        """Store feed data in database"""
        stored_count = 0

        # Get database session
        db_gen = get_db()
        db: Session = next(db_gen)

        try:
            for feed in feeds:
                try:
                    # Extract and validate data
                    field1_value = feed.get("field1")
                    field2_value = feed.get("field2")
                    created_at_str = feed.get("created_at")
                    entry_id = feed.get("entry_id")

                    # Skip if essential data is missing
                    if not field1_value or not field2_value:
                        logger.warning(
                            f"Skipping entry {entry_id} - missing field data")
                        continue

                    # Skip invalid sensor readings (like -127.00 which indicates sensor error)
                    try:
                        temp_value = float(field2_value)
                        if temp_value <= -100:  # Likely sensor error
                            logger.warning(
                                f"Skipping entry {entry_id} - invalid temperature reading: {temp_value}")
                            continue

                        dist_value = float(field1_value)
                        if dist_value < 0:  # Invalid distance
                            logger.warning(
                                f"Skipping entry {entry_id} - invalid distance reading: {dist_value}")
                            continue

                    except ValueError:
                        logger.warning(
                            f"Skipping entry {entry_id} - non-numeric field values")
                        continue

                    # Map fields according to configuration
                    water_level = dist_value  # Distance maps to water level
                    temperature = temp_value  # Temperature maps to temperature

                    # Create sensor data entry
                    sensor_data = TankSensorDataCreate(
                        tank_id=self.config["tank_id"],
                        water_level_cm=water_level,
                        temperature_c=temperature
                    )

                    db_sensor_data = TankSensorData(**sensor_data.dict())

                    # Use ThingSpeak timestamp if available
                    if created_at_str:
                        try:
                            # Convert ThingSpeak UTC timestamp
                            ts_datetime = datetime.fromisoformat(
                                created_at_str.replace('Z', '+00:00'))
                            db_sensor_data.created_at = ts_datetime
                        except ValueError:
                            # Use current time if parsing fails
                            pass

                    db.add(db_sensor_data)
                    db.commit()
                    db.refresh(db_sensor_data)

                    stored_count += 1
                    logger.info(
                        f" Stored entry {entry_id}: Water={water_level}cm, Temp={temperature}°C")

                except Exception as e:
                    logger.error(
                        f"Error storing feed entry {feed.get('entry_id', 'unknown')}: {e}")
                    db.rollback()
                    continue

        finally:
            db.close()

        return stored_count

    def get_status(self) -> dict:
        """Get current status of auto-sync service"""
        return {
            "enabled": self.config["enabled"],
            "running": self.is_running,
            "config": self.config.copy(),
            "last_processed_entry_id": self.last_processed_entry_id,
            "next_run": (
                self.scheduler.get_job(
                    "thingspeak_sync").next_run_time.isoformat()
                if self.is_running and self.scheduler.get_job("thingspeak_sync")
                else None
            )
        }


# Global instance
auto_sync_service = ThingSpeakAutoSync()
