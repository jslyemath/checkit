"""Plain-Python generator runtime (SymPy backend).

The Python-side counterpart to wrapper.sage. Both are launched as a subprocess
by wrapper/__init__.py, both load a bank author's generator, and both write the
same seeds.json. Which one runs is decided by the generator's file extension:
generator.py -> here, generator.sage -> wrapper.sage.

The contract between the two is deliberately narrow and must stay that way:

  * the CLI signature (argv) is identical
  * the names exposed to generators are the same (see GENERATOR_NAMESPACE)
  * BaseGenerator / CheckIt / provide_data present the same API
  * json_ready() emits only str/bool/list/dict, so nothing backend-specific
    ever reaches seeds.json and the whole Python layer stays runtime-agnostic

Output is *not* identical between the runtimes: the RNGs differ, so a given seed
produces different content, and SymPy's LaTeX spacing differs cosmetically from
Sage's. A bank that switches runtimes regenerates from scratch.
"""
import sys, json, os, datetime, random

# This script is copied to a temp directory and run as a subprocess, but the
# interpreter is the one checkit is installed into, so the package is
# importable. Taking the seed boundaries from there rather than restating
# them keeps one definition on the Python side; the viewer has the only
# other copy, and a test asserts the two agree.
from checkit import PUBLIC_SEEDS, BUNDLE_UNTIL

import sympy
from sympy import Matrix, Rational, Symbol, latex as _sympy_latex, zeros


# ---------------------------------------------------------------------------
# Names handed to generator files
#
# A generator is exec'd in a namespace built from GENERATOR_NAMESPACE below.
# Under Sage these names come for free from the interpreter; here they must be
# supplied explicitly. Keep this list aligned with what wrapper.sage's namespace
# actually offers, since it is the author-facing surface.
# ---------------------------------------------------------------------------

def var(name, latex_name=None):
    """A symbol, mirroring Sage's var().

    `latex_name` is accepted for source compatibility. Sage used it to give a
    symbol a sort key different from its printed name (e.g. var("zw",
    latex_name="w") so it sorts after z but prints as w). SymPy prints a symbol
    by its own name and has no display-name override, so when latex_name is
    given we simply use it as the name. That changes sort position; helpers that
    care about variable order take an explicit ordered list instead.
    """
    if latex_name is None and len(name.split()) > 1:
        # Sage's var("x y") returns a tuple of symbols; match that.
        return sympy.symbols(name)
    return Symbol(latex_name if latex_name is not None else name)


def latex(obj):
    """LaTeX for a value, mirroring Sage's latex()."""
    return _sympy_latex(obj)


def set_random_seed(seed=None):
    """Seed the RNG, mirroring Sage's set_random_seed()."""
    random.seed(seed)


class _Plot:
    """Wraps a matplotlib figure so it satisfies the `.save(path)` contract that
    BaseGenerator.graphics() promises (see §12 of the codebase notes).

    matplotlib is imported lazily and is NOT a hard dependency: only banks that
    actually call plot() need it, and they get a clear error if it is missing.
    """
    def __init__(self, figure):
        self._figure = figure

    def save(self, path):
        self._figure.savefig(path, bbox_inches="tight")


