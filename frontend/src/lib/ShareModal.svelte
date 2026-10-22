<script>
   import Modal from './Modal.svelte';

   // Each change goes to the server as it is made -- a team added, a level
   // changed, a team removed -- and `board` comes back fresh, so the list
   // below is always what the server holds rather than a form to submit.
   let {
     open,
     onClose,
     board,
     availableTeams = [],
     availableOrgs = [],
     onSetTeam,
     onRemoveTeam,
     onShareOrg,
     onInvite,
     onRevokeInvite,
   } = $props();

   const LEVELS = [
     { value: 'read', label: 'Can read' },
     { value: 'write', label: 'Can edit' },
     { value: 'admin', label: 'Admin' },
   ];

   let busy = $state(false);
   let error = $state(null);
   let addTeamId = $state(null);
   let addLevel = $state('write');
   let inviteEmail = $state('');
   let inviteLevel = $state('write');
   // Set when the server could not mail the invite (no mailer configured):
   // the link is then the inviter's to pass on.
   let unsentLink = $state(null);

   // Seeded by the $effect below rather than from `board` directly. Reading a
   // prop inside $state() captures only its initial value, so a different
   // board shown without remounting would keep the first board's settings.
   let isPublicToOrg = $state(false);
   let selectedOrgId = $state(null);
   let orgLevel = $state('write');

   $effect(() => {
     isPublicToOrg = board?.is_public_to_org ?? false;
     orgLevel = board?.org_permission ?? 'write';
     // Whichever org it is already shared into, else the only candidate.
     // With several to choose from we leave it unset and make the user pick:
     // the server refuses an ambiguous share rather than guessing, because
     // guessing wrong exposes the board to the wrong people silently.
     selectedOrgId =
       board?.organization_id ?? (availableOrgs.length === 1 ? availableOrgs[0].id : null);
   });

   let shared = $derived(board?.teams ?? []);
   let invitesByTeam = $derived(
     (board?.invites ?? []).reduce((map, invite) => {
       (map[invite.team_id] ??= []).push(invite);
       return map;
     }, {})
   );
   let addable = $derived(availableTeams.filter((t) => !shared.some((s) => s.id === t.id)));
   let orgChanged = $derived(
     isPublicToOrg !== (board?.is_public_to_org ?? false) ||
       (isPublicToOrg && orgLevel !== (board?.org_permission ?? 'write')) ||
       (isPublicToOrg && selectedOrgId !== board?.organization_id)
   );

   function teamLabel(team) {
     const org = team.organization_name ?? team.organization;
     return org ? `${team.name} (${org})` : team.name;
   }

   async function run(action) {
     busy = true;
     error = null;
     try {
       await action();
     } catch (e) {
       error = e.message;
     } finally {
       busy = false;
     }
   }

   function sendInvite() {
     const email = inviteEmail.trim();
     if (!email) return;
     run(async () => {
       const result = await onInvite(email, inviteLevel);
       unsentLink = result?.email_sent === false ? { email, url: result.invite.url } : null;
       inviteEmail = '';
       inviteLevel = 'write';
     });
   }

   async function copyLink() {
     try {
       await navigator.clipboard.writeText(unsentLink.url);
     } catch {
       // Clipboard refused (permissions, insecure origin): the link is on
       // screen and selectable, which is enough.
     }
   }

   function addTeam() {
     if (addTeamId == null) return;
     run(async () => {
       await onSetTeam(addTeamId, addLevel);
       addTeamId = null;
       addLevel = 'write';
     });
   }
 </script>

