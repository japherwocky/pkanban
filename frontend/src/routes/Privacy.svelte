<script>
  import PageLayout from '../lib/PageLayout.svelte';
</script>

<PageLayout title="Privacy Policy" description="">
  <div class="legal-content">
    <section>
      <p class="last-updated">Last updated: September 2026</p>

      <h2>Data Collection</h2>
      <p>
        pkanban collects minimal data necessary to provide the service. This includes
        account information (username, email if provided), board data you create,
        organization and team membership, invitations you send or receive, and usage
        metrics to improve the service.
      </p>

      <h2>Organizations, Teams, and Sharing</h2>
      <p>
        Boards can be shared with a team, and teams can span organizations -- a
        board's visibility follows whoever has been granted access to it, not just
        the organization that created it. Inviting someone by email shares that
        address with us and, once they accept, with the team or organization they
        joined; an invite that is never accepted is not treated as consent to
        anything beyond receiving that one email.
      </p>

      <h2>Data Storage</h2>
      <p>
        All data is stored securely using industry-standard practices. We do not sell
        or share your data with third parties for advertising purposes.
      </p>

      <h2>AI Agent Data</h2>
      <p>
        Any data processed through our CLI or API is treated with the same privacy
        standards as user-created content. We do not use your board data to train
        external AI models.
      </p>

      <h2>Cookies</h2>
      <p>
        We use essential cookies for authentication and session management. You can
        disable cookies in your browser settings, though some features may not work.
      </p>

      <h2>Contact</h2>
      <p>
        For privacy concerns, contact us at <a href="mailto:pkanban@pearachute.com">pkanban@pearachute.com</a>.
      </p>
    </section>
  </div>
</PageLayout>

<style>
  .legal-content {
    text-align: left;
  }

  .last-updated {
    color: var(--color-muted-foreground);
    font-size: var(--text-sm);
    font-style: italic;
    margin: 0 0 var(--space-8) 0;
  }

  section {
    margin-bottom: var(--space-8);
  }

  h2 {
    font-size: var(--text-xl);
    font-weight: 600;
    color: var(--color-foreground);
    margin: 0 0 var(--space-3) 0;
  }

  p {
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
    h2 {
      font-size: var(--text-lg);
    }
  }
</style>