def plot(expr, xrange=(-10, 10), yrange=None, points=400, **kwargs):
    """A 2-D plot of a SymPy expression, styled like a school coordinate grid.

    Deliberately not matplotlib's defaults, which draw a boxed chart with
    auto-chosen ticks -- students cannot read a coordinate off that. Instead:
    axes cross at the origin with arrowheads, a gridline and a tick at *every*
    integer, and an equal aspect ratio so a slope of 1 actually looks like 45
    degrees.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # no display in a generation subprocess
        import matplotlib.pyplot as plt
        from matplotlib.ticker import MultipleLocator
    except ImportError as e:
        raise RuntimeError(
            "plot() requires matplotlib, which is not installed. Either "
            "`pip install matplotlib`, or generate figures with tikz_graphics() "
            "instead, which needs no Python plotting library."
        ) from e
    free = sorted(expr.free_symbols, key=lambda s: s.name)
    x = free[0] if free else Symbol("x")
    f = sympy.lambdify(x, expr, "math")
    lo, hi = xrange
    ylo, yhi = yrange if yrange is not None else (lo, hi)
    xs, ys = [], []
    for i in range(points + 1):
        xv = lo + (hi - lo) * i / points
        try:
            yv = f(xv)
        except (ValueError, ZeroDivisionError, OverflowError):
            continue
        xs.append(xv)
        ys.append(yv)

    figure, axes = plt.subplots(figsize=(5, 5))
    axes.plot(xs, ys, linewidth=2, zorder=3, **kwargs)
    axes.set_xlim(lo, hi)
    axes.set_ylim(ylo, yhi)
    # Equal aspect: without it matplotlib stretches to fill the figure and the
    # slope a student measures off the picture is not the slope of the line.
    axes.set_aspect("equal")

    # A tick and a gridline at every integer, so values can be read off.
    axes.xaxis.set_major_locator(MultipleLocator(1))
    axes.yaxis.set_major_locator(MultipleLocator(1))
    axes.grid(True, linewidth=0.5, color="0.85", zorder=0)

    # Axes through the origin rather than around the outside.
    axes.spines["left"].set_position("zero")
    axes.spines["bottom"].set_position("zero")
    axes.spines["right"].set_visible(False)
    axes.spines["top"].set_visible(False)
    for side in ("left", "bottom"):
        axes.spines[side].set_linewidth(1.2)
        axes.spines[side].set_zorder(2)

    # Arrowheads on both ends of both axes -- the textbook convention, showing
    # the axes continue rather than stopping at the edge of the picture. Drawn
    # in axis coordinates so they land at the ends regardless of the range.
    axes.plot(1, 0, ">k", markersize=5, transform=axes.get_yaxis_transform(), clip_on=False)
    axes.plot(0, 0, "<k", markersize=5, transform=axes.get_yaxis_transform(), clip_on=False)
    axes.plot(0, 1, "^k", markersize=5, transform=axes.get_xaxis_transform(), clip_on=False)
    axes.plot(0, 0, "vk", markersize=5, transform=axes.get_xaxis_transform(), clip_on=False)

    axes.tick_params(axis="both", labelsize=7, length=3)
    # The "0" label sits on top of the other axis and just adds clutter.
    axes.xaxis.set_major_formatter(lambda v, _: "" if abs(v) < 1e-9 else f"{v:g}")
    axes.yaxis.set_major_formatter(lambda v, _: "" if abs(v) < 1e-9 else f"{v:g}")
    return _Plot(figure)


# ---------------------------------------------------------------------------
# Matrices
#
# Sage matrices carry "subdivisions" -- the vertical bar of an augmented matrix.
# SymPy has no such concept, so CheckItMatrix wraps a SymPy Matrix and carries
# the split column index alongside it, exposing the subset of Sage's matrix API
# the CheckIt helpers and demo generators actually use.
# ---------------------------------------------------------------------------

class CheckItMatrix:
    def __init__(self, m, col_split=None):
        self._m = Matrix(m)
        self._col_split = col_split

    # -- shape ------------------------------------------------------------
    def nrows(self):
        return self._m.rows

    def ncols(self):
        return self._m.cols

    def rows(self):
        return [list(self._m.row(i)) for i in range(self._m.rows)]

    def columns(self):
        return [list(self._m.col(j)) for j in range(self._m.cols)]

    def column(self, j):
        return list(self._m.col(j))

    # -- subdivisions (the augmented-matrix bar) --------------------------
    def subdivide(self, row_splits=None, col_splits=None):
        if col_splits:
            self._col_split = col_splits[0]
        return self

    def subdivisions(self):
        return ([], [self._col_split] if self._col_split is not None else [])

    def subdivision(self, i, j):
        """The (0,0) block, i.e. everything left of the bar."""
        if self._col_split is None:
            return CheckItMatrix(self._m)
        return CheckItMatrix(self._m[:, :self._col_split])

    def augment(self, vector, subdivide=False):
        col = Matrix(vector) if not isinstance(vector, CheckItMatrix) else vector._m
        joined = self._m.row_join(col.reshape(self._m.rows, 1))
        return CheckItMatrix(joined, self._m.cols if subdivide else self._col_split)

    # -- linear algebra ---------------------------------------------------
    def rref(self):
        """Sage returns just the reduced matrix; SymPy returns (matrix, pivots).
        Match Sage's shape here so the helpers read the same in both runtimes."""
        reduced, _ = self._m.rref()
        return CheckItMatrix(reduced, self._col_split)

    def pivots(self):
        _, pivots = self._m.rref()
        return tuple(pivots)

    def right_kernel_basis(self):
        """Basis of the kernel. Sage was called with basis='pivot'; SymPy's
        nullspace uses its own parametrization, so the solution set is correct
        but may be presented with different free parameters."""
        return [list(v) for v in self._m.nullspace()]

    def transpose(self):
        return CheckItMatrix(self._m.T, self._col_split)

    def __getitem__(self, key):
        return self._m[key]

    def _sympy_(self):
        return self._m

    def _latex(self, printer):
        """Lets sympy.latex() render this wrapper, so a generator can return a
        matrix straight out of data() and have json_ready() latexify it.

        When the matrix is subdivided, render an `array` with a `|` in the
        column spec so an augmented matrix shows its vertical bar. SymPy's own
        matrix printer emits a plain `matrix` environment and has no notion of
        subdivisions, so without this the bar Sage drew was silently lost and an
        augmented matrix looked like an ordinary one.
        """
        if self._col_split is None:
            return printer.doprint(self._m)
        spec = "c" * self._col_split + "|" + "c" * (self._m.cols - self._col_split)
        body = " \\\\ ".join(
            " & ".join(printer.doprint(self._m[i, j]) for j in range(self._m.cols))
            for i in range(self._m.rows)
        )
        return r"\left[\begin{array}{" + spec + "}" + body + r"\end{array}\right]"

    def __repr__(self):
        return repr(self._m)


