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

## Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```
