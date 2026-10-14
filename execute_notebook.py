"""Execute ordinary Python notebook cells; capture tables/images without a kernel."""
import os,sys,json,types,io,contextlib,base64
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parent
os.chdir(root);sys.path.insert(0,str(root))
# Force a noninteractive Matplotlib backend before the display-only adapter.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
outputs=[]
class Image:
 def __init__(self,filename):self.filename=filename

def display(obj):
 if isinstance(obj,Image):data={'image/png':base64.b64encode(Path(obj.filename).read_bytes()).decode(),'text/plain':'PNG figure'}
 elif isinstance(obj,pd.DataFrame):data={'text/html':obj.to_html(),'text/plain':obj.to_string()}
 else:data={'text/plain':repr(obj)}
 outputs.append(dict(output_type='display_data',data=data,metadata={}))
# Display rendering only is adapted. All calculations/imported project code run normally.
mod=types.ModuleType('IPython.display');mod.display=display;mod.Image=Image
sys.modules['IPython.display']=mod
nbpath=root/'Multicity_Kalshi_Analysis.ipynb';nb=json.loads(nbpath.read_text());env={};count=0
for c in nb['cells']:
 if c['cell_type']!='code':continue
 count+=1;outputs=[];stdout=io.StringIO();stderr=io.StringIO()
 with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
  exec(compile(c['source'],f'notebook cell {count}','exec'),env)
 c['execution_count']=count;c['outputs']=[]
 if stdout.getvalue():c['outputs'].append(dict(output_type='stream',name='stdout',text=stdout.getvalue()))
 if stderr.getvalue():c['outputs'].append(dict(output_type='stream',name='stderr',text=stderr.getvalue()))
 c['outputs']+=outputs
nb['metadata']['execution_note']='All code cells executed sequentially as Python with a display-only adapter for table/PNG capture; no Jupyter kernel used.'
nbpath.write_text(json.dumps(nb,indent=1))
print(f'Executed {count} code cells without errors.')
print(json.dumps(env['summary'],indent=2))
print(env['tables']['out_of_sample_brier'].to_string(index=False))
print('Distinct out-of-sample events:',env['predictions'].event_id.nunique())
print('Test range:',env['predictions'].entry_time.min(),env['predictions'].entry_time.max())
