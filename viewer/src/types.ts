export type Bank = {
    title: string;
    url: string;
    slug: string;
    // Optional: banks generated before <ai-prompt> existed simply lack the key,
    // so every consumer must tolerate undefined as well as null.
    ai_prompt?: string | null;
    generated_on: string;
    // Which CheckIt built this bank. Absent on anything generated before the
    // footer stopped carrying the number as literal text, so the footer falls
    // back to naming no version rather than showing "undefined".
    checkit_version?: string;
    outcomes: Array<Outcome>;
    // Absent on any bank generated before the viewer stopped transforming
    // SpaTeXt itself. Absent means "not precomputed at all", which is a
    // different thing from "precomputed but missing this seed" -- the viewer
    // reports them differently, because the fixes differ.
    precomputed?: Precomputed;
    // LaTeX support files this bank publishes, theme first. Absent on banks
    // generated before the feature; an empty array means the bank genuinely
    // ships none, and the assessment builder falls back to its generic
    // template. The two cases behave the same here, but only one is a bank
    // that could be rebuilt to gain a theme.
    latex_support?: LatexSupport[];
}
/** What the emitter says it wrote. Declared so a consumer can ask rather than
 *  infer a gap from finding nothing. See checkit/__init__.py. */
export type Precomputed = {
    inline_formats: string[];
    inline_below: number;
    bundle_formats: string[];
    bundle_from: number;
    bundle_path: string;
}
/** One outcome's non-public seeds, fetched on demand. */
export type DerivedBundle = {
    slug: string;
    first_seed: number;
    formats: string[];
    seeds: Record<string, Record<string, string>>;
}
export type Outcome = {
    title: string;
    slug: string;
    description: string;
    // null/undefined means "inherit the bank's ai_prompt"
    ai_prompt?: string | null;
    template: string;
    exercises: Array<Exercise>;
    // xcolor name for this skill's box in a themed LaTeX export, resolved by
    // the platform from bank.xml's <color_map>. Absent means the theme's
    // default -- which is also every bank that declares no map.
    color?: string;
}
export type Exercise = {
    seed: number;
    data: Object;
    // Present only for seeds below Precomputed.inline_below.
    html?: string;
    latex?: string;
    pretext?: string;
}
export type Params = {
    outcomeSlug: string;
    exerciseVersion: string;
}
type AssessmentExercise = {
    outcome: Outcome
    seed: number
}
export type Assessment = {
    exercises: AssessmentExercise[]
    /** One self-contained file: the theme inlined, nothing to fetch. What the
     *  copy button and the source preview carry. */
    latex: string
    /** The same document as a real project, for services that accept several
     *  files. `main.tex` loads the support files by name instead of inlining
     *  them, so what Overleaf opens looks like what printit writes to disk. */
    files: AssessmentFile[]
}
export type AssessmentFile = {
    name: string
    content: string
}
/** A LaTeX support file the bank publishes, in the order it must be loaded.
 *  See LATEX_SUPPORT in checkit/__init__.py. Absent on banks generated before
 *  the feature, which is why every consumer treats it as optional. */
export type LatexSupport = {
    filename: string
    role: string
    path: string
}
