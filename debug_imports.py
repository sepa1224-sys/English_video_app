
import sys
import traceback

print("Starting import debug...")
try:
    import main
    print("Import main successful")
except Exception:
    print("Import main failed:")
    traceback.print_exc()
