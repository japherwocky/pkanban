<script>
  import { navigate } from 'svelte-routing';
  import PageLayout from '../lib/PageLayout.svelte';

  // Mirrors FREE_MAX_BOARDS and FREE_MAX_CARDS_PER_BOARD in backend/billing.py,
  // and the Pro price in Stripe. Pricing.test.js reads billing.py and fails if
  // these drift, because a page that promises one limit while the server
  // enforces another is the kind of mistake that ends in a refund.
  const FREE_BOARDS = 5;
  const FREE_CARDS_PER_BOARD = 100;
  const PRO_PRICE = '$6/mo';

  // Presence only; whether the token is still good is ProtectedRoute's problem.
  const loggedIn = typeof localStorage !== 'undefined' && !!localStorage.getItem('token');
</script>

<PageLayout title="Pricing" description="Two plans. The limits count what you own, not who you work with.">
  <table class="plans">
    <caption class="sr-only">Free and Pro plans compared</caption>
    <thead>
      <tr>
        <td></td>
        <th scope="col">Free</th>
        <th scope="col" class="pro">Pro</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <th scope="row">Boards you own</th>
        <td>{FREE_BOARDS}</td>
        <td class="pro">Unlimited</td>
      </tr>
      <tr>
        <th scope="row">Cards per board</th>
        <td>{FREE_CARDS_PER_BOARD}</td>
        <td class="pro">Unlimited</td>
      </tr>
      <tr>
        <th scope="row">Collaborators, API keys, CLI</th>
        <td>Unlimited</td>
        <td class="pro">Unlimited</td>
      </tr>
      <tr class="price">
        <th scope="row">Price</th>
        <td>$0</td>
        <td class="pro">{PRO_PRICE}</td>
      </tr>
    </tbody>
  </table>

  <div class="cta">
    {#if loggedIn}
      <button class="primary" onclick={() => navigate('/settings/plan')}>Upgrade to Pro</button>
    {:else}
      <button class="primary" onclick={() => navigate('/signup')}>Sign up free</button>
      <p class="note">Upgrade from Settings &rarr; Plan once you're in.</p>
    {/if}
  </div>

  <section>
    <h2>What counts</h2>
    <p>
      The limits are on what you own. A board counts toward your {FREE_BOARDS} if
      you created it. A board shared with you doesn't, and it follows its owner's
      plan: if the owner is on Pro, everyone working on it is unlimited there.
    </p>
    <p>
      Every card counts toward a board's {FREE_CARDS_PER_BOARD}, including the ones
      in Done.
    </p>
  </section>

  <section>
    <h2>Going over is not a lockout</h2>
    <p>
      Past a limit, or if your subscription ends while you're over one, you can't
      create new boards or cards until you're back under or you upgrade. Reading,
      editing, reordering and deleting keep working, and nothing is deleted for you.
    </p>
  </section>

  <section>
    <h2>Agents and API keys</h2>
    <p>
      API keys, the CLI and collaborators aren't metered separately. They act on
      your boards, so your boards' limits are the limits.
    </p>
  </section>

  <section>
    <h2>Self-hosting</h2>
    <p>
      pkanban is MIT licensed. Run your own copy and the limits don't exist: they're
      off unless the server is configured to enforce them.
      <a href="https://github.com/japherwocky/pkanban" target="_blank" rel="noopener">Source on GitHub.</a>
    </p>
  </section>

  <section>
    <h2>Billing</h2>
    <p>
      Pro is {PRO_PRICE}, billed monthly through Stripe. Cancel any time from
      Settings &rarr; Plan; Pro continues until the end of the period you've paid
      for. The details are in the
      <a href="/terms" onclick={(e) => { e.preventDefault(); navigate('/terms'); }}>Terms</a>.
    </p>
  </section>
</PageLayout>

<style>
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }

  .plans {
    width: 100%;
    border-collapse: collapse;
    margin: var(--space-8) 0 var(--space-6) 0;
  }

  .plans th,
  .plans td {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--color-border);
    text-align: center;
    color: var(--color-foreground);
  }

  .plans thead th {
    font-size: var(--text-lg);
    font-weight: 700;
  }

  .plans tbody th {
    text-align: left;
    font-weight: 500;
    color: var(--color-muted-foreground);
  }

  .plans .pro {
    color: var(--color-primary);
    font-weight: 700;
  }

  .plans .price th,
  .plans .price td {
    font-size: var(--text-lg);
    border-bottom: none;
  }

  .cta {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-12);
  }

  .primary {
    padding: var(--space-3) var(--space-6);
    background: var(--color-primary);
    color: var(--color-primary-foreground);
    border: 1px solid var(--color-primary);
    border-radius: var(--radius-lg);
    font-size: var(--text-base);
    font-weight: 500;
    cursor: pointer;
  }

  .note {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
  }

  section {
    margin-bottom: var(--space-8);
  }

  h2 {
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-3) 0;
  }

  section p {
    color: var(--color-muted-foreground);
    font-size: var(--text-base);
    line-height: 1.7;
    margin: 0 0 var(--space-4) 0;
  }

  a {
    color: var(--color-primary);
    text-decoration: none;
  }

  a:hover {
    text-decoration: underline;
  }

  @media (max-width: 640px) {
    .plans th,
    .plans td {
      padding: var(--space-2);
    }

    h2 {
      font-size: var(--text-lg);
    }
  }
</style>
