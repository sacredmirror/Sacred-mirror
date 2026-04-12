# Founders Brain — Query Guide

Your knowledge base lives in `/markdown/` (one file per founder) and `INDEX.json`.

## How to query it

Open this folder in Claude Code and ask anything:

**Synthesize across all founders:**
- "What are the top 10 mental models that repeat across founders?"
- "Give me every founder who dealt with bankruptcy or near-death of their company"
- "Find all founders who built in spaces that didn't exist yet"
- "Show me how different founders responded to the same type of crisis"

**Single founder deep-dives:**
- "Walk me through Charlie Munger's mental model lattice"
- "What decisions did Jeff Bezos make that are counter to conventional wisdom?"

**Pattern extraction:**
- "What operating principles appear in more than 10 founders?"
- "Which founders used inversion as a thinking tool?"
- "Find every example of a founder who was told their idea was stupid"

**Actionable extraction:**
- "Give me 5 principles I can apply tomorrow from all 229 founders"
- "What would these founders say about [your specific problem]?"

## Files

| Path | Contents |
|------|----------|
| `INDEX.json` | Master index with top insight + mental models per founder |
| `markdown/[Name].md` | Full structured profile for each founder |
| `structured/[Name].json` | Machine-readable JSON for each founder |
| `raw/[Name].txt` | Original transcript |

## Re-run / update

```bash
# First run (builds everything)
python3 founders_brain.py

# Resume after interruption
python3 founders_brain.py --resume

# Test with just 3 videos
python3 founders_brain.py --limit 3

# Save transcripts only, no Claude API needed
python3 founders_brain.py --no-llm
```

Set your API key first:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 founders_brain.py
```
