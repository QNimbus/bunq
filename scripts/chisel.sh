#!/bin/env bash

# Hack since vscode tasks.json doesn't support envFile (yet)
if [[ -f .env ]]; then
    source .env
fi

/usr/local/bin/chisel client \
    --fingerprint=${CHISEL_SERVER_FINGERPRINT} \
    --auth=${CHISEL_SERVER_AUTH} \
    ${CHISEL_SERVER_URL} \
    R:5000:localhost:5000