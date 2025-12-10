#!/bin/bash
# run_baseline.sh

# 1. Reset network settings
sudo tc qdisc del dev lo root 2>/dev/null

# 2. Detect a working Python command
for cmd in python3 python py; do
    if command -v $cmd &>/dev/null; then
        if $cmd -V &>/dev/null; then
            PYTHON=$cmd
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ No working Python interpreter found! Please install Python and add it to PATH."
    exit 1
else
    echo "✅ Using Python command: $PYTHON"
fi

# 3. Ask user for configuration
read -p "Enter test duration for each interval in seconds [default: 60]: " DURATION
DURATION=${DURATION:-60}

read -p "Enter intervals separated by commas [default: 1,5,30]: " INTERVALS
INTERVALS=${INTERVALS:-1,5,30}

echo ""
echo "➡️  Running test with duration=${DURATION}s and intervals=${INTERVALS}"
echo ""

# 4. Start server in background
$PYTHON udpsrv.py > server_baseline.log 2>&1 &
SERVER_PID=$!
echo "Server started with PID $SERVER_PID"
sleep 1

# 5. Run client with user-chosen values
$PYTHON udpclnt.py $DURATION $INTERVALS > client_baseline.log 2>&1
echo "Client finished."
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
if [ -f logs/iot_device_data.csv ]; then
    mv logs/iot_device_data.csv logs/baseline.csv 2>/dev/null

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