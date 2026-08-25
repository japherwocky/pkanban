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
Our voice is **Technical, Direct, and "Hard Sci-Fi."** We sound like the interface of a spaceship, not a SaaS marketing brochure.

### The Vibe
* **Esthetic:** Cyberpunk, Terminal-Chic, Dark Mode.
* **Personality:** Efficient, precise, slightly robotic but helpful.

### Voice Rules
1.  **No Fluff:** Avoid words like "Empower," "Unleash," "Revolutionize," or "Synergy."
2.  **Use Engineering Terms:** Use words like "Orchestrate," "Deploy," "Sync," "StdOut," "Pipe," "Context Window."
3.  **Show, Don't Tell:** Don't say "It's easy to use." Show the command: `pip install pkanban`.
4.  **Respect the User:** Assume the user is smart. Don't dumb down the concepts.

## 4. Copy Guidelines (Do's & Don'ts)

| **Do NOT Say** | **DO Say** | **Why?** |
| :--- | :--- | :--- |
| "Manage your projects easily." | "Orchestrate agents via CLI." | Specificity wins. |
| "We have a great API." | "Standard Input/Output Interface." | Appeals to the universal nature of CLI. |
| "Collaborate with your team." | "Hybrid Human-Agent Workflows." | Highlights the unique value prop. |
| "Sign up now!" | "Initialize Workspace." | Keeps the "Terminal" immersion. |
| "Seamless integration." | "Zero-config handshake." | "Seamless" is a marketing buzzword. |

## 5. Visual Identity Guidelines
When building UI components or generating assets, follow these strict aesthetic rules:

* **Color Palette:**
    * **Backgrounds:** Deep Slate / Void Black (`#0f172a`, `#020617`).
    * **Accents:** "Terminal Green" (`#22c55e`), "Cyber Cyan" (`#06b6d4`), or "Error Red" (`#ef4444`).
    * **Text:** High contrast white/gray.
* **Typography:**
    * **Headlines:** Monospace fonts (e.g., *JetBrains Mono*, *Fira Code*, *Roboto Mono*). This reinforces the CLI nature.
    * **Body:** Clean sans-serif (e.g., *Inter*, *System UI*) for readability.
* **UI Elements:**
    * **Buttons:** Should look like command inputs or stark, rectangular blocks. No pill shapes.
    * **Borders:** Thin, subtle borders (1px) with low opacity.
    * **Glassmorphism:** Use subtle blur effects for cards to give a modern feel.

## 6. Key Value Propositions (The "Elevator Pitch")

If you need to generate text for a new section, pick one of these three angles:

1.  **Universal Compatibility:**
    * "If your agent can print to stdout, it can use pkanban. No SDKs, no wrappers, no dependency hell."
2.  **Observability:**
    * "Turn the black box of agent execution into a visual board. Watch your agents think and act in real-time."
3.  **Human-in-the-Loop:**
    * "Agents get stuck. Humans get tired. pkanban lets you hand off tasks between biological and synthetic intelligence seamlessly."

---

*This document serves as the source of truth for all copy and design decisions. If a feature or sentence doesn't align with "Agent-Native," cut it.*
