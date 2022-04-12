import subprocess

def pull():
    subprocess.call("git pull", shell=True, cwd="../membalancer-paper")

def push():
    subprocess.call("git add -A", shell=True, cwd="../membalancer-paper")
    subprocess.call("git commit -am 'sync file generated from eval'", shell=True, cwd="../membalancer-paper")
    subprocess.call("git push", shell=True, cwd="../membalancer-paper")
