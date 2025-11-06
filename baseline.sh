#!/bin/bash
# run_baseline.sh

# 1. Reset network settings
sudo tc qdisc del dev lo root 2>/dev/null

# 2. Start the server in the background
python3 udpsrv.py > server_baseline.log 2>&1 &
SERVER_PID=$!
echo "Server started with PID $SERVER_PID"

# 3. Wait a moment to ensure the server is ready
sleep 1

# 4. Run the client
python3 udpclnt.py > client_baseline.log 2>&1
echo "Client finished."

# 5. Give the server time to finish processing
sleep 1

# 6. Stop the server if it's still running
if ps -p $SERVER_PID > /dev/null; then
    kill $SERVER_PID
    echo "Server stopped."
else
    echo "Server already exited."
fi

# 7. Move the CSV file to logs
mkdir -p logs
if [ -f iot_device_data.csv ]; then
    mv iot_device_data.csv logs/baseline.csv 2>/dev/null

    # If move failed, try with sudo or fallback
    if [ ! -f logs/baseline.csv ]; then
        echo "Permission issue — trying with sudo..."
        sudo mv iot_device_data.csv logs/baseline.csv 2>/dev/null
    fi

    # Final fallback if still not moved
    if [ ! -f logs/baseline.csv ]; then
        echo "Still can't move file — saving to home folder instead."
        mv iot_device_data.csv ~/baseline.csv
        echo "Data saved to ~/baseline.csv"
    else
        echo "Data saved to logs/baseline.csv"
    fi
else
    echo "No CSV file found — server may not have received data."
fi

echo "Baseline test complete."