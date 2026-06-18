import sys,json,os,datetime

# Library of helpful functions
class CheckIt:
    @staticmethod
    def vars(*latex_names, random_order=True):
        """
        Given one or more `latex_names` of strings, returns a tuple
        of Sage variables. `random_order` names them so that they appear
        in expressions in a random order.
        """
        stamp = randrange(100000,999999)
        indices = list(range(len(latex_names)))
        if random_order:
            shuffle(indices)
        import string
        random_letter = choice(list(string.ascii_lowercase))
        return (var(f"{random_letter}_mi_var_{stamp}_{indices[i]}", latex_name=name) for i, name in enumerate(latex_names))

    @staticmethod
    def shuffled_equation(*terms):
        """
        Represents the equation sum(terms)==0, but with terms shuffled randomly
        to each side.
        """
        new_equation = (SR(0)==0)
        for term in terms:
            if choice([True,False]):
                new_equation += (SR(term)==0)
            else:
                new_equation += (0==-SR(term))
        return new_equation*choice([-1,1])

    @staticmethod
    def shuffled_inequality(*terms,strict=True):
        """
        Represents the equation sum(terms)>0 or >=0, but with terms shuffled randomly
        to each side, and random direction of inequality
        """
        if choice([True,False]):
            if strict:
                new_equation = (SR(0)>0)
            else:
                new_equation = (SR(0)>=0)
            for term in terms:
                if choice([True,False]):
                    new_equation += (SR(term)==0)
                else:
                    new_equation += (0==-SR(term))
        else:
            if strict:
                new_equation = (SR(0)<0)
            else:
                new_equation = (SR(0)<=0)
            for term in terms:
                if choice([True,False]):
                    new_equation += (-SR(term)==0)
                else:
                    new_equation += (0==SR(term))
        return new_equation

    @staticmethod
    def latex_system_from_matrix(matrix, variables="x", alpha_mode=False, variable_list=None):
        # Augment with zero vector if not already augmented
        if not matrix.subdivisions()[1]:
            matrix=matrix.augment(zero_vector(QQ, len(matrix.rows())), subdivide=true)
        num_vars = matrix.subdivisions()[1][0]
        # Start using requested variables
        if variable_list is None:
            system_vars = []
        else:
            system_vars = variable_list
        # Conveniently add xyzwv if requested
        if alpha_mode:
            system_vars += list(var("x y z w v"))
        # Finally fall back to x_n as needed
        system_vars += [var(f"{variables}_{n+1}") for n in range(num_vars)]
        # Build matrix
        latex_output = "\\begin{matrix}\n"
        for row in matrix.rows():
            if row[0]!= 0:
                latex_output += latex(row[0]*system_vars[0])
                previous_terms = True
            else:
                previous_terms = False
            for n,cell in enumerate(row[1:num_vars]):
                latex_output += " & "
                if cell < 0:
                    latex_output += " - "
                elif cell > 0 and previous_terms:
                    latex_output += " + "
                latex_output += " & "
                if cell != 0:
                    latex_output += latex(cell.abs()*system_vars[n+1])
                if not previous_terms:
                    previous_terms = bool(cell!=0)
            if not previous_terms:
                latex_output += " 0 "
            latex_output += " & = & "
            latex_output += latex(row[num_vars])
            latex_output += "\\\\\n"
        latex_output += "\\end{matrix}"
        return latex_output

    @staticmethod
    def latex_solution_set_from_matrix(matrix):
        # Augment with zero vector if not already augmented
        if not matrix.subdivisions()[1]:
            matrix=matrix.augment(zero_vector(QQ, len(matrix.rows())), subdivide=true)
        if (len(matrix.columns())-1) in matrix.pivots():
            return r" \{\} "
        solution_dimension = len(matrix.columns())-1
        free_variables = list(var("a b c d e f g h i j"))
        kernel_basis=matrix.subdivision(0,0).right_kernel(basis='pivot').basis()
        span = sum([kernel_basis[i]*free_variables[i] for i in range(len(kernel_basis))])
        offset = zero_vector(QQ,solution_dimension)
        for row_index,col_index in enumerate(matrix.pivots()):
            offset[col_index] = matrix.rref().columns()[-1][row_index]
        rep = column_matrix(span+offset)
        predicate = ",".join([latex(a) for a in free_variables[:len(kernel_basis)]])
        return r" \left\{ " + latex(rep) + r" \,\middle|\, " + predicate + r" \in\mathbb R \right\} "

    @staticmethod
    def simple_random_matrix_of_rank(rank,rows=1,columns=1,augmented=False):
        # get extra rows and columns, at least zero
        extra_rows = max(0,rows-rank)
        extra_columns = max(0,columns-rank)
        # create matrix with terms between -5 and 5 inclusive, rank in every column, and integer entries RREF
        A = random_matrix(QQ,rank+extra_rows,rank,algorithm='echelonizable',rank=rank,upper_bound=6)
        # randomly choose pivot indices where dependent columns are injected afterward
        inserts = [randrange(rank) for _ in range(extra_columns)]
        # pedagogically we want final column to be dependent at least half the time
        if extra_columns>0 and choice([True,False]):
            inserts[0]=rank-1
        # we'll insert columns backwards to avoid messing up where to inject columns
        inserts.sort(reverse=True)
        # we won't repeat dependent columns
        inserted_columns = []
        for pivot in inserts:
            while True:
                # get random numbers for pivot rows
                rref_pivot_entries = [randrange(-3,4) for _ in range(pivot+1)]
                # ensure at least one is nonzero
                rref_pivot_entries[randrange(pivot+1)] = randrange(1,4)*choice([-1,1])
                # create vector
                dependent_vector = sum([rref_pivot_entries[_]*A.column(_) for _ in range(pivot+1)])
                if dependent_vector not in inserted_columns:
                    inserted_columns.append(dependent_vector)
                    A = matrix(A.columns()[:pivot+1]+[dependent_vector]+A.columns()[pivot+1:]).transpose()
                    break
        if augmented:
            A.subdivide([],[columns-1])
        return A

