<script lang="ts">
    import {
        Container,
        Row,
        Col,
        Button,
        ButtonDropdown,
        DropdownToggle,
        DropdownMenu,
        DropdownItem,
        FormGroup, Label, Input,
    } from 'sveltestrap';
    import OutcomeDropdown from '../components/dropdowns/Outcome.svelte';
    import Sorter from '../components/Sorter.svelte';
    import { assessmentOutcomeSlugs, instructorEnabled, assessmentTemplate } from '../stores/instructor';
    import { bank } from '../stores/banks';
    import { getOutcomeFromSlug, pickAssessmentExercises, renderAssessment,
        ensureDerivedForSlugs, ensureLatexSupport, bankHasTheme,
        defaultTemplateFor } from '../utils';
    import type { Assessment, Outcome } from '../types';
    import Exercise from '../components/Exercise.svelte'

    $instructorEnabled = true
    $assessmentOutcomeSlugs = $assessmentOutcomeSlugs.filter(s=>getOutcomeFromSlug($bank,s)!==undefined)
    const display = (slug:string) => {
        let o = getOutcomeFromSlug($bank,slug);
        return `${slug} — ${o.title}`
    };
    let generatedAssessment: Assessment | undefined = undefined
    let generateError:string = ""
    let answerKey = false

    // The bank's default template: themed when the bank publishes a theme.
    // $assessmentTemplate is null until the instructor edits it, so an
    // unedited template follows the bank rather than whichever default the
    // browser happened to store first.
    $: themed = bankHasTheme($bank)
    $: bankDefaultTemplate = defaultTemplateFor($bank)
    $: effectiveTemplate = $assessmentTemplate ?? bankDefaultTemplate

    // Assessments draw from seeds above the publicly visible ones, which are not
    // inlined in bank.json -- so their precomputed LaTeX has to be fetched first.
    // A themed bank also needs its .sty, which is published beside bank.json
    // rather than inside it: every visitor downloads bank.json, and a theme
    // only matters on this tab.
    // The chosen exercises are held separately from the rendered document, so
    // ticking the answer key re-renders these same versions. Re-picking would
    // hand back a key for an assessment the instructor never saw.
    let chosen: {outcome:Outcome, seed:number}[] = []
    const generate = async () => {
        generateError = ""
        try {
            await ensureDerivedForSlugs($bank,$assessmentOutcomeSlugs)
            await ensureLatexSupport($bank)
            chosen = pickAssessmentExercises($bank,$assessmentOutcomeSlugs)
            generatedAssessment = renderAssessment(
                $bank,chosen,effectiveTemplate,answerKey)
        } catch (e) {
            generatedAssessment = undefined
            generateError = e instanceof Error ? e.message : String(e)
        }
    }
    // Editing the template or ticking the key updates what is on screen, so
    // the preview never disagrees with what the buttons would export.
    $: if (chosen.length) {
        generatedAssessment = renderAssessment(
            $bank,chosen,effectiveTemplate,answerKey)
    }

    const copyToClipboard = (text:string) => () => {
        navigator.clipboard.writeText(text)
        alert("Copied to clipboard!")
    }
    let latexForm: HTMLFormElement

    /**
     * Overleaf accepts several files in one request: repeated snip_uri[] with
     * matching snip_name[], and main_document naming the root. Each file is
     * sent as a base64 data: URL, so nothing has to be publicly hosted first.
     *
     * This is why the export is a project rather than one long file -- the
     * theme arrives as a real .sty that Overleaf loads with \usepackage,
     * exactly as the print tool writes it to disk.
     */
    const asDataUrl = (text:string) => {
        // btoa is bytes, not characters; a theme with any non-ASCII in it
        // throws otherwise, and a hieroglyph has reached this pipeline before.
        const bytes = new TextEncoder().encode(text)
        let binary = ""
        bytes.forEach((b)=>{ binary += String.fromCharCode(b) })
        return `data:application/x-tex;base64,${btoa(binary)}`
    }
    const overleafFields = (assessment:Assessment) => {
        const fields: {name:string, value:string}[] = []
        assessment.files.forEach((f)=>{
            fields.push({name:"snip_uri[]", value:asDataUrl(f.content)})
            fields.push({name:"snip_name[]", value:f.name})
        })
        fields.push({name:"main_document", value:"main.tex"})
        fields.push({name:"engine", value:"pdflatex"})
        return fields
    }
    const openInOverleaf = () => {
        latexForm.target = "_blank"
        latexForm.action = "https://www.overleaf.com/docs"
        latexForm.method = "POST"
        latexForm.submit()
    }
</script>

