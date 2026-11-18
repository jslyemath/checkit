<?xml version="1.0"?>
<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:stx="https://spatext.clontz.org"
                exclude-result-prefixes="stx">

    <xsl:output method="text"/>

    <!-- kill undefined elements -->
    <xsl:template match="*"/>

    <!-- Normalize text() whitespace but don't completely trim beginning or end: https://stackoverflow.com/a/5044657/1607849

         Then escaped. Text outside <m>, <me> and an @latex attribute is
         prose, and the web shows it exactly as written, so print has to as
         well. Copied verbatim, a "50% off" printed as "50" (the % began a
         comment), an & was a compile error, and a brace silently vanished. -->
    <xsl:template match="text()">
        <xsl:call-template name="tex-escape">
            <xsl:with-param name="text" select="translate(normalize-space(concat('&#x7F;',.,'&#x7F;')),'&#x7F;','')"/>
        </xsl:call-template>
    </xsl:template>

    <!-- The ten characters LaTeX reads as instructions, and what prints each
         one literally. The same table as checkit-printit's tex_escape, which
         does this for the names and titles printit types into main.tex.

         XSLT 1.0 has no replace(). translate() turns every special character
         into a backslash, so the text before the first backslash in that copy
         is the run of ordinary characters; it is written as is, the special
         character after it is written escaped, and the rest goes round
         again.

         That is one call per special character, and libxslt stops at a depth
         of 3000, so text with thousands of them would fail to render at all.
         Long text is therefore halved first (escaping is per character, so
         any split point is safe), which keeps the depth near log2(length)
         plus 200 however the text is made. -->
    <xsl:variable name="tex-specials" select="'\{}$&amp;#^_%~'"/>
    <xsl:variable name="tex-marks" select="'\\\\\\\\\\'"/>

    <xsl:template name="tex-escape">
        <xsl:param name="text"/>
        <xsl:variable name="marked" select="translate($text, $tex-specials, $tex-marks)"/>
        <xsl:choose>
            <xsl:when test="string-length($text) &gt; 200 and contains($marked, '\')">
                <xsl:variable name="half" select="floor(string-length($text) div 2)"/>
                <xsl:call-template name="tex-escape">
                    <xsl:with-param name="text" select="substring($text, 1, $half)"/>
                </xsl:call-template>
                <xsl:call-template name="tex-escape">
                    <xsl:with-param name="text" select="substring($text, $half + 1)"/>
                </xsl:call-template>
            </xsl:when>
            <xsl:when test="contains($marked, '\')">
                <xsl:variable name="plain" select="string-length(substring-before($marked, '\'))"/>
                <xsl:value-of select="substring($text, 1, $plain)"/>
                <xsl:variable name="ch" select="substring($text, $plain + 1, 1)"/>
                <xsl:choose>
                    <xsl:when test="$ch = '\'">\textbackslash{}</xsl:when>
                    <xsl:when test="$ch = '~'">\textasciitilde{}</xsl:when>
                    <xsl:when test="$ch = '^'">\textasciicircum{}</xsl:when>
                    <xsl:otherwise><xsl:value-of select="concat('\', $ch)"/></xsl:otherwise>
                </xsl:choose>
                <xsl:call-template name="tex-escape">
                    <xsl:with-param name="text" select="substring($text, $plain + 2)"/>
                </xsl:call-template>
            </xsl:when>
            <xsl:otherwise>
                <xsl:value-of select="$text"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <xsl:template match="/">
        <xsl:text>%%%%% SpaTeXt Commands %%%%%</xsl:text>
        <xsl:text>&#xa;</xsl:text>
        <xsl:text>\providecommand{\stxKnowl}{}\renewcommand{\stxKnowl}[1]{#1}</xsl:text>
        <xsl:text>&#xa;</xsl:text>
        <xsl:text>\providecommand{\stxOuttro}{}\renewcommand{\stxOuttro}[1]{#1}</xsl:text>
        <xsl:text>&#xa;</xsl:text>
        <xsl:text>\providecommand{\stxTitle}{}\renewcommand{\stxTitle}[1]{#1}</xsl:text>
        <xsl:text>&#xa;</xsl:text>
        <xsl:text>% Comment next line to show outtros</xsl:text>
        <xsl:text>&#xa;</xsl:text>
        <xsl:text>\renewcommand{\stxOuttro}[1]{}</xsl:text>
        <xsl:text>&#xa;</xsl:text>
        <xsl:text>%%%%%%%%%%%%%%%%%%%%%%%%%%%%</xsl:text>
        <xsl:text>&#xa;</xsl:text>
        <xsl:apply-templates select="*"/>
    </xsl:template>

    <xsl:template match="stx:knowl">
        <xsl:text>\stxKnowl{</xsl:text>
        <xsl:text>&#xa;</xsl:text>
        <xsl:apply-templates select="stx:title[1]"/>
        <xsl:apply-templates select="stx:intro[1]"/>
        <xsl:choose>
            <xsl:when test="stx:knowl">
                <xsl:text>\begin{enumerate}</xsl:text>
                <xsl:text>&#xa;</xsl:text>
                <xsl:for-each select="stx:knowl">
                    <xsl:text>\item</xsl:text>
                    <xsl:text>&#xa;</xsl:text>
                    <xsl:apply-templates select="."/>
                </xsl:for-each>
                <xsl:text>\end{enumerate}</xsl:text>
                <xsl:text>&#xa;</xsl:text>
            </xsl:when>
            <xsl:otherwise>
                <xsl:apply-templates select="stx:content[1]"/>
            </xsl:otherwise>
        </xsl:choose>
        <xsl:apply-templates select="stx:outtro[not(@distractor='true')][1]"/>
        <xsl:text>}</xsl:text>
        <xsl:text>&#xa;</xsl:text>
        <xsl:text>&#xa;</xsl:text>
    </xsl:template>

    <xsl:template match="stx:title">
        <xsl:text>\stxTitle{</xsl:text>
        <xsl:apply-templates select="text()|stx:m|stx:q|stx:c"/>
        <xsl:text>}</xsl:text>
        <xsl:text>&#xa;</xsl:text>
        <xsl:text>&#xa;</xsl:text>
    </xsl:template>

    <xsl:template match="stx:intro">
        <xsl:apply-templates select="stx:p|stx:list"/>
    </xsl:template>

    <xsl:template match="stx:content">
        <xsl:choose>
            <xsl:when test="ancestor::stx:knowl">
                <xsl:apply-templates select="stx:p|stx:list"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:apply-templates select="stx:p|stx:list|stx:knowl"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <xsl:template match="stx:outtro">
        <xsl:text>\stxOuttro{</xsl:text>
        <xsl:text>&#xa;</xsl:text>
        <xsl:apply-templates select="stx:p|stx:list"/>
        <xsl:text>}</xsl:text>
        <xsl:text>&#xa;</xsl:text>
    </xsl:template>

    <xsl:template match="stx:list">
        <xsl:if test="stx:item">
            <xsl:text>\begin{itemize}</xsl:text>
            <xsl:text>&#xa;</xsl:text>
                <xsl:for-each select="stx:item">
                    <xsl:text>\item</xsl:text>
                    <xsl:text>&#xa;</xsl:text>
                    <xsl:apply-templates select="stx:p|stx:list"/>
                </xsl:for-each>
            <xsl:text>\end{itemize}</xsl:text>
            <xsl:text>&#xa;</xsl:text>
        </xsl:if>
    </xsl:template>

    <xsl:template name="parseDisplay">
        <xsl:apply-templates select="text()|stx:m|stx:me|stx:q|stx:c|stx:em|stx:url|stx:image|stx:tikz-image|stx:glyphs|stx:nobreak"/>
    </xsl:template>

    <xsl:template match="stx:p">
        <xsl:call-template name="parseDisplay"/>
        <xsl:text>&#xa;&#xa;</xsl:text>
    </xsl:template>

    <xsl:template match="stx:m">
        <xsl:text>\(</xsl:text>
        <xsl:value-of select="normalize-space(text())"/>
        <xsl:text>\)</xsl:text>
    </xsl:template>
    <xsl:template match="stx:m[@mode='display']|stx:me">
        <xsl:text>\[</xsl:text>
        <xsl:value-of select="normalize-space(text())"/>
        <xsl:text>\]</xsl:text>
    </xsl:template>

    <xsl:template match="stx:em">
        <xsl:text>\textbf{</xsl:text>
        <xsl:call-template name="parseDisplay"/>
        <xsl:text>}</xsl:text>
    </xsl:template>

    <!-- Print is the reason this element exists. W4's equations are long enough
         that LaTeX broke them across lines at the operators, which is wrong for
         a question asking which property an equation exemplifies. \mbox is the
         fix. It used to be written into the generator behind a mode='latex'
         branch, so the browser showed a literal "\mbox{" instead.

         Content, not text(): this wraps <m> elements, and reading only text
         nodes would discard them exactly as the <m> rule does. -->
    <xsl:template match="stx:nobreak">
        <xsl:text>\mbox{</xsl:text>
        <xsl:call-template name="parseDisplay"/>
        <xsl:text>}</xsl:text>
    </xsl:template>

    <xsl:template match="stx:c">
        <xsl:text>\texttt{</xsl:text>
        <xsl:call-template name="tex-escape">
            <xsl:with-param name="text" select="normalize-space(text())"/>
        </xsl:call-template>
        <xsl:text>}</xsl:text>
    </xsl:template>

    <xsl:template match="stx:q">
        <xsl:text>``</xsl:text>
        <xsl:call-template name="parseDisplay"/>
        <xsl:text>''</xsl:text>
    </xsl:template>

    <xsl:template match="stx:image">
        <xsl:text>\includegraphics{</xsl:text>
        <xsl:value-of select="@source"/>
        <xsl:text>}</xsl:text>
    </xsl:template>

    <xsl:template match="stx:tikz-image">
        <xsl:text>\input{</xsl:text>
        <xsl:value-of select="@source"/>
        <xsl:text>.tikz}</xsl:text>
    </xsl:template>

    <!-- Each font name maps to the LaTeX command that provides it; adding a
         font means adding a case here and a rule in html.xsl. An unknown name
         falls through to plain text rather than emitting an undefined command,
         which would fail the whole document at compile time. -->
    <xsl:template match="stx:glyphs">
        <xsl:choose>
            <xsl:when test="@latex">
                <!-- Some scripts have no single set of characters that works in
                     both media: Babylonian numerals are Unicode cuneiform on
                     screen but macros in print, so no font
                     wrapper can bridge them. Such an element carries both, and
                     the element still holds the decision rather than a
                     generator branching on the output format.

                     Braced, always. A @latex value is written by a generator
                     author and typically starts with a size or font switch such
                     as \Large, which is a declaration, not a wrapper: without a
                     group it stays in force to the end of the enclosing one. An
                     unbraced \Large once made every page after the first
                     Egyptian numeral enormous. The group costs nothing for a
                     value that did not need it. -->
                <xsl:text>{</xsl:text>
                <xsl:value-of select="@latex"/>
                <xsl:text>}</xsl:text>
            </xsl:when>
            <xsl:when test="@font='egyptian'">
                <xsl:text>{\Large\textpmhg{</xsl:text>
                <xsl:value-of select="text()"/>
                <xsl:text>}}</xsl:text>
            </xsl:when>
            <xsl:otherwise>
                <xsl:call-template name="tex-escape">
                    <xsl:with-param name="text" select="text()"/>
                </xsl:call-template>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <xsl:template match="stx:url[@href]">
        <xsl:choose>
            <xsl:when test=". != ''">
                <xsl:text>\href{</xsl:text>
                <xsl:value-of select="@href"/>
                <xsl:text>}{</xsl:text>
                <xsl:call-template name="parseDisplay"/>
                <xsl:text>}</xsl:text>
            </xsl:when>
            <xsl:otherwise>
                <xsl:text>\url{</xsl:text>
                <xsl:value-of select="@href"/>
                <xsl:text>}</xsl:text>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

</xsl:stylesheet>