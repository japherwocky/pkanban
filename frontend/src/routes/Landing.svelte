<script>
  import HeroSection from '../components/HeroSection.svelte';
  import FeaturesSection from '../components/FeaturesSection.svelte';
  import InstallSection from '../components/InstallSection.svelte';
  import SignupCTA from '../components/SignupCTA.svelte';
</script>

<div class="landing">
  <HeroSection />

  <FeaturesSection />

  <InstallSection />

  <SignupCTA />
</div>

<style>
  .landing {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-8);
    background: var(--color-background);
  }
</style>

