# DistributedInfraMonitoring
CPSC 559 - Group 9 Final Project

## Backend

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
.venv/bin/activate       # Unix/Mac
pip install -r requirements.txt

python -m capital.server          # (Flask on :5000, TCP on :6000)
python -m regional.node           
```

## Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```
