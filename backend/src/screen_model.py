import json,hashlib
from pathlib import Path
from functools import lru_cache
import numpy as np
from sklearn.ensemble import IsolationForest
FEATURES=['weight_kg','temperature','activity','feed_left']
@lru_cache(maxsize=1)
def reference_model():
    raw=(Path(__file__).resolve().parents[1]/'fixtures/winter_reference.json').read_bytes();rows=json.loads(raw)
    x=np.array([[r[k] for k in FEATURES] for r in rows])
    model=IsolationForest(n_estimators=150,contamination=.15,random_state=42,n_jobs=1)
    model.fit(x);scores=model.score_samples(x)
    evidence={'reference_rows':len(rows),'contamination':.15,'threshold':float(model.offset_),'reference_min':float(scores.min()),'reference_max':float(scores.max()),'reference_flagged':int((scores<model.offset_).sum()),'sha256':hashlib.sha256(raw).hexdigest(),'random_state':42,'method':'IsolationForest / 150 trees / score_samples'}
    return model,evidence

def screen(visit):
    model,evidence=reference_model()
    score=float(model.score_samples([[getattr(visit,k) for k in FEATURES]])[0])
    return score,score<evidence['threshold'],score-evidence['threshold'],evidence
