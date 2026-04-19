#!/bin/bash
set -euxo pipefail

dnf update -y
dnf install -y git python3 python3-pip unzip awscli

curl -LsSf https://astral.sh/uv/install.sh | sh
install -Dm755 /root/.local/bin/uv /usr/local/bin/uv
install -Dm755 /root/.local/bin/uvx /usr/local/bin/uvx

mkdir -p /etc/distinfra

cat >/etc/distinfra/node.json <<EOF
{
  "region_name": "${region_name}",
  "entry": {
    "name": "${node_name}",
    "address": {
      "ip": "${node_ip}",
      "port": ${node_port}
    }
  },
  "peers": ${peers_json},
  "capitals": ${capitals_json}
}
EOF

cat >/etc/distinfra/infra.json <<EOF
${infra_json}
EOF

rm -rf "${app_dir}"
mkdir -p /opt
rm -rf /tmp/distinfra-unpack
mkdir -p /tmp/distinfra-unpack

aws s3 cp s3://cpsc-559-repo-158210429599-us-west-2-an/DistributedInfraMonitoring.zip /tmp/distinfra.zip
unzip -q /tmp/distinfra.zip -d /tmp/distinfra-unpack

APP_ROOT="$(find /tmp/distinfra-unpack -type f -name pyproject.toml -exec dirname {} \; | head -n 1)"

if [ -z "$${APP_ROOT}" ]; then
  echo "Could not locate app root after unzip"
  find /tmp/distinfra-unpack -maxdepth 3 -type d
  exit 1
fi

mv "$${APP_ROOT}" "${app_dir}"

rm -rf "${app_dir}/.venv"

chown -R ${app_user}:${app_user} "${app_dir}" /etc/distinfra

sudo -u ${app_user} -H bash -lc '
  cd "'"${app_dir}"'"
  /usr/local/bin/uv sync || true
  /usr/local/bin/uv pip install websockets pydantic colorama
'

cat >/etc/systemd/system/distinfra-regional.service <<EOF
[Unit]
Description=Distributed Infra Regional Runner
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${app_user}
WorkingDirectory=${app_dir}
Environment=HOME=/home/${app_user}
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Environment=NODE_CONFIG_PATH=/etc/distinfra/node.json
ExecStart=/usr/local/bin/uv run python -m backend.runners.regional_runner
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/distinfra-infra.service <<EOF
[Unit]
Description=Distributed Infra Hospital Runner
After=network-online.target distinfra-regional.service
Wants=network-online.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/opt/DistributedInfraMonitoring
Environment=HOME=/home/ec2-user
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Environment=NODE_CONFIG_PATH=/etc/distinfra/infra.json
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/local/bin/uv run python -u -m backend.runners.infra_runner
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable distinfra-regional.service
systemctl enable distinfra-infra.service
systemctl start distinfra-regional.service
sleep 5
systemctl start distinfra-infra.service