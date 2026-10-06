<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';

  let { children } = $props();
  let authChecked = $state(false);
  let isAuthenticated = $state(false);

  onMount(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      // With the query string: /device?code=... must come back with its code.
      const currentPath = window.location.pathname + window.location.search;
      localStorage.setItem('redirectPath', currentPath);
      navigate('/login', { replace: true });
    } else {
      authChecked = true;
      isAuthenticated = true;
    }
  });
</script>

{#if authChecked && isAuthenticated}
  {@render children()}
{/if}
