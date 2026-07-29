<script lang="ts">
    import Exercise from '../components/Exercise.svelte';
    import type { Params } from '../types';
    import { Button, Row, Col } from 'sveltestrap';
    import { bank } from '../stores/banks';
    import { instructorEnabled, assessmentOutcomeSlugs } from '../stores/instructor';
    import Bank from './Bank.svelte';
    import { push, querystring } from 'svelte-spa-router';
    import { toggleCodeCell, outcomeToAiText } from '../utils';

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
        seed = Math.max(0,Math.min(19,seed+diff))
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

    const copyForAi = async () => {
        const text = outcomeToAiText($bank,outcome,seed)
        clearTimeout(copyTimer)
        try {
            // writeText() resolving is the *only* trustworthy success signal:
            // per spec it resolves after the clipboard is actually written.
            await navigator.clipboard.writeText(text)
            manualText = ''
            copyState = 'copied'
            copyTimer = setTimeout(()=>copyState='idle',2000)
        } catch {
            // document.execCommand('copy') was tried here as a fallback and
            // deliberately removed. On a browser that denies clipboard writes it
            // still returns true AND fires a copy event carrying clipboardData,
            // while writing nothing -- verified on the published site. Since its
            // success cannot be distinguished from its failure, using it
            // reintroduces the exact "looks like it worked" bug this branch
            // exists to prevent. Showing the text is the only honest fallback.
            manualText = text
            copyState = 'failed'
        }
    }

    const resetCopyState = () => {
        clearTimeout(copyTimer)
        copyState = 'idle'
        manualText = ''
    }

    // Routing here is hash-based, so moving to another outcome or version never
    // reloads the page. Without this reset, a "Copied!"/"Copy blocked" state --
    // and the previous exercise's text sitting in the textarea -- would follow
    // the student onto the next exercise.
    //
    // The body MUST stay in a function rather than being inlined here. Inline,
    // `clearTimeout(copyTimer)` reads copyTimer, which makes it a dependency of
    // this block -- and copyForAi's own `copyTimer = setTimeout(...)` would then
    // re-trigger the block and reset copyState to 'idle' in the same flush that
    // set it to 'copied', so the confirmation never rendered at all.
    $: { params; seed; resetCopyState() }
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
                    {#each Array(20) as _, i}
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
