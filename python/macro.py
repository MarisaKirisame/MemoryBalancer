import subprocess
import json
from util import tex_def_generic
import paper

j = json.loads(subprocess.check_output(["./build/MemoryBalancer", "macro"]))

tex = ""
for k, v in j.items():
    tex += tex_def_generic("", k, v)

paper.pull()
with open(f"../membalancer-paper/hyper_param.tex", "w") as tex_file:
    tex_file.write(tex)
paper.push()
