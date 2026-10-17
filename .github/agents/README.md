# Multi-Agent Coding Workflow for GitHub Copilot CLI

This directory contains custom agent definitions for a **three-tier workflow** with **automatic standards discovery and caching**:

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        STRATEGIZER                              │
│  (High-level vision, requirements, standards discovery)       │
│                                                               │
│  Subagents:                                                  │
│  ├── standards-discoverer → Finds & caches project standards │
│  ├── requirements-analyzer → Extracts all requirements        │
│  └── validator → Validates strategy against requirements       │
└──────────────────────────┬────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                          PLANNER                                │
│  (All technical reasoning, exact specifications)               │
│                                                               │
│  Subagents:                                                  │
│  ├── code-analyzer → Finds exact files & line numbers         │
│  ├── spec-writer → Writes exact code specifications            │
│  └── change-planner → Sequences changes & dependencies        │
└──────────────────────────┬────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                           CODER                                │
│  (Dumb executor - applies exact specifications)                │
│                                                               │
│  Subagents:                                                  │
│  ├── code-applier → Applies exact code changes                 │
│  └── verifier → Runs validation & reports results              │
└─────────────────────────────────────────────────────────────┘
```

## Key Principles

### 1. Intelligence Distribution
- **Strategizer**: Understands WHAT needs to be done (vision, requirements)
- **Planner**: Figures out HOW to do it (all technical reasoning)
- **Coder**: Executes the exact plan (no thinking, no decisions)

### 2. Standards Discovery & Caching
- All project-specific standards are **automatically discovered** from files
- Standards are **cached** in `.github/cache/standards.json`
- Cached standards are reused for **all future sessions**
- Cache is automatically refreshed when project files change

### 3. Dumb Coder Principle
- Coder receives **exact specifications** with:
  - Exact file paths
  - Exact line numbers
  - Exact code to insert/modify/delete
  - Exact validation commands
- Coder **does not**:
  - Make decisions
  - Fix errors
  - Interpret ambiguous instructions
  - Optimize code

### 4. Technology Agnostic
- No hardcoded assumptions about:
  - Programming language (C, C++, etc.)
  - Build system (Make, CMake, etc.)
  - Testing framework
  - Coding standards
- Everything is **discovered from the project** or **asked to the user**

## Directory Structure

```
.github/
├── agents/                          # Main agents
│   ├── strategizer.agent.md        # Vision & requirements
│   ├── planner.agent.md            # Technical reasoning & specifications
│   └── coder.agent.md              # Execution
│
├── agents/strategizer/            # Strategizer subagents
│   ├── standards-discoverer.agent.md
│   ├── requirements-analyzer.agent.md
│   └── validator.agent.md
│
├── agents/planner/                # Planner subagents
│   ├── code-analyzer.agent.md
│   ├── spec-writer.agent.md
│   └── change-planner.agent.md
│
├── agents/coder/                  # Coder subagents
│   ├── code-applier.agent.md
│   └── verifier.agent.md
│
└── cache/                        # Auto-generated
    ├── .gitignore
    └── standards.json              # Cached project standards
```

## Agent Descriptions

### Main Agents

#### Strategizer
- **Role**: High-level planning and requirements understanding
- **Responsibilities**:
  - Discover and cache project standards
  - Understand user goals
  - Define success criteria
  - Identify constraints
  - Delegate to Planner
- **Model**: gpt-4o (high intelligence for understanding)
- **Subagents**: standards-discoverer, requirements-analyzer, validator

#### Planner
- **Role**: All technical reasoning and planning
- **Responsibilities**:
  - Analyze codebase to find exact locations
  - Design complete technical solution
  - Write exact code with proper formatting
  - Specify exact file paths and line numbers
  - Plan execution sequence
  - Provide complete spec to Coder
- **Model**: gpt-4o (high intelligence for reasoning)
- **Subagents**: code-analyzer, spec-writer, change-planner

#### Coder
- **Role**: Exact execution of Planner's specifications
- **Responsibilities**:
  - Apply exact file changes
  - Run exact build/test commands
  - Report exact results
- **Model**: gpt-4o-mini (lower cost, execution only)
- **Subagents**: code-applier, verifier

### Subagents

#### Strategizer Subagents
- **standards-discoverer**: Scans project files to find coding standards, build system, toolchain
- **requirements-analyzer**: Extracts and categorizes all requirements from user input
- **validator**: Validates strategy against requirements and constraints

#### Planner Subagents
- **code-analyzer**: Finds exact files, line numbers, and context for changes
- **spec-writer**: Creates exact implementation specifications with precise code
- **change-planner**: Determines optimal order of changes with dependencies

#### Coder Subagents
- **code-applier**: Applies exact code changes (create/modify/delete)
- **verifier**: Runs exact validation commands and reports results

## Usage

### Starting a Workflow

```bash
# Start with Strategizer
copilot --agent Strategizer "[your request]"

# Or use fleet for parallel execution
copilot "/fleet Use Strategizer for strategy, Planner for planning, Coder for implementation"
```

### Agent Invocation

```bash
# Explicit agent selection
copilot --agent Strategizer "Add a new CAN message handler"

# In-session agent switching
/agent Strategizer
/agent Planner
/agent Coder

