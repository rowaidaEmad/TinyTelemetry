import socket
import threading
import time
import os
import sys
from protocol import MAX_BYTES, build_header, MSG_INIT, MSG_DATA, HEART_BEAT

# Configurable defaults
DEFAULT_INTERVAL_DURATION = 60  # total test duration = 60s
DEFAULT_INTERVALS = [1, 5, 30]
# Parse command-line arguments
if len(sys.argv) > 1:
    try:
        Interval_Duration = int(sys.argv[1])
    except ValueError:
        Interval_Duration = DEFAULT_INTERVAL_DURATION
else:
    Interval_Duration = DEFAULT_INTERVAL_DURATION

# 4 arguments: Interval_Duration, intervals_csv, device_id, measuring_unit
if len(sys.argv) != 5:
    print("Usage: python udpclnt.py <Interval_Duration_seconds> <intervals_csv> <device_id> <measuring_unit>")
    print("ex: python udpclnt.py 60 \"1,5,30\" 1 Temp_C")
    sys.exit(1)

try:
    Interval_Duration = int(sys.argv[1])
except ValueError:
    print("error: Interval_Duration must be an integer (seconds).")
    sys.exit(1)

try:
    intervals = [int(x) for x in sys.argv[2].split(",") if x.strip()]
    if not intervals:
        raise ValueError
except ValueError:
    print("error: intervals_csv must be a comma-separated list of integers, ex: \"1,5,30\".")
    sys.exit(1)

try:
    device_id = int(sys.argv[3])
except ValueError:
    print("error: device_id must be an integer.")
    sys.exit(1)

measuring_unit = sys.argv[4].strip()
if not measuring_unit:
    print("error: measuring_unit must be a non-empty string (ex: temp_C).")
    sys.exit(1)

print(f"Configured Interval_Duration={Interval_Duration}s, intervals={intervals}, device_id={device_id}, unit={measuring_unit}")



SERVER_ADDR = ('localhost', 12000)
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

seq_num = 1
running = True

# Send INIT message once
init_payload = measuring_unit.encode("utf-8")

header = build_header(device_id=device_id, batch_count=0, seq_num=seq_num, msg_type=MSG_INIT)

init_packet = header + init_payload
client_socket.sendto(init_packet, SERVER_ADDR)
print(f"Sent INIT (device_id={device_id}, seq={seq_num}, unit={measuring_unit})")
seq_num += 1


def send_heartbeat():
    """Send heartbeat messages every 10 seconds."""
    global seq_num, running
    while running:
        time.sleep(10)
        header = build_header(device_id=device_id, batch_count=0, seq_num=seq_num, msg_type=HEART_BEAT)
        client_socket.sendto(header, SERVER_ADDR)
        print(f"Sent HEARTBEAT (device_id={device_id}, seq={seq_num})")
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
        print(f"Starting test for intervals {intervals} ({Interval_Duration}s each)...")

        for interval in intervals:
            print(f"\n--- Running {interval}s interval for {Interval_Duration} seconds ---")
            start_interval = time.time()
            while time.time() - start_interval < Interval_Duration:
                line = lines[(seq_num - 1) % len(lines)]
                values = [v.strip() for v in line.split(",") if v.strip()]
                batch_count = len(values)
                payload = ",".join(values).encode("utf-8")

                header = build_header(device_id=device_id, batch_count=batch_count, seq_num=seq_num, msg_type=MSG_DATA)
                packet = header + payload


                client_socket.sendto(packet, SERVER_ADDR)
                print(f"Sent DATA seq={seq_num}, interval={interval}s, readings={values}")
                seq_num += 1
                time.sleep(interval)

print("Test finished. Closing client...")
running = False
client_socket.close()
print("Client finished.")