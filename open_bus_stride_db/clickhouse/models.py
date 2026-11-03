"""Generated ClickHouse ORM mappings; run bin/generate_clickhouse_models.py."""

from sqlalchemy import BigInteger, Column, Date, DateTime, Float, Integer, String, Table
from sqlalchemy.orm import declarative_base

Base = declarative_base()


siri_ride = Table('siri_ride', Base.metadata,
    Column('id', String, nullable=False),
    Column('siri_route_id', String, nullable=False),
    Column('journey_ref', String, nullable=False),
    Column('scheduled_start_time', DateTime, nullable=False),
    Column('vehicle_ref', String, nullable=False),
    Column('first_vehicle_location_id', String, nullable=False),
    Column('last_vehicle_location_id', String, nullable=False),
    Column('duration_minutes', Integer, nullable=True),
    Column('gtfs_ride_id', Integer, nullable=True),
)


class SiriRideDurations(Base):
    __tablename__ = 'siri_ride_durations'
    siri_ride_id = Column(String, primary_key=True)
    first_vehicle_location_id = Column(String, nullable=False)
    last_vehicle_location_id = Column(String, nullable=False)
    first_recorded_at_time = Column(DateTime, nullable=False)
    last_recorded_at_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    calculated_at = Column(DateTime, nullable=False)


siri_ride_durations_mv = Table('siri_ride_durations_mv', Base.metadata,
    Column('siri_ride_id', String, nullable=False),
    Column('first_vehicle_location_id', String, nullable=False),
    Column('last_vehicle_location_id', String, nullable=False),
    Column('first_recorded_at_time', DateTime, nullable=False),
    Column('last_recorded_at_time', DateTime, nullable=False),
    Column('duration_minutes', Integer, nullable=True),
    Column('calculated_at', DateTime, nullable=False),
)


class SiriRideGtfsRide(Base):
    __tablename__ = 'siri_ride_gtfs_ride'
    siri_ride_id = Column(String, primary_key=True)
    gtfs_ride_id = Column(Integer, nullable=True)
    calculated_at = Column(DateTime, nullable=False)


siri_ride_gtfs_ride_mv = Table('siri_ride_gtfs_ride_mv', Base.metadata,
    Column('siri_ride_id', String, nullable=False),
    Column('gtfs_ride_id', Integer, nullable=True),
    Column('calculated_at', DateTime, nullable=False),
)


class SiriRideStopGtfsStop(Base):
    __tablename__ = 'siri_ride_stop_gtfs_stop'
    siri_ride_stop_id = Column(String, primary_key=True)
    gtfs_stop_id = Column(Integer, nullable=True)
    calculated_at = Column(DateTime, nullable=False)


siri_ride_stop_gtfs_stop_mv = Table('siri_ride_stop_gtfs_stop_mv', Base.metadata,
    Column('siri_ride_stop_id', String, nullable=False),
    Column('gtfs_stop_id', Integer, nullable=True),
    Column('calculated_at', DateTime, nullable=False),
)


class SiriVehicleLocation(Base):
    __tablename__ = 'siri_vehicle_location'
    siri_snapshot_id = Column(String, nullable=False)
    recorded_at_time = Column(DateTime, primary_key=True)
    line_ref = Column(String, nullable=False)
    data_frame_ref = Column(String, nullable=False)
    dated_vehicle_journey_ref = Column(String, nullable=False)
    operator_ref = Column(String, nullable=False)
    origin_aimed_departure_time = Column(DateTime, nullable=False)
    vehicle_location_longitude = Column(String, nullable=False)
    vehicle_location_latitude = Column(String, nullable=False)
    bearing = Column(String, nullable=False)
    velocity = Column(String, nullable=False)
    vehicle_ref = Column(String, nullable=False)
    stop_point_ref = Column(String, nullable=False)
    stop_order = Column(String, nullable=False)
    distance_from_stop = Column(String, nullable=False)
    journey_ref = Column(String, nullable=False)
    id = Column(String, nullable=False)
    siri_route_id = Column(String, nullable=False)
    scheduled_start_time = Column(DateTime, nullable=False)
    siri_ride_id = Column(String, nullable=False)
    stop_code = Column(String, nullable=False)
    siri_stop_id = Column(String, nullable=False)
    siri_ride_stop_id = Column(String, nullable=False)


class SiriVehicleLocationDistanceFromGtfsStop(Base):
    __tablename__ = 'siri_vehicle_location_distance_from_gtfs_stop'
    siri_ride_stop_id = Column(String, primary_key=True)
    vehicle_location_latitude = Column(String, primary_key=True)
    vehicle_location_longitude = Column(String, primary_key=True)
    distance_from_gtfs_stop_meters = Column(Float, nullable=True)
    calculated_at = Column(DateTime, nullable=False)


siri_vehicle_location_distance_from_gtfs_stop_mv = Table('siri_vehicle_location_distance_from_gtfs_stop_mv', Base.metadata,
    Column('siri_ride_stop_id', String, nullable=False),
    Column('vehicle_location_latitude', String, nullable=False),
    Column('vehicle_location_longitude', String, nullable=False),
    Column('distance_from_gtfs_stop_meters', Float, nullable=True),
    Column('calculated_at', DateTime, nullable=False),
)
