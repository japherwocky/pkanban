# MARKETING.md

## 1. The Core Philosophy
**pkanban is not "just another Kanban board."**
It is the **Shared Memory Layer** between a person and the AI that works for them.

### The "Why"
* **The Problem:** People now hand real work to AI agents -- Claude Code, Codex, opencode and the like. The agent works in a scrolling chat or a terminal: you can't see its plan at a glance, you lose track of what it finished, and it forgets all of it when the session ends. Existing tools (Jira, Trello) are too heavy, require complex OAuth, and have messy DOMs that agents struggle to read.
* **The Solution:** A Kanban board the agent can read and update on its own.
    * **For Humans:** A fast, readable web board -- what's planned, what's in progress, what's done.
    * **For Agents:** A command (`pkanban card move`) it can run with no SDK, no plugin, and nobody writing integration code.

## 2. Positioning & Audience

*(Revised 2026-10-04: the primary audience used to be "AI Engineers, LLM
researchers, and developers building autonomous workflows," and the hero said
"If your agent can print to stdout, it can use pkanban." A good line for
engineers -- and the person we're actually for has no idea what stdout is.)*

* **Primary Audience:** People who get work done through an AI agent app --
  Claude Code, Codex, opencode, Cursor -- and are not necessarily engineers.
  They're comfortable telling an AI what to do; they may never have opened a
  terminal outside of one. Smart, not technical.
* **Secondary Audience:** Developers and AI engineers. They'll get it either
  way, and the docs and the CLI's own `--help` are written for them.
* **The Hook:** "Give your AI a to-do list you can both see."
* **Setup is one sentence.** The visitor doesn't install anything. They paste
  *"Install pkanban and use it to track your work."* into their AI, which
  installs pkanban and asks them to sign in. Lead with that sentence, not with
  `pip install pkanban`.
* **Only promise where it works.** pkanban works in any AI that can run
  commands. The ChatGPT and Claude *chat windows* can't, so never name
  "ChatGPT" or "Claude" bare -- name the agent apps (Claude Code, Codex). The
  less technical the reader, the likelier they are to try it in the chat
  window first, and that's a bad first five minutes. This changes only if
  pkanban ships an MCP connector.

## 3. Brand Voice & Tone
Our voice is **dry, concrete, and technically load-bearing.** We sound like a
colleague who knows the codebase -- not a SaaS brochure, and not a mascot
doing a bit.

*(Revised 2026-09-06: the previous version of this section called for "Hard
Sci-Fi," "the interface of a spaceship," and "slightly robotic." The shipped
product never sounded like that -- see `routes/About.svelte`'s mascot note --
and forcing "robotic" onto a brand with a mascot was actively fighting itself.
This section now describes the voice the product actually uses.)*

### The Vibe
* **Aesthetic:** Terminal-native, not cyberpunk -- see Visual Identity below
  for why the background is a *warm* black rather than blue-violet near-black.
  Restrained, not maximalist. Themeable: the product runs in light mode too,
  so "dark mode" isn't the aesthetic, "terminal" is.
* **Personality:** Precise, a little dry, occasionally funny. Humor is
  allowed -- encouraged, even -- but it never announces itself. A joke that
  has to explain itself has already failed. The old hero line is still the
  best example: *"If your agent can print to stdout, it can use pkanban. No
  SDKs, no wrappers, no dependency hell."* "No dependency hell" is a joke. It
  doesn't pause to point at itself. (It left the hero for its audience, not
  its tone -- see section 2.)

### Voice Rules
1.  **No Fluff:** Avoid words like "Empower," "Unleash," "Revolutionize," or "Synergy."
2.  **Use the Reader's Words, Not Ours:** "Your AI," "run a command," "board,"
    "card," "sign in." Not "stdout," "pipe," "SDK," "CLI," or "orchestrate" --
    not in a headline, anyway. Engineering terms belong in the docs and in
    `--help`, where the reader came looking for them.
3.  **Show, Don't Tell:** Don't say "It's easy to set up." Show the sentence
    they paste into their AI.
4.  **Respect the User:** Assume the user is smart. Don't dumb down the
    concepts. Smart isn't the same as technical: explain what it does for
    them, not how it's wired.
5.  **State the joke once.** If a bit needs a second sentence to land, or a
    third callback later on the same page, cut it down to the one telling
    that actually works.

## 4. Copy Guidelines (Do's & Don'ts)

