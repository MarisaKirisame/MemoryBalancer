import subprocess

def check(cwd):
    if subprocess.check_output("git status -s", shell=True, cwd=cwd) != "":
        print(f"Local change not committed in {cwd}!")
        raise

check("./")
check("../chromium/src/v8")
