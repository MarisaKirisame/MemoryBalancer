from git_check import get_commit

with open("v8_commit", "w") as f:
    f.write(str(get_commit("../v8/src")))
