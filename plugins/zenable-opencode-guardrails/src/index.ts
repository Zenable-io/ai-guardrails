import type { Plugin } from "@opencode-ai/plugin"

/**
 * Zenable Guardrails Plugin for OpenCode
 *
 * Subscribes to tool.execute.after hook for file-editing tools and runs
 * Zenable conformance checks automatically.
 *
 * References:
 *   Plugin API: https://opencode.ai/docs/plugins/
 *   Hooks interface: anomalyco/opencode packages/plugin/src/index.ts
 *   Hook trigger: anomalyco/opencode packages/opencode/src/session/prompt.ts:822
 *   Tool IDs: anomalyco/opencode packages/opencode/src/tool/{edit,write,multiedit,apply_patch}.ts
 *   Hooks discussion: https://github.com/anomalyco/opencode/issues/1473
 *   Equivalent: Claude Code PostToolUse on Write|Edit|MultiEdit
 */

// OpenCode file-editing tool IDs (from packages/opencode/src/tool/*.ts)
const FILE_EDIT_TOOLS = new Set([
  "edit",        // Tool.define("edit", ...) in edit.ts
  "write",       // Tool.define("write", ...) in write.ts
  "multiedit",   // Tool.define("multiedit", ...) in multiedit.ts
  "apply_patch", // Tool.define("apply_patch", ...) in apply_patch.ts
])

export const ZenableGuardrails: Plugin = async ({ $ }) => {
  return {
    // tool.execute.after is a direct hook called via Plugin.trigger(), not a bus event.
    // Signature: (input: { tool: string; sessionID: string; callID: string; args: any },
    //             output: { title: string; output: string; metadata: any }) => Promise<void>
    "tool.execute.after": async (input, _output) => {
      if (!FILE_EDIT_TOOLS.has(input.tool)) return

      try {
        await $`zenable hook`
      } catch {
        // Don't block the user on hook failures
      }
    },
  }
}
