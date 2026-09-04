import type {Bank, Assessment, AssessmentFile, Outcome, Precomputed,
    DerivedBundle, LatexSupport} from '../types';

import {get} from 'svelte/store';
import {bank as bankStore} from '../stores/banks';
import {isOpen as codeCellIsOpen} from '../stores/codecell';

import katex from 'katex';

import Mustache from 'mustache';
// @ts-ignore
import assessmentTemplate from '../templates/assessmentTemplate.tex?raw'
// @ts-ignore
import themedAssessmentTemplate from '../templates/themedAssessmentTemplate.tex?raw'

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

/**
 * One past the last seed precomputed for the browser.
 *
 * Seeds from here up exist in the bank's seeds.json for the print tool, but
 * nothing is precomputed for them and nothing is published, so no instructor
 * feature may ask for one.
 *
 * DUPLICATED IN PYTHON as BUNDLE_UNTIL in checkit/__init__.py, for the same
 * reason as PUBLIC_SEEDS; dashboard/tests/test_subset.py asserts they match.
 */
export const BUNDLE_UNTIL = 400

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
 * Every exercise's LaTeX ships with a preamble defining \stxKnowl, \stxTitle
 * and \stxOuttro -- so a single exercise can be copied and pasted into any
 * document and still compile. latex.xsl writes it, ending with this line.
 *
 * A whole document wants those definitions once, at the top, where a theme can
 * override them. Pasting them per exercise also silently forces
 * \renewcommand{\stxOuttro}[1]{} on every one, which throws every answer away
 * -- so an answer key is impossible until they are hoisted out.
 *
 * checkit-printit strips exactly this marker for exactly this reason; see
 * _SPATEXT_PREAMBLE_END in assemble.py. Keep the two in step.
 */
const SPATEXT_PREAMBLE_END = "%".repeat(28)

export const stripSpatextPreamble = (latex:string):string => {
    const at = latex.indexOf(SPATEXT_PREAMBLE_END)
    if (at < 0) return latex.trim()
    return latex.slice(at + SPATEXT_PREAMBLE_END.length).trim()
}

/** The bank's support files, in load order. Empty for a bank that ships none,
 *  and for any bank generated before they were published. */
export const latexSupport = (bank:Bank):LatexSupport[] => bank.latex_support ?? []

export const bankHasTheme = (bank:Bank):boolean =>
    latexSupport(bank).some((e)=>e.role=="theme")

const loadedSupport:Record<string,string> = {}

/**
 * Fetch the support files' contents, so an assessment can inline them.
 *
 * Separate from bank.json on purpose: every visitor downloads that, and a
 * theme only matters to an instructor who opens this tab.
 */
export const ensureLatexSupport = async (bank:Bank):Promise<void> => {
    await Promise.all(latexSupport(bank).map(async (entry)=>{
        if (loadedSupport[entry.filename] !== undefined) return
        const url = `${siteBase()}/${entry.path}`
        const response = await fetch(url)
        if (!response.ok) {
            throw new Error(
                `Could not fetch ${entry.filename}: HTTP ${response.status} ` +
                `from ${url}. bank.json lists it under latex_support, so the ` +
                `bank was published without the file itself.`
            )
        }
        loadedSupport[entry.filename] = await response.text()
    }))
}

/**
 * The file a theme expects its skill names and descriptions to arrive in.
 *
 * A theme defines \setskilldesc and then \input's this, so the descriptions
 * land after the command exists and before \skillheader needs them. printit
 * writes the same file beside main.tex; keeping the name identical means a
 * theme works unmodified in both.
 */
export const DESCRIPTIONS_FILENAME = "Skill Descriptions.tex"

const DESCRIPTIONS_INPUT = /^[ \t]*\\input\{Skill Descriptions\.tex\}[ \t]*$/m