def matrix(rows):
    return CheckItMatrix(rows)


def column_matrix(entries):
    return CheckItMatrix(Matrix(list(entries)).reshape(len(list(entries)), 1))


def zero_vector(n):
    return [0] * n


def _random_full_column_rank(rows, cols, upper_bound=6):
    """A `rows` x `cols` integer matrix of rank `cols` with modest entries.

    Replaces Sage's random_matrix(QQ, ..., algorithm='echelonizable'), which has
    no SymPy equivalent. Starts from the identity stacked on zero rows -- which
    has exactly the target rank -- then applies random unimodular row operations
    (adding an integer multiple of one row to another). Those preserve both rank
    and integrality, so the result stays exactly solvable by hand.
    """
    m = zeros(rows, cols)
    for i in range(min(rows, cols)):
        m[i, i] = 1
    # Rows past the identity block start empty. Fill them with a random
    # combination of the pivot rows: still rank `cols`, but no all-zero row --
    # which would otherwise surface to students as a vacuous "0 = 0" equation.
    for i in range(cols, rows):
        for k in range(cols):
            m[i, k] = random.randrange(-2, 3)
        if all(v == 0 for v in m[i, :]):
            m[i, random.randrange(cols)] = random.choice([-1, 1])
    if rows < 2:
        return m
    # Scramble with unimodular row operations, which preserve both rank and
    # integrality. Undo any step that pushes an entry past the bound -- undoing
    # must reuse the same sign, or it compounds the problem instead of fixing it.
    for _ in range(rows * 4):
        i, j = random.sample(range(rows), 2)
        sign = random.choice([-1, 1])
        m[i, :] += sign * m[j, :]
        if max(abs(v) for v in m) > upper_bound:
            m[i, :] -= sign * m[j, :]
    return m


