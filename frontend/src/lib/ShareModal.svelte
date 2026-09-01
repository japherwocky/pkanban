<script>
   import Modal from './Modal.svelte';

   let { open, onClose, board, availableTeams, availableOrgs = [], onShare } = $props();

   // Seeded by the $effect below rather than from `board` directly. Reading a
   // prop inside $state() captures only its initial value, so a different
   // board shown without remounting would keep the first board's settings.
   let selectedTeamId = $state(null);
   let selectedOrgId = $state(null);
   let isPublicToOrg = $state(false);
   let loading = $state(false);

   // Only reads `board`, so it re-seeds when the board changes and never
   // clobbers edits the user is making to the form.
   $effect(() => {
     selectedTeamId = board?.shared_team_id ?? null;
     isPublicToOrg = board?.is_public_to_org ?? false;
     // Whichever org it is already shared into, else the only candidate.
     // With several to choose from we leave it unset and make the user pick:
     // the server refuses an ambiguous share rather than guessing, because
     // guessing wrong exposes the board to the wrong people silently.
     selectedOrgId =
       board?.organization_id ?? (availableOrgs.length === 1 ? availableOrgs[0].id : null);
   });

   async function handleShare() {
     loading = true;
     try {
       // If public to org, don't send team_id
       // Otherwise, send the selected team_id (or null to unshare)
       await onShare(
         isPublicToOrg ? null : selectedTeamId,
         isPublicToOrg,
         isPublicToOrg ? selectedOrgId : null
       );
       onClose();
     } catch (e) {
       alert('Failed to share board: ' + e.message);
     } finally {
       loading = false;
     }
   }

   // When public is checked, clear team selection
   $effect(() => {
     if (isPublicToOrg) {
       selectedTeamId = null;
     }
   });
 </script>

{#if open}
  <Modal open={open} onClose={onClose} title={board?.name ? `Share Board: ${board.name}` : 'Share Board'}>
    {#snippet children()}
      {#if availableTeams.length === 0 && availableOrgs.length === 0}
        <div class="no-teams-message">
          <div class="message-icon">📋</div>
          <h3>Create an organization first</h3>
          <p>To share this board with others, you need to create an organization and add members.</p>
          <button class="create-org-btn" onclick={onClose}>Go to Organizations</button>
        </div>
      {:else}
        <div class="share-content">
          <div class="share-option">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={isPublicToOrg}
                id="public-checkbox"
              />
              <span>Public to organization</span>
            </label>
            <p class="share-help">When public, all organization members can view and edit this board.</p>
          </div>

          {#if isPublicToOrg && availableOrgs.length > 1}
            <label class="share-label" for="org-select">Which organization:</label>
            <select id="org-select" class="team-select" bind:value={selectedOrgId}>
              <option value={null}>Choose an organization</option>
              {#each availableOrgs as org (org.id)}
                <option value={org.id}>{org.name}</option>
              {/each}
            </select>
          {/if}

          {#if !isPublicToOrg}
            <label class="share-label" for="team-select">Share with team:</label>
            <select
              id="team-select"
              class="team-select"
              bind:value={selectedTeamId}
              disabled={isPublicToOrg}
            >
              <option value={null}>Not shared</option>
              {#each availableTeams as team (team.id)}
                <option value={team.id}>{team.name} ({team.organization})</option>
              {/each}
            </select>
          {/if}

          <div class="share-info">
            {#if isPublicToOrg && !board?.is_public_to_org}
              <p class="info">ℹ️ This will make the board accessible to all organization members.</p>
            {:else if !isPublicToOrg && board?.shared_team_id && !selectedTeamId}
              <p class="warning">⚠️ This will unshare the board from its current team.</p>
            {:else if !isPublicToOrg && selectedTeamId && selectedTeamId !== board?.shared_team_id}
              <p class="info">ℹ️ This will share the board with the selected team. All team members will be able to view and edit.</p>
            {:else if !isPublicToOrg && !board?.shared_team_id && !selectedTeamId}
              <p class="info">ℹ️ Sharing a board allows all team members to view and edit it.</p>
            {:else}
              <p class="info">ℹ️ This board is currently {board?.is_public_to_org ? 'public to the organization' : 'shared with ' + availableTeams.find(t => t.id === board.shared_team_id)?.name + '.'}</p>
            {/if}
          </div>
        </div>

        <div class="modal-actions">
          <button type="button" class="cancel-btn" onclick={onClose}>Cancel</button>
          <button type="button" class="create-btn" onclick={handleShare} disabled={loading || (isPublicToOrg && !selectedOrgId)}>
            {loading ? 'Saving...' : 'Save'}
          </button>
        </div>
      {/if}
    {/snippet}
  </Modal>
{/if}

<style>
   .share-content {
     display: flex;
     flex-direction: column;
     gap: var(--space-5);
   }

   .share-option {
     display: flex;
     flex-direction: column;
     gap: var(--space-2);
     padding: var(--space-4);
     border-radius: var(--radius-lg);
     background: var(--color-muted);
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
     font-size: var(--text-sm);
     font-weight: 500;
     color: var(--color-foreground);
   }

   .team-select {
     padding: var(--space-3) var(--space-4);
     font-size: var(--text-base);
     border-radius: var(--radius-lg);
     border: 1px solid var(--color-border);
     background: var(--color-card);
     color: var(--color-foreground);
     width: 100%;
   }

   .team-select:focus {
     outline: none;
    border-color: var(--color-primary);
     box-shadow: 0 0 0 3px var(--color-primary);
   }

   .team-select:disabled {
    opacity: 0.5;
    cursor: not-allowed;
   }

   .share-info p {
     font-size: var(--text-sm);
     margin: 0;
     padding: var(--space-3);
     border-radius: var(--radius-md);
   }

   .share-info .warning {
     background-color: color-mix(in srgb, var(--color-error) 12%, transparent);
     color: var(--color-error);
     border: 1px solid color-mix(in srgb, var(--color-error) 40%, transparent);
   }

    .share-info .info {
      background: var(--color-muted);
      color: var(--color-foreground);
    }

    .no-teams-message {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: var(--space-6);
      padding: var(--space-8);
      text-align: center;
    }

    .message-icon {
      font-size: var(--text-4xl);
      opacity: 0.5;
    }

    .no-teams-message h3 {
      font-size: var(--text-xl);
      font-weight: 600;
      color: var(--color-foreground);
      margin: 0;
    }

    .no-teams-message p {
      font-size: var(--text-sm);
      color: var(--color-muted-foreground);
      margin: 0;
      line-height: 1.5;
    }

    .create-org-btn {
      margin-top: var(--space-4);
      padding: var(--space-3) var(--space-6);
      background: var(--color-primary);
      color: var(--color-primary-foreground);
      border: none;
      font-size: var(--text-sm);
      border-radius: var(--radius-lg);
    }

    .create-org-btn:hover {
      opacity: 0.9;
    }

    .modal-actions {
     display: flex;
     justify-content: flex-end;
     gap: var(--space-3);
     margin-top: var(--space-4);
   }

   .cancel-btn {
     background: transparent;
     color: var(--color-foreground);
     border:1px solid var(--color-border);
   }

   .cancel-btn:hover {
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

   .create-btn:disabled {
     opacity: 0.5;
     cursor: not-allowed;
   }
 </style>

