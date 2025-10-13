---
description: Show active Zenable requirements and guardrails for this project
---

# Zenable Requirements

Display the active conformance requirements, policies, and guardrails configured for this project.

## Usage

```
/requirements
```

## What it does

1. Queries the Zenable MCP server for project-specific requirements
2. Displays:
   - Active policy rules
   - Security requirements
   - Quality standards
   - Compliance guardrails
   - Custom organizational rules
3. Shows context about why each requirement matters
4. Provides links to detailed documentation

## Example Output

```
Active Zenable Requirements:
- Security: No hardcoded credentials
- Quality: Test coverage > 80%
- Compliance: GDPR data handling
- Style: Follow Python PEP 8
```

## Implementation

Use the `mcp__zenable__get_requirements` tool to fetch and display active requirements for the current project.

**Steps:**

1. Call `mcp__zenable__get_requirements` with current project context
2. Parse and format the requirements
3. Group by category (security, quality, compliance, etc.)
4. Display in a readable format with descriptions
