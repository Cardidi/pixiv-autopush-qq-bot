from datetime import datetime
import sys
import traceback

print_debug = True


def _ptprint(msg: str):
    n = datetime.now()
    t = n.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t}] " + msg)


def success(text: str = None):
    if text is None:
        _ptprint("✅ Success")
    else:
        _ptprint("✅ Success: " + text)


def process(text: str = None):
    if text is None:
        _ptprint("⏳ Process")
    else:
        _ptprint("⏳ Process: " + text)


def warn(text: str = None):
    if text is None:
        _ptprint("⚠️ Warning")
    else:
        _ptprint("⚠️ Warning: " + text)


def failed(text: str = None):
    if text is None:
        _ptprint("❌ Failed")
    else:
        _ptprint("❌ Failed: " + text)


def debug(text: str = None):
    if not print_debug:
        return
    if text is None:
        _ptprint("💡 Debug")
    else:
        _ptprint("💡 Debug: " + text)


def print_recent_err():
    et, ev, tb = sys.exc_info()
    traceback.print_exception(et, ev, tb)