# ---------------------------------------------------------------------------
# Library of helpful functions (mirrors wrapper.sage's CheckIt)
# ---------------------------------------------------------------------------

class CheckIt:
    @staticmethod
    def vars(*latex_names, random_order=True):
        """Given one or more `latex_names`, returns a tuple of symbols.
        `random_order` names them so that they appear in expressions in a
        random order.

        Still needed under SymPy: like Sage, SymPy orders the terms of a sum by
        symbol name, so without this the same variable always sorts first.
        """
        stamp = random.randrange(100000, 999999)
        indices = list(range(len(latex_names)))
        if random_order:
            random.shuffle(indices)
        import string
        random_letter = random.choice(list(string.ascii_lowercase))
        return (
            Symbol(f"{random_letter}_mi_var_{stamp}_{indices[i]}")
            for i, name in enumerate(latex_names)
        )

    @staticmethod
    def shuffled_equation(*terms):
        """Represents the equation sum(terms)==0, but with terms shuffled
        randomly to each side."""
        left, right = [], []
        for term in terms:
            if random.choice([True, False]):
                left.append(sympy.sympify(term))
            else:
                right.append(-sympy.sympify(term))
        flip = random.choice([True, False])
        lhs = sum(left) if left else sympy.Integer(0)
        rhs = sum(right) if right else sympy.Integer(0)
        return sympy.Eq(rhs, lhs) if flip else sympy.Eq(lhs, rhs)

    @staticmethod
    def shuffled_inequality(*terms, strict=True):
        """sum(terms) > 0 (or >= 0), with terms shuffled randomly to each side
        and a random direction of inequality."""
        left, right = [], []
        for term in terms:
            if random.choice([True, False]):
                left.append(sympy.sympify(term))
            else:
                right.append(-sympy.sympify(term))
        lhs = sum(left) if left else sympy.Integer(0)
        rhs = sum(right) if right else sympy.Integer(0)
        if random.choice([True, False]):
            return sympy.StrictGreaterThan(lhs, rhs) if strict else sympy.Ge(lhs, rhs)
        return sympy.StrictLessThan(rhs, lhs) if strict else sympy.Le(rhs, lhs)

    @staticmethod
    def choices_from_list(lst):
        """
        Given a list, return a list of choices in a canonical way,
        in a random order.
        The first item of the provided `lst` is correct, and all
        other items are distractors.

        Ported from wrapper.sage, where upstream added it for MCQ support, so an
        MCQ outcome can be authored against either runtime. `shuffle` there is
        Sage's global; here it is random.shuffle, seeded identically by
        set_random_seed, so the two runtimes agree seed for seed.
        """
        choices = [
            {"item": lst[i], "correct": (i == 0)}
            for i in range(len(lst))
        ]
        random.shuffle(choices)
        for i in range(len(lst)):
            choices[i]["letter"] = chr(ord('a') + i)
        return choices

    @staticmethod
    def latex_system_from_matrix(m, variables="x", alpha_mode=False, variable_list=None):
        if not isinstance(m, CheckItMatrix):
            m = CheckItMatrix(m)
        # Augment with a zero vector if not already augmented
        if not m.subdivisions()[1]:
            m = m.augment(zero_vector(m.nrows()), subdivide=True)
        num_vars = m.subdivisions()[1][0]
        # Start using requested variables
        system_vars = list(variable_list) if variable_list is not None else []
        # Conveniently add xyzwv if requested
        if alpha_mode:
            system_vars += [Symbol(n) for n in ("x", "y", "z", "w", "v")]
        # Finally fall back to x_n as needed
        system_vars += [Symbol(f"{variables}_{n+1}") for n in range(num_vars)]
        # Build matrix
        latex_output = "\\begin{matrix}\n"
        for row in m.rows():
            if row[0] != 0:
                latex_output += latex(row[0] * system_vars[0])
                previous_terms = True
            else:
                previous_terms = False
            for n, cell in enumerate(row[1:num_vars]):
                latex_output += " & "
                if cell < 0:
                    latex_output += " - "
                elif cell > 0 and previous_terms:
                    latex_output += " + "
                latex_output += " & "
                if cell != 0:
                    latex_output += latex(abs(cell) * system_vars[n + 1])
                if not previous_terms:
                    previous_terms = bool(cell != 0)
            if not previous_terms:
                latex_output += " 0 "
            latex_output += " & = & "
            latex_output += latex(row[num_vars])
            latex_output += "\\\\\n"
        latex_output += "\\end{matrix}"
        return latex_output

    @staticmethod
    def latex_solution_set_from_matrix(m):
        if not isinstance(m, CheckItMatrix):
            m = CheckItMatrix(m)
        if not m.subdivisions()[1]:
            m = m.augment(zero_vector(m.nrows()), subdivide=True)
        if (m.ncols() - 1) in m.pivots():
            return r" \{\} "
        solution_dimension = m.ncols() - 1
        free_variables = [Symbol(c) for c in "abcdefghij"]
        kernel_basis = m.subdivision(0, 0).right_kernel_basis()
        span = zeros(solution_dimension, 1)
        for i, basis_vector in enumerate(kernel_basis):
            span += Matrix(basis_vector) * free_variables[i]
        offset = zeros(solution_dimension, 1)
        reduced = m.rref()
        for row_index, col_index in enumerate(m.pivots()):
            offset[col_index] = reduced.columns()[-1][row_index]
        rep = span + offset
        predicate = ",".join([latex(a) for a in free_variables[:len(kernel_basis)]])
        return (r" \left\{ " + latex(rep) + r" \,\middle|\, "
                + predicate + r" \in\mathbb R \right\} ")

    @staticmethod
    def simple_random_matrix_of_rank(rank, rows=1, columns=1, augmented=False):
        # get extra rows and columns, at least zero
        extra_rows = max(0, rows - rank)
        extra_columns = max(0, columns - rank)
        # matrix with the requested rank and integer RREF
        A = _random_full_column_rank(rank + extra_rows, rank)
        cols = [list(A.col(j)) for j in range(A.cols)]
        # randomly choose pivot indices where dependent columns are injected
        inserts = [random.randrange(rank) for _ in range(extra_columns)]
        # pedagogically we want the final column dependent at least half the time
        if extra_columns > 0 and random.choice([True, False]):
            inserts[0] = rank - 1
        # insert backwards so earlier indices stay valid
        inserts.sort(reverse=True)
        inserted_columns = []
        for pivot in inserts:
            while True:
                entries = [random.randrange(-3, 4) for _ in range(pivot + 1)]
                entries[random.randrange(pivot + 1)] = random.randrange(1, 4) * random.choice([-1, 1])
                dependent = [
                    sum(entries[k] * cols[k][r] for k in range(pivot + 1))
                    for r in range(len(cols[0]))
                ]
                if dependent not in inserted_columns:
                    inserted_columns.append(dependent)
                    cols = cols[:pivot + 1] + [dependent] + cols[pivot + 1:]
                    break
        result = CheckItMatrix(Matrix(cols).reshape(len(cols), len(cols[0])).T)
        if augmented:
            result.subdivide([], [columns - 1])
        return result


