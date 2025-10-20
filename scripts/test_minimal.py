import subprocess
import json
import time

cmd = [
    "claude",
    "-p",
    "--verbose",
    "--input-format", "stream-json",
    "--output-format", "stream-json",
]

print("CMD:", " ".join(cmd))
proc = subprocess.Popen(
    " ".join(cmd),
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    shell=True,
)

msg = {
    "type": "user",
    "message": {
        "role": "user",
        "content": "Sag kurz Hallo."
    }
}

proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
proc.stdin.flush()

start = time.time()
while time.time() - start < 15:
    line = proc.stdout.readline()
    if not line:
        continue
    print("OUT:", line.decode("utf-8", errors="ignore").strip())
    break
else:
    print("No response within 15s")

stderr = proc.stderr.read().decode("utf-8", errors="ignore")
if stderr:
    print("STDERR:")
    print(stderr)

proc.terminate()
