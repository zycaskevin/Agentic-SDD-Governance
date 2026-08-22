#!/bin/sh
# Stdlib/package isolation happens before importing sddgov.  This script is
# installed byte-for-byte into the Owner venv and reverified by owner_cli.
set -eu

case "$0" in
  /*) launcher=$0 ;;
  *) echo "[ERROR] sddgov-owner requires an absolute invocation path" >&2; exit 3 ;;
esac

# Loader cleanliness is an Owner-custody precondition before this shebang runs.
# This check is only a fail-closed diagnostic; it cannot undo earlier loader code.
if [ "${LD_PRELOAD+x}" = x ] || [ "${LD_LIBRARY_PATH+x}" = x ] || \
   [ "${DYLD_INSERT_LIBRARIES+x}" = x ] || [ "${DYLD_LIBRARY_PATH+x}" = x ]; then
  echo "[ERROR] sddgov-owner rejects dynamic-loader injection variables" >&2
  exit 3
fi

launcher_dir=${launcher%/*}
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONINSPECT
export SDDGOV_OWNER_ISOLATED_LAUNCHER="$launcher"
exec "$launcher_dir/python" -I -m sddgov.owner_cli "$@"
