import socket
import threading
import time
import os
import sys
from protocol import MAX_BYTES, build_header, MSG_INIT, MSG_DATA, HEART_BEAT, unit_to_code

# Configurable defaults
DEFAULT_TOTAL_DURATION = 20  # total test duration = 60s * 3 intervals
DEFAULT_INTERVALS = [1, 5, 30]

# Parse command-line arguments
if len(sys.argv) > 1:
    try:
        total_duration = int(sys.argv[1])
    except ValueError:
        total_duration = DEFAULT_TOTAL_DURATION
else:
    total_duration = DEFAULT_TOTAL_DURATION

if len(sys.argv) > 2:
    try:
        intervals = [int(x) for x in sys.argv[2].split(",")]
    except ValueError:
        intervals = DEFAULT_INTERVALS
else:
    intervals = DEFAULT_INTERVALS

if len(sys.argv) > 3:
    unit = sys.argv[3]
else:
    unit = "celsius"

unit_code = unit_to_code(unit)

SERVER_ADDR = ('localhost', 12000)
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

seq_num = 1
running = True

# Send INIT message once
header = build_header(device_id=1, batch_count=unit_code, seq_num=seq_num, msg_type=MSG_INIT)
client_socket.sendto(header, SERVER_ADDR)
print(f"Sent INIT (seq={seq_num}, unit={unit})")
seq_num += 1
time.sleep(0.1)  # Ensure INIT is sent first

def send_heartbeat():
    """Send heartbeat messages every 3 seconds."""
    global seq_num, running
    while running:
        time.sleep(3)
        header = build_header(device_id=1, batch_count=0, seq_num=seq_num, msg_type=HEART_BEAT)
        client_socket.sendto(header, SERVER_ADDR)
        print(f"Sent HEARTBEAT (seq={seq_num})")
        seq_num += 1

# Start heartbeat thread
threading.Thread(target=send_heartbeat, daemon=True).start()

# Load sensor data
if not os.path.exists("sensor_values.txt"):
    print("sensor_values.txt not found. Please create it with comma-separated values.")
    running = False
else:
    with open("sensor_values.txt") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        print("sensor_values.txt is empty.")
        running = False
    else:
        print(f"Starting test for intervals {intervals} (60s each)...")

        for interval in intervals:
            print(f"\n--- Running {interval}s interval for 60 seconds ---")
            start_interval = time.time()
            while time.time() - start_interval < 60:
                line = lines[(seq_num - 1) % len(lines)]
                values = [v.strip() for v in line.split(",") if v.strip()]
                while values:
                    chunk = values[:10]
                    batch_count = len(chunk)
                    payload = ",".join(chunk).encode("utf-8")

                    header = build_header(device_id=1, batch_count=batch_count,
                                          seq_num=seq_num, msg_type=MSG_DATA)
                    filler = b"\x00" * (MAX_BYTES - len(header) - len(payload))
                    packet = header + payload + filler

                    client_socket.sendto(packet, SERVER_ADDR)
                    print(f"Sent DATA seq={seq_num}, interval={interval}s, readings={chunk}")
                    seq_num += 1
                    values = values[10:]
                time.sleep(interval)

print("Test finished. Closing client...")
running = False
client_socket.close()
print("Client finished.")