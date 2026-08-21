import type {Bank, Assessment, Outcome, Precomputed, DerivedBundle} from '../types';

import {get} from 'svelte/store';
import {bank as bankStore} from '../stores/banks';
import {isOpen as codeCellIsOpen} from '../stores/codecell';

import katex from 'katex';

import Mustache from 'mustache';
// @ts-ignore
import assessmentTemplate from '../templates/assessmentTemplate.tex?raw'

/**
 * How many exercise versions the viewer exposes to students.
 *
 * Used for the version picker, its prev/next clamp, and as the floor for
 * assessment seeds -- printed assessments draw from seeds at or above this, so
 * a student cannot look up the printed version in the viewer.
 *
 * THIS VALUE IS DUPLICATED IN PYTHON as PUBLIC_SEEDS in checkit/__init__.py,
 * because the browser cannot import from it. The two must match;
 * dashboard/tests/test_subset.py asserts that they do.
 */
export const PUBLIC_SEEDS = 50

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

/**
 * The site's own address, without a trailing slash.
 *
 * The same expression @remote is built from at generate time, so a bundle URL
 * and an <img src> resolve against the same base.
 */
const siteBase = () =>
    `${location.protocol}//${location.host}${location.pathname.replace(/\/+$/, "")}`

/**
 * What the bank says it precomputed, or a message explaining how to fix it.
 *
 * Browsers removed XSLT, so the viewer can no longer build these formats for
 * itself. A bank generated before that change simply has no `precomputed` key,
 * and there is nothing this code can do about it -- so it says which command to
 * run rather than failing in a way that looks like a viewer bug.
 */
const precomputedOrThrow = ():Precomputed => {
    const b = get(bankStore)
    if (!b || !b.precomputed) {
        throw new Error(
            "This bank has no precomputed exercise formats, so the instructor " +
            "views cannot be rendered. Browsers have removed XSLT, which the " +
            "viewer previously used to build HTML, LaTeX and PreTeXt in the " +
            "page. Regenerate the bank with a current CheckIt and republish it:" +
            "\n\n    python -m checkit generate -r --remote <the site's URL>\n"
        )
    }
    return b.precomputed
}

// One entry per outcome, fetched at most once. Keyed by slug because that is
// what bundle_path is parameterised by.
const loadedBundles:Record<string,DerivedBundle> = {}
const inflightBundles:Record<string,Promise<void>> = {}

/**
 * Fetch one outcome's non-public seeds, if they are not already in hand.
 *
 * Callers that touch seeds at or above `inline_below` -- the assessment builder
 * and the LMS export -- must await this first. Everything a student sees, and
 * every instructor tab, uses the inlined public seeds and needs no fetch.
 */
export const ensureDerived = (outcome:Outcome):Promise<void> => {
    if (loadedBundles[outcome.slug]) return Promise.resolve()
    if (!inflightBundles[outcome.slug]) {
        const pre = precomputedOrThrow()
        const url = `${siteBase()}/${pre.bundle_path.replace("{slug}", outcome.slug)}`
        inflightBundles[outcome.slug] = fetch(url).then(async (response) => {
            if (!response.ok) {
                delete inflightBundles[outcome.slug]
                throw new Error(
                    `Could not fetch precomputed exercises for ${outcome.slug}: ` +
                    `HTTP ${response.status} from ${url}. The bank may have been ` +
                    `published without its assets/<slug>/generated/ files.`
                )
            }
            loadedBundles[outcome.slug] = await response.json()
        })
    }
    return inflightBundles[outcome.slug]
}

export const ensureDerivedForSlugs = (bank:Bank, slugs:string[]):Promise<void[]> =>
    Promise.all(slugs.map((s)=>{
        const o = getOutcomeFromSlug(bank,s)
        return o ? ensureDerived(o) : Promise.resolve()
    }))

/**
 * One precomputed format for one exercise.
 *
 * Every failure here is loud and specific, because the alternative -- returning
 * undefined and letting Mustache render the word "undefined" into a LaTeX file
 * -- is exactly the silent hole that capping --image-seeds once produced.
 */
const derived = (outcome:Outcome, seed:number, format:string):string => {
    const pre = precomputedOrThrow()
    const inline = seed < pre.inline_below

    const available = inline ? pre.inline_formats : pre.bundle_formats
    if (available.indexOf(format) < 0) {
        throw new Error(
            `${format} was not precomputed for ${outcome.slug} seed ${seed}. ` +
            `The bank declares [${pre.inline_formats.join(", ")}] below seed ` +
            `${pre.inline_below} and [${pre.bundle_formats.join(", ")}] from ` +
            `seed ${pre.bundle_from} up.`
        )
    }

    let value:string|undefined
    if (inline) {
        const exercise = outcome.exercises[seed]
        value = exercise ? exercise[format] : undefined
    } else {
        const bundle = loadedBundles[outcome.slug]
        if (!bundle) {
            throw new Error(
                `Precomputed exercises for ${outcome.slug} have not been ` +
                `fetched. Await ensureDerived(outcome) before rendering seed ` +
                `${seed}, which is outside the inlined range.`
            )
        }
        const entry = bundle.seeds[String(seed)]
        value = entry ? entry[format] : undefined
    }

    if (typeof value !== "string") {
        throw new Error(
            `${outcome.slug} seed ${seed} has no precomputed ${format}, though ` +
            `the bank declares it should. Regenerate and republish the bank.`
        )
    }
    return value
}

export const outcomeToLatex = (o:Outcome,seed:number) => derived(o,seed,"latex").trim()

export const outcomeToPtx = (o:Outcome,seed:number) => derived(o,seed,"pretext").trim()

export const outcomeToHtml = (
    o:Outcome,seed:number,
    mathMode:'default'|'canvas'|'brightspace'='default',
    solutions:'show'|'hide'|'only'='show'
) => {
    // The base rendering only: subset='all', consumer='basic'. The filtering
    // and MathML below are plain DOM work and KaTeX, neither of which the XSLT
    // removal touches, so they stay here rather than multiplying the payload
    // by emitting every subset x consumer combination.
    const doc = parser.parseFromString(derived(o,seed,"html"), "text/html")
    let ele = doc.querySelector('div[class~="stx"]')
    if (!ele) {
        throw new Error(
            `Precomputed HTML for ${o.slug} seed ${seed} has no div.stx ` +
            `wrapper. It began: ${derived(o,seed,"html").slice(0,200)}`
        )
    }
    // Class selectors below are written as [class~="..."] for a historical
    // reason worth keeping: when this HTML came from XSLTProcessor it lived in
    // a non-HTML document, where ".foo" silently matched nothing in Firefox --
    // so LMS math conversion and solution filtering did nothing at all rather
    // than failing loudly. Parsing as "text/html" above makes ".foo" safe again,
    // but the attribute form has identical semantics and costs nothing.
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
            // pull a random seed from above the publicly visible ones
            let seed = Math.floor(
                Math.random() * (o.exercises.length-PUBLIC_SEEDS)
            )+PUBLIC_SEEDS;
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
