import subprocess
import sys

with open("run_log_captured.txt", "w", encoding="utf-8") as f:
    process = subprocess.Popen(
        [sys.executable, "main.py", "--topic", "Debug Video Gen 13", "--level", "B2"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace"
    )
    
    for line in process.stdout:
        print(line, end="")
        f.write(line)
        f.flush()
    
    process.wait()
