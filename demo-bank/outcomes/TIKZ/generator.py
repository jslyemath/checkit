class Generator(BaseGenerator):
    def data(self):
        ax, ay = randrange(0, 3), randrange(0, 3)
        bx, by = randrange(4, 7), randrange(0, 3)
        cx, cy = randrange(1, 6), randrange(4, 7)
        return {
            "ax": ax, "ay": ay,
            "bx": bx, "by": by,
            "cx": cx, "cy": cy,
        }

    @provide_data
    def tikz_graphics(data):
        ax, ay = data["ax"], data["ay"]
        bx, by = data["bx"], data["by"]
        cx, cy = data["cx"], data["cy"]
        tikz = (
            r"\begin{tikzpicture}" "\n"
            r"\tkzDefPoint(" + str(ax) + "," + str(ay) + r"){A}" "\n"
            r"\tkzDefPoint(" + str(bx) + "," + str(by) + r"){B}" "\n"
            r"\tkzDefPoint(" + str(cx) + "," + str(cy) + r"){C}" "\n"
            r"\tkzDefCircle[circum](A,B,C)" "\n"
            r"\tkzGetPoint{O}" "\n"
            # \tkzDrawCircle(O,A), not [circum]: `circum` is an option of
            # \tkzDefCircle above, not of \tkzDrawCircle. Passing it here made
            # every compile emit "I do not know the key '/tikz/circum'".
            # pdflatex recovers and still draws the circle, so the figure looked
            # fine and the error went unnoticed -- but it is noise in every log.
            r"\tkzDrawCircle(O,A)" "\n"
            r"\tkzDrawPolygon(A,B,C)" "\n"
            r"\tkzDrawPoints(A,B,C)" "\n"
            r"\tkzLabelPoints(A,B,C)" "\n"
            r"\end{tikzpicture}"
        )
        return {"triangle": tikz}