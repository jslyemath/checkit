import { writable } from 'svelte/store';

/**
 * Which answers are currently revealed.
 *
 * Each entry is "<slug>/<seed>/<path>", where path is the task's numbering
 * within the exercise -- "" for the exercise itself, "3" for its third task,
 * "3.2" for that task's second subtask.
 *
 * Keying on the seed is what makes peeking at one version's answer stop
 * following you to the next: version 2's task 3 is a different key from version
 * 1's, so it starts hidden. Going back to version 1 finds its entries still
 * there and reopens exactly what was open before.
 *
 * The whole set is dropped when the skill changes, since carrying W1's reveals
 * into N3 is meaningless and the memory would only grow.
 */
export const openAnswers = writable(new Set<string>());

/**
 * The exercise on screen, set by Exercise.svelte. Knowl reads it to build its
 * key, which saves threading the slug and seed down through every layer of
 * content and node components between them.
 */
export const currentExercise = writable({ slug: '', seed: 0 });

let lastSlug: string | null = null;
currentExercise.subscribe(({ slug }) => {
    if (slug !== lastSlug) {
        lastSlug = slug;
        openAnswers.set(new Set());
    }
});

/** Reveal or hide one answer. */
export const toggleAnswer = (key: string) => {
    openAnswers.update((open) => {
        const next = new Set(open);
        if (next.has(key)) {
            next.delete(key);
        } else {
            next.add(key);
        }
        return next;
    });
};