# decorator to help authors avoid confusing .data() with .get_data()
def provide_data(func):
    return lambda self: func(self.get_data())


class BaseGenerator:
    # See wrapper.sage for the full explanation; behavior here is identical.
    variants = None

    def __init__(self):
        self.__data = None
        self.__seed = None
        # Both are read by data(). `seed` lets a generator branch on *which*
        # version it is -- e.g. serving a fixed, hand-written problem for each
        # of the seeds the viewer exposes and drawing randomly above that.
        # Without it a generator can only see the seed after data() has already
        # run, via get_data()'s __seed__ key, which is too late to use.
        self.seed = None
        self.variant = None

    def data(self):
        return {}

    @provide_data
    def graphics(data):
        return None

    @provide_data
    def tikz_graphics(data):
        return None

    def build_variant_bag(self, amount):
        """Length-`amount` list of variant labels drawn from self.variants using
        a shuffle-bag, under a fixed RNG seed so the order is reproducible."""
        k = len(self.variants)
        random.seed(0)
        order, prev_last = [], None
        while len(order) < amount:
            chunk = list(range(k))
            random.shuffle(chunk)
            if k > 1 and prev_last is not None and chunk[0] == prev_last:
                for _ in range(20):
                    random.shuffle(chunk)
                    if chunk[0] != prev_last:
                        break
            order += chunk
            prev_last = chunk[-1]
        return [self.variants[i] for i in order[:amount]]

    def roll_data(self, seed=None, variant=None):
        if seed is None:
            random.seed()
            seed = random.randrange(1000)
        self.__seed = seed
        self.seed = seed
        self.variant = variant
        random.seed(seed)
        self.__data = self.data()

    def get_data(self):
        data = self.__data
        data["__seed__"] = f"{self.__seed:04}"
        if isinstance(self.variant, (str, int, bool)):
            data["__variant__"] = self.variant
        return self.__data


