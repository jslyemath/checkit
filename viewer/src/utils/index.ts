import type {Bank, Assessment, Outcome} from '../types';

import {isOpen as codeCellIsOpen} from '../stores/codecell';

import katex from 'katex';

import Mustache from 'mustache';
// @ts-ignore
import latexXsl from '../spatext/xsl/latex.xsl?raw'
// @ts-ignore
import htmlXsl from '../spatext/xsl/html.xsl?raw'
// @ts-ignore
import ptxXsl from '../spatext/xsl/pretext.xsl?raw'
// @ts-ignore
import assessmentTemplate from '../templates/assessmentTemplate.tex?raw'

const parser = new DOMParser()

const errorStx = (message:string) =>
    `<knowl><content><p><em>ERROR:</em> ${message}</p></content></knowl>`

/**
 * The SpaTeXt for one exercise, as a **Document**.
 *
 * Every XSLT caller must pass this rather than its root element. The three
 * stylesheets key their wrapper off `<xsl:template match="/">`, and `/` matches
 * the document node -- so handing transformToDocument() an Element means that
 * template never fires and the wrapper is never emitted.
 *
 * Chrome papers over this by resolving an element source to its owner document,
 * so it produced correct output either way. Firefox follows the spec, and
 * measuring it there showed the difference exactly:
 *
 *   source = document -> <div class="stx">ROOT<div class="stx-knowl">…</div></div>
 *   source = element  -> <div class="stx-knowl">…</div>          (no wrapper)
 *
 * With no wrapper, outcomeToHtml()'s lookup returned null and `.outerHTML` threw
 * "can't access property outerHTML, l is null", taking down every caller --
 * including the "Copy for AI Chatbot" button.
 */
export const outcomeToStxDocument = (o:Outcome,seed:number) => {
    let stxString:string
    try {
        stxString = Mustache.render(o.template, o.exercises[seed]['data'])
    } catch (error) {
        stxString = errorStx("Mustache template could not be parsed.")
    }
    let doc = parser.parseFromString(stxString, "application/xml")
    if (doc.querySelector('parsererror')) {
        doc = parser.parseFromString(errorStx("XML could not be parsed."), "application/xml")
    }
    const remote = `${location.protocol}//${location.host}${location.pathname.replace(/\/+$/, "")}`
    doc.querySelectorAll("image, tikz-image").forEach(image => {
        image.setAttribute("remote", remote)
    });
    return doc
}

// The root element, for the Svelte display path (Knowl.svelte walks an Element).
// XSLT callers want outcomeToStxDocument instead -- see the note above.
export const outcomeToStx = (o:Outcome,seed:number) =>
    outcomeToStxDocument(o,seed).documentElement

export const outcomeToLatex = (o:Outcome,seed:number) => {
    const e = outcomeToStxDocument(o,seed)
    const transform = new XSLTProcessor()
    const xslDom = parser.parseFromString(latexXsl, "application/xml")
    transform.importStylesheet(xslDom)
    return transform.transformToDocument(e).querySelector(":scope").textContent.trim()
}

export const outcomeToHtml = (
    o:Outcome,seed:number,
    mathMode:'default'|'canvas'|'brightspace'='default',
    solutions:'show'|'hide'|'only'='show'
) => {
    const e = outcomeToStxDocument(o,seed)
    const transform = new XSLTProcessor()
    const xslDom = parser.parseFromString(htmlXsl, "application/xml")
    transform.importStylesheet(xslDom)
    const doc = transform.transformToDocument(e)
    // `div[class~="stx"]` rather than `div.stx`: a plain attribute selector with
    // the same semantics, but not subject to how a given engine treats `class`
    // in a non-HTML document. Firefox returned null from the class-selector form
    // here, so `.outerHTML` threw "can't access property outerHTML, l is null"
    // and every caller of outcomeToHtml() died with it -- including the "Copy for
    // AI Chatbot" button, which looked like a clipboard bug for several rounds.
    //
    // Note documentElement is NOT usable instead: Chrome honors
    // <xsl:output method="html"/> and returns an HTML document, so its root is
    // <html> and using it drags a <html><body> wrapper into the output.
    //
    // If this still throws, the message reports what the transform actually
    // produced, since the alternative explanation is that it yielded nothing at
    // all -- and that is the fact needed to tell the two cases apart.
    let ele = doc.querySelector('div[class~="stx"]')
    if (!ele) {
        const root = doc.documentElement
        throw new Error(
            "html.xsl transform produced no div.stx wrapper. " +
            `Root element: ${root ? root.nodeName : "(none)"}. ` +
            `Output began: ${
                root ? new XMLSerializer().serializeToString(root).slice(0,200) : "(empty document)"
            }`
        )
    }
    // Class selectors below are written as [class~="..."] for the same reason:
    // ".foo" only matches in HTML documents, so in Firefox these silently
    // matched nothing -- meaning LMS math conversion and solution filtering did
    // nothing at all rather than failing loudly. [class~="foo"] is a plain
    // attribute selector with identical semantics that works in both.
    if (mathMode == 'canvas' || mathMode == 'brightspace') {
        ele.querySelectorAll('[class~="math"][data-latex]').forEach((math)=>{
            katex.render(
                math.getAttribute("data-latex"),
                math,
                {
                    output: 'mathml',
                    displayMode: math.classList.contains("display-math")
                }
            )
        })
    }
    if (solutions=="hide") {
        ele.querySelectorAll('[class~="stx-outtro"]').forEach((outtro)=>{
            outtro.parentElement.removeChild(outtro)
        })
    }
    if (solutions=="only") {
        ele.querySelectorAll('[class~="stx-intro"]').forEach((intro)=>{
            intro.parentElement.removeChild(intro)
        })
        ele.querySelectorAll('[class~="stx-content"]').forEach((content)=>{
            content.parentElement.removeChild(content)
        })
    }
    return ele.outerHTML.trim()
}

