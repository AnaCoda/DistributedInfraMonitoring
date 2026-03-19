# DistributedInfraMonitoring
CPSC 559 - Group 9 Final Project

## Backend

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
.venv/bin/activate       # Unix/Mac
pip install -r requirements.txt

python -m backend.setup     
```

## Active Replication  (run INSTEAD of `python -m backend.setup`)
```bash
python -m replication.rmtest
```

## Replica Failover Demo

```bash
python -m replication.failover_demo
```
- Around 10s, replica 1 goes down
- Around 20s, replica 1 comes back up
- Around 30s, replica 2 goes down
- Around 40s, replica 1 goes down again, leaving only replica 3 up

## Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```