def json_ready(obj):
    """Convert generated values into JSON-safe LaTeX strings.

    This is the seam that keeps the rest of CheckIt runtime-agnostic: nothing
    but str/bool/list/dict ever reaches seeds.json, so no SymPy (or Sage) object
    escapes the subprocess.
    """
    if isinstance(obj, str) or isinstance(obj, bool):
        return obj
    elif isinstance(obj, list):
        return [json_ready(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: json_ready(obj[key]) for key in obj.keys()}
    else:
        return str(latex(obj))


# Names a generator file sees. Sage supplies its equivalents automatically.
GENERATOR_NAMESPACE = {
    "CheckIt": CheckIt,
    "BaseGenerator": BaseGenerator,
    "provide_data": provide_data,
    # The seed boundaries, so a generator can tell which surface a seed is for.
    # Below PUBLIC_SEEDS a student browses it; at or above, it feeds an
    # assessment. Some outcomes hold genuinely different content for the two --
    # a handout leaves the explanation blank where the study copy models it --
    # and this is the axis that distinguishes them.
    "PUBLIC_SEEDS": PUBLIC_SEEDS,
    "BUNDLE_UNTIL": BUNDLE_UNTIL,
    # random
    "randrange": random.randrange,
    "shuffle": random.shuffle,
    "choice": random.choice,
    "sample": random.sample,
    "set_random_seed": set_random_seed,
    # symbolic
    "var": var,
    "latex": latex,
    "matrix": matrix,
    "column_matrix": column_matrix,
    "zero_vector": zero_vector,
    "plot": plot,
    "e": sympy.E,
    "pi": sympy.pi,
    "I": sympy.I,
    "oo": sympy.oo,
    "Rational": Rational,
    # In Sage, `a == b` on symbolic expressions BUILDS an equation. In Python it
    # compares and returns a bool, so ported generators must use Eq(a, b).
    "Eq": sympy.Eq,
    "symbols": sympy.symbols,
    "Symbol": Symbol,
    # Add(..., evaluate=False) keeps a sum unsimplified for display, the way
    # Sage's expr.add(other, hold=True) did.
    "Add": sympy.Add,
    "Mul": sympy.Mul,
    "sqrt": sympy.sqrt,
    "exp": sympy.exp,
    "log": sympy.log,
    "sin": sympy.sin,
    "cos": sympy.cos,
    "tan": sympy.tan,
    "diff": sympy.diff,
    "expand": sympy.expand,
    "factor": sympy.factor,
    "simplify": sympy.simplify,
    "solve": sympy.solve,
    "binomial": sympy.binomial,
    "factorial": sympy.factorial,
    "gcd": sympy.gcd,
    "lcm": sympy.lcm,
    "Integer": sympy.Integer,
    "IntegerRange": lambda *a: list(range(*a)),
    "sympy": sympy,
}


def load_generator(generator_path):
    """Execute a generator file and return its Generator class.

    The Python analogue of wrapper.sage's `load(generator_path)`.
    """
    # Make bank-local helper modules importable from a generator.
    #
    # Running a script puts *that script's* directory on sys.path, which here is
    # the wrapper's own temp directory -- not the bank. The current working
    # directory is the bank root (wrapper/__init__.py enters it before spawning
    # us), but cwd is not on sys.path in Python 3. So without this a generator
    # cannot `import` a helper module that sits beside it or at the bank root,
    # and a bank has to resort to runpy tricks to share code between outcomes.
    #
    # Two locations: the generator's own directory, then the bank root. A
    # shared module (bank_helpers.py) lives at the bank root and is importable
    # from every outcome.
    #
    # Appended, NOT inserted at position 0. Prepending would let a bank file
    # shadow the standard library -- a bank_helpers.py sitting next to a
    # math.py or random.py would break the runtime in a thoroughly confusing
    # way. Appending means the worst case is a bank module being ignored
    # because an installed package already claims the name, which is confined
    # to the file that misnamed itself.
    for path in (os.path.dirname(os.path.abspath(generator_path)), os.getcwd()):
        if path not in sys.path:
            sys.path.append(path)

    namespace = dict(GENERATOR_NAMESPACE)
    with open(generator_path, encoding="utf-8") as f:
        source = f.read()
    code = compile(source, generator_path, "exec")
    exec(code, namespace)
    if "Generator" not in namespace:
        raise RuntimeError(
            f"{generator_path} does not define a `Generator` class extending "
            "BaseGenerator."
        )
    return namespace["Generator"]


# this script should be called from the root directory of the bank
# python wrapper.py /path/to/generator.py /path/to/output/seeds.json 1000 random? images?
if __name__ == "__main__":
    if len(sys.argv) >= 4:
        generator_path = sys.argv[1]
        seeds_path = sys.argv[2]
        amount = int(sys.argv[3])
        randomized = (len(sys.argv) >= 5 and sys.argv[4].lower() == "random")
        gen_images = (len(sys.argv) >= 6 and sys.argv[5].lower() == "images")
        image_amount = int(sys.argv[6]) if (gen_images and len(sys.argv) >= 7) else amount

        Generator = load_generator(generator_path)
        generator = Generator()

        variant_bag = (generator.build_variant_bag(amount)
                       if getattr(generator, "variants", None) else None)

        seeds = []
        for i in range(amount):
            if i > 0 and (i % 50) == 0:
                print(f"Generating seed {i}")
            if randomized:
                random.seed()
                seed_int = int(random.randrange(1_000))
            else:
                seed_int = int(i)
            variant = variant_bag[i] if variant_bag is not None else None
            generator.roll_data(seed=seed_int, variant=variant)
            seed = {"seed": seed_int, "data": json_ready(generator.get_data())}
            directory = os.path.dirname(seeds_path)
            seed_path = os.path.join(directory, f"{seed_int:04}")
            # TikZ source is cheap text and print needs it for every seed, so it
            # is written unconditionally -- see wrapper.sage for the full note.
            tikz = generator.tikz_graphics()
            if tikz is not None:
                os.makedirs(seed_path, exist_ok=True)
                for name, source in tikz.items():
                    with open(os.path.join(seed_path, f"{name}.tikz"), "w") as f:
                        f.write(source)
            # Rasterizing is the expensive half, so it stays gated.
            if gen_images and i < image_amount:
                graphics = generator.graphics()
                if graphics is not None:
                    os.makedirs(seed_path, exist_ok=True)
                    for filename in graphics:
                        graphics[filename].save(os.path.join(seed_path, f"{filename}.png"))
            seeds.append(seed)
        data = {
            "seeds": seeds,
            "generated_on": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        os.makedirs(os.path.dirname(seeds_path), exist_ok=True)
        with open(os.path.join(seeds_path), "w") as f:
            json.dump(data, f)
    else:
        raise RuntimeError("Three positional arguments are required")
