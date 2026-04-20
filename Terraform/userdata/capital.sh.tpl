#!/bin/bash
set -euo pipefail

dnf update -y
dnf install -y git unzip curl
curl -LsSf https://astral.sh/uv/install.sh | sh
install -m 0755 /root/.local/bin/uv /usr/local/bin/uv
if [ -f /root/.local/bin/uvx ]; then
  install -m 0755 /root/.local/bin/uvx /usr/local/bin/uvx
fi
export PATH="/root/.local/bin:/home/ec2-user/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

id -u "${app_user}" >/dev/null 2>&1 || useradd -m "${app_user}"

rm -rf "${app_dir}"
install -d -o "${app_user}" -g "${app_user}" "$(dirname "${app_dir}")"
sudo -u "${app_user}" git clone --branch "${repo_ref}" --single-branch "${repo_url}" "${app_dir}"

cd "${app_dir}"
sudo -u "${app_user}" /usr/local/bin/uv venv
sudo -u "${app_user}" /usr/local/bin/uv sync || true
sudo -u "${app_user}" /usr/local/bin/uv pip install websockets pydantic colorama

mkdir -p /etc/distinfra

cat >/etc/distinfra/node.json <<EOF
{
  "capital_name": "${capital_name}",
  "entry": {
    "name": "${node_name}",
    "address": {
      "ip": "${node_ip}",
      "port": ${node_port}
    }
  },
  "peers": ${peers_json}
}
EOF

cat >/etc/systemd/system/distinfra-capital.service <<EOF
[Unit]
Description=Distributed Infra Capital Runner
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
ExecStart=/usr/local/bin/uv run python -u -m backend.runners.capital_runner
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable distinfra-capital.service
systemctl restart distinfra-capital.service
if [ -n "${dns_name}" ]; then
  set +e
  curl -fsSL "https://caddyserver.com/api/download?os=linux&arch=amd64" -o /usr/local/bin/caddy
  caddy_download_status=$?
  set -e

  if [ "$caddy_download_status" -eq 0 ]; then
    chmod 0755 /usr/local/bin/caddy
    mkdir -p /etc/caddy /var/lib/caddy

    cat >/etc/caddy/Caddyfile <<EOF
${dns_name} {
    reverse_proxy ${node_ip}:${node_port}
}
EOF

    cat >/etc/systemd/system/caddy.service <<EOF
[Unit]
Description=Caddy Web Server
After=network-online.target distinfra-capital.service
Wants=network-online.target

[Service]
Type=simple
Environment=XDG_DATA_HOME=/var/lib/caddy
Environment=XDG_CONFIG_HOME=/etc/caddy
ExecStart=/usr/local/bin/caddy run --environ --config /etc/caddy/Caddyfile
ExecReload=/usr/local/bin/caddy reload --config /etc/caddy/Caddyfile --force
Restart=on-failure
TimeoutStopSec=5s
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable caddy.service
    systemctl restart caddy.service
  else
    echo "Caddy download failed; distinfra service is still running without WSS proxy" >&2
  fi
fi
