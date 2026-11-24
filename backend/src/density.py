from collections import defaultdict, deque
from statistics import median

from .contracts import PointKind

MIN_WINDOWS = 3
QUEUE_THRESHOLD = 8
EPS_METERS = 18
MIN_POINTS = 3


def map_floor(stores, observations):
    """Cluster congested stores by physical queue entrance, including each point in its own neighborhood."""
    counts = defaultdict(list)
    for window in observations:
        counts[window['store_id']].append(window['queue_count'])

    points = {}
    candidates = []
    for store in sorted(stores, key=lambda item: item['code']):
        samples = counts[store['id']]
        queue_median = median(samples) if samples else None
        kind = PointKind.INSUFFICIENT
        if len(samples) >= MIN_WINDOWS:
            kind = PointKind.BELOW_THRESHOLD
            if queue_median >= QUEUE_THRESHOLD:
                kind = PointKind.NOISE
                candidates.append(store)
        points[store['id']] = {'windows': len(samples), 'median_queue': queue_median,
                               'kind': kind, 'zone': None}

    neighborhoods = {
        a['id']: [b['id'] for b in candidates
                  if (a['x'] - b['x']) ** 2 + (a['y'] - b['y']) ** 2 <= EPS_METERS ** 2]
        for a in candidates
    }
    cores = {store_id for store_id, nearby in neighborhoods.items() if len(nearby) >= MIN_POINTS}
    anchors = {}
    for store in candidates:
        start = store['id']
        if start not in cores or points[start]['zone'] is not None:
            continue
        zone = len(anchors) + 1
        queue = deque([start])
        points[start].update(kind=PointKind.CORE, zone=zone)
        members = [start]
        while queue:
            for neighbor in neighborhoods[queue.popleft()]:
                if points[neighbor]['zone'] is not None:
                    continue
                is_core = neighbor in cores
                points[neighbor].update(kind=PointKind.CORE if is_core else PointKind.BORDER, zone=zone)
                if is_core:
                    queue.append(neighbor)
                members.append(neighbor)
        # Assign the temporary holding point of the most congested core. Store code breaks ties.
        anchors[zone] = min(
            (item for item in candidates if item['id'] in members and item['id'] in cores),
            key=lambda item: (-points[item['id']]['median_queue'], item['code']),
        )['id']
    return points, anchors
