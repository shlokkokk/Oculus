I have a Python CLI project called Oculus. It is currently a working CLI recon/orchestration tool, and I do not want the CLI broken, rewritten, or degraded.

I want you to design and build a full web version alongside the CLI.

Important goal:
Do not make this just a landing page, documentation page, or command builder. I want a real usable web interface where users can run the tool from the browser in a friendly way, see progress/output, configure scans, choose modules/modes, and review generated results/artifacts.

Keep the existing CLI as the source of truth. The web version should call into or wrap the existing CLI/backend logic safely instead of duplicating all scan logic in the frontend. The CLI must continue working exactly as before.

Please inspect the repository carefully before choosing the architecture. Pick the stack you think is best, but keep it practical, scalable, and maintainable. I am open to React, Next.js, FastAPI, Flask, Node, or anything else if it makes sense.

What I want:
- A polished, modern, professional web UI
- No generic AI-looking design
- No sloppy alignment, random gradients, bad spacing, or fake dashboard filler
- A real operator/workspace feel
- Clean responsive layout
- Good empty/loading/error/running/completed states
- Start/stop scan controls
- Target/domain input
- Scan mode selection
- Module selection
- Runtime/config options
- Live output/log streaming
- Report/result viewing if artifacts exist
- Clear safety messaging that the tool is only for authorized testing
- Scalable structure so I can add more modules/features later
- Good README instructions for running the web version locally
- Do not include secrets or hardcoded API keys
- Do not destroy or refactor unrelated CLI code unless required

Before editing:
- Understand the existing CLI entrypoints, flags, config, modules, and output folders.
- Preserve current behavior.
- Add the web app in a separate folder or clearly separated structure.
- Use existing project naming and style where appropriate.

After building:
- Run basic verification/build checks.
- Tell me exactly how to run it.
- Summarize what changed.
- Mention any limitations or future improvements.

Be creative with the product design. I do not want a basic template. Make it feel like a serious, beautiful web cockpit for the existing CLI. make it so top tier all covering god level goated perfect okay and use icons instead of emojis if youre planning to use emojis anywhere cuz emojis are bad ui anyways and just do al covering super nice ui ux like you have full as in full full freedom in it i trust you will make this 1000x better and nicely themed but jus yeah yk