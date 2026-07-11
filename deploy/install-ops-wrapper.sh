#!/bin/sh

# One-time root installer for Onedu operations automation.
#
# Run on the NAS as root:
#   cd /volume1/wbinstitute/docker/onedu/app
#   sh deploy/install-ops-wrapper.sh
#
# After installation, the SSH user can run:
#   sudo -n /usr/local/sbin/onedu-ops status

set -eu

APP_DIR="${ONEDU_APP_DIR:-/volume1/wbinstitute/docker/onedu/app}"
OPS_USER="${ONEDU_OPS_USER:-withbrain}"
INSTALL_PATH="${ONEDU_OPS_INSTALL_PATH:-/usr/local/sbin/onedu-ops}"
SUDOERS_D="${ONEDU_SUDOERS_D:-/etc/sudoers.d}"
SUDOERS_FILE="$SUDOERS_D/onedu-ops"
SOURCE_PATH="$APP_DIR/deploy/onedu-ops.sh"

if [ "$(id -u)" -ne 0 ]; then
  echo "This installer must be run as root."
  exit 1
fi

if [ ! -f "$SOURCE_PATH" ]; then
  echo "Cannot find $SOURCE_PATH"
  exit 1
fi

mkdir -p "$(dirname "$INSTALL_PATH")"
install -m 0750 "$SOURCE_PATH" "$INSTALL_PATH"

if [ -d "$SUDOERS_D" ]; then
  cat > "$SUDOERS_FILE" <<EOF
$OPS_USER ALL=(root) NOPASSWD: $INSTALL_PATH *
EOF
  chmod 0440 "$SUDOERS_FILE"

  if command -v visudo >/dev/null 2>&1; then
    if ! visudo -cf "$SUDOERS_FILE"; then
      rm -f "$SUDOERS_FILE"
      echo "sudoers validation failed. Removed $SUDOERS_FILE"
      exit 1
    fi
  fi
else
  echo "Warning: $SUDOERS_D does not exist. Installed $INSTALL_PATH only."
  echo "Add this sudoers line manually if needed:"
  echo "$OPS_USER ALL=(root) NOPASSWD: $INSTALL_PATH *"
fi

echo "Installed $INSTALL_PATH"
if [ -f "$SUDOERS_FILE" ]; then
  echo "Installed $SUDOERS_FILE"
fi
echo
echo "Test as the SSH user:"
echo "  sudo -n $INSTALL_PATH status"
