# Distributed Wartime Monitoring Infrastructure
> **By:** Group 9
> **Class:** CPSC5529

## Configuration
1. You must first configure your AWS CLI with the Access Key + Secret Key. Fam Ghaly has this.
2. You must make a `terraform.tfvars` file in the `Terraform/` directory. It should have the following file contents:
```tf
aws_region = "us-west-2"

allowed_ssh_cidr_blocks      = ["<YOUR_IP>/32"]
allowed_frontend_cidr_blocks = ["<YOUR_IP>/32"]

key_name = "<KEYPAIR_NAME>"
```
3. If you wish to re-deploy infrastructure, then you can use the Hashicorp Terraform teardown-and-redeploy:
```bash
$ terraform destroy
$ terraform apply
```
4. **However in most cases we are simply interested in updating the codebase** and thus we can run the following command:
```powershell
.\scripts\redeploy-ec2.ps1 -KeyPath "C:\path\to\your-key.pem"
```

Redeploy only one node type:

```powershell
.\scripts\redeploy-ec2.ps1 -Role capital -KeyPath "C:\path\to\your-key.pem"
.\scripts\redeploy-ec2.ps1 -Role regional -KeyPath "C:\path\to\your-key.pem"
.\scripts\redeploy-ec2.ps1 -Role infra -KeyPath "C:\path\to\your-key.pem"
```

If your SSH agent or SSH config already knows the key, omit `-KeyPath`.

Monitoring

```
sudo journalctl -u distinfra-capital.service -n 4000 -f -o cat
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

## Methods
### Any Node
- `sim.down`: The payload for this request is `{ duration: INTEGER }` and it will return success if it deems that the request is valid. There are limits on how long a node is allowed to sleep and the request may be rejected.

### Infrastructure Nodes
- `infra.random`: This causes the infrastructure node to generate a new randomized state on demand.

## Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```
