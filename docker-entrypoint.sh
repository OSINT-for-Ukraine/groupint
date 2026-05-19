#!/bin/sh
set -e
mkdir -p /home/appuser/.groupint/sessions /home/appuser/.streamlit
chown -R appuser:appgroup /home/appuser/.groupint /home/appuser/.streamlit
exec runuser -u appuser -- "$@"