<main>
    <Container>
        <h1 class="display-4">☑️It Assessment Builder</h1>
        <Row>
            <Col sm="4">
                <p>
                    Build your assessment by first adding learning outcomes:
                </p>
                <p><OutcomeDropdown/></p>
                <p>
                    Then you can sort these outcomes into whatever order 
                    you wish. 
                </p>
            </Col>
            <Col sm="8">
                <div class="outcome-ordering">
                    {#if $assessmentOutcomeSlugs.length < 1}
                        (Add outcomes for your assessment.)
                    {/if}
                    <Sorter bind:array={$assessmentOutcomeSlugs} {display} removesItems/>
                    {#if $assessmentOutcomeSlugs.length > 0}
                        <a 
                            href="#."
                            on:click|preventDefault={()=>$assessmentOutcomeSlugs=[]}>
                            [Reset outcomes]
                        </a>
                    {/if}
                </div>
            </Col>
        </Row>
        <Row>
            <Col>
                <details class="my-3">
                    <summary>
                        Customize the LaTeX template
                    </summary>
                    {#if themed}
                        <p class="text-muted">
                            This bank publishes a LaTeX theme, so the default
                            template builds an assessment that looks like its
                            printed handouts.
                        </p>
                    {/if}
                    {#if $assessmentTemplate !== null}
                        <p>
                            <a
                                href="#."
                                on:click|preventDefault={()=>$assessmentTemplate=null}>
                                [Reset to default template]
                            </a>
                        </p>
                    {/if}
                    <textarea
                        class="form-control font-monospace mb-3"
                        rows="10"
                        value={effectiveTemplate}
                        on:input={(e)=>$assessmentTemplate=e.currentTarget.value}
                    />
                </details>
            </Col>
        </Row>
        <Row>
            <Col>
                <p>
                    Clicking "Generate" will choose a random exercise assessing
                    each outcome.
                </p>
                {#if themed}
                    <!-- Only offered on a themed bank: the key needs the
                         theme's \ifanstoggle to show answers, and the generic
                         template has no such switch. -->
                    <FormGroup check class="mb-2">
                        <Input type="checkbox" id="answerKey" bind:checked={answerKey} />
                        <Label for="answerKey" check>
                            Include answer key
                            <span class="text-muted">
                                — repeats the same versions with answers shown,
                                after the student copy
                            </span>
                        </Label>
                    </FormGroup>
                {/if}
                <Row class="mb-2">
                    <Col xs="auto" class="ml-auto">
                        <Button
                            color="primary"
                            disabled={$assessmentOutcomeSlugs.length < 1}
                            outline={generatedAssessment !== undefined}
                            on:click={generate}>
                            {#if generatedAssessment}
                                Re-generate
                                {:else}
                                Generate
                            {/if}
                        </Button>
                        {#if generateError}
                            <!-- Shown rather than logged: a bank that was never
                                 regenerated cannot be fixed from the browser,
                                 and the instructor is the one who can fix it. -->
                            <div class="alert alert-danger mt-3" style="white-space:pre-wrap">{generateError}</div>
                        {/if}
                    </Col>  
                    <Col xs="auto" class="mr-auto">
                        {#if generatedAssessment}
                            <ButtonDropdown>
                                <DropdownToggle caret>
                                    Export:
                                </DropdownToggle>
                                <DropdownMenu>
                                    <DropdownItem on:click={openInOverleaf}>
                                        Open PDF using Overleaf.com
                                    </DropdownItem>
                                    <DropdownItem
                                        on:click={copyToClipboard(generatedAssessment.latex)}>
                                        Copy LaTeX to your clipboard 📋
                                    </DropdownItem>
                                </DropdownMenu>
                            </ButtonDropdown>
                        {/if}
                    </Col>
                </Row>
                {#if generatedAssessment}
                    <Row>
                        <Col sm="4">
                            <form bind:this={latexForm}>
                                <!-- The preview and the clipboard both carry
                                     the standalone file, since a clipboard
                                     holds one thing. Overleaf gets the same
                                     document split into real files, posted
                                     from the hidden inputs below. -->
                                <p>
                                    <em>Source code:</em>
                                    <textarea
                                        class="form-control text-monospace"
                                        rows="20"
                                        readonly
                                        value={generatedAssessment.latex}
                                    />
                                </p>
                                {#each overleafFields(generatedAssessment) as field}
                                    <input type="hidden" name={field.name} value={field.value} />
                                {/each}
                            </form>
                        </Col>
                        <Col sm="8">
                            <h3>Preview</h3>
                            {#each generatedAssessment.exercises as exercise,i}
                                <h4>Exercise {i+1}</h4>
                                <Exercise outcome={exercise.outcome} seed={exercise.seed} statementOnly/>
                            {/each}
                        </Col>
                    </Row>
                {/if}
            </Col>
        </Row>
    </Container>
</main>

<style>
    h1 { margin-top:0.5em }
    .outcome-ordering {
        border: 1px #888 solid; 
        border-radius: 5px; 
        padding: 10px; 
        margin-bottom: 1em;
        color: gray;
        text-align: center;
    }
</style>