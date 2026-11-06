#!/usr/bin/env bash
# One-time provisioning for a self-hosted GitHub Actions runner on a fresh
# Hetzner CX32 (4 vCPU / 8GB RAM, Ubuntu 24.04 x86_64).
#
# This exists because GitHub-hosted runners cap concurrent jobs at 20 (Free)
# account-wide, which is what forces the 900-frame native re-renders into
# multiple sequential rounds. A self-hosted runner is outside that cap and
# costs no Actions minutes, at the cost of running (and paying for) the box.
#
# This installs the EXACT same Blender binary (hash-pinned) and Python
# dependencies that curious-mechanics-b-timeline-rerender.yml and
# curious-mechanics-ac-timeline-rerender.yml already install fresh on every
# shard job, but once, persistently -- so a workflow run against this runner
# can skip the "Install hash-pinned Blender" step entirely instead of paying
# its cost (minutes-long download+extract) on every single shard.
#
# Usage (run as a sudo-capable user on the fresh server):
#   sudo bash ops/hetzner-cx32-runner-setup.sh <repo-url> <runner-registration-token> [runner-name]
#
# <repo-url>: https://github.com/mingi201209-star/shorts-studio
# <runner-registration-token>: from the repo's Settings -> Actions -> Runners
#   -> "New self-hosted runner" page. It is valid for about one hour, so
#   generate it right before running this script, not in advance.
#
# Public-repo safety: register with "Only select repositories" scope (the
# registration-token page already does this per-repo), and never point a
# self-hosted runner at a workflow triggered by pull_request_target or by
# pull_request from forks. Every workflow in this repo only triggers on
# push to specific branches, which is the safe case.
set -euo pipefail

REPO_URL="${1:?usage: $0 <repo-url> <runner-registration-token> [runner-name]}"
RUNNER_TOKEN="${2:?usage: $0 <repo-url> <runner-registration-token> [runner-name]}"
RUNNER_NAME="${3:-shorts-studio-cx32}"

BLENDER_VERSION=5.0.1
BLENDER_TARBALL_SHA256=8019580ee1b7262e505f4196a00237ccf743c88d205b38d34201510676e60b09
BLENDER_URL="https://download.blender.org/release/Blender5.0/blender-${BLENDER_VERSION}-linux-x64.tar.xz"
RENDERER_SOURCE_SHA256=04fdc326a6a8a874840072ce82529e777ff0956f5c17c991ad8f87b4e59ac765

echo "== apt packages =="
apt-get update -qq
apt-get install -y xvfb libxrender1 libxi6 libxfixes3 libxkbcommon0 libsm6 \
  ffmpeg fonts-dejavu-core curl tar python3 python3-venv jq

echo "== Blender ${BLENDER_VERSION} (hash-pinned, matches the GitHub-hosted workflows) =="
mkdir -p /opt/shorts-studio
if [ ! -x "/opt/shorts-studio/blender-${BLENDER_VERSION}-linux-x64/blender" ]; then
  curl -fLsS --retry 3 --max-time 300 "$BLENDER_URL" -o /tmp/blender.tar.xz
  echo "${BLENDER_TARBALL_SHA256}  /tmp/blender.tar.xz" | sha256sum -c -
  tar -xJf /tmp/blender.tar.xz -C /opt/shorts-studio
  rm -f /tmp/blender.tar.xz
fi
echo "Blender installed at /opt/shorts-studio/blender-${BLENDER_VERSION}-linux-x64/blender"

echo "== Python venv with the pinned native+final QA dependencies =="
python3 -m venv /opt/shorts-studio/venv
/opt/shorts-studio/venv/bin/pip install --quiet --upgrade pip
/opt/shorts-studio/venv/bin/pip install --quiet Pillow==13.0.0 pydantic==2.14.1
/opt/shorts-studio/venv/bin/pip install --quiet --index-url https://download.pytorch.org/whl/cpu \
  torch==2.14.1+cpu torchvision==0.29.1+cpu
/opt/shorts-studio/venv/bin/pip install --quiet open-clip-torch==3.3.0 opencv-python-headless==5.0.0.93

echo "== GitHub Actions runner (latest release) =="
id -u ghrunner >/dev/null 2>&1 || useradd -m -s /bin/bash ghrunner
RUNNER_LATEST=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest | jq -r .tag_name | sed 's/^v//')
RUNNER_TARBALL="actions-runner-linux-x64-${RUNNER_LATEST}.tar.gz"
mkdir -p /opt/actions-runner
if [ ! -f /opt/actions-runner/config.sh ]; then
  curl -fLsS -o "/tmp/${RUNNER_TARBALL}" \
    "https://github.com/actions/runner/releases/download/v${RUNNER_LATEST}/${RUNNER_TARBALL}"
  tar xzf "/tmp/${RUNNER_TARBALL}" -C /opt/actions-runner
  rm -f "/tmp/${RUNNER_TARBALL}"
fi
chown -R ghrunner:ghrunner /opt/actions-runner /opt/shorts-studio

echo "== Registering runner against ${REPO_URL} (label: shorts-studio-cx32) =="
sudo -u ghrunner /opt/actions-runner/config.sh --unattended \
  --url "$REPO_URL" \
  --token "$RUNNER_TOKEN" \
  --name "$RUNNER_NAME" \
  --labels shorts-studio-cx32 \
  --work _work \
  --replace

echo "== Installing as a systemd service so it survives reboots =="
cd /opt/actions-runner
./svc.sh install ghrunner
./svc.sh start

echo "== Done =="
echo "Runner '$RUNNER_NAME' is registered and running as a systemd service."
echo "Blender: /opt/shorts-studio/blender-${BLENDER_VERSION}-linux-x64/blender"
echo "Python venv: /opt/shorts-studio/venv"
echo "A workflow job targeting runs-on: [self-hosted, shorts-studio-cx32] can skip"
echo "the Blender-install step entirely and use these paths directly."
