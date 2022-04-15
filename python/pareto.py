def tuple_add(x, y):
    assert len(x) == len(y)
    l = len(x)
    return tuple(x[i] + y[i] for i in range(l))

class CostSpace:
    def __init__(self, points):
        self.sorted_points = points.sorted()
    def __add__(self, rhs):
        assert isinstance(rhs, CostSpace)
        return CostSpace([x])

print(tuple_add((1,2,3), (4,5,6)))
