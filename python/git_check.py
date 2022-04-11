import subprocess

def check(cwd):
    out = subprocess.check_output("git status -s", shell=True, cwd=cwd)
    if out != "":
        print(f"Local change not committed in {cwd}: {out}!")
        raise

check("./")
check("../chromium/src/v8")
