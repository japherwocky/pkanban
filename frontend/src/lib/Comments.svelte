<script>
  import { api } from './api.js';

  let { card, onCommentsUpdate } = $props();

  // Seeded by the $effect below rather than from `card` directly. Reading a
  // prop inside $state() captures only its initial value, so a card swapped
  // in later would leave the previous card's comments on screen.
  let comments = $state([]);
  let newComment = $state('');
  let loading = $state(false);
  let editingCommentId = $state(null);
  let editContent = $state('');

  // Get current user's id from token
  let currentUserId = $state(null);
  try {
    const token = localStorage.getItem('token');
    if (token) {
      const tokenData = JSON.parse(atob(token.split('.')[1]));
      currentUserId = tokenData.sub;
    }
  } catch (e) {
    console.error('Failed to decode token:', e);
  }

  // Update comments when card prop changes. Unconditional: guarding on
  // `card?.comments` being present meant a card that arrived without the
  // field kept the comments of whichever card was shown before it.
  $effect(() => {
    comments = [...(card?.comments ?? [])];
  });

  function formatRelativeTime(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffInSeconds = Math.floor((now - date) / 1000);

    if (diffInSeconds < 60) return 'just now';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
    if (diffInSeconds < 2592000) return `${Math.floor(diffInSeconds / 86400)}d ago`;
    
    return date.toLocaleDateString();
  }

  async function createComment() {
    if (!newComment.trim()) return;
    
    loading = true;
    try {
      const comment = await api.comments.create(card.id, newComment.trim());
      comments = [...comments, comment];
      newComment = '';
      
      // Notify parent component of the update
      if (onCommentsUpdate) {
        onCommentsUpdate(card.id, [...comments]);
      }
    } catch (e) {
      alert('Failed to create comment: ' + e.message);
    } finally {
      loading = false;
    }
  }

  async function deleteComment(commentId) {
    if (!confirm('Delete this comment?')) return;
    
    try {
      await api.comments.delete(commentId);
      comments = comments.filter(c => c.id !== commentId);
      
      // Notify parent component of the update
      if (onCommentsUpdate) {
        onCommentsUpdate(card.id, [...comments]);
      }
    } catch (e) {
      alert('Failed to delete comment: ' + e.message);
    }
  }

  function startEdit(comment) {
    editingCommentId = comment.id;
    editContent = comment.content;
  }

  function cancelEdit() {
    editingCommentId = null;
    editContent = '';
  }

  async function saveEdit(commentId) {
    if (!editContent.trim()) return;
    
    try {
      const updatedComment = await api.comments.update(commentId, editContent.trim());
      comments = comments.map(c => c.id === commentId ? updatedComment : c);
      editingCommentId = null;
      editContent = '';
      
      // Notify parent component of the update
      if (onCommentsUpdate) {
        onCommentsUpdate(card.id, [...comments]);
      }
    } catch (e) {
      alert('Failed to update comment: ' + e.message);
    }
  }

  function handleKeydown(event, action, ...args) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      action(...args);
    }
  }
</script>

