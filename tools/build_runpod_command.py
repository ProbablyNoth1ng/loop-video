"""Create a short RunPod command that runs the installer from GitHub."""
import json
from pathlib import Path


def build_command():
    code = '''import os,pathlib,subprocess,sys,tempfile
p=pathlib.Path(os.environ.get("PROJECT_ROOT","/workspace/ambient-loop"))
if not p.exists():
    p.parent.mkdir(parents=True,exist_ok=True)
    t=pathlib.Path(tempfile.mkdtemp(prefix="ambient-clone-",dir=p.parent))
    subprocess.run(["git","clone","--depth","1",os.environ.get("AMBIENT_REPO","https://github.com/ProbablyNoth1ng/loop-video.git"),str(t)],check=True)
    r=os.environ.get("AMBIENT_REVISION")
    if r:
        subprocess.run(["git","-C",str(t),"fetch","--depth","1","origin",r],check=True)
        subprocess.run(["git","-C",str(t),"checkout","--detach","FETCH_HEAD"],check=True)
    t.rename(p)
s=p/"cloud/runpod_entrypoint.py"
if not s.is_file() or not (p/"cloud/install.py").is_file():
    sys.exit("Installer files missing from repository. Publish cloud/install.py and cloud/runpod_entrypoint.py before deploying.")
os.execv(sys.executable,[sys.executable,str(s)])
'''
    return {'entrypoint': ['python3.12', '-c'], 'cmd': [code]}


if __name__ == '__main__':
    project = Path(__file__).resolve().parents[1]
    output = project / 'outputs/runpod-start-command.json'
    output.parent.mkdir(exist_ok=True)
    serialized = json.dumps(build_command(), separators=(',', ':')) + '\n'
    if len(serialized) > 4000:
        raise RuntimeError('RunPod Start command exceeds the 4000-character limit.')
    output.write_text(serialized, encoding='utf-8')
    print(f'{output} ({len(serialized)} characters)')
