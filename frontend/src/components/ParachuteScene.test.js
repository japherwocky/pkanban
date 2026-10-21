import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, waitFor } from '@testing-library/svelte';
import ParachuteScene from './ParachuteScene.svelte';

// jsdom has no WebGL, which is exactly the case worth pinning: a browser
// without it must get the page around the scene, unchanged, and no error.
describe('ParachuteScene without WebGL', () => {
  afterEach(() => vi.restoreAllMocks());

  it('holds its space while loading, then removes itself quietly', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});

    const { container } = render(ParachuteScene, { props: { height: '400px' } });
    const scene = container.querySelector('.parachute-scene');
    expect(scene).toBeInTheDocument();
    expect(scene.style.height).toBe('400px');
    expect(scene.getAttribute('role')).toBe('img');

    await waitFor(() => expect(container.querySelector('.parachute-scene')).toBeNull(), {
      timeout: 10000,
    });
    expect(console.warn).toHaveBeenCalledWith('Parachute scene unavailable:', expect.anything());
  });
});
