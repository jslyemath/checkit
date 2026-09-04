<script lang="ts">
    import type { Outcome } from '../types';
    import { instructorEnabled } from '../stores/instructor';
    import { Nav, NavItem, NavLink, Row, Col } from 'sveltestrap';
    import { outcomeToStx, outcomeToHtml, outcomeToLatex, outcomeToPtx } from '../utils';
    import Knowl from '../spatext/Elements/Knowl.svelte';
    import { currentExercise } from '../stores/answers';

    export let embedded:Boolean = false;

    export let outcome: Outcome;
    export let seed = 0;
    export let statementOnly: boolean=false;


    const modes = ['display', 'edit', 'embed', 'html', 'latex', 'pretext']
    const modeLabels = ['Display', 'Edit Template', 'Embed HTML', 'Raw HTML', 'LaTeX', 'PreTeXt']
    let mode = "display";
    const changeMode = (m:string) => (e:Event) => {
        e.preventDefault();
        mode = m;
    }
    // The derived formats are read from the bank rather than transformed here,
    // and reading can fail for reasons an instructor can act on -- most often a
    // bank generated before precomputation existed. Rendering the message beats
    // throwing: an exception in markup leaves the tab simply blank, which is
    // indistinguishable from an exercise that happens to be empty.
    type Rendered = { text:string|null, error:string|null }
    const render = (m:string, o:Outcome, s:number):Rendered => {
        try {
            if (m == "html")    return { text: outcomeToHtml(o,s),  error: null }
            if (m == "latex")   return { text: outcomeToLatex(o,s), error: null }
            if (m == "pretext") return { text: outcomeToPtx(o,s),   error: null }
            return { text: null, error: null }
        } catch (e) {
            return { text: null, error: e instanceof Error ? e.message : String(e) }
        }
    }
    // outcome and seed are named here so Svelte tracks them: a reactive
    // statement depends on what the statement mentions, not on what the
    // function it calls happens to read.
    $: rendered = render(mode, outcome, seed)

    // Told to the answer store rather than passed down: Knowl sits several
    // layers of content and node components below here, and none of them has
    // any other reason to know which skill or version it is rendering.
    $: currentExercise.set({ slug: outcome.slug, seed })

    let embed:string
    $: embed = `<iframe title="Iframe CheckIt Outcome"
    width="800"
    height="450"
    src="${location.protocol}//${location.host}${location.pathname}#/bank/${outcome.slug}/${seed+1}/?embed">
</iframe>`

    // let canvasMath = false
    // let canvasSolutions:'show'|'hide'|'only' = 'show'
</script>

{#if !statementOnly && !embedded}
    {#if $instructorEnabled}
        <div class="navtabs">
            <Nav tabs>
                {#each modes as m,i}
                    <NavItem>
                        <NavLink 
                            active={mode==m} 
                            on:click={changeMode(m)} 
                            href="#/">
                            {modeLabels[i]}
                        </NavLink>
                    </NavItem>
                {/each}
            </Nav>
        </div>
    {/if}
{/if}

{#if embedded || mode == "display"}
    <Knowl knowl={outcomeToStx(outcome,seed)}/>
{:else if mode == "edit"}
    <Row>
        <Col sm="6">
            <p><textarea bind:value={outcome.template}/></p>
            <p><textarea readonly value={JSON.stringify(outcome.exercises[seed]['data'], null, 2)}/></p>
        </Col>
        <Col sm="6">
            <Knowl knowl={outcomeToStx(outcome,seed)}/>
        </Col>
    </Row>
{:else if mode == "html"}
    {#if rendered.error}
        <div class="alert alert-danger" style="white-space:pre-wrap">{rendered.error}</div>
    {:else}
        <textarea readonly value={rendered.text}/>
    {/if}
    <!-- <input type="checkbox" bind:checked={canvasMath}/>
    <select bind:value={canvasSolutions}>
        {#each ['show','hide','only'] as opt}
            <option value={opt}>{opt}</option>
        {/each}
    </select>
    {@html outcomeToHtml(outcome,seed,canvasMath,canvasSolutions)} -->
{:else if mode == "latex"}
    {#if rendered.error}
        <div class="alert alert-danger" style="white-space:pre-wrap">{rendered.error}</div>
    {:else}
        <textarea readonly value={rendered.text}/>
    {/if}
{:else if mode == "pretext"}
    {#if rendered.error}
        <div class="alert alert-danger" style="white-space:pre-wrap">{rendered.error}</div>
    {:else}
        <textarea readonly value={rendered.text}/>
    {/if}
{:else if mode == "embed"}
    <textarea readonly value={embed}/>
{:else}
    Invalid mode.
{/if}

<style>
    .navtabs {
        margin-bottom: 1em;
    }
    textarea {
        width:100%;
        height:25em;
        font-family:Consolas,Monaco,Lucida Console,Liberation Mono,DejaVu Sans Mono,Bitstream Vera Sans Mono,Courier New, monospace;
    }
    textarea[readonly] {
        background-color: #eee;
    }
</style>