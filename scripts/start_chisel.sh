#!/bin/env bash

# start_chisel.sh

# Hack since vscode tasks.json doesn't support envFile (yet)
if [[ -f .env.chisel-dev ]]; then
    source .env.chisel-dev
fi

/usr/local/bin/chisel client \
    --fingerprint=${CHISEL_SERVER_FINGERPRINT} \
    --auth=${CHISEL_SERVER_AUTH} \
    ${CHISEL_SERVER_URL} \
    R:${CHISEL_PROXY_PORT}:localhost:5000 &

# Execute the Docker CMD

# If there are command line arguments, execute them:
if [[ $# -gt 0 ]]; then
    exec "$@"
else
    # Otherwise, execute the default command:
    sleep infinity
fi
