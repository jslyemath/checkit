class Generator(BaseGenerator):
    def data(self):
        a = randrange(1, 6)
        b = randrange(1, 6)
        return {
            "a": a,
            "b": b,
        }

    @provide_data
    def tikz_graphics(data):
        a = data["a"]
        b = data["b"]
        tikz = (
            r"\begin{tikzpicture}" "\n"
            r"\draw (0,0) rectangle (" + str(a) + "," + str(b) + ");\n"
            r"\node at (" + str(a/2) + "," + str(b/2) + r") {" + str(a*b) + "};\n"
            r"\end{tikzpicture}"
        )
        return {"rect": tikz}