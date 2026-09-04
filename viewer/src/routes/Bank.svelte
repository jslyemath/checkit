<script lang="ts">
    import type {Params, Outcome} from '../types';
    export let params:Params;

    import {
        Container,
        Alert,
    } from 'sveltestrap';
    import OutcomeDropdown from '../components/dropdowns/Outcome.svelte';

    let outcome: Outcome | undefined = undefined;
    $: if (params && params.outcomeSlug) {
        outcome = $bank.outcomes.find((o)=>o.slug==params.outcomeSlug)
    }

    import { querystring } from 'svelte-spa-router';
    import { bank } from '../stores/banks';

    // generated_on is stored as UTC; both of these render it in the reader's
    // own timezone and locale, so a student two zones away sees the moment the
    // bank was built as it was for them. Minutes, no seconds -- the point is
    // telling two builds on the same day apart, not stopwatch precision.
    $: generatedOn = new Date(Date.parse($bank.generated_on));
</script>

<main>
    <Container>
        <h1>{$bank.title}</h1>
        {#if $bank.outcomes}
            {#if $querystring != "embed"}
                <p>
                    <OutcomeDropdown {outcome}/>
                </p>
            {/if}
        {:else}
            <Alert color="warning">No outcomes found for this bank.</Alert>
        {/if}
        {#if !outcome}
            <p>Homepage: <a href={$bank.url}>{$bank.url}</a></p>
            <p>
                Bank generated on:
                <date datetime={$bank.generated_on}>
                    {generatedOn.toDateString()}, at
                    {generatedOn.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'})}
                </date>
            </p>
        {/if}
        <slot/>
    </Container>
</main>

<style>
    h1 {margin-top: 0.5em;}
</style>