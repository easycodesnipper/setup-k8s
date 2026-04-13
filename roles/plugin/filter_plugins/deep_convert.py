# roles/plugin/filter_plugins/deep_convert.py

def deep_convert(value):
    """
    Recursively convert:
    - string digits -> int
    - string 'true'/'false' -> bool
    - everything else remains unchanged
    """
    if isinstance(value, dict):
        return {k: deep_convert(v) for k, v in value.items()}
    if isinstance(value, list):
        return [deep_convert(v) for v in value]
    if isinstance(value, str):
        # integer
        if value.isdigit():
            return int(value)
        # boolean
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
    return value

class FilterModule:
    def filters(self):
        return {'deep_convert': deep_convert}