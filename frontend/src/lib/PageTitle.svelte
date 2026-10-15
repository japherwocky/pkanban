<script>
  // Sets the tab title from the route, inside <Router> where the location is.
  // Docs pages set their own once their markdown has loaded (Docs.svelte).
  import { useLocation } from 'svelte-routing';
  import { titleFor } from './pageTitle.js';

  const location = useLocation();

  $effect(() => {
    document.title = titleFor($location.pathname);
  });
</script>
