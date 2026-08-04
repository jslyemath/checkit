class Generator(BaseGenerator):
    def data(self):
        # create a 3x5 or 4x4 matrix
        rows = randrange(3,5)
        columns = 8-rows

        #start with nice RREF
        max_number_of_pivots = min(rows,columns-1)
        number_of_pivots = randrange(2,max_number_of_pivots+1)
        A = CheckIt.simple_random_matrix_of_rank(number_of_pivots,rows=rows,columns=columns)
        A.subdivide([],[columns-1])

        # construct variables
        # plain var("w"): Sage used var("zw",latex_name="w") so the symbol would
        # sort after z while printing as w. Order here comes from this list's
        # position, not the symbol name, so the trick is unnecessary.
        xs=choice([
            [var("x_"+str(i+1)) for i in range(0,columns-1)],
            [var("x"),var("y"),var("z"),var("w")][0:columns-1],
        ])

        return {
            "system": CheckIt.latex_system_from_matrix(A,variable_list=xs),
            "matrix": A,
        }
