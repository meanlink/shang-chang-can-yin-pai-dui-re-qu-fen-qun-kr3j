from math import ceil, floor

from fastapi import HTTPException

PEAK_MINIMUM = 25
MIN_INCREASE = 5


def thresholds(sealed_median):
    return {
        'trigger_queue': max(PEAK_MINIMUM, ceil(sealed_median + MIN_INCREASE)),
        'release_limit': floor(sealed_median),
    }


def require_trigger(reported_queue, sealed_median):
    standard = thresholds(sealed_median)
    if reported_queue < standard['trigger_queue']:
        raise HTTPException(409, f"当前人数未达到临时控流门槛（{standard['trigger_queue']} 人）")
    return standard['release_limit']


def require_release(queue_count, limit):
    if queue_count > limit:
        raise HTTPException(409, f'复测须降至封存基线以内（最多 {limit} 人）')
