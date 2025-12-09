import socket
import time
import csv
import os
import sys
from datetime import datetime
from protocol import MAX_BYTES, HEADER_SIZE, parse_header, MSG_INIT, MSG_DATA, HEART_BEAT

# --- Real-time logging ---
sys.stdout.reconfigure(line_buffering=True)

# --- Server setup ---
SERVER_PORT = 12000
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(('', SERVER_PORT))
print(f"UDP Server running on port {SERVER_PORT} (max {MAX_BYTES} bytes)")

# --- CSV Configuration ---
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

CSV_FILENAME = os.path.join(LOG_DIR, "iot_device_data.csv")
CSV_HEADERS = [
    "server_timestamp", "unit","device_id", "batch_count", "sequence_number",
    "device_timestamp", "message_type", "payload",
    "client_address", "delay_seconds", "duplicate_flag", "gap_flag", "packet_size"
]

def init_csv_file():
    """Initialize CSV file with headers if it doesn't exist or is empty."""
    needs_header = False
    if not os.path.exists(CSV_FILENAME):
        needs_header = True
    elif os.path.getsize(CSV_FILENAME) == 0:
        needs_header = True

    if needs_header:
        with open(CSV_FILENAME, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(CSV_HEADERS)
        print(f"Created new CSV file with headers: {CSV_FILENAME}")
    else:
        print(f"Appending to existing CSV: {CSV_FILENAME}")

def save_to_csv(data_dict):
    """Append one row to the CSV file."""
    try:
        with open(CSV_FILENAME, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            msg_type = data_dict['msg_type']
            if msg_type == MSG_INIT:
                msg_type_str = "INIT"
            elif msg_type == MSG_DATA:
                msg_type_str = "DATA"
            elif msg_type == HEART_BEAT:
                msg_type_str = "HEARTBEAT"
            else:
                msg_type_str = f"UNKNOWN({msg_type})"

            row = [
                data_dict['server_timestamp'],
                data_dict['unit'],  
                data_dict['device_id'],
                data_dict['batch_count'],
                data_dict['seq'],
                data_dict['timestamp'],
                msg_type_str,
                data_dict['payload'],
                data_dict['client_address'],
                data_dict['delay_seconds'],
                data_dict['duplicate_flag'],
                data_dict['gap_flag'],
                data_dict['packet_size']
            ]
            writer.writerow(row)
            print(f" Data saved (seq={data_dict['seq']})")
    except Exception as e:
        print(f" Error writing to CSV: {e}")

# --- Initialize ---
init_csv_file()
device_state = {}
received_count = 0
duplicate_count = 0
all_sequences = {}
device_units = {}

try:
    while True:
        data, addr = server_socket.recvfrom(MAX_BYTES)
        server_receive_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

        try:
            header = parse_header(data)
        except ValueError as e:
            print("Header error:", e)
            continue

        payload = data[HEADER_SIZE:].decode('utf-8', errors='ignore')

        device_id = header['device_id']
        seq = header['seq']
        duplicate_flag = 0
        gap_flag = 0

        # --- Duplicate & Gap detection ---
        if device_id in device_state:
            last_seq = device_state[device_id]
            if seq == last_seq:
                duplicate_flag = 1
            elif seq > last_seq + 1:
                gap_flag = 1
        device_state[device_id] = seq

        # --- Delay calculation ---
        delay = round(time.time() - header['timestamp'], 3)

        # --- Tracking ---
        received_count += 1
        if device_id not in all_sequences:
            all_sequences[device_id] = set()
        if seq in all_sequences[device_id]:
            duplicate_count += 1
        all_sequences[device_id].add(seq)
        unit = device_units.get(device_id, "")  # empty if unknown
        csv_data = {
            'server_timestamp': f" {server_receive_time}",
            'unit': unit,
            'device_id': header['device_id'],
            'batch_count': header['batch_count'],
            'seq': header['seq'],
            'timestamp': f" {time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(header['timestamp']))}.{header['milliseconds']:03d}",
            'msg_type': header['msg_type'],
            'payload': payload,
            'client_address': f"{addr[0]}:{addr[1]}",
            'delay_seconds': delay,
            'duplicate_flag': duplicate_flag,
            'gap_flag': gap_flag,
            'packet_size': len(data)
        }

        # --- Message handling ---
        if header['msg_type'] == MSG_DATA:
            save_to_csv(csv_data)
            print(f" -> DATA message received (seq={seq}, delay={delay}s)")
        elif header['msg_type'] == MSG_INIT:
            unit = payload.strip()
            device_units[device_id] = unit
            print(f" -> INIT message from Device {device_id}, unit={unit}")
        elif header['msg_type'] == HEART_BEAT:
            print(f" -> HEARTBEAT from Device {device_id} at {time.ctime(header['timestamp'])}")
        else:
            print("Unknown message type.")

except KeyboardInterrupt:
    print("\nServer interrupted. Generating summary...")

    total_expected = max(max(seqs) for seqs in all_sequences.values()) if all_sequences else 0
    missing_count = total_expected - received_count
    delivery_rate = (received_count / total_expected) * 100 if total_expected else 0

    print("\n=== Baseline Test Summary ===")
    print(f"Total received: {received_count}")
    print(f"Missing packets: {missing_count}")
    print(f"Duplicate packets: {duplicate_count}")
    print(f"Delivery rate: {delivery_rate:.2f}%")