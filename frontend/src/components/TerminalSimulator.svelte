<script>
  import { onMount, onDestroy } from 'svelte';
  import { executeCommand, getDemoState } from '$lib/demoApi';

  // Demo command sequence - uses actual CLI syntax.
  //
  // The card id has to match what `card create` actually returns against
  // demoApi's initial state, which seeds cards 1-3 and so hands out 4. These
  // referenced card 12, which never existed: both update commands failed with
  // "Card 12 not found" on every run.
  const DEMO_COMMANDS = [
    'pkanban board get 1',
    'pkanban card create 1 "Fix API latency"',
    'pkanban card update 4 "Fix API latency" --column 2',
    'pkanban card update 4 "Fix API latency" --description "Optimize DB queries"'
  ];

let displayedText = '';
let currentLineIndex = 0;
let currentCharIndex = 0;
let isPaused = false;
let showOutput = false;
let outputLines = [];
let commandHistory = [];
let animationFrame;
let timeoutId;
let currentCommand = '';
let isResetting = false;

const TYPING_SPEED = 40;
const PAUSE_AFTER_COMMAND = 1500;
const PAUSE_BETWEEN_LINES = 300;
const RESET_PAUSE = 2000; // Longer pause during reset to make it more noticeable

  function typeCharacter() {
    if (currentLineIndex >= DEMO_COMMANDS.length) {
      // Reset after completing all commands
      setTimeout(resetAnimation, PAUSE_AFTER_COMMAND);
      return;
    }

    currentCommand = DEMO_COMMANDS[currentLineIndex];

    if (currentCharIndex < currentCommand.length) {
      displayedText = currentCommand.substring(0, currentCharIndex + 1);
      currentCharIndex++;
      animationFrame = setTimeout(typeCharacter, TYPING_SPEED + Math.random() * 20);
    } else {
      // Command complete - execute it
      showOutput = true;
      const result = executeCommand(currentCommand);
      // demoApi returns stderr instead of stdout on a failed command, so
      // reading .stdout unconditionally threw a TypeError and killed the
      // animation. Show whichever the command produced.
      const output = result.stdout ?? result.stderr ?? '';
      outputLines = output.split('\n');
      commandHistory = [...commandHistory, {
        command: currentCommand,
        output,
        exitCode: result.exitCode
      }];

      isPaused = true;
      timeoutId = setTimeout(() => {
        isPaused = false;
        showOutput = false;
        currentLineIndex++;
        currentCharIndex = 0;
        displayedText = '';
        // Dispatch state update for KanbanDemo
        window.dispatchEvent(new CustomEvent('demo-state-update', {
          detail: { state: getDemoState() }
        }));
        timeoutId = setTimeout(typeCharacter, PAUSE_BETWEEN_LINES);
      }, PAUSE_AFTER_COMMAND);
    }
  }

function resetAnimation() {
  // Prevent multiple resets
  if (isResetting) return;
  isResetting = true;
  
  // Show a visual indication that we're resetting
  displayedText = '[RESETTING DEMO...]';
  isPaused = true;
  
  // Reset demo state
  executeCommand('reset');
  window.dispatchEvent(new CustomEvent('demo-state-update', {
    detail: { state: getDemoState() }
  }));
  
  // Wait a bit longer during reset to make it noticeable
  timeoutId = setTimeout(() => {
    // Reset to beginning of demo
    currentLineIndex = 0;
    currentCharIndex = 0;
    displayedText = '';
    commandHistory = [];
    isPaused = false;
    showOutput = false;
    outputLines = [];
    isResetting = false;
    
    // Start typing again
    timeoutId = setTimeout(typeCharacter, PAUSE_BETWEEN_LINES);
  }, RESET_PAUSE);
}

  onMount(() => {
    timeoutId = setTimeout(typeCharacter, 800);
  });

  onDestroy(() => {
    if (animationFrame) clearTimeout(animationFrame);
    if (timeoutId) clearTimeout(timeoutId);
  });
</script>

<div class="terminal-window">
  <div class="terminal-header">
    <div class="window-controls">
      <span class="control close"></span>
      <span class="control minimize"></span>
      <span class="control maximize"></span>
    </div>
    <div class="terminal-title">Terminal — zsh</div>
  </div>
  <div class="terminal-content">
    {#each commandHistory as entry}
      <div class="command-entry">
        <div class="command-line">
          <span class="prompt">➜  ~</span>
          <span class="command">{entry.command}</span>
        </div>
        <pre class="output {entry.exitCode !== 0 ? 'error' : ''}">{entry.output}</pre>
      </div>
    {/each}

    <div class="command-line">
      <span class="prompt">➜  ~</span>
      <span class="command">{displayedText}</span>
      <span class="cursor" class:hidden={isPaused}></span>
    </div>

    {#if showOutput && outputLines.length > 0}
      <pre class="output">{outputLines.join('\n')}</pre>
    {/if}
  </div>
</div>

<style>
  .terminal-window {
    width: 100%;
    height: 100%;
    min-height: 280px;
    background: var(--color-code-bg);
    border-radius: var(--radius-xl);
    overflow: hidden;
    box-shadow: var(--shadow-lg);
    border: 1px solid var(--color-border);
  }

  .terminal-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-4);
    background-color: var(--color-surface);
    border-bottom: 1px solid var(--color-border);
  }

  .window-controls {
    display: flex;
    gap: var(--space-2);
  }

  .control {
    width: 12px;
    height: 12px;
    border-radius: 50%;
  }

  .control.close { background: var(--color-error); }
  .control.minimize { background: var(--color-warning); }
  .control.maximize { background: var(--color-success); }

  .terminal-title {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin-left: auto;
    margin-right: auto;
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
  }

  .terminal-content {
    padding: var(--space-4) var(--space-5);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    line-height: 1.5;
    color: var(--color-code-fg);
    overflow-y: auto;
    max-height: calc(100% - 50px);
  }

  .command-entry {
    margin-bottom: var(--space-2);
  }

  .command-entry:last-of-type {
    margin-bottom: 0;
  }

  .command-line {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
  }

  .prompt {
    color: var(--color-success);
    margin-right: var(--space-2);
    font-weight: 600;
  }

  .command {
    color: var(--color-code-fg);
  }

  .output {
    margin: var(--space-1) 0 var(--space-2) var(--space-6);
    color: var(--color-muted-foreground);
    font-size: var(--text-sm);
    white-space: pre-wrap;
    line-height: 1.4;
  }

  .output.error {
    color: var(--color-error);
  }

  .cursor {
    display: inline-block;
    width: 8px;
    height: 18px;
    background: var(--color-success);
    margin-left: 2px;
    animation: blink 1s step-end infinite;
    vertical-align: middle;
  }

  .cursor.hidden {
    opacity: 0;
  }

  @keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
  }

  @media (max-width: 768px) {
    .terminal-window {
      min-height: 200px;
    }

    .terminal-content {
      font-size: var(--text-sm);
      padding: var(--space-3) var(--space-4);
    }

    .output {
      margin-left: var(--space-5);
      font-size: var(--text-xs);
    }
  }
</style>
