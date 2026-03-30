import sqlalchemy.orm

from .base import Base, DateTimeWithTimeZone, info


class SiriRide(Base):
    __tablename__ = 'siri_ride'
    __table_args__ = (
        sqlalchemy.Index(
            'idx_route_journey_ref_vehicle_ref',
            'siri_route_id', 'journey_ref', 'vehicle_ref',
            unique=True
        ),
        sqlalchemy.Index(
            'idx_siri_ride_scheduled_start_date',
            sqlalchemy.text("date_trunc('day', scheduled_start_time)::date")
        ),
        sqlalchemy.ForeignKeyConstraint(
            ['first_vehicle_location_recorded_at_time', 'first_vehicle_location_id'],
            ['siri_vehicle_location.recorded_at_time', 'siri_vehicle_location.id'],
            name='fk_siri_ride_first_vehicle_location_id_siri_vehicle_location',
        ),
        sqlalchemy.ForeignKeyConstraint(
            ['last_vehicle_location_recorded_at_time', 'last_vehicle_location_id'],
            ['siri_vehicle_location.recorded_at_time', 'siri_vehicle_location.id'],
            name='fk_siri_ride_last_vehicle_location_id_siri_vehicle_location',
        ),
        {**info("""
            A ride along a [[siri_route]]. 
            Populated in near real time from the SIRI data by [[siri-etl-process-snapshot-new-snapshots-daemon]].
        """)}
    )
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    siri_route_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('siri_route.id'), index=True,
        **info("The related [[siri_route]].")
    )
    siri_route = sqlalchemy.orm.relationship(
        'SiriRoute', back_populates='siri_rides',
        foreign_keys=[siri_route_id]
    )
    journey_ref = sqlalchemy.Column(
        sqlalchemy.String, index=True,
        **info("A unique identifier for this ride as provided by the SIRI data.")
    )
    scheduled_start_time = sqlalchemy.Column(
        DateTimeWithTimeZone, index=True,
        **info("""
            The scheduled start time as provided by the SIRI data.
            Note that this value may change over time but we only show the first
            value as received from the SIRI real-time data.
            See [this issue](https://github.com/hasadna/open-bus/issues/390) for more details.
        """)
    )
    vehicle_ref = sqlalchemy.Column(
        sqlalchemy.String, index=True,
        **info("""
            A unique identifier of the bus or vehicle.
            This may be the license number but could 
            also be other identifier as provided by the SIRI data.
        """)
    )
    siri_ride_stops = sqlalchemy.orm.relationship(
        'SiriRideStop', back_populates='siri_ride',
        primaryjoin='SiriRide.id==SiriRideStop.siri_ride_id'
    )

    # added by open-bus-stride-etl siri add-ride-duration-minutes
    updated_first_last_vehicle_locations = sqlalchemy.Column(
        DateTimeWithTimeZone, index=True, **info(hide=True)
    )
    first_vehicle_location_recorded_at_time = sqlalchemy.Column(
        DateTimeWithTimeZone, **info(hide=True)
    )
    first_vehicle_location_id = sqlalchemy.Column(
        sqlalchemy.BigInteger,
        **info("""
            The first [[siri_vehicle_location]] along this ride.
            Populated by [[stride-etl-siri-add-ride-durations]].
        """)
    )
    last_vehicle_location_recorded_at_time = sqlalchemy.Column(
        DateTimeWithTimeZone, **info(hide=True)
    )
    last_vehicle_location_id = sqlalchemy.Column(
        sqlalchemy.BigInteger,
        **info("""
            The last [[siri_vehicle_location]] along this ride.
            Populated by [[stride-etl-siri-add-ride-durations]].
        """)
    )
    updated_duration_minutes = sqlalchemy.Column(
        DateTimeWithTimeZone, index=True, **info(hide=True)
    )
    duration_minutes = sqlalchemy.Column(
        sqlalchemy.Integer, index=True,
        **info("""
            The duration of this ride in minutes.
            Populated by [[stride-etl-siri-add-ride-durations]].
        """)
    )

    # added by open-bus-stride-etl siri update-rides-gtfs
    journey_gtfs_ride_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('gtfs_ride.id'),
        **info("""
            Deprecated: The related [[gtfs_ride]] based on journey_ref.
            Populated by [[stride-etl-siri-update-rides-gtfs]].
        """)
    )
    route_gtfs_ride_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('gtfs_ride.id'), index=True,
        **info("""
            Deprecated: The related [[gtfs_ride]] based on operator_ref, line_ref and scheduled_start_time.
            Populated by [[stride-etl-siri-update-rides-gtfs]].
        """)
    )
    scheduled_time_gtfs_ride_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('gtfs_ride.id'), index=True,
        **info("""
            The related [[gtfs_ride]] based on operator_ref, line_ref and scheduled_start_time.
            Populated by [[stride-etl-siri-update-rides-gtfs]].
        """)
    )
    gtfs_ride_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('gtfs_ride.id'),
        **info("""
            The related [[gtfs_ride]] based on best match from either [[journey_gtfs_ride_id]] or [[route_gtfs_ride_id]].
            Populated by [[stride-etl-siri-update-rides-gtfs]].
        """)
    )
