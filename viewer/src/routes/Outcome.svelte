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

    // Older fallback: execCommand only needs the user gesture we're already
    // inside, not the permission the async Clipboard API requires. Deprecated,
    // so it's a second chance rather than the primary path.
    const legacyCopy = (text:string) => {
        const ta = document.createElement('textarea')
        ta.value = text
        ta.setAttribute('readonly','')
        ta.style.position = 'fixed'
        ta.style.top = '0'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        let ok = false
        try { ok = document.execCommand('copy') } catch { ok = false }
        document.body.removeChild(ta)
        return ok
    }

    const copyForAi = async () => {
        const text = outcomeToAiText($bank,outcome,seed)
        let ok = false
        try {
            await navigator.clipboard.writeText(text)
            ok = true
        } catch {
            ok = legacyCopy(text)
        }
        clearTimeout(copyTimer)
        if (ok) {
            manualText = ''
            copyState = 'copied'
            copyTimer = setTimeout(()=>copyState='idle',2000)
        } else {
            manualText = text
            copyState = 'failed'
        }
    }

    // Routing here is hash-based, so moving to another outcome or version never
    // reloads the page. Without this reset, a "Copied!"/"Copy blocked" state --
    // and the previous exercise's text sitting in the textarea -- would follow
    // the student onto the next exercise.
    $: {
        params; seed;
        clearTimeout(copyTimer)
        copyState = 'idle'
        manualText = ''
    }
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
                    Your browser blocked clipboard access. Select the text below
                    and copy it manually.
                </p>
                <textarea
                    class="form-control text-monospace"
                    rows="12"
                    readonly
                    value={manualText}
                    on:focus={(e)=>e.currentTarget.select()}
                />
            </Col>
        </Row>
    {/if}

    <div class='mt-2'>
        <Exercise {outcome} {seed} embedded={$querystring=="embed"}/>
    </div>
</Bank>
