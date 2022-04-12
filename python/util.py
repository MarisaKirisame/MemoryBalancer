def fmt(x):
    return "{0:.3g}".format(x)

def tex_fmt(x):
    return f"\\num{{{fmt(x)}}}"

def tex_def(eval_name, name, definition):
    return f"\def\{eval_name}{name}{{{definition}\\xspace}}\n"
