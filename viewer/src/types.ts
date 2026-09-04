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
    latex: string
}
