from sqlalchemy import Column, Integer, Float, DateTime, String
from sqlalchemy.sql import func
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from .database import Base

# SQLAlchemy Database Models
class TankSensorData(Base):
    __tablename__ = "tank_sensor_data"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tank_id = Column(String(50), nullable=True, comment="ID of the tank")
    water_level_cm = Column(Float, nullable=False, comment="Water level in centimeters")
    temperature_c = Column(Float, nullable=False, comment="Temperature in Celsius")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Timestamp when data was recorded")
    
    def __repr__(self):
        return f"<TankSensorData(id={self.id}, tank_id={self.tank_id}, water_level_cm={self.water_level_cm}, temperature_c={self.temperature_c}, created_at={self.created_at})>"

class TankConfiguration(Base):
    __tablename__ = "tank_sensorparameters"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    node_id = Column(String(50), nullable=True, comment="ID of the node")
    tank_height_cm = Column(Float, nullable=False, comment="Tank height in centimeters")
    tank_length_cm = Column(Float, nullable=False, comment="Tank length in centimeters")
    tank_width_cm = Column(Float, nullable=False, comment="Tank width in centimeters")
    lat = Column(Float, nullable=True, comment="Latitude coordinate")
    long = Column(Float, nullable=True, comment="Longitude coordinate")
    
    def __repr__(self):
        return f"<TankConfiguration(id={self.id}, node_id={self.node_id}, tank_height_cm={self.tank_height_cm}, tank_length_cm={self.tank_length_cm}, tank_width_cm={self.tank_width_cm}, lat={self.lat}, long={self.long})>"

# Pydantic Schemas for TankSensorData
class TankSensorDataBase(BaseModel):
    tank_id: Optional[str] = Field(None, description="ID of the tank", max_length=50)
    water_level_cm: float = Field(..., description="Water level in centimeters", ge=0)
    temperature_c: float = Field(..., description="Temperature in Celsius", ge=-50, le=100)

class TankSensorDataCreate(TankSensorDataBase):
    """Schema for creating new tank sensor data"""
    pass

class TankSensorDataUpdate(BaseModel):
    """Schema for updating tank sensor data"""
    tank_id: Optional[str] = Field(None, description="ID of the tank", max_length=50)
    water_level_cm: Optional[float] = Field(None, description="Water level in centimeters", ge=0)
    temperature_c: Optional[float] = Field(None, description="Temperature in Celsius", ge=-50, le=100)

class TankSensorDataResponse(TankSensorDataBase):
    """Schema for tank sensor data response"""
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class TankSensorDataListResponse(BaseModel):
    """Schema for paginated tank sensor data list response"""
    total: int
    page: int
    size: int
    data: list[TankSensorDataResponse]

# Pydantic Schemas for TankConfiguration
class TankConfigurationBase(BaseModel):
    node_id: Optional[str] = Field(None, description="ID of the node", max_length=50)
    tank_height_cm: float = Field(..., description="Tank height in centimeters", ge=0)
    tank_length_cm: float = Field(..., description="Tank length in centimeters", ge=0)
    tank_width_cm: float = Field(..., description="Tank width in centimeters", ge=0)
    lat: Optional[float] = Field(None, description="Latitude coordinate", ge=-90, le=90)
    long: Optional[float] = Field(None, description="Longitude coordinate", ge=-180, le=180)

class TankConfigurationCreate(TankConfigurationBase):
    """Schema for creating new tank configuration"""
    pass

class TankConfigurationUpdate(BaseModel):
    """Schema for updating tank configuration"""
    node_id: Optional[str] = Field(None, description="ID of the node", max_length=50)
    tank_height_cm: Optional[float] = Field(None, description="Tank height in centimeters", ge=0)
    tank_length_cm: Optional[float] = Field(None, description="Tank length in centimeters", ge=0)
    tank_width_cm: Optional[float] = Field(None, description="Tank width in centimeters", ge=0)
    lat: Optional[float] = Field(None, description="Latitude coordinate", ge=-90, le=90)
    long: Optional[float] = Field(None, description="Longitude coordinate", ge=-180, le=180)

class TankConfigurationResponse(TankConfigurationBase):
    """Schema for tank configuration response"""
    id: int
    
    class Config:
        from_attributes = True

class TankConfigurationListResponse(BaseModel):
    """Schema for paginated tank configuration list response"""
    total: int
    page: int
    size: int
    data: list[TankConfigurationResponse]
    
class MessageResponse(BaseModel):
    """Generic message response schema"""
    message: str