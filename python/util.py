def fmt(x):
	return "{0:.2f}".format(float(x))

def tex_fmt(x):
    return f"\\num{{{fmt(x)}}}"

def tex_fmt_bold(x):
    return f"\\textbf{{{fmt(x)}}}"

def tex_def_generic(eval_name, name, definition):
    return f"\def\{eval_name}{name}{{{definition}\\xspace}}\n"
