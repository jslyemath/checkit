class Generator(BaseGenerator):
    def data(self):
        x = var('x')
        a = randrange(-9,10)
        b = randrange(-9,10)
        p = randrange(2,6)

        return {
            # `**` is exponentiation in Python (`^` is bitwise XOR).
            # Add(..., evaluate=False) leaves the sum unsimplified for display,
            # the way Sage's .add(..., hold=True) did.
            "sum": Add(a*x**p, b*x**p, evaluate=False),
            "result": (a+b)*x**p,
        }