/**
 * The support files as one preamble block.
 *
 * A .sty is read with @ counting as a letter, which is how packages keep
 * internal names like \@acadclass private. Pasted into a document preamble
 * that is no longer true, so the whole block goes between \makeatletter and
 * \makeatother.
 *
 * Two edits are made to the source, and only these two:
 *   - \ProvidesPackage is dropped; it means nothing outside a real package
 *     file and warns when the name does not match.
 *   - the \input of the descriptions file becomes the descriptions
 *     themselves, since a standalone file has nothing to read from disk. A
 *     theme without that line gets them appended instead, so a theme that
 *     does not follow the convention still ends up with its descriptions.
 */
const inlinedSupport = (bank:Bank, descriptions:string):string => {
    let placed = false
    const parts = latexSupport(bank).map((entry)=>{
        let source = (loadedSupport[entry.filename] ?? "")
            .replace(/^\s*\\ProvidesPackage\{[^}]*\}.*$/m, "")
        if (DESCRIPTIONS_INPUT.test(source)) {
            source = source.replace(DESCRIPTIONS_INPUT,
                `% ---- ${DESCRIPTIONS_FILENAME}, inlined\n${descriptions}`)
            placed = true
        }
        return `% ---- ${entry.filename}, inlined\n${source.trim()}`
    })
    if (!parts.length) return ""
    const block = parts.join("\n\n") + (placed ? "" : `\n\n${descriptions}`)
    return `\\makeatletter\n${block}\n\\makeatother`
}

/** The same support files as \usepackage lines, for a multi-file project. */
const loadedSupportPackages = (bank:Bank):string =>
    latexSupport(bank)
        .map((e)=>`\\usepackage{${e.filename.replace(/\.sty$/, "")}}`)
        .join("\n")

/**
 * \setskilldesc for every skill on the assessment, from the bank manifest.
 *
 * The theme's \skillheader looks a slug up here for its title and colour;
 * without these lines every box prints the theme's default. printit generates
 * the same file from the same manifest -- see descriptions_tex in assemble.py.
 */
const skillDescriptions = (outcomes:Outcome[]):string =>
    outcomes.map((o)=>{
        const description = (o.description ?? "").split(/\s+/).join(" ").trim()
        // The optional argument is the box colour, resolved by the platform
        // from <color_map>. Omitting it leaves every skill in the theme's
        // default, which is not what a bank declaring a colour map is asking
        // for -- printit hit the same thing.
        const prefix = o.color ? `\\setskilldesc[${o.color}]` : "\\setskilldesc"
        return `${prefix}{${o.slug}}{${description}}`
    }).join("\n")

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

// Upstream split outcomeToHtml in two so the MCQ export could reach the
// unfiltered element. Same split here, over precomputed HTML rather than a
// browser-side XSLT transform.
const stxToHtmlElement = (
    o:Outcome,seed:number,
    mathMode:'default'|'canvas'|'brightspace'='default'
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
    return ele
}

export const outcomeToHtml = (
    o:Outcome,seed:number,
    mathMode:'default'|'canvas'|'brightspace'='default',
    solutions:'show'|'hide'|'only'='show'
) => {
    let ele = stxToHtmlElement(o,seed,mathMode)
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
        // A distractor is a wrong answer. It belongs in the choices, never in
        // the "answer only" view an LMS import uses as the correct response.
        ele.querySelectorAll('[class~="stx-outtro"][data-distractor="true"]').forEach((outtro)=>{
            outtro.parentElement.removeChild(outtro)
        })
    }
    return ele.outerHTML.trim()
}

/**
 * The MCQ choices for one exercise, for the LMS export.
 *
 * A distractor is an extra <outtro> carrying @distractor, which html.xsl turns
 * into data-distractor. Read off the unfiltered element, because outcomeToHtml
 * strips distractors for the "answer only" view.
 */
