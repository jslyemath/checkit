export type Bank = {
    title: string;
    url: string;
    slug: string;
    // Optional: banks generated before <ai-prompt> existed simply lack the key,
    // so every consumer must tolerate undefined as well as null.
    ai_prompt?: string | null;
    generated_on: string;
    outcomes: Array<Outcome>;
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
