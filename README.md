# Distributed Wartime Monitoring Infrastructure
> **By:** Group 9
> **Class:** CPSC5529

# Directory
- We use `fly.io` for hosting. If you go to the bottom there is an entire section on deployment. _Before touching anything deployment related please read it so that our infrastructure stays alive and happy!_


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
```bash
$ uv run python -m replication.redeploy --key "$HOME\.ssh\Homer-Sus2.pem"
```


## Monitoring
You can use the following command to watch infrastructure:
```bash
$ uv run python -m replication.watch --service Hospital-1 --key "$HOME\.ssh\Homer-Sus2.pem"
```


Monitoring

```
sudo journalctl -u distinfra-capital.service -n 4000 -f -o cat
sudo journalctl -u distinfra-infra.service -n 4000 -f -o cat
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

# Running
## Locally
It is extremely trivial to run the nodes locally. You can simply run this commmand:
```bash
$ $Env:LOCAL = "TRUE"; $Env:CONFIG_NAME = "rm-1"; uv run python -m runner
```

# Specifying nodes
If you go to `runners/config.py` we have several `pydantic` models that describe how configuration files should look. The actual configuration is stored in `configs/fly/...`. The fly nodes will determine their state depending on the `CONFIG_NAME` secret, which is passed to the `runner.py` script as an environment variable.

## Connection Registries
We have two cases for node resolution:
- **LOCAL:** If we are local then we can allocate a random port on a block from the OS, we keep track and manage these automatically when a node is started with the runner and the `LOCAL` environment variable is set to a string of non-zero length.
- **REMOTE:** In the case of remote, all nodes start on `0.0.0.0:8080`. Their connections with other nodes are specified with a name to url mapping in `backend/runners/remote_registry.json`.

# FLY.IO DEPLOYMENT
The actual deployment logic for a replica named `rm-1` is as follows:
```bash
$ fly apps create <app-name>
$ fly secrets set CONFIG_NAME=rm-1 -a rm-1 
$ fly deploy -a rm-1 --ha=False --depot=false --local-only
$ fly scale count 1 -a rm-1
```
Although we will abstract this away into a builder script.