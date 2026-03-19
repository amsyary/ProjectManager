#-----------------------------------------------------------------------------
# Custom hook to work around PyInstaller tkinter Tcl/Tk collection error.
# When tcl_dir is None (e.g. Microsoft Store Python, non-standard install),
# the default hook crashes. This hook catches the error and continues.
#-----------------------------------------------------------------------------

from PyInstaller import compat
from PyInstaller.utils.hooks import logger


def hook(hook_api):
    """Freeze Tcl/Tk data files, or skip gracefully if collection fails."""
    if not (compat.is_win or compat.is_darwin or compat.is_unix):
        logger.error("... skipping Tcl/Tk handling on unsupported platform %s", __import__("sys").platform)
        return

    try:
        from PyInstaller.utils.hooks.tcl_tk import collect_tcl_tk_files
        datas = collect_tcl_tk_files(hook_api.__file__)
        if datas:
            hook_api.add_datas(datas)
    except (TypeError, OSError) as e:
        logger.warning(
            "Could not collect Tcl/Tk files (tcl_dir may be None). "
            "The frozen app may still work if Tcl/Tk is available at runtime. Error: %s",
            e,
        )
