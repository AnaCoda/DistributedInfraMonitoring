# DistributedInfraMonitoring
CPSC 559 - Group 9 Final Project

## Terraform
1. Configure your AWS CLI with the Access Key + Secret Key from Fam
```tf
aws_region = "us-west-2"

allowed_ssh_cidr_blocks      = ["<YOUR_IP>/32"]
allowed_frontend_cidr_blocks = ["<YOUR_IP>/32"]

key_name = "<KEYPAIR_NAME>"
```

## Backend
```bash
$ uv run python -m replication.failover_demo
```

## Tests
```bash
$ uv run python -m backend.tests
```

## Query Tool
The general form of the command is the following:
```bash
$ uv run python -m replication.query_tool --ip localhost:4001 --name homer --route query.capital
```
Here are some useful commands:
- `infra.random` (INFRASTRUCTURE): This causes the infrastructure node to generate a new randomized state.
- `query.capital` (CAPITAL): Causes the capital to return the current state of the system.

## Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```
