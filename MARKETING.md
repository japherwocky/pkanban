# MARKETING.md

## 1. The Core Philosophy
**pkanban is not "just another Kanban board."**
It is the **Shared Memory Layer** for hybrid teams of Humans and AI Agents.

### The "Why"
* **The Problem:** AI Agents (like AutoGPT, CrewAI, custom scripts) are becoming autonomous workers. But they currently work in "black boxes" (terminals). You can't see their plan, and you can't easily intervene without stopping them. Existing tools (Jira, Trello) are too heavy, require complex OAuth, and have messy DOMs that agents struggle to read.
* **The Solution:** A Kanban board that treats the **Command Line Interface (CLI)** as a first-class citizen.
    * **For Humans:** It’s a fast, beautiful web dashboard to track progress.
    * **For Agents:** It’s a simple CLI command (`pkanban card move`) that lets them report status instantly using standard IO.

## 2. Positioning & Audience
We are pivoting from "A Dev Tool" to **"The Agent-Native Orchestration Layer."**

* **Primary Audience:** AI Engineers, LLM researchers, and developers building autonomous workflows.
* **Secondary Audience:** Power-user developers who hate leaving the terminal.
* **The Hook:** "Stop parsing logs to see what your agent is doing. Give it a board."

## 3. Brand Voice & Tone
Our voice is **dry, concrete, and technically load-bearing.** We sound like a
colleague who knows the codebase -- not a SaaS brochure, and not a mascot
doing a bit.

*(Revised 2026-09-06: the previous version of this section called for "Hard
Sci-Fi," "the interface of a spaceship," and "slightly robotic." The shipped
product never sounded like that -- see `routes/About.svelte`'s pteranodon --
and forcing "robotic" onto a brand with a mascot was actively fighting itself.
This section now describes the voice the product actually uses.)*

### The Vibe
* **Aesthetic:** Terminal-native, not cyberpunk -- see Visual Identity below
  for why the background is a *warm* black rather than blue-violet near-black.
  Restrained, not maximalist. Themeable: the product runs in light mode too,
  so "dark mode" isn't the aesthetic, "terminal" is.
* **Personality:** Precise, a little dry, occasionally funny. Humor is
  allowed -- encouraged, even -- but it never announces itself. A joke that
  has to explain itself has already failed. The model line is in section 6:
  *"If your agent can print to stdout, it can use pkanban. No SDKs, no
  wrappers, no dependency hell."* "No dependency hell" is a joke. It doesn't
  pause to point at itself.

### Voice Rules
1.  **No Fluff:** Avoid words like "Empower," "Unleash," "Revolutionize," or "Synergy."
2.  **Use Engineering Terms:** Use words like "Orchestrate," "Deploy," "Sync," "StdOut," "Pipe," "Context Window."
3.  **Show, Don't Tell:** Don't say "It's easy to use." Show the command: `pip install pkanban`.
4.  **Respect the User:** Assume the user is smart. Don't dumb down the concepts.
5.  **State the joke once.** If a bit needs a second sentence to land, or a
    third callback later on the same page, cut it down to the one telling
    that actually works.

## 4. Copy Guidelines (Do's & Don'ts)

| **Do NOT Say** | **DO Say** | **Why?** |
| :--- | :--- | :--- |
| "Manage your projects easily." | "Orchestrate agents via CLI." | Specificity wins. |
| "We have a great API." | "Standard Input/Output Interface." | Appeals to the universal nature of CLI. |
| "Collaborate with your team." | "Hybrid Human-Agent Workflows." | Highlights the unique value prop. |
| "Sign up now!" | "Initialize Workspace." | Keeps the "Terminal" immersion. |
| "Seamless integration." | "Zero-config handshake." | "Seamless" is a marketing buzzword. |

## 5. Visual Identity Guidelines
This section describes what actually shipped in `frontend/src/theme.css`, not
an earlier plan that was abandoned when the product moved onto the
pearachute brand. **theme.css is the source of truth** for exact values and
the reasoning behind them (contrast ratios, why the black is warm instead of
blue-violet); this section is the summary. When the two disagree, theme.css
wins.

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

If you need to generate text for a new section, pick one of these three angles:

1.  **Universal Compatibility:**
    * "If your agent can print to stdout, it can use pkanban. No SDKs, no wrappers, no dependency hell."
2.  **Observability:**
    * "Turn the black box of agent execution into a visual board. Watch your agents think and act in real-time."
3.  **Human-in-the-Loop:**
    * "Agents get stuck. Humans get tired. pkanban lets you hand off tasks between biological and synthetic intelligence -- no status meeting required."

---

*This document serves as the source of truth for all copy and design decisions. If a feature or sentence doesn't align with "Agent-Native," cut it.*
