def fmt(x):
    return "{0:.3g}".format(x)

def tex_fmt(x):
    return f"\\num{{{fmt(x)}}}"
