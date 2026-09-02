class Generator(BaseGenerator):
    def data(self):
        x = var("x")
        a, b = [choice([-1, 1]) * n for n in sample(range(1, 10), 2)]
        # Add(..., evaluate=False), not a*x + b*x: performing the addition is
        # the exercise, so the sum has to stay unsimplified. Sage wrote this
        # as (a*x).add(b*x, hold=True).
        exercise = Add(a * x, b * x, evaluate=False)
        correct = a * x + b * x
        choices = [correct] + sample(
            [correct + i * x for i in range(-3, 4) if i != 0], 3)
        return {
            "exercise": exercise,
            "choices": CheckIt.choices_from_list(choices),
        }