export const outcomeToMcqChoices = (
    o:Outcome,seed:number,
    mathMode:'default'|'canvas'|'brightspace'='default'
) => {
    const ele = stxToHtmlElement(o,seed,mathMode)
    return Array.from(ele.querySelectorAll('[class~="stx-outtro"]')).map((outtro, i) => {
        return {
            "ident": `choice${i}`,
            "html": outtro.innerHTML.trim(),
            "correct": outtro.getAttribute('data-distractor') !== 'true'
        }
    })
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

/** The template a bank gets by default: themed when it publishes one. */
export const defaultTemplateFor = (bank:Bank):string =>
    bankHasTheme(bank) ? themedAssessmentTemplate : assessmentTemplate

/** Pick one random version of each outcome. Separate from rendering, so the
 *  same assessment can be re-rendered -- with an answer key, say -- without
 *  quietly drawing a different set of exercises underneath the instructor. */
export const pickAssessmentExercises = (bank:Bank, slugs:string[]) => {
    const chosen: {outcome:Outcome, seed:number}[] = []
    slugs.forEach( (slug) => {
        let o = getOutcomeFromSlug(bank,slug)
        if (o) {
            // A seed above the publicly visible ones, but still inside the
            // range that was precomputed -- past BUNDLE_UNTIL nothing is
            // published for the browser to read.
            const top = Math.min(o.exercises.length, BUNDLE_UNTIL)
            let seed = Math.floor(
                Math.random() * (top-PUBLIC_SEEDS)
            )+PUBLIC_SEEDS;
            chosen.push({outcome:o, seed:seed})
        }
    })
    return chosen
}

export const renderAssessment = (
    bank:Bank,
    chosen:{outcome:Outcome, seed:number}[],
    template:string=defaultTemplateFor(bank),
    answerKey:boolean=false,
) => {
    const themed = bankHasTheme(bank)
    // A themed document defines the SpaTeXt commands once in its preamble, so
    // each exercise arrives without its own copy. The generic template has no
    // preamble of its own and relies on them travelling with the exercise.
    const body = (e:{outcome:Outcome,seed:number}) => {
        const latex = outcomeToLatex(e.outcome, e.seed)
        return themed ? stripSpatextPreamble(latex) : latex
    }
    const descriptions = skillDescriptions(chosen.map((e)=>e.outcome))
    const context = {
        "version": Date.now(),
        "bankTitle": bank.title,
        "answerKey": answerKey,
        "exercises": chosen.map((e)=>({
            "latex": body(e),
            // Prebuilt, because a Mustache field cannot sit directly inside a
            // LaTeX brace: \skillheader{{{slug}}} renders as \skillheader}.
            // The two lines arrive assembled so the template never has to.
            "header": `\\setvseed{${e.seed}}\n\\skillheader{${e.outcome.slug}}`,
            "slug": e.outcome.slug,
            "seed": e.seed,
            "title": e.outcome.title,
        })),
    }

    const render = (theme:string) =>
        Mustache.render(template, {...context, "theme": theme})

    // Two shapes of the same document. The copy button and the preview carry
    // the standalone one, because a clipboard holds one thing; Overleaf gets
    // the project, because it can hold several and a real .sty reads better
    // than 600 lines pasted into a preamble.
    const assessment: Assessment = {
        "exercises": chosen,
        "latex": render(inlinedSupport(bank, descriptions)),
        "files": [{"name": "main.tex", "content": render(loadedSupportPackages(bank))}],
    }
    latexSupport(bank).forEach((entry)=>{
        assessment.files.push({
            "name": entry.filename,
            "content": loadedSupport[entry.filename] ?? "",
        })
    })
    if (themed) {
        // The theme reads this from disk. Shipped as its own file so the .sty
        // travels unmodified -- the multi-file project is then exactly the
        // file set printit writes.
        assessment.files.push({
            "name": DESCRIPTIONS_FILENAME,
            "content": `% Generated from the bank. Do not edit -- edit the bank.\n${descriptions}\n`,
        })
    }
    return assessment
}

/** Pick and render in one step, which is what "Generate" does. */
export const getRandomAssessmentFromSlugs = (
    bank:Bank,
    slugs:string[],
    template:string=defaultTemplateFor(bank),
    answerKey:boolean=false,
) => renderAssessment(bank, pickAssessmentExercises(bank,slugs), template, answerKey)
