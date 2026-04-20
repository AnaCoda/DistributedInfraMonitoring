#!/bin/bash
set -euo pipefail

dnf update -y
dnf install -y gcc git unzip
curl -LsSf https://astral.sh/uv/install.sh | sh
install -m 0755 /root/.local/bin/uv /usr/local/bin/uv
if [ -f /root/.local/bin/uvx ]; then
  install -m 0755 /root/.local/bin/uvx /usr/local/bin/uvx
fi
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
export PATH="/root/.cargo/bin:/root/.local/bin:/home/ec2-user/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

id -u "${app_user}" >/dev/null 2>&1 || useradd -m "${app_user}"

rm -rf "${app_dir}"
install -d -o "${app_user}" -g "${app_user}" "$(dirname "${app_dir}")"
sudo -u "${app_user}" git clone --branch "${repo_ref}" --single-branch "${repo_url}" "${app_dir}"

cd "${app_dir}"
sudo -u "${app_user}" /usr/local/bin/uv venv
sudo -u "${app_user}" /usr/local/bin/uv sync || true
sudo -u "${app_user}" /usr/local/bin/uv pip install websockets pydantic colorama

cd "${app_dir}/backend2"
cargo build --release
install -m 0755 target/release/backend2 /usr/local/bin/distinfra-backend2

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
  "capitals": ${capitals_json},
  "peers": ${peers_json}
}
EOF

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
Environment=PATH=/home/${app_user}/.local/bin:/root/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=NODE_CONFIG_PATH=/etc/distinfra/node.json
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/local/bin/distinfra-backend2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable distinfra-regional.service
systemctl restart distinfra-regional.service
