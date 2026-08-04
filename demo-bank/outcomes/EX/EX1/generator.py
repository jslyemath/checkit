class Generator(BaseGenerator):
    def data(self):
        x,y = var("x y")

        # Genereate random line with slope -B/A
        A = randrange(1,10)*choice([-1,1])
        B = A
        while A==B:
            B = randrange(1,10)*choice([-1,1])
        C = randrange(-9,10)
        # standard equation
        # Eq(...), not `==`: in Python `==` compares and returns a bool, where
        # Sage's `==` built a symbolic equation.
        line1 = {
            'equation': Eq(A*x+B*y, C),
            # Rational(...), not `-A/B`: plain Python division would give a
            # float (-0.666...) instead of an exact fraction.
            'slope': Rational(-A,B),
        }

        # Genereate random line with slope m
        m = randrange(1,10)*choice([-1,1])
        b = randrange(-9,10)
        # slope-intercept equation
        line2 = {
            'equation': Eq(y, m*x+b),
            'slope': m,
        }

        lines = [line1,line2]
        shuffle(lines)

        return {
            "lines": lines,
            "alt_prompt": choice([True,False]),
        }
