"""複数ホストの runs / queue を横断集約する Fleet API。"""

from parc.fleet.aggregate import (
    enqueue_on_host,
    fleet_hosts,
    fleet_queue,
    fleet_runs,
)
from parc.fleet.gpu_watch import gpu_check

__all__ = [
    "enqueue_on_host",
    "fleet_hosts",
    "fleet_queue",
    "fleet_runs",
    "gpu_check",
]
