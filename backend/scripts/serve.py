"""Serve the validation-selected artifact on localhost; no network needed after setup."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
summary=json.loads((ROOT/'artifacts/smesd-v1/summary.json').read_text())
# Resolve relative to this checkout so the project remains relocatable.
selected=Path(summary['selected_artifact']).name
os.environ.setdefault('COMRISK_MODEL_DIR',str(ROOT/'artifacts/smesd-v1'/selected))
os.environ.setdefault('COMRISK_DATA_PATH',str(ROOT/'data/processed/smesd/test.json'))
if __name__=='__main__':
 import uvicorn
 import torch
 torch.set_num_threads(int(os.environ.get('COMRISK_TORCH_THREADS','1')))
 uvicorn.run('comrisk.api:app',host='127.0.0.1',port=8000)
