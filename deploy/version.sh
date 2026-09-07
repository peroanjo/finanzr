#!/bin/sh

finanzr_load_version() {
    if [ ! -f VERSION ]; then
        echo "Missing VERSION in $PWD" >&2
        return 1
    fi
    source_version=$(sed -n '1p' VERSION)
    if [ -z "$source_version" ]; then
        echo "VERSION is empty" >&2
        return 1
    fi
    if [ -n "${FINANZR_VERSION:-}" ] && [ "$FINANZR_VERSION" != "$source_version" ]; then
        echo "FINANZR_VERSION ($FINANZR_VERSION) does not match VERSION ($source_version)" >&2
        return 1
    fi
    FINANZR_VERSION=$source_version
    export FINANZR_VERSION
}
