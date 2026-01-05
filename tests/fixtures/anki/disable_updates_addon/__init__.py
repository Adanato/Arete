# Disable Anki update checks
# This add-on patches the update check function to do nothing

from aqt import mw


# Patch the update check function
def noop_update_check(*args, **kwargs):
    pass


# Hook into Anki's startup and disable update checking
if hasattr(mw, "pm") and hasattr(mw.pm, "set_next_update_check"):
    # Disable automatic update checks
    mw.pm.set_next_update_check(2147483647)  # Set to max int (year 2038)

# Monkey-patch the update check function
try:
    import aqt.update

    aqt.update.check_for_update = noop_update_check
except (ImportError, AttributeError):
    pass
