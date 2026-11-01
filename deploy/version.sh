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

finanzr_load_git_metadata() {
    FINANZR_GIT_COMMIT=${FINANZR_GIT_COMMIT:-$(git rev-parse --verify HEAD 2>/dev/null || true)}
    FINANZR_GIT_BRANCH=${FINANZR_GIT_BRANCH:-$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)}
    if [ -n "$FINANZR_GIT_COMMIT" ]; then
        export FINANZR_GIT_COMMIT
    fi
    if [ -n "$FINANZR_GIT_BRANCH" ]; then
        export FINANZR_GIT_BRANCH
    fi
}
