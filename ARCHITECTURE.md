# 🦾 Full-Stack Agent Team Architecture

## Overview

A multi-agent system for full-stack web + algorithm development, orchestrated by a PM agent.

## Team Structure

```
                 ┌─────────────┐
                 │   🎯 PM     │
                 │  (Orchestrator)
                 └──────┬──────┘
          ┌──────────────┼──────────────┐
          │              │              │
    ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
    │ 🎨 Frontend│ │ ⚙️ Backend │ │ 🧪 Algo    │
    │ Engineer   │ │ Engineer  │ │ Engineer   │
    └───────────┘ └───────────┘ └───────────┘
          │              │              │
          └──────────────┼──────────────┘
                   ┌─────▼─────┐
                   │ 🔧 DevOps  │
                   └───────────┘
```

## Agent Roles

### 🎯 PM Agent (`pm-agent`)
- **Entry point** for all development requests
- Analyzes requirements → breaks into tasks → routes to specialists
- Tracks progress and synthesizes outputs
- **Model**: thinking-heavy (DeepSeek V4 Flash or stronger)
- **Skills**: task breakdown, code review coordination, requirement analysis

### 🎨 Frontend Engineer (`fe-agent`)
- **Stack**: HTML5, CSS3, JavaScript/TypeScript, React/Vue, Tailwind
- **Scope**: UI components, pages, state management, responsive design
- **Model**: coding-optimized
- **Skills**: component architecture, styling, browser APIs

### ⚙️ Backend Engineer (`be-agent`)
- **Stack**: Node.js/Python, Express/FastAPI, SQL/NoSQL, REST/GraphQL
- **Scope**: API design, database schema, auth, business logic
- **Model**: coding-optimized
- **Skills**: server architecture, data modeling, security patterns

### 🧪 Algorithm Engineer (`algo-agent`)
- **Stack**: Python, PyTorch/TF, NumPy, ML pipelines
- **Scope**: Model training, data preprocessing, inference APIs, evaluation
- **Model**: reasoning-heavy
- **Skills**: ML/DL, data analysis, optimization, math

### 🔧 DevOps/Infra Agent (`devops-agent`)
- **Stack**: Docker, Docker Compose, CI/CD, nginx, cloud
- **Scope**: Deployment config, containerization, monitoring, scaling
- **Model**: general-purpose
- **Skills**: infrastructure as code, container orchestration, CI/CD pipelines

## Communication Flow

1. User → **PM Agent**: Project requirements
2. PM Agent → **Specialists**: Task breakdown via `sessions_send`
3. Specialists → PM Agent: Code/design deliverables
4. PM Agent → **DevOps Agent**: Deployment config
5. DevOps Agent: Deploy & verify

## Shared Context

- All agents share access to `/home/pz04-a-001/.openclaw/workspace/AnyDocConverter/`
- Each agent writes to its own role directory
- PM agent coordinates via sub-agent spawning
