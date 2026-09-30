<script>
  import { navigate } from 'svelte-routing';
  import Modal from './Modal.svelte';
  import { planLimitNotice, dismissPlanLimit, describeLimit } from './planLimit.js';

  function seePlan() {
    dismissPlanLimit();
    navigate('/settings/plan');
  }
</script>

<Modal
  open={$planLimitNotice !== null}
  onClose={dismissPlanLimit}
  title={describeLimit($planLimitNotice?.limit)}
>
  {#if $planLimitNotice}
    <p class="message">{$planLimitNotice.message}</p>
    <div class="actions">
      <button class="secondary" onclick={dismissPlanLimit}>Close</button>
      <button class="primary" onclick={seePlan}>See your plan</button>
    </div>
  {/if}
</Modal>

<style>
  .message {
    margin: 0 0 var(--space-6);
    color: var(--color-foreground);
    line-height: 1.6;
  }

  .actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
  }

  button {
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-lg);
    font-size: var(--text-sm);
    font-weight: 500;
    cursor: pointer;
  }

  .secondary {
    background: transparent;
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
  }

  .primary {
    background: var(--color-primary);
    color: var(--color-primary-foreground);
    border: 1px solid var(--color-primary);
  }
</style>
