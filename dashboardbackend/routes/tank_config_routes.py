from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
from datetime import datetime
from pydantic import BaseModel
from models.database import get_db
from models.models import (
    TankConfiguration,
    TankConfigurationCreate,
    TankConfigurationResponse,
    TankConfigurationUpdate,
    TankConfigurationListResponse,
    TankSensorData,
    TankSensorDataCreate,
    MessageResponse
)
from services.thingspeak_auto_sync import auto_sync_service

router = APIRouter()

THINGSPEAK_API_KEY = "VFSNJB4V3DAZMBL5"
THINGSPEAK_CHANNEL_ID = 3290207  # Default channel ID for all ThingSpeak operations

# ThingSpeak Models


class ThingSpeakToDBPayload(BaseModel):
    tank_id: str
    field1_name: str = "water_level_cm"  # Map field1 to water level
    field2_name: str = "temperature_c"   # Map field2 to temperature


class AutoSyncConfig(BaseModel):
    tank_id: Optional[str] = None
    polling_interval_seconds: Optional[int] = None
    channel_id: Optional[int] = None
    api_key: Optional[str] = None
    enabled: Optional[bool] = None


class AutoSyncStatus(BaseModel):
    enabled: bool
    running: bool
    config: dict
    last_processed_entry_id: int
    next_run: Optional[str] = None


@router.post("/tank-sensorparameters", response_model=TankConfigurationResponse, status_code=201)
async def create_tank_sensorparameters(tank_config: TankConfigurationCreate, db: Session = Depends(get_db)):
    """Create new tank configuration"""
    try:
        print(
            f"\n🏗️ Creating new tank configuration for Node: {tank_config.node_id}")
        print(
            f"   Dimensions: {tank_config.tank_height_cm}H x {tank_config.tank_length_cm}L x {tank_config.tank_width_cm}W cm")
        if tank_config.lat and tank_config.long:
            print(f"   Location: {tank_config.lat}, {tank_config.long}")

        db_tank_config = TankConfiguration(**tank_config.dict())
        db.add(db_tank_config)
        db.commit()
        db.refresh(db_tank_config)

        print(f"✅ Tank configuration created with ID: {db_tank_config.id}\n")
        return db_tank_config
    except Exception as e:
        print(f"❌ Error creating tank configuration: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"Error creating tank configuration: {str(e)}")


@router.get("/tank-sensorparameters", response_model=TankConfigurationListResponse)
async def get_tank_sensorparameterss(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100,
                      description="Number of items per page"),
    node_id: Optional[str] = Query(None, description="Filter by node ID"),
    sort_by: str = Query("id", description="Field to sort by"),
    sort_order: str = Query("asc", regex="^(asc|desc)$",
                            description="Sort order"),
    db: Session = Depends(get_db)
):
    """Get paginated list of tank configurations with filtering and sorting"""
    try:
        # Build query
        query = db.query(TankConfiguration)

        # Apply filters
        if node_id:
            query = query.filter(TankConfiguration.node_id == node_id)

        # Apply sorting
        sort_column = getattr(TankConfiguration, sort_by, TankConfiguration.id)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * size
        data = query.offset(offset).limit(size).all()

        return TankConfigurationListResponse(
            total=total,
            page=page,
            size=size,
            data=data
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error fetching tank configurations: {str(e)}")


@router.get("/thingspeak/data")
async def get_thingspeak_data(
    channel_id: Optional[int] = Query(
        default=None, gt=0, description="ThingSpeak channel ID (optional)"),
    read_api_key: Optional[str] = Query(
        default=None, description="ThingSpeak read API key (optional)"),
    results: int = Query(default=10, ge=1, le=8000),
) -> dict:
    """Fetch data from ThingSpeak channel"""
    # Use default values if none provided
    api_key_to_use = read_api_key or THINGSPEAK_API_KEY
    channel_id_to_use = channel_id or THINGSPEAK_CHANNEL_ID

    params = {"results": results}
    if api_key_to_use:
        params["api_key"] = api_key_to_use

    base_url = f"https://api.thingspeak.com/channels/{channel_id_to_use}/feeds.json"
    url = f"{base_url}?{urlencode(params)}"

    try:
        print(f"\n Fetching data from ThingSpeak...")
        print(f" Channel ID: {channel_id_to_use}")
        print(f" Results requested: {results}")
        print(
            f"� Using API Key: {'*' * (len(api_key_to_use) - 4) + api_key_to_use[-4:] if api_key_to_use else 'None'}")
        print(f"� URL: {url}")

        with urlopen(url, timeout=10) as response:
            payload = response.read().decode("utf-8")

        data = json.loads(payload)

        # Print channel info
        channel_info = data.get("channel", {})
        print(f"\n Channel Info:")
        print(f"   Name: {channel_info.get('name', 'N/A')}")
        print(f"   Description: {channel_info.get('description', 'N/A')}")
        print(f"   Field1: {channel_info.get('field1', 'N/A')}")
        print(f"   Field2: {channel_info.get('field2', 'N/A')}")

        # Print feeds data
        feeds = data.get("feeds", [])
        print(f"\n Retrieved {len(feeds)} data entries:")

        for i, feed in enumerate(feeds[-5:], 1):  # Show last 5 entries
            print(f"   Entry {i}:")
            print(f"     Created At: {feed.get('created_at', 'N/A')}")
            print(f"     Field1: {feed.get('field1', 'N/A')}")
            print(f"     Field2: {feed.get('field2', 'N/A')}")
            print(f"     Entry ID: {feed.get('entry_id', 'N/A')}")

        print(" ThingSpeak data fetched successfully!\n")
        return data

    except Exception as exc:
        print(f" Error fetching ThingSpeak data: {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch data from ThingSpeak: {exc}",
        ) from exc


@router.post("/thingspeak/fetch-and-store")
async def fetch_thingspeak_and_store(
    channel_id: Optional[int] = Query(
        default=None, gt=0, description="ThingSpeak channel ID (optional)"),
    tank_mapping: ThingSpeakToDBPayload = ...,
    read_api_key: Optional[str] = Query(
        default=None, description="ThingSpeak read API key (optional)"),
    results: int = Query(default=10, ge=1, le=8000),
    db: Session = Depends(get_db)
) -> dict:
    """Fetch data from ThingSpeak and store it in the database"""
    try:
        # Use default values if none provided
        channel_id_to_use = channel_id or THINGSPEAK_CHANNEL_ID

        print(f"\n Starting ThingSpeak fetch and store operation...")
        print(f"  Channel ID: {channel_id_to_use}")
        print(f"  Target Tank ID: {tank_mapping.tank_id}")
        print(f" Field Mapping:")
        print(f"   Field1 -> {tank_mapping.field1_name}")
        print(f"   Field2 -> {tank_mapping.field2_name}")
        print(f" Results to fetch: {results}")

        # Use default API key if none provided
        api_key_to_use = read_api_key or THINGSPEAK_API_KEY
        print(
            f" Using API Key: {'*' * (len(api_key_to_use) - 4) + api_key_to_use[-4:] if api_key_to_use else 'None'}")

        # Fetch data from ThingSpeak
        params = {"results": results}
        if api_key_to_use:
            params["api_key"] = api_key_to_use

        base_url = f"https://api.thingspeak.com/channels/{channel_id_to_use}/feeds.json"
        url = f"{base_url}?{urlencode(params)}"

        print(f" Fetching from: {url}")

        with urlopen(url, timeout=10) as response:
            payload = response.read().decode("utf-8")

        thingspeak_data = json.loads(payload)
        feeds = thingspeak_data.get("feeds", [])

        print(f" Retrieved {len(feeds)} feed entries from ThingSpeak")

        stored_records = []
        skipped_records = 0

        # Store each feed entry in the database
        for idx, feed in enumerate(feeds, 1):
            field1_value = feed.get("field1")
            field2_value = feed.get("field2")
            created_at_str = feed.get("created_at")
            entry_id = feed.get("entry_id")

            print(f"\n Processing Entry {idx} (ID: {entry_id}):")
            print(f"   Created At: {created_at_str}")
            print(f"   Field1: {field1_value}")
            print(f"   Field2: {field2_value}")

            # Skip if essential data is missing
            if not field1_value or not field2_value:
                print(f"    Skipping - Missing data")
                skipped_records += 1
                continue

            try:
                # Determine field mapping based on the parameters
                water_level = float(
                    field1_value) if tank_mapping.field1_name == "water_level_cm" else float(field2_value)
                temperature = float(
                    field2_value) if tank_mapping.field2_name == "temperature_c" else float(field1_value)

                print(f"   Water Level: {water_level} cm")
                print(f"   Temperature: {temperature} °C")

                # Create sensor data entry
                sensor_data = TankSensorDataCreate(
                    tank_id=tank_mapping.tank_id,
                    water_level_cm=water_level,
                    temperature_c=temperature
                )

                db_sensor_data = TankSensorData(**sensor_data.dict())

                # If ThingSpeak provides timestamp, use it (optional)
                if created_at_str:
                    try:
                        db_sensor_data.created_at = datetime.fromisoformat(
                            created_at_str.replace('Z', '+00:00'))
                        print(f"   Using ThingSpeak timestamp")
                    except:
                        print(
                            f"   Using current timestamp (failed to parse ThingSpeak time)")

                db.add(db_sensor_data)
                db.commit()
                db.refresh(db_sensor_data)

                print(f"    Stored in database with ID: {db_sensor_data.id}")

                stored_records.append({
                    "id": db_sensor_data.id,
                    "tank_id": db_sensor_data.tank_id,
                    "water_level_cm": db_sensor_data.water_level_cm,
                    "temperature_c": db_sensor_data.temperature_c,
                    "created_at": db_sensor_data.created_at
                })

            except (ValueError, TypeError) as e:
                print(f"    Error processing entry: {e}")
                skipped_records += 1
                continue

        print(f"\n Summary:")
        print(f"   Total feeds fetched: {len(feeds)}")
        print(f"   Successfully stored: {len(stored_records)}")
        print(f"   Skipped (invalid): {skipped_records}")
        print("Fetch and store operation completed!\n")

        return {
            "message": f"Successfully stored {len(stored_records)} records from ThingSpeak",
            "channel_id": channel_id_to_use,
            "total_feeds_fetched": len(feeds),
            "stored_records": len(stored_records),
            "skipped_records": skipped_records,
            "stored_data": stored_records
        }

    except Exception as exc:
        print(f" Error in fetch and store operation: {exc}")
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch and store ThingSpeak data: {exc}",
        ) from exc


# Auto-Sync Endpoints

@router.get("/thingspeak/auto-sync/status", response_model=AutoSyncStatus)
async def get_auto_sync_status():
    """Get current status of auto-sync service"""
    return auto_sync_service.get_status()


@router.post("/thingspeak/auto-sync/enable", response_model=MessageResponse)
async def enable_auto_sync():
    """Enable auto-sync (allows it to be started)"""
    auto_sync_service.enable()
    print("Auto-sync enabled")
    return MessageResponse(message="Auto-sync enabled successfully")





@router.post("/thingspeak/auto-sync/trigger", response_model=MessageResponse)
async def trigger_manual_sync():
    """Manually trigger a sync operation (works even if auto-sync is disabled)"""
    try:
        print("🔄 Triggering manual sync...")

        # Get the private sync method from auto_sync_service
        result = await auto_sync_service._sync_data()

        print(" Manual sync completed")
        return MessageResponse(message="Manual sync triggered successfully")
    except Exception as e:
        print(f" Error in manual sync: {e}")
        raise HTTPException(
            status_code=500, detail=f"Manual sync failed: {str(e)}")
