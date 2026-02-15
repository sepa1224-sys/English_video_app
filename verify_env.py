
import os
import sys

print("Hello from verify_env.py")
with open("verify_log.txt", "w") as f:
    f.write("Hello file system")
    f.write(f"CWD: {os.getcwd()}")

import script_gen
print("script_gen imported")
