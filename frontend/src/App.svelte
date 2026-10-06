<script>
  import { onMount } from 'svelte';
  import { Router, Route } from 'svelte-routing';
  import { theme } from './lib/theme.js';

  import Landing from './routes/Landing.svelte';
  import Login from './routes/Login.svelte';
  import BoardsList from './routes/BoardsList.svelte';
  import Board from './routes/Board.svelte';
  import Organizations from './routes/Organizations.svelte';
  import Organization from './routes/Organization.svelte';
  import Admin from './routes/Admin.svelte';
  import Docs from './routes/Docs.svelte';
  import NotFound from './routes/NotFound.svelte';
  import ProtectedRoute from './lib/ProtectedRoute.svelte';
  import PublicLayout from './lib/PublicLayout.svelte';
  import Pricing from './routes/Pricing.svelte';
  import About from './routes/About.svelte';
  import Contact from './routes/Contact.svelte';
  import Privacy from './routes/Privacy.svelte';
  import Terms from './routes/Terms.svelte';
  import Settings from './routes/Settings.svelte';
  import SettingsApiKeys from './routes/SettingsApiKeys.svelte';
  import SettingsPlan from './routes/SettingsPlan.svelte';
  import PlanLimitModal from './lib/PlanLimitModal.svelte';
  import ApiKeyCreated from './routes/ApiKeyCreated.svelte';
  import Invite from './routes/Invite.svelte';
  import Signup from './routes/Signup.svelte';
  import VerifyEmail from './routes/VerifyEmail.svelte';
  import Device from './routes/Device.svelte';

  onMount(() => {
    theme.init();
  });
</script>

<Router>
  <!-- Marketing pages with Header and Footer (via PublicLayout) -->
  <Route path="/" let:params>
    <PublicLayout>
      <Landing {params} />
    </PublicLayout>
  </Route>

  <Route path="/docs" let:params>
    <PublicLayout>
      <Docs {params} />
    </PublicLayout>
  </Route>

  <Route path="/docs/:section" let:params>
    <PublicLayout>
      <Docs {params} />
    </PublicLayout>
  </Route>

  <!-- Per-command pages live at docs/commands/<name>.md -->
  <Route path="/docs/commands/:page" let:params>
    <PublicLayout>
      <Docs params={{ section: `commands/${params.page}` }} />
    </PublicLayout>
  </Route>

  <Route path="/login" let:params>
    <PublicLayout>
      <Login {params} />
    </PublicLayout>
  </Route>

  <Route path="/signup" let:params>
    <PublicLayout>
      <Signup {params} />
    </PublicLayout>
  </Route>

  <Route path="/verify" let:params>
    <PublicLayout>
      <VerifyEmail {params} />
    </PublicLayout>
  </Route>

  <!-- Approving a `pkanban login`. Handles signed-out visitors itself, like
       /invite, so a new user can sign up on the way rather than bounce. -->
  <Route path="/device">
    <PublicLayout>
      <Device />
    </PublicLayout>
  </Route>

  <Route path="/pricing" let:params>
    <PublicLayout>
      <Pricing {params} />
    </PublicLayout>
  </Route>

  <Route path="/about" let:params>
    <PublicLayout>
      <About {params} />
    </PublicLayout>
  </Route>

  <Route path="/contact" let:params>
    <PublicLayout>
      <Contact {params} />
    </PublicLayout>
  </Route>

  <Route path="/privacy" let:params>
    <PublicLayout>
      <Privacy {params} />
    </PublicLayout>
  </Route>

  <Route path="/terms" let:params>
    <PublicLayout>
      <Terms {params} />
    </PublicLayout>
  </Route>

  <!-- App pages: standalone, no Header/Footer -->
  <Route path="/boards">
    <ProtectedRoute>
      <BoardsList />
    </ProtectedRoute>
  </Route>

  <Route path="/boards/:id" let:params>
    <ProtectedRoute>
      <Board {params} />
    </ProtectedRoute>
  </Route>

  <Route path="/boards/:id/card/:cardId" let:params>
    <ProtectedRoute>
      <Board {params} />
    </ProtectedRoute>
  </Route>

  <Route path="/organizations">
    <ProtectedRoute>
      <Organizations />
    </ProtectedRoute>
  </Route>

  <Route path="/organizations/:id" let:params>
    <ProtectedRoute>
      <Organization {params} />
    </ProtectedRoute>
  </Route>

  <Route path="/admin" let:params>
    <ProtectedRoute>
      <Admin {params} />
    </ProtectedRoute>
  </Route>

  <Route path="/admin/:section" let:params>
    <ProtectedRoute>
      <Admin {params} />
    </ProtectedRoute>
  </Route>

  <Route path="/settings/api-keys/created" let:params>
    <ProtectedRoute>
      <ApiKeyCreated {params} />
    </ProtectedRoute>
  </Route>

  <Route path="/invite/:token" let:params>
    <Invite {params} />
  </Route>

  <Route path="/settings/api-keys" let:params>
    <ProtectedRoute>
      <Settings>
        <SettingsApiKeys {params} />
      </Settings>
    </ProtectedRoute>
  </Route>

  <Route path="/settings/plan">
    <ProtectedRoute>
      <Settings>
        <SettingsPlan />
      </Settings>
    </ProtectedRoute>
  </Route>

  <Route path="/settings" let:params>
    <ProtectedRoute>
      <Settings>
        <SettingsApiKeys {params} />
      </Settings>
    </ProtectedRoute>
  </Route>

  <Route path="*">
    <NotFound />
  </Route>
</Router>

<PlanLimitModal />

<style>
  :global(body) {
    margin: 0;
  }
</style>
