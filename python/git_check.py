import subprocess

def check(cwd):
    out = subprocess.check_output("git status -s", shell=True, cwd=cwd).decode(encoding='utf8', errors='strict')
    if out != "":
        print(f"Local change not committed in {cwd}: {out}!")
        raise

check("./")
check("../chromium/src/v8")
