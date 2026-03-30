#!/usr/bin/env python
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from open_bus_stride_db.timescale_framework import (
    OnlineHypertableMigrationOperator,
    SIRI_VEHICLE_LOCATION_SPEC,
)


def main():
    operator = OnlineHypertableMigrationOperator(SIRI_VEHICLE_LOCATION_SPEC)
    return operator.main()


if __name__ == '__main__':
    sys.exit(main())
