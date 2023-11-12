#!/bin/env bash

# entrypoint.sh

# Hack since vscode tasks.json doesn't support envFile (yet)
if [[ -f .env ]]; then
    source .env
fi

/usr/local/bin/chisel client \
    --fingerprint=${CHISEL_SERVER_FINGERPRINT} \
    --auth=${CHISEL_SERVER_AUTH} \
    ${CHISEL_SERVER_URL} \
    R:5000:localhost:5000 &

# Execute the Docker CMD

# If there are command line arguments, execute them:
if [[ $# -gt 0 ]]; then
    exec "$@"
else
    # Otherwise, execute the default command:
    sleep infinity
fi