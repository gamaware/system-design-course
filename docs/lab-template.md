# Lab Template Reference

Standard structure for all lab modules in this course. Every lab README should
follow these sections in order.

## Required Sections

### 1. Title and Badges

Module title as H1, followed by relevant technology badges (shields.io).

### 2. Overview

Two to three sentences describing what the lab covers and the scenario
students will work through.

### 3. Learning Objectives

Bullet list of specific skills students will gain. Start each with a verb
(configure, understand, troubleshoot, implement).

### 4. Prerequisites

What students need before starting: tools, accounts, prior labs, knowledge.

### 5. Architecture

Mermaid diagram showing the lab environment, components, and their
relationships. Use color to highlight key elements.

### 6. Lab Structure

Directory tree showing the module's file layout.

### 7. Quick Start

One-liner to launch the lab environment (typically `./setup.sh`).

### 8. Tasks

Numbered exercises that build on each other. Each task follows this pattern:

```markdown
### Task N: Descriptive Title

Brief context explaining what students will do and why.

#### Step N.1: Action description

Command to run in a fenced code block, followed by explanation of
expected output.

> **Question:** A question that reinforces understanding.
>
> **Hint:** Guidance without giving the full answer.
```

### 9. Cleanup

Steps to tear down all resources. Include both scripted and manual options.

### 10. Troubleshooting

Table or list of common issues with symptoms, causes, and fixes.

### 11. Key Concepts

Summary of important technical concepts covered in the lab. Use a table
or concise definitions.

### 12. Conclusions

Lessons learned and practical takeaways. What should students remember
beyond the specific commands they ran?

### 13. Next Steps

Links to the next module and related external resources.

## Guidelines

- Keep lines under 120 characters
- Use fenced code blocks with language identifiers
- Use placeholder values, never real credentials or IPs
- All content in English, dateless, and semester-independent
- Include expected output after commands so students can verify
- Questions should test understanding, not just command recall
