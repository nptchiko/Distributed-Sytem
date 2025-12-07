#!/bin/bash
# A script to run multiple instances of the main.py DFS server for replication.

# Number of server replicas to run
NUM_REPLICAS=2

# Base port number
BASE_PORT=9001

# Path to the main server script
SERVER_SCRIPT="../ServerSide/main2.py"

# --- Main script logic ---

# Array to hold the PIDs of the background server processes
pids=()

# Function to shut down all server processes
shutdown() {
    echo "Shutting down all server replicas..."
    for pid in "${pids[@]}"; do
        # A SIGTERM is sent, allowing the server's shutdown hooks to run
        kill "$pid"
    done
    # Wait for all background processes to terminate
    wait

    echo "Clear replica directory..."

    for (( i = 0; i < NUM_REPLICAS; i++)); do 
      PORT=$((BASE_PORT + i))

      # Define a unique storage directory for this replica
      STORAGE_DIR="$PWD/temp/storage_replica_$PORT"

      rmdir -p "$STORAGE_DIR"

    done
    echo "All replicas have been shut down."
}

# Register the shutdown function to be called on script exit (e.g., Ctrl+C)
trap shutdown SIGINT SIGTERM

# Check if the main server script exists
if [ ! -f "$SERVER_SCRIPT" ]; then
    echo "Error: Server script not found at '$SERVER_SCRIPT'"
    exit 1
fi

# Loop to start each server replica
for (( i=0; i<NUM_REPLICAS; i++ )); do
    # Calculate the port for the current replica
    PORT=$((BASE_PORT + i))

    # Define a unique storage directory for this replica
    STORAGE_DIR="$PWD/temp/storage_replica_$PORT"
    # Create the storage directory if it doesn't exist
    mkdir -p "$STORAGE_DIR"

    echo "Starting server replica #$((i+1)) on port $PORT with storage at '$STORAGE_DIR'..."

    # To ensure the server script uses the correct storage directory,
    # we'll modify the script to accept the storage path as a command-line argument.
    # Let's assume the server is updated to be run like:
    # python main.py <host> <port> <storage_dir>

    # For now, we'll launch it and it will use its default storage path.
    # A more robust solution would involve passing the storage directory to the server.
    python3 "$SERVER_SCRIPT" "0.0.0.0" "$PORT" "$STORAGE_DIR" &

    # Capture the PID of the last background process
    pids+=($!)
done

echo "All $NUM_REPLICAS server replicas are running in the background."
echo "PIDs: ${pids[*]}"
echo "Press Ctrl+C to shut them all down."

# Wait indefinitely until the script is interrupted
wait
