<?xml version="1.0"?>
<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:stx="https://spatext.clontz.org"
                exclude-result-prefixes="stx">

    <xsl:output method="html"/>

    <!-- Subset is 'statement', 'answer', or 'all'.

         This mirrors the filtering the viewer performs in JavaScript after the
         transform (utils/index.ts, the `solutions` argument to outcomeToHtml):
             'all'       == solutions 'show'  : everything
             'statement' == solutions 'hide'  : drop every stx-outtro
             'answer'    == solutions 'only'  : drop every stx-intro and stx-content
         Those two implementations must agree; see CODEBASE_NOTES.md.

         Restored from ccc9b09 (Jan 2022), which lost it in the fde75e8 SpaTeXt
         rewrite while leaving Exercise.html_ele()'s signature behind, so the
         parameter was accepted and silently ignored for four years.

         There is deliberately no `consumer` parameter yet. ccc9b09 had one, but
         nothing in this stylesheet reads it, and declaring an unused parameter
         is what created the original bug. It arrives with the MathML work. -->
    <xsl:param name="subset" select="'all'"/>

    <!-- kill undefined elements -->
    <xsl:template match="*"/>

    <!-- Normalize text() whitespace but don't completely trim beginning or end: https://stackoverflow.com/a/5044657/1607849 -->
    <xsl:template match="text()"><xsl:value-of select="translate(normalize-space(concat('&#x7F;',.,'&#x7F;')),'&#x7F;','')"/></xsl:template>

    <xsl:template match="/">
        <div class="stx">
            <xsl:apply-templates/>
        </div>
    </xsl:template>

    <!-- Nested knowls re-enter this template, so guarding here filters every
         level at once, matching the viewer, whose querySelectorAll removal is
         likewise global. The <ol>/<li> wrapper is deliberately outside the
         guards: the viewer strips only stx-intro/stx-content, so list numbering
         survives subset='answer' and must survive here too. -->
    <xsl:template match="stx:knowl">
        <div class="stx-knowl">
            <xsl:apply-templates select="stx:title[1]"/>
            <xsl:if test="$subset != 'answer'">
                <xsl:apply-templates select="stx:intro[1]"/>
            </xsl:if>
            <xsl:choose>
                <xsl:when test="stx:knowl">
                    <ol>
                        <xsl:for-each select="stx:knowl">
                            <li>
                                <xsl:apply-templates select="."/>
                            </li>
                        </xsl:for-each>
                    </ol>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:if test="$subset != 'answer'">
                        <xsl:apply-templates select="stx:content[1]"/>
                    </xsl:if>
                </xsl:otherwise>
            </xsl:choose>
            <xsl:if test="$subset != 'statement'">
                <xsl:apply-templates select="stx:outtro[1]"/>
            </xsl:if>
        </div>
    </xsl:template>

    <xsl:template match="stx:title">
        <h3 class="stx-title">
            <xsl:apply-templates select="text()|stx:m|stx:q|stx:c"/>
        </h3>
    </xsl:template>

    <xsl:template match="stx:intro">
        <div class="stx-intro">
            <xsl:apply-templates select="stx:p|stx:list"/>
        </div>
    </xsl:template>

    <xsl:template match="stx:content">
        <div class="stx-content">
            <xsl:choose>
                <xsl:when test="ancestor::stx:knowl">
                    <xsl:apply-templates select="stx:p|stx:list"/>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:apply-templates select="stx:p|stx:list|stx:knowl"/>
                </xsl:otherwise>
            </xsl:choose>
        </div>
    </xsl:template>

    <xsl:template match="stx:outtro">
        <div class="stx-outtro">
            <xsl:apply-templates select="stx:p|stx:list"/>
        </div>
    </xsl:template>

    <xsl:template match="stx:list">
        <xsl:if test="stx:item">
            <ul class="stx-list">
                <xsl:for-each select="stx:item">
                    <li>
                        <xsl:apply-templates select="stx:p|stx:list"/>
                    </li>
                </xsl:for-each>
            </ul>
        </xsl:if>
    </xsl:template>

    <xsl:template name="parseDisplay">
        <xsl:apply-templates select="text()|stx:m|stx:me|stx:q|stx:c|stx:em|stx:url|stx:image|stx:tikz-image|stx:glyphs"/>
    </xsl:template>

    <xsl:template match="stx:p">
        <p>
            <xsl:call-template name="parseDisplay"/>
        </p>
    </xsl:template>

    <xsl:template match="stx:m">
        <span class="math inline-math">
            <xsl:attribute name="data-latex">
                <xsl:value-of select="normalize-space(text())"/>
            </xsl:attribute>
            <xsl:text>\(</xsl:text>
            <xsl:value-of select="normalize-space(text())"/>
            <xsl:text>\)</xsl:text>
        </span>
    </xsl:template>
    <xsl:template match="stx:m[@mode='display']|stx:me">
        <span class="math display-math">
            <xsl:attribute name="data-latex">
                <xsl:value-of select="normalize-space(text())"/>
            </xsl:attribute>
            <xsl:text>\[</xsl:text>
            <xsl:value-of select="normalize-space(text())"/>
            <xsl:text>\]</xsl:text>
        </span>
    </xsl:template>

    <xsl:template match="stx:em">
        <em>
            <xsl:call-template name="parseDisplay"/>
        </em>
    </xsl:template>

    <xsl:template match="stx:c">
        <code>
            <xsl:value-of select="normalize-space(text())"/>
        </code>
    </xsl:template>

    <xsl:template match="stx:q">
        <xsl:text>"</xsl:text>
        <xsl:call-template name="parseDisplay"/>
        <xsl:text>"</xsl:text>
    </xsl:template>

    <xsl:template match="stx:image">
        <img>
            <xsl:attribute name="src">
                <xsl:value-of select="@remote"/>
                <xsl:text>/</xsl:text>
                <xsl:value-of select="@source"/>
            </xsl:attribute>
            <xsl:attribute name="alt">
                <xsl:value-of select="@description"/>
            </xsl:attribute>
        </img>
    </xsl:template>

    <xsl:template match="stx:tikz-image">
        <img>
            <xsl:attribute name="src">
                <xsl:value-of select="@remote"/>
                <xsl:text>/</xsl:text>
                <xsl:value-of select="@source"/>
                <xsl:text>.png</xsl:text>
            </xsl:attribute>
            <xsl:attribute name="alt">
                <xsl:value-of select="@description"/>
            </xsl:attribute>
        </img>
    </xsl:template>

    <!-- Characters needing a typeface the browser and LaTeX name differently.
         The size is inline rather than a class because this HTML is also read
         outside the viewer, in the LMS exports and the AI payload, where none
         of the site stylesheet travels with it. -->
    <xsl:template match="stx:glyphs">
        <span class="stx-glyphs" style="font-size:2em; line-height:1.2">
            <xsl:attribute name="data-font">
                <xsl:value-of select="@font"/>
            </xsl:attribute>
            <xsl:value-of select="text()"/>
        </span>
    </xsl:template>

    <xsl:template match="stx:url[@href]">
        <xsl:choose>
            <xsl:when test=". != ''">
                <a>
                    <xsl:attribute name="href">
                        <xsl:value-of select="@href"/>
                    </xsl:attribute>
                    <xsl:call-template name="parseDisplay"/>
                </a>
            </xsl:when>
            <xsl:otherwise>
                <a>
                    <xsl:attribute name="href">
                        <xsl:value-of select="@href"/>
                    </xsl:attribute>
                    <xsl:value-of select="@href"/>
                </a>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

</xsl:stylesheet>