# decorator to help authors avoid confusing .data() with .get_data() in a Generator
def provide_data(func):
    return lambda self: func(self.get_data())

# BaseGenerator class inherited by each outcome's Generator class to minimize boilerplate
class BaseGenerator:
    # Authors may set this to a list of "problem type" labels: strings, ints, or
    # even dicts carrying a whole hand-built problem. When set, the wrapper
    # assigns each seed one label via an even shuffle-bag, see build_variant_bag,
    # and exposes it as self.variant for data() to branch on, instead of the
    # author calling choice themselves. Leaving it None keeps the legacy
    # behavior unchanged.
    variants = None

    def __init__(self):
        self.__data = None
        self.__seed = None
        self.variant = None

    def data(self):
        return {}

    @provide_data
    def graphics(data):
        return None

    @provide_data
    def tikz_graphics(data):
        return None

    def build_variant_bag(self,amount):
        """
        Returns a length-`amount` list of variant labels drawn from self.variants
        using a shuffle-bag: each chunk is a freshly shuffled full permutation of
        all variants, so counts are as even as possible. A bounded re-shuffle of
        each new chunk prevents a label repeating across a chunk boundary. Built
        under a fixed RNG seed so the order is reproducible and the first-N prefix
        is stable across different `amount` values.
        """
        k = len(self.variants)
        set_random_seed(0)
        order, prev_last = [], None
        while len(order) < amount:
            chunk = list(range(k))
            shuffle(chunk)
            if k > 1 and prev_last is not None and chunk[0] == prev_last:
                for _ in range(20):
                    shuffle(chunk)
                    if chunk[0] != prev_last:
                        break
            order += chunk
            prev_last = chunk[-1]
        return [self.variants[i] for i in order[:amount]]

    def roll_data(self,seed=None,variant=None):
        if seed is None:
            set_random_seed()
            seed = randrange(1000)
        self.__seed = seed
        self.variant = variant
        set_random_seed(seed)
        self.__data = self.data()

    def get_data(self):
        data = self.__data
        data["__seed__"] = f"{self.__seed:04}"
        if isinstance(self.variant,(str,int,bool)):
            data["__variant__"] = self.variant
        return self.__data

# converts SageMath objects into latexified strings
# note Python numbers are latexified into strings as well
def json_ready(obj):
    if isinstance(obj,str) or isinstance(obj,bool):
        return obj
    elif isinstance(obj,list):
        return [json_ready(item) for item in obj]
    elif isinstance(obj,dict):
        return {key:json_ready(obj[key]) for key in obj.keys()}
    else:
        return str(latex(obj))

# this script should be called from the root directory of the bank
# so loads in the generator file work as intended
# sage /path/to/wrapper.sage /path/to/generator.sage /path/to/output/seeds.json 1000 random? images?
if len(sys.argv) >= 4:
    generator_path = sys.argv[1]
    seeds_path = sys.argv[2]
    amount = int(sys.argv[3])
    random = (len(sys.argv) >= 5 and sys.argv[4].lower() == "random")
    gen_images = (len(sys.argv) >= 6 and sys.argv[5].lower()=="images")
    image_amount = int(sys.argv[6]) if (gen_images and len(sys.argv) >= 7) else amount

    load(generator_path) # must provide Generator class extending BaseGenerator
    generator = Generator()

    # if the generator declares problem-type variants, assign them across the
    # seeds with an even shuffle-bag instead of letting each seed roll its own
    variant_bag = generator.build_variant_bag(amount) if getattr(generator,"variants",None) else None

    # preview/build to specified JSON file
    seeds = []
    for i in range(amount):
        if i > 0 and (i % 50) == 0:
            print(f"Generating seed {i}")
        if random:
            set_random_seed()
            seed_int = int(randrange(1_000))
        else:
            seed_int = int(i)
        variant = variant_bag[i] if variant_bag is not None else None
        generator.roll_data(seed=seed_int,variant=variant)
        seed  = {"seed":seed_int,"data":json_ready(generator.get_data())}
        if gen_images and i < image_amount:
            directory = os.path.dirname(seeds_path)
            seed_path = os.path.join(directory, f"{seed_int:04}")
            graphics = generator.graphics()
            if graphics is not None:
                os.makedirs(seed_path, exist_ok=True)
                for filename in graphics:
                    graphics[filename].save(os.path.join(seed_path, f"{filename}.png"))
            tikz = generator.tikz_graphics()
            if tikz is not None:
                os.makedirs(seed_path, exist_ok=True)
                for name, source in tikz.items():
                    with open(os.path.join(seed_path, f"{name}.tikz"), "w") as f:
                        f.write(source)
        seeds.append(seed)
    data = {
        "seeds": seeds,
        "generated_on": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    os.makedirs(os.path.dirname(seeds_path), exist_ok=True)
    with open(os.path.join(seeds_path), 'w') as f:
        json.dump(data, f)
else:
    raise RuntimeError("Three positional arguments are required")
