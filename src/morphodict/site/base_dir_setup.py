"""
We want to set most settings with `from $default_settings_module import*`. But
to set BASE_DIR correctly, that file needs to know which site it’s being called
from. The current workaround to pass that is to store the base dir here in a
variable that can only be set once.
"""

_base_dir = None


def get_base_dir():
    assert _base_dir is not None, "base_dir unset: set it with set_base_dir()"
    return _base_dir


def set_base_dir(dir):
    global _base_dir

    assert _base_dir is None, "base_dir is already set!"
    assert dir.is_dir()
    _base_dir = dir