| **Do NOT Say** | **DO Say** | **Why?** |
| :--- | :--- | :--- |
| "Manage your projects easily." | "Give your AI a to-do list you can both see." | Specificity wins. |
| "Orchestrate agents via CLI." | "Your AI moves the cards as it works." | Say what happens, not how it's plumbed. |
| "Standard Input/Output Interface." | "Works with any AI that can run commands." | The reader knows what their AI can do. They don't know what stdout is. |
| "Works with ChatGPT." | "Works with Claude Code, Codex, opencode." | Only name places it actually works -- see section 2. |
| "Initialize Workspace." | "Create your account." | Terminal role-play reads as a barrier to someone who has never used one. |
| "Seamless integration." | "Paste one sentence into your AI." | "Seamless" is a buzzword. The sentence is the proof. |

*(Revised 2026-10-04: "Orchestrate agents via CLI," "Standard Input/Output
Interface" and "Initialize Workspace" used to be in the right-hand column.
Some pages still say them -- that's drift to fix, not precedent to follow.)*

## 5. Visual Identity Guidelines
This section describes what actually shipped in `frontend/src/theme.css`, not
an earlier plan that was abandoned when the product moved onto the
pearachute brand. **theme.css is the source of truth** for exact values and
the reasoning behind them (contrast ratios, why the black is warm instead of
blue-violet); this section is the summary. When the two disagree, theme.css
wins.

* **Logo:** The pearachute logo -- a pear under a parachute, so it's the "p"
  -- unmodified apart from cropping, in `frontend/src/assets/logo.svg`. That
  one file is the `Logo` component, the favicon and the source for the PNG
  icons and OG image in `frontend/public/`. It's a self-contained disc with
  its own outline, so it's never recolored per theme.
* **Color Palette:**
    * **Backgrounds:** Warm black (`#231f20`), keyed to the pearachute logo
      rather than a blue-violet near-black -- it's meant to read as a
      terminal, not a dark-mode SaaS dashboard.
    * **Accents:** Pear cyan (`#63cdf5`) and pear green (`#42ba3b`) -- the
      brand's own colors, not a generic cyberpunk palette. Light mode uses
      AA-corrected darker variants (`#0b6c91`, `#277322`) rather than the raw
      brand hex: the pale cyan is roughly 1.8:1 as text on a light
      background, well under the 4.5:1 AA floor.
    * **Text:** Warm off-white (`#f2efec`) on dark, warm near-black
      (`#231f20`) on light. Never pure `#fff` or `#000` -- both buzz against
      the warm surfaces.
* **Typography:**
    * **Both faces are Ubuntu:** Ubuntu for headlines and body, Ubuntu Mono
      for data -- ids, counts, timestamps, code, CLI output. Mono marks data,
      not decoration; a headline set in Ubuntu Mono is not the house style.
    * *(Decided 2026-09-07: keeping Ubuntu. It's the warm, humanist choice
      that suits a mascot-led brand, not the colder, more clinical aesthetic
      an earlier draft of this document asked for -- see the "hard sci-fi"
      note above. Still routed through tokens, so this can change without a
      rewrite if the brand direction ever does.)*
* **UI Elements:**
    * **Buttons:** Rectangular, never pill-shaped.
    * **Borders:** Thin (1px), carrying the separation work a shadow would
      do elsewhere -- deliberately tighter corners than earlier drafts ran,
      since a soft-rounded card reads as generic SaaS.
    * **Shadow:** A last resort, reserved for things that genuinely float
      above the page -- modals, dropdowns, a card mid-drag. Not used for
      routine separation.
    * No glassmorphism, no blur. It never shipped, and it isn't the
      direction: a terminal-native UI uses borders, not frosted glass.

## 6. Key Value Propositions (The "Elevator Pitch")

If you need to generate text for a new section, pick one of these four angles:

1.  **Works With Your AI:**
    * "Give your AI a to-do list you can both see. Works with Claude Code, Codex, opencode, or any AI that can run commands."
    * "If your AI can run a command, it can use pkanban."
2.  **Visibility:**
    * "See what your AI is working on, what it finished, and what it's stuck on -- without scrolling back through the chat."
3.  **Memory:**
    * "Your AI forgets between chats. The board doesn't."
4.  **Human-in-the-Loop:**
    * "Agents get stuck. Humans get tired. pkanban lets you hand off tasks between biological and synthetic intelligence -- no status meeting required."

---

*This document serves as the source of truth for all copy and design decisions. If a feature or sentence doesn't align with "Agent-Native," cut it. If a sentence on a public page only makes sense to someone who already uses a terminal, rewrite it.*
