import json, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
from script import SCRIPT
from ttsprep import prep
k=Kokoro("kokoro-v1.0.onnx","voices-v1.0.bin")
durs=[]
for i,(mood,t) in enumerate(SCRIPT):
    s,sr=k.create(prep(t),voice="am_michael",speed=1.2,lang="en-us")
    s=np.asarray(s,dtype=np.float32)
    a=np.abs(s); idx=np.where(a>0.01)[0]
    if len(idx): s=s[max(0,idx[0]-int(0.03*sr)):idx[-1]+int(0.08*sr)]
    sf.write(f"audio/b_{i:03d}.wav",s,sr)
    durs.append(len(s)/sr)
    print(i,round(durs[-1],2),flush=True)
json.dump(durs,open("audio/durs.json","w"))
print("TOTAL",sum(durs))
