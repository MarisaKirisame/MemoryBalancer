import subprocess

def run(cmd, cwd):
    return subprocess.check_output(cmd, shell=True, cwd=cwd).decode(encoding='utf8', errors='strict')
def get_commit(cwd):
    out = run("git status -s", cwd)
    if out != "":
        print(f"Local change not committed in {cwd}: {out}!")
        raise
    return run("git show -s --format=%H")

get_commit("./")
get_commit("../chromium/src/v8")
