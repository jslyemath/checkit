<script lang="ts">
    import Exercise from '../components/Exercise.svelte';
    import type { Params } from '../types';
    import { Button, Row, Col } from 'sveltestrap';
    import { bank } from '../stores/banks';
    import { instructorEnabled, assessmentOutcomeSlugs } from '../stores/instructor';
    import Bank from './Bank.svelte';
    import { push, querystring } from 'svelte-spa-router';
    import { toggleCodeCell, outcomeToAiText, PUBLIC_SEEDS } from '../utils';

    export let params:Params;

    const versionStringToInt = (vs:string) => parseInt(vs)-1

    $: outcome = $bank.outcomes.find((o)=>o.slug==params.outcomeSlug);
    $: version = versionStringToInt(params.exerciseVersion);
    let seed = versionStringToInt(params.exerciseVersion);
    let outcomeSlug = params.outcomeSlug;
    $: if (outcomeSlug !== params.outcomeSlug) {
        seed = version;
        outcomeSlug = params.outcomeSlug;
    }
    $: if (seed !== version) {
        push(`/bank/${params.outcomeSlug}/${seed+1}/${$querystring ? "?"+$querystring : ""}`);
    }
    $: countInAssessment = $assessmentOutcomeSlugs.filter(slug=>slug==outcome.slug).length
    const addToAssessment = () => {
        $assessmentOutcomeSlugs = [...$assessmentOutcomeSlugs, outcome.slug]
    }
    const removeFromAssessment = () => {
        let i = $assessmentOutcomeSlugs
            .map(slug=>slug==outcome.slug)
            .lastIndexOf(true)
        $assessmentOutcomeSlugs = [
            ...$assessmentOutcomeSlugs.slice(0, i),
            ...$assessmentOutcomeSlugs.slice(i + 1)
        ]
    }

    const changeSeed = (diff:number) => {
        seed = Math.max(0,Math.min(PUBLIC_SEEDS-1,seed+diff))
    }

    // 'failed' is a real state, not an error case to hide: browsers can and do
    // refuse clipboard writes (NotAllowedError) even on a secure origin inside a
    // click handler, depending on permission settings. When that happens we show
    // the student the text so they can copy it by hand -- the one thing this
    // button must never do is appear to work while doing nothing.
    let copyState:'idle'|'copied'|'failed' = 'idle'
    let manualText = ''
    let copyTimer:ReturnType<typeof setTimeout>

    // Focus and select the fallback textarea as soon as it appears, so the
    // student only has to press Ctrl/Cmd+C.
    const selectAll = (node:HTMLTextAreaElement) => {
        node.focus()
        node.select()
    }

    const copyForAi = () => {
        const text = outcomeToAiText($bank,outcome,seed)
        clearTimeout(copyTimer)

        // Show the confirmation immediately rather than awaiting writeText().
        // Firefox performs the copy but does not settle the promise the way
        // Chrome does, so `await`ing it here meant the copy succeeded while
        // copyState was never assigned and no confirmation ever appeared.
        // Nothing is claimed permanently: a genuine rejection downgrades to the
        // textarea below, which is the case that actually matters.
        manualText = ''
        copyState = 'copied'
        copyTimer = setTimeout(()=>copyState='idle',2000)

        navigator.clipboard.writeText(text).catch(() => {
            // Real refusal (NotAllowedError): retract the confirmation and show
            // the text so the student can copy it by hand.
            //
            // document.execCommand('copy') was tried as a fallback here and
            // deliberately removed: on a browser that denies clipboard writes it
            // still returns true AND fires a copy event carrying clipboardData
            // while writing nothing, so its success is indistinguishable from
            // its failure.
            clearTimeout(copyTimer)
            manualText = text
            copyState = 'failed'
        })
    }

    // Which exercise the current copy state belongs to, so the reset below can
    // distinguish "the student navigated" from "this statement merely re-ran".
    let copyStateExercise = ''

    const resetCopyStateIfMoved = (exercise:string) => {
        if (exercise === copyStateExercise) return
        copyStateExercise = exercise
        clearTimeout(copyTimer)
        copyState = 'idle'
        manualText = ''
    }

    // Routing here is hash-based, so moving to another outcome or version never
    // reloads the page. Without this reset, a "Copied!"/"Copy blocked" state --
    // and the previous exercise's text sitting in the textarea -- would follow
    // the student onto the next exercise.
    //
    // Two things stop this from eating its own confirmation, both learned the
    // hard way:
    //   1. The body stays in a function. Inlined, `clearTimeout(copyTimer)`
    //      reads copyTimer, making it a dependency here -- so copyForAi's
    //      `copyTimer = setTimeout(...)` re-triggered this and reset copyState
    //      in the same flush that set it to 'copied'.
    //   2. The reset is idempotent, keyed on the exercise actually displayed.
    //      `params` is a prop object whose identity the router may renew on any
    //      re-render, and how often that happens varies by browser, so an
    //      unconditional reset here cannot be relied on.
    $: resetCopyStateIfMoved(`${params.outcomeSlug}/${seed}`)
</script>

<Bank {params}>
    
    {#if $querystring=="embed"}<h5>{outcomeSlug} — {outcome.title}</h5>{/if}
    <p>
        {outcome.description}
    </p>
    
    <Row>
        <Col xs="auto">
            <div class="input-group mb-3">
                <label class="input-group-text" for="versionSelect">Version</label>
                <button class="btn btn-dark" on:click={()=>changeSeed(-1)}>&laquo;</button>
                <select class="form-select" label="versionSelect" bind:value={seed}>
                    {#each Array(PUBLIC_SEEDS) as _, i}
                        <option value={i}>
                            {i+1}
                        </option>
                    {/each}
                </select>
                <button class="btn btn-dark" on:click={()=>changeSeed(+1)}>&raquo;</button>
            </div>
        </Col>
        <Col xs="auto">
            <p>
                <Button color="secondary" outline on:click={toggleCodeCell}>
                    Show/Hide Code Cell
                </Button>
            </p>
        </Col>
        <Col xs="auto">
            <p>
                <Button color="secondary" outline on:click={copyForAi}>
                    {#if copyState=="copied"}
                        Copied!
                    {:else if copyState=="failed"}
                        Copy blocked — see below
                    {:else}
                        Copy for AI Chatbot
                    {/if}
                </Button>
            </p>
        </Col>
        {#if $instructorEnabled }
            <Col xs="auto">
                <p>
                    <span># Included in Assessment:</span>
                    <span class="btn-group ml-2" role="group">
                        <Button
                            color="success" 
                            disabled={countInAssessment<1} 
                            on:click={removeFromAssessment}>
                            -
                        </Button>
                        <Button
                            color="success"
                            outline>
                            {countInAssessment}
                        </Button>
                        <Button
                            color="success" 
                            on:click={addToAssessment}>
                            +
                        </Button>
                    </span>
                </p>
            </Col>
        {/if}
    </Row>
    
    {#if copyState=="failed"}
        <Row>
            <Col>
                <p class="text-danger mb-1">
                    Your browser blocked clipboard access. The text below is
                    already selected — press Ctrl+C (or Cmd+C) to copy it.
                </p>
                <textarea
                    class="form-control text-monospace"
                    rows="12"
                    readonly
                    value={manualText}
                    use:selectAll
                    on:focus={(e)=>e.currentTarget.select()}
                />
            </Col>
        </Row>
    {/if}

    <div class='mt-2'>
        <Exercise {outcome} {seed} embedded={$querystring=="embed"}/>
    </div>
</Bank>
