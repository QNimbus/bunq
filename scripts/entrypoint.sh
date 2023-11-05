#!/bin/env bash

# entrypoint.sh

# Start the background process
scripts/chisel.sh &

# Execute the Docker CMD
exec "$@"
