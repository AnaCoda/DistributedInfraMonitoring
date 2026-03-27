



def _recurse_merge_dict(source: dict, new: dict):
    for k, v in new.items():
        # Case 1: We do not even have this key.
        if k not in source:
            source[k] = v
        else:
            # Case 2: We DO have this key.
            if isinstance(v, dict) and isinstance(source[k], dict):
                # Case 2A: Both are dictionaries, so we recursively merge.
                _recurse_merge_dict(source[k], v)
            else:
                # Case 2B: They are not both dictionaries, therefore override with this key.
                source[k] = v
            

def merge_dictionaries(source: dict, new: dict):
    _recurse_merge_dict(source, new)