{#if open}
  <Modal open={open} onClose={onClose} title={board?.name ? `Share Board: ${board.name}` : 'Share Board'}>
    {#snippet children()}
      <div class="share-content">
        <section class="share-section">
          <h3 class="share-label">Teams</h3>
          {#if shared.length === 0}
            <p class="share-help">Not shared with any team.</p>
          {:else}
            <ul class="team-list">
              {#each shared as team (team.id)}
                <li class="team-item">
                <div class="team-row">
                  <span class="team-name">{teamLabel(team)}</span>
                  <select
                    class="level-select"
                    aria-label={`Access for ${team.name}`}
                    value={team.permission}
                    disabled={busy}
                    onchange={(e) => run(() => onSetTeam(team.id, e.currentTarget.value))}
                  >
                    {#each LEVELS as level (level.value)}
                      <option value={level.value}>{level.label}</option>
                    {/each}
                  </select>
                  <button
                    type="button"
                    class="remove-btn"
                    aria-label={`Remove ${team.name}`}
                    disabled={busy}
                    onclick={() => run(() => onRemoveTeam(team.id))}
                  >Remove</button>
                </div>
                {#each invitesByTeam[team.id] ?? [] as invite (invite.id)}
                  <div class="pending-row">
                    <span class="pending-text">{invite.email} · invited, not yet accepted</span>
                    <button
                      type="button"
                      class="link-btn"
                      aria-label={`Revoke the invitation to ${invite.email}`}
                      disabled={busy}
                      onclick={() => run(() => onRevokeInvite(invite.id))}
                    >Revoke</button>
                  </div>
                {/each}
                </li>
              {/each}
            </ul>
          {/if}

          {#if addable.length > 0}
            <div class="team-row add-row">
              <select class="team-select" aria-label="Team to add" bind:value={addTeamId} disabled={busy}>
                <option value={null}>Add a team…</option>
                {#each addable as team (team.id)}
                  <option value={team.id}>{teamLabel(team)}</option>
                {/each}
              </select>
              <select class="level-select" aria-label="Access for the new team" bind:value={addLevel} disabled={busy}>
                {#each LEVELS as level (level.value)}
                  <option value={level.value}>{level.label}</option>
                {/each}
              </select>
              <button type="button" class="create-btn" onclick={addTeam} disabled={busy || addTeamId == null}>Add</button>
            </div>
          {/if}
          <p class="share-help">Everyone on a team gets its access. Admins can share the board too; only you can delete it.</p>
        </section>

        {#if onInvite}
          <section class="share-section">
            <h3 class="share-label">Invite by email</h3>
            <form class="team-row invite-form" onsubmit={(e) => { e.preventDefault(); sendInvite(); }}>
              <input
                type="email"
                class="team-select email-input"
                placeholder="name@example.com"
                aria-label="Email to invite"
                bind:value={inviteEmail}
                disabled={busy}
                required
              />
              <select class="level-select" aria-label="Access for the invitee" bind:value={inviteLevel} disabled={busy}>
                {#each LEVELS as level (level.value)}
                  <option value={level.value}>{level.label}</option>
                {/each}
              </select>
              <button type="submit" class="create-btn" disabled={busy || !inviteEmail.trim()}>Invite</button>
            </form>
            <p class="share-help">They get a link to this board, for that address only. They don't need an account yet.</p>
            {#if unsentLink}
              <div class="unsent" role="status">
                <p class="share-help">This server doesn't send mail. Send {unsentLink.email} this link yourself:</p>
                <div class="team-row">
                  <input class="team-select" readonly value={unsentLink.url} aria-label="Invitation link" onfocus={(e) => e.currentTarget.select()} />
                  <button type="button" class="remove-btn" onclick={copyLink}>Copy</button>
                </div>
              </div>
            {/if}
          </section>
        {/if}

        {#if availableOrgs.length > 0 || board?.is_public_to_org}
          <section class="share-section share-option">
            <label class="checkbox-label">
              <input type="checkbox" bind:checked={isPublicToOrg} id="public-checkbox" disabled={busy} />
              <span>Public to organization</span>
            </label>
            {#if isPublicToOrg}
              <div class="team-row">
                {#if availableOrgs.length > 1}
                  <select id="org-select" class="team-select" aria-label="Which organization" bind:value={selectedOrgId} disabled={busy}>
                    <option value={null}>Choose an organization</option>
                    {#each availableOrgs as org (org.id)}
                      <option value={org.id}>{org.name}</option>
                    {/each}
                  </select>
                {/if}
                <select class="level-select" aria-label="Access for the organization" bind:value={orgLevel} disabled={busy}>
                  {#each LEVELS as level (level.value)}
                    <option value={level.value}>{level.label}</option>
                  {/each}
                </select>
              </div>
            {/if}
            <p class="share-help">Every member of the organization gets this access.</p>
            {#if orgChanged}
              <div class="org-actions">
                <button
                  type="button"
                  class="create-btn"
                  disabled={busy || (isPublicToOrg && !selectedOrgId)}
                  onclick={() => run(() => onShareOrg(isPublicToOrg, isPublicToOrg ? selectedOrgId : null, orgLevel))}
                >
                  {isPublicToOrg ? 'Save organization access' : 'Stop sharing with the organization'}
                </button>
              </div>
            {/if}
          </section>
        {/if}

        {#if error}
          <p class="warning" role="alert">{error}</p>
        {/if}
      </div>

      <div class="modal-actions">
        <button type="button" class="cancel-btn" onclick={onClose}>Done</button>
      </div>
    {/snippet}
  </Modal>
{/if}

<style>
   .share-content {
     display: flex;
     flex-direction: column;
     gap: var(--space-5);
   }

   .share-section {
     display: flex;
     flex-direction: column;
     gap: var(--space-3);
   }

   .share-option {
     padding: var(--space-4);
     border-radius: var(--radius-lg);
     background: var(--color-muted);
   }

   .team-list {
     list-style: none;
     margin: 0;
     padding: 0;
     display: flex;
     flex-direction: column;
     gap: var(--space-2);
   }

   .team-row {
     display: flex;
     align-items: center;
     gap: var(--space-2);
     flex-wrap: wrap;
   }

   .team-list .team-row {
     flex-wrap: nowrap;
   }

   .team-item {
     display: flex;
     flex-direction: column;
     gap: var(--space-1);
   }

   .pending-row {
     display: flex;
     align-items: center;
     gap: var(--space-2);
     padding-left: var(--space-3);
     font-size: var(--text-sm);
     color: var(--color-muted-foreground);
   }

   .pending-text {
     flex: 1 1 0;
     min-width: 0;
     overflow-wrap: anywhere;
   }

   .link-btn {
     padding: 0;
     background: none;
     border: none;
     color: var(--color-primary);
     font-size: var(--text-sm);
     cursor: pointer;
     text-decoration: underline;
   }

   .link-btn:disabled {
     opacity: 0.5;
     cursor: not-allowed;
   }

   /* A row, explicitly: the modal's form styles stack a form's children,
      which turns the input's flex-basis into a height. */
   .invite-form {
     flex-direction: row;
     align-items: center;
     margin: 0;
   }

   .email-input {
     font-family: inherit;
     height: auto;
     min-height: 0;
   }

   .unsent {
     display: flex;
     flex-direction: column;
     gap: var(--space-2);
   }

   .team-name {
     flex: 1 1 0;
     min-width: 0;
     overflow-wrap: anywhere;
     color: var(--color-foreground);
   }

   .checkbox-label {
     display: flex;
     align-items: center;
     gap: var(--space-3);
     font-size: var(--text-base);
     font-weight: 500;
     color: var(--color-foreground);
     cursor: pointer;
   }

   .checkbox-label input[type="checkbox"] {
     width: 1.25rem;
     height: 1.25rem;
     cursor: pointer;
   }

   .share-help {
     font-size: var(--text-sm);
     color: var(--color-muted-foreground);
     margin: 0;
   }

   .share-label {
     margin: 0;
     font-size: var(--text-sm);
     font-weight: 500;
     color: var(--color-foreground);
   }

   .team-select,
   .level-select {
     padding: var(--space-2) var(--space-3);
     font-size: var(--text-sm);
     border-radius: var(--radius-lg);
     border: 1px solid var(--color-border);
     background: var(--color-card);
     color: var(--color-foreground);
   }

   .team-select {
     flex: 1 1 10rem;
     min-width: 0;
   }

   .team-select:focus,
   .level-select:focus {
     outline: none;
     border-color: var(--color-primary);
     box-shadow: 0 0 0 3px var(--color-primary);
   }

   .team-select:disabled,
   .level-select:disabled {
     opacity: 0.5;
     cursor: not-allowed;
   }

   .org-actions {
     display: flex;
     justify-content: flex-end;
   }

   .warning {
     font-size: var(--text-sm);
     margin: 0;
     padding: var(--space-3);
     border-radius: var(--radius-md);
     background-color: color-mix(in srgb, var(--color-error) 12%, transparent);
     color: var(--color-error);
     border: 1px solid color-mix(in srgb, var(--color-error) 40%, transparent);
   }

   .modal-actions {
     display: flex;
     justify-content: flex-end;
     gap: var(--space-3);
     margin-top: var(--space-4);
   }

   .cancel-btn,
   .remove-btn,
   .create-btn {
     padding: var(--space-2) var(--space-4);
     font-size: var(--text-sm);
     border-radius: var(--radius-lg);
     cursor: pointer;
   }

   .cancel-btn,
   .remove-btn {
     background: transparent;
     color: var(--color-foreground);
     border: 1px solid var(--color-border);
   }

   .remove-btn {
     padding: var(--space-2) var(--space-3);
     flex: none;
   }

   .cancel-btn:hover,
   .remove-btn:hover {
     background: var(--color-muted);
   }

   .create-btn {
     background: var(--color-primary);
     color: var(--color-primary-foreground);
     border: none;
   }

   .create-btn:hover {
     opacity: 0.9;
   }

   .create-btn:disabled,
   .remove-btn:disabled {
     opacity: 0.5;
     cursor: not-allowed;
   }
 </style>
