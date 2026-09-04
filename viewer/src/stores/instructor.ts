import { writable } from 'svelte/store';
// @ts-ignore
import defaultAssessmentTemplateRaw from '../templates/assessmentTemplate.tex?raw'

export const defaultAssessmentTemplate = defaultAssessmentTemplateRaw;

let _ie = false;
if (localStorage.getItem(location.pathname+'#instructorEnabled')) {
    try {
        let _ietry = JSON.parse(localStorage.getItem(location.pathname+'#instructorEnabled'));
        if (typeof _ietry == 'boolean') { _ie = _ietry }
    } catch {}
}
export const instructorEnabled = writable(_ie);
instructorEnabled.subscribe(value => {
    localStorage.setItem(location.pathname+"#instructorEnabled", JSON.stringify(value));
});

let _ao: Array<string> = [];
if (localStorage.getItem(location.pathname+'#assessmentOutcomeSlugs')) {
    try {
        let _aotry = JSON.parse(localStorage.getItem(location.pathname+'#assessmentOutcomeSlugs'));
        if (Array.isArray(_aotry)) { _ao = _aotry }
    } catch {}
}
export const assessmentOutcomeSlugs = writable(_ao);
assessmentOutcomeSlugs.subscribe(value => {
    localStorage.setItem(location.pathname+"#assessmentOutcomeSlugs", JSON.stringify(value));
});

/**
 * The instructor's own template, or null for "whatever this bank's default is".
 *
 * It has to be null rather than a copy of the default, because the default now
 * depends on the bank: a bank publishing a theme gets a themed template. If an
 * unedited template were stored as text, everyone who had ever opened this tab
 * would be pinned forever to the generic one they happened to see first, and
 * the themed default would only ever reach new visitors.
 *
 * A stored value equal to the generic template is treated as unedited, for the
 * same reason -- that is exactly what a previous visit wrote.
 */
let _at: string|null = null;
if (localStorage.getItem(location.pathname+'#assessmentTemplate')) {
    try {
        let _attry = JSON.parse(localStorage.getItem(location.pathname+'#assessmentTemplate'));
        if (typeof _attry == 'string' && _attry !== defaultAssessmentTemplate) {
            _at = _attry
        }
    } catch {}
}
export const assessmentTemplate = writable(_at);
assessmentTemplate.subscribe(value => {
    localStorage.setItem(location.pathname+"#assessmentTemplate", JSON.stringify(value));
});
