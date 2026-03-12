_compact_requested = False


def request_compact():
    global _compact_requested
    _compact_requested = True


def was_compact_requested() -> bool:
    global _compact_requested
    result = _compact_requested
    _compact_requested = False
    return result
