#!/bin/bash
# Validate plugin structure and schema compliance

set -e

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../plugins/zenable-guardrails" && pwd)"

echo "Validating Zenable plugin structure..."

# Check required files exist
required_files=(
  ".claude-plugin/plugin.json"
  ".mcp.json"
  "hooks/hooks.json"
)

for file in "${required_files[@]}"; do
  if [ ! -f "$PLUGIN_ROOT/$file" ]; then
    echo "❌ Missing required file: $file"
    exit 1
  fi
  echo "✓ Found: $file"
done

# Check required directories exist
required_dirs=(
  "commands"
  "agents"
  "hooks"
)

for dir in "${required_dirs[@]}"; do
  if [ ! -d "$PLUGIN_ROOT/$dir" ]; then
    echo "❌ Missing required directory: $dir"
    exit 1
  fi
  echo "✓ Found directory: $dir"
done

# Validate JSON files
for json_file in .claude-plugin/plugin.json .mcp.json hooks/hooks.json; do
  if ! python3 -m json.tool "$PLUGIN_ROOT/$json_file" > /dev/null 2>&1; then
    echo "❌ Invalid JSON in $json_file"
    exit 1
  fi
  echo "✓ Valid JSON: $json_file"
done

# Check plugin.json has required fields
if ! grep -q '"name"' "$PLUGIN_ROOT/.claude-plugin/plugin.json"; then
  echo "❌ plugin.json missing required 'name' field"
  exit 1
fi

# Count commands and agents
command_count=$(find "$PLUGIN_ROOT/commands" -name "*.md" | wc -l)
agent_count=$(find "$PLUGIN_ROOT/agents" -name "*.md" | wc -l)

echo ""
echo "Plugin structure validation passed!"
echo "  Commands: $command_count"
echo "  Agents: $agent_count"
echo ""
echo "You can now install this plugin with:"
echo "  /plugin marketplace add Zenable-io/ai-guardrails"
echo "  /plugin install zenable-guardrails@claude-plugins"
