# starter-engine

The working video engine from the first Stickman Studio video (Japan in WW2, 10:55, 80 scenes).
Put this folder next to where you start Claude Code, and the prompt in
`claude-code-prompt-stickman-studio.md` tells Claude Code how to reuse it.

- engine/        reusable modules (core, props, doodle, geo, terr, audio, ttsprep) + fonts and map data
- examples/      reference files from the first video. These import the old flat module names
                 (`from props import *`, `import terr`), so treat them as examples to copy from, not as runnable code.

Licenses: Fredoka and Patrick Hand fonts are SIL OFL 1.1; world-atlas data is ISC (from Natural Earth, public domain).
