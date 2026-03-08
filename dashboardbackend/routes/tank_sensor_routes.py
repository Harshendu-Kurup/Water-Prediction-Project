from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from typing import List, Optional
from models.database import get_db
from models.models import (
    TankSensorData,
    TankSensorDataCreate,
    TankSensorDataResponse,
    TankSensorDataUpdate,
    TankSensorDataListResponse,
    MessageResponse
)

router = APIRouter()


@router.post("/tank-sensor", response_model=TankSensorDataResponse, status_code=201)
async def create_tank_sensor_data(tank_sensor: TankSensorDataCreate, db: Session = Depends(get_db)):
    """Create new tank sensor data"""
    try:
        db_tank_sensor = TankSensorData(**tank_sensor.dict())
        db.add(db_tank_sensor)
        db.commit()
        db.refresh(db_tank_sensor)
        return db_tank_sensor
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"Error creating tank sensor data: {str(e)}")


@router.get("/tank-sensor", response_model=TankSensorDataListResponse)
async def get_tank_sensor_data(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100,
                      description="Number of items per page"),
    tank_id: Optional[str] = Query(None, description="Filter by tank ID"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", regex="^(asc|desc)$",
                            description="Sort order"),
    db: Session = Depends(get_db)
):
    """Get paginated list of tank sensor data with filtering and sorting"""
    try:
        # Build query
        query = db.query(TankSensorData)

        # Apply filters
        if tank_id:
            query = query.filter(TankSensorData.tank_id == tank_id)

        # Apply sorting
        sort_column = getattr(TankSensorData, sort_by,
                              TankSensorData.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * size
        data = query.offset(offset).limit(size).all()

        return TankSensorDataListResponse(
            total=total,
            page=page,
            size=size,
            data=data
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error fetching tank sensor data: {str(e)}")


@router.put("/tank-sensor/{sensor_id}", response_model=TankSensorDataResponse)
async def update_tank_sensor_data(
    sensor_id: int,
    tank_sensor_update: TankSensorDataUpdate,
    db: Session = Depends(get_db)
):
    """Update existing tank sensor data"""
    try:
        db_tank_sensor = db.query(TankSensorData).filter(
            TankSensorData.id == sensor_id).first()
        if not db_tank_sensor:
            raise HTTPException(
                status_code=404, detail="Tank sensor data not found")

        # Update only provided fields
        update_data = tank_sensor_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_tank_sensor, field, value)

        db.commit()
        db.refresh(db_tank_sensor)
        return db_tank_sensor
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"Error updating tank sensor data: {str(e)}")


@router.delete("/tank-sensor/{sensor_id}", response_model=MessageResponse)
async def delete_tank_sensor_data(sensor_id: int, db: Session = Depends(get_db)):
    """Delete tank sensor data by ID"""
    try:
        db_tank_sensor = db.query(TankSensorData).filter(
            TankSensorData.id == sensor_id).first()
        if not db_tank_sensor:
            raise HTTPException(
                status_code=404, detail="Tank sensor data not found")

        db.delete(db_tank_sensor)
        db.commit()
        return MessageResponse(message=f"Tank sensor data with ID {sensor_id} deleted successfully")
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"Error deleting tank sensor data: {str(e)}")