export const outcomeToPtx = (o:Outcome,seed:number) => {
    const e = outcomeToStxDocument(o,seed)
    const transform = new XSLTProcessor()
    const xslDom = parser.parseFromString(ptxXsl, "application/xml")
    transform.importStylesheet(xslDom)
    return transform.transformToDocument(e).querySelector(':scope').outerHTML.trim()
}

// Used when neither the outcome nor the bank supplies an <ai-prompt>. Kept
// deliberately thin: the bank author owns the pedagogy, so the platform default
// should orient the chatbot without prescribing how it ought to help.
const DEFAULT_AI_PROMPT =
    "The following is a practice exercise, together with its answer. " +
    "Help me understand how to arrive at that answer."

/**
 * Builds the payload for the "Copy for AI Chatbot" button: a prompt header
 * chosen by the bank author, some identifying context, then the exercise
 * rendered as HTML *including* its answer.
 *
 * HTML rather than LaTeX on purpose. outcomeToHtml() runs through outcomeToStx,
 * which stamps @remote with the page's absolute origin+path, so every <img src>
 * comes out as a fully-qualified public URL that a chatbot can fetch to see the
 * figure. The LaTeX output instead emits bank-relative \includegraphics /
 * \input paths, which are meaningless to anything off this machine. HTML also
 * leaves math as raw \( \) LaTeX rather than rendered KaTeX spans.
 *
 * Note the absolute URLs only resolve when the bank is *published* -- from a
 * local preview they point at localhost, which no remote model can reach.
 */
export const outcomeToAiText = (bank:Bank, outcome:Outcome, seed:number) => {
    const prompt = outcome.ai_prompt || bank.ai_prompt || DEFAULT_AI_PROMPT
    const base = `${location.protocol}//${location.host}${location.pathname}`
    return [
        prompt,
        "",
        "---",
        "",
        `Exercise: ${outcome.slug} — ${outcome.title}`,
        `Learning outcome: ${(outcome.description||"").trim()}`,
        `Version: ${seed+1}`,
        `Source: ${base}#/bank/${outcome.slug}/${seed+1}/`,
        "",
        "The exercise and its answer follow as HTML.",
        "- Math is LaTeX, delimited by \\( \\) inline or \\[ \\] for display.",
        "- Each <img> src is a public URL you may fetch to view the figure.",
        "",
        outcomeToHtml(outcome,seed),
    ].join("\n")
}

export const toggleCodeCell = () => {codeCellIsOpen.update(x=>!x)}

export const getOutcomeFromSlug = (bank:Bank,slug:string) =>
    bank.outcomes.find((o)=>o.slug===slug)

export const sample = (a:Array<any>) => a[Math.floor(Math.random()*a.length)]

export const decodeXmlString = (s:string) => {
    return s.replace(/&apos;/g, "'")
            .replace(/&quot;/g, '"')
            .replace(/&gt;/g, '>')
            .replace(/&lt;/g, '<')
            .replace(/&amp;/g, '&');
}

export const parseMath = (html:string) => {
    let inlineMathRe = /\\\((.*?)\\\)/gs;
    let displayMathRe = /\\\[(.*?)\\\]/gs;
    return html.replace(
        inlineMathRe,
        (_, tex:string) => katex.renderToString(decodeXmlString(tex), {
            'displayMode': false,
            'throwOnError': false,
        })
    ).replace(
        displayMathRe,
        (_, tex:string) => katex.renderToString(decodeXmlString(tex), {
            'displayMode': true,
            'throwOnError': false,
        })
    );
}

export const getRandomAssessmentFromSlugs = (bank:Bank,slugs:string[],template:string=assessmentTemplate) => {
    let assessment: Assessment = {
        "latex": "",
        "exercises": [],
    }
    slugs.forEach( (slug) => {
        let o = getOutcomeFromSlug(bank,slug)
        if (o) {
            // pull random seed besides first public 20
            let seed = Math.floor(Math.random() * (o.exercises.length-20))+20;
            assessment.latex = assessment.latex + "\n\n" + outcomeToLatex(o,seed)
            assessment.latex = assessment.latex + "\n\n\\newpage\n\n"
            assessment.exercises = [...assessment.exercises, {outcome:o,seed:seed}]
        }
    })
    assessment.latex = Mustache.render(
        template,
        {
            "version": Date.now(),
            "exercises": assessment.exercises.map((e)=>{
                return {"latex": outcomeToLatex(e.outcome,e.seed)}
            })
        }
    )
    return assessment
}
