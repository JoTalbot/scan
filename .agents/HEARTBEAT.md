# Agent Heartbeat

## Purpose
Shared state for parallel AI agents and machines.

## Required updates
Every agent must update this file or create a dated log entry before and after work.

## Current Status
- Agent: github-actions-nonstop-scan
- State: initialized
- Last heartbeat: automatic

## Fields
- agent_id
- machine
- task
- current_step
- started_at
- completed_at
- blockers
- next_action

## Rules
1. Never overwrite another agent's active task.
2. Read current state before starting work.
3. Save progress after every significant step.
4. Convert useful discoveries into reusable skills.