# Spawn subagents (automatic)
# Strategizer will spawn: standards-discoverer, requirements-analyzer
# Planner will spawn: code-analyzer, spec-writer, change-planner
# Coder will spawn: code-applier, verifier
```

### Manual Subagent Invocation

```bash
# Directly invoke a subagent
/agent Strategizer-Standards-Discoverer
/agent Planner-Code-Analyzer
```

## Standards Discovery

The workflow automatically discovers and caches:

### Coding Standards
- Language (C, C++, etc.)
- Style guide (AUTOSAR, MISRA, Google, etc.)
- Naming conventions
- Formatting rules (indentation, braces, line length)
- Comment style (Doxygen, JavaDoc, etc.)

### Build System
- Type (Make, CMake, etc.)
- Build commands
- Clean commands
- Test commands

### Toolchain
- Compiler (gcc, clang, armcc, etc.)
- Compiler version
- Compiler flags
- C/C++ standard version

### Testing
- Test framework (Google Test, Unity, etc.)
- Coverage tools and targets
- Test commands

### Quality
- Static analysis tools
- Linting tools
- Code metrics (complexity, function length, etc.)

### Version Control
- System (git, svn, etc.)
- Workflow (git-flow, trunk-based)
- Branch naming conventions

## Communication Protocol

All agents communicate using structured JSON messages:

### Message Types

| Type | Direction | Purpose |
|------|-----------|---------|
| `requirements_handoff` | Strategizer → Planner | Complete requirements package |
| `exact_implementation_spec` | Planner → Coder | Exact changes to make |
| `execution_report` | Coder → Planner | Results of execution |
| `standards_query` | Any → User | Ask about missing standards |
| `standards_discovery_complete` | Standards-Discoverer → Strategizer | Discovered standards |

### Example Message Flow

```
User Request
    ↓
Strategizer (discovers standards, analyzes requirements)
    ↓
Planner (analyzes code, writes exact spec)
    ↓
Coder (applies changes, runs validations)
    ↓
Planner (reviews results)
    ↓
Strategizer (validates against requirements)
    ↓
User (receives final result)
```

## Workflow Example

### User Request
```bash
copilot --agent Strategizer "Add a new message handler for ID 0x123"
```

### What Happens

1. **Strategizer Phase**:
   - Checks cache for standards
   - If missing: spawns standards-discoverer
   - Spawns requirements-analyzer
   - Sends complete context to Planner

2. **Planner Phase**:
   - Spawns code-analyzer to find exact files/lines
   - Spawns spec-writer to create exact code
   - Spawns change-planner to sequence changes
   - Sends exact spec to Coder

3. **Coder Phase**:
   - Spawns code-applier to apply changes
   - Spawns verifier to run validations
   - Reports results to Planner

4. **Final Phase**:
   - Planner reviews results
   - Strategizer validates against requirements
   - Final result delivered to user

## Cache Management

### Standards Cache Location
```
.github/cache/standards.json
```

### Cache Format
```json
{
  "last_updated": "2025-10-17T10:00:00Z",
  "source": "file:README.md",
  "coding_standards": { ... },
  "build_system": { ... },
  "toolchain": { ... },
  "testing": { ... },
  "quality": { ... }
}
```

### Cache Invalidation
Cache is automatically invalidated when:
- User explicitly requests refresh
- Project files change significantly
- After configurable period (default: 30 days)

### Manual Cache Refresh
```bash
# Delete cache to force rediscovery
rm .github/cache/standards.json

# Or edit to update specific fields
```

## Customization

### Adding New Standards
Add standards to the discovery process by:
1. Creating a documentation file (e.g., `CODING_STANDARDS.md`)
2. The standards-discoverer will automatically pick it up

### Modifying Agent Behavior
Edit the `.agent.md` files to:
- Change agent instructions
- Modify subagent usage
- Adjust message formats
- Update quality standards

## Best Practices

### For AUTOSAR/C Projects
1. **Document Standards**: Ensure coding standards are documented in README or separate file
2. **Consistent Formatting**: Use `.clang-format` for consistent code formatting
3. **Build Configuration**: Document build commands in Makefile or CMakeLists.txt
4. **Test Framework**: Specify test framework and commands
5. **Static Analysis**: Document which tools are used for quality checks

### For Agent Usage
1. **Start with Strategizer**: Always begin workflow with Strategizer
2. **Let Agents Do Their Job**: Don't micromanage - agents will coordinate
3. **Review Specifications**: Planner's spec should be reviewable before Coder executes
4. **Check Cache**: Verify standards cache is up-to-date
5. **Ask for Clarification**: If output is unclear, ask the agent to explain

## File Reference

### Main Agents
- [`strategizer.agent.md`](strategizer.agent.md) - Vision and requirements
- [`planner.agent.md`](planner.agent.md) - Technical reasoning
- [`coder.agent.md`](coder.agent.md) - Execution

### Strategizer Subagents
- [`strategizer/standards-discoverer.agent.md`](strategizer/standards-discoverer.agent.md) - Standards discovery
- [`strategizer/requirements-analyzer.agent.md`](strategizer/requirements-analyzer.agent.md) - Requirements analysis
- [`strategizer/validator.agent.md`](strategizer/validator.agent.md) - Strategy validation

### Planner Subagents
- [`planner/code-analyzer.agent.md`](planner/code-analyzer.agent.md) - Code analysis
- [`planner/spec-writer.agent.md`](planner/spec-writer.agent.md) - Specification writing
- [`planner/change-planner.agent.md`](planner/change-planner.agent.md) - Change sequencing

### Coder Subagents
- [`coder/code-applier.agent.md`](coder/code-applier.agent.md) - Code application
- [`coder/verifier.agent.md`](coder/verifier.agent.md) - Validation

## Support

For issues or questions:
1. Check the standards cache for accuracy
2. Verify agent files are correctly formatted
3. Ensure Copilot CLI is up-to-date
4. Review GitHub Copilot documentation for custom agents

## Version
Initial implementation: October 17, 2025
