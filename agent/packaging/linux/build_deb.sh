#!/bin/sh
# Developer-only Debian candidate. Must run from the repository root on Linux.
set -eu

VERSION="0.1.0~rc1"
ARCH="amd64"
PROJECT="fleetluma-agent"
STAGING="dist/deb-root"
OUTPUT="FleetLuma-Linux-UNSIGNED-CANDIDATE.deb"

python -m PyInstaller --noconfirm --clean --onedir   --name fleetluma-agent --paths agent   agent/packaging/linux/service_entry.py
python -m PyInstaller --noconfirm --clean --onefile   --name fleetluma-control --paths agent   agent/packaging/linux/control_entry.py

rm -rf "$STAGING"
mkdir -p "$STAGING/DEBIAN"          "$STAGING/usr/lib/fleetluma"          "$STAGING/usr/bin"          "$STAGING/lib/systemd/system"
cp -a dist/fleetluma-agent/. "$STAGING/usr/lib/fleetluma/"
cp dist/fleetluma-control "$STAGING/usr/bin/fleetluma-control"
cp agent/packaging/linux/fleetluma-setup "$STAGING/usr/bin/fleetluma-setup"
cp agent/packaging/linux/fleetluma-agent.service    "$STAGING/lib/systemd/system/fleetluma-agent.service"
cp agent/packaging/linux/debian/control "$STAGING/DEBIAN/control"
for maintainer_script in postinst prerm postrm; do
  cp "agent/packaging/linux/debian/$maintainer_script" "$STAGING/DEBIAN/$maintainer_script"
  chmod 0755 "$STAGING/DEBIAN/$maintainer_script"
done
chmod 0755 "$STAGING/usr/lib/fleetluma/fleetluma-agent"
chmod 0755 "$STAGING/usr/bin/fleetluma-control"
chmod 0755 "$STAGING/usr/bin/fleetluma-setup"
chmod 0644 "$STAGING/lib/systemd/system/fleetluma-agent.service"
dpkg-deb --build --root-owner-group "$STAGING" "$OUTPUT"
echo "Developer candidate generated: $OUTPUT"