<div class="comments-section">
  <h4 class="comments-title">Comments ({comments.length})</h4>
  
  <!-- Comments list -->
  <div class="comments-list">
    {#each comments as comment (comment.id)}
      <div class="comment">
        <div class="comment-header">
          <span class="comment-author">{comment.username}</span>
          <span class="comment-time">{formatRelativeTime(comment.created_at)}</span>
          {#if comment.user_id === currentUserId}
            <div class="comment-actions">
              <button 
                class="comment-action-btn" 
                onclick={() => startEdit(comment)}
                title="Edit comment"
              >
                ✏️
              </button>
              <button 
                class="comment-action-btn delete" 
                onclick={() => deleteComment(comment.id)}
                title="Delete comment"
              >
                🗑️
              </button>
            </div>
          {/if}
        </div>
        
        <div class="comment-content">
          {#if editingCommentId === comment.id}
            <div class="edit-form">
              <textarea 
                bind:value={editContent}
                class="edit-textarea"
                placeholder="Edit your comment..."
                onkeydown={(e) => handleKeydown(e, saveEdit, comment.id)}
              ></textarea>
              <div class="edit-actions">
                <button 
                  class="btn btn-sm btn-primary" 
                  onclick={() => saveEdit(comment.id)}
                  disabled={!editContent.trim()}
                >
                  Save
                </button>
                <button 
                  class="btn btn-sm btn-secondary" 
                  onclick={cancelEdit}
                >
                  Cancel
                </button>
              </div>
            </div>
          {:else}
            <p class="comment-text">{comment.content}</p>
            {#if comment.updated_at && comment.updated_at !== comment.created_at}
              <span class="comment-edited">(edited)</span>
            {/if}
          {/if}
        </div>
      </div>
    {/each}
    
    {#if comments.length === 0}
      <p class="no-comments">No comments yet. Be the first to comment!</p>
    {/if}
  </div>
  
  <!-- New comment form -->
  <div class="new-comment-form">
    <textarea 
      bind:value={newComment}
      class="new-comment-input"
      placeholder="Add a comment..."
      disabled={loading}
      onkeydown={(e) => handleKeydown(e, createComment)}
    ></textarea>
    <button 
      class="btn btn-primary" 
      onclick={createComment}
      disabled={loading || !newComment.trim()}
    >
      {loading ? 'Adding...' : 'Add Comment'}
    </button>
  </div>
</div>

<style>
  /* Everything here reads from the theme tokens, which already flip on
     .dark -- so the parallel light block and the :global(.dark) overrides
     this file used to carry (a full duplicate of every rule, in Bootstrap
     colors that never matched the rest of the app) are gone. */

  .comments-section {
    margin-top: var(--space-4);
    border-top: 1px solid var(--color-border);
    padding-top: var(--space-4);
  }

  .comments-title {
    margin: 0 0 var(--space-4) 0;
    font-size: var(--text-sm);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: var(--tracking-wide);
    color: var(--color-muted-foreground);
    font-family: var(--font-mono);
  }

  .comments-list {
    max-height: 300px;
    overflow-y: auto;
    margin-bottom: var(--space-4);
  }

  .comment {
    margin-bottom: var(--space-3);
    padding: var(--space-3);
    background-color: var(--color-surface);
    border-radius: var(--radius-md);
    border: 1px solid var(--color-border);
  }

  .comment-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }

  .comment-author {
    font-weight: 700;
    color: var(--color-primary);
  }

  /* Timestamps are data, so they get the mono face and tabular figures --
     which also stops the list jittering as relative times tick over. */
  .comment-time {
    font-size: var(--text-xs);
    color: var(--color-muted-foreground);
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
  }

  .comment-actions {
    margin-left: auto;
    display: flex;
    gap: var(--space-1);
  }

  .comment-action-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: var(--space-1);
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    opacity: 0.7;
    color: var(--color-muted-foreground);
    transition: opacity var(--transition-fast), background-color var(--transition-fast);
  }

  .comment-action-btn:hover {
    opacity: 1;
    background-color: var(--color-muted);
  }

  .comment-action-btn.delete:hover {
    background-color: color-mix(in srgb, var(--color-error) 15%, transparent);
    color: var(--color-error);
  }

  .comment-content {
    margin: 0;
  }

  .comment-text {
    margin: 0;
    line-height: var(--leading-normal);
    white-space: pre-wrap;
    word-wrap: break-word;
    color: var(--color-foreground);
  }

  .comment-edited {
    font-size: var(--text-xs);
    color: var(--color-muted-foreground);
    font-style: italic;
  }

  .edit-form {
    margin: 0;
  }

  .edit-textarea,
  .new-comment-input {
    width: 100%;
    padding: var(--space-2);
    background-color: var(--color-card);
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    font-family: inherit;
    font-size: var(--text-sm);
    resize: vertical;
    transition: border-color var(--transition-fast);
  }

  .edit-textarea {
    min-height: 60px;
    margin-bottom: var(--space-2);
  }

  .new-comment-input {
    min-height: 80px;
    padding: var(--space-3);
  }

  .edit-textarea:focus,
  .new-comment-input:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--color-primary) 30%, transparent);
  }

  .edit-actions {
    display: flex;
    gap: var(--space-2);
  }

  .no-comments {
    text-align: center;
    color: var(--color-muted-foreground);
    font-style: italic;
    margin: var(--space-8) 0;
  }

  .new-comment-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .btn {
    padding: var(--space-2) var(--space-4);
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition: background-color var(--transition-fast), border-color var(--transition-fast);
    align-self: flex-start;
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-primary {
    background-color: var(--color-primary);
    border-color: var(--color-primary);
    color: var(--color-primary-foreground);
  }

  .btn-primary:hover:not(:disabled) {
    background-color: color-mix(in srgb, var(--color-primary) 86%, var(--color-foreground));
    border-color: color-mix(in srgb, var(--color-primary) 86%, var(--color-foreground));
  }

  .btn-secondary {
    background-color: transparent;
    border-color: var(--color-border-strong);
    color: var(--color-foreground);
  }

  .btn-secondary:hover:not(:disabled) {
    background-color: var(--color-muted);
  }

  .btn-sm {
    padding: var(--space-1) var(--space-2);
    font-size: var(--text-xs);
  }
</style>
