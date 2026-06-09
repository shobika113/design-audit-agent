# Design Audit Agent

## Overview

The Design Audit Agent is an AI-powered system that automatically analyzes UI screenshots and identifies design issues based on established UI/UX design principles.

The agent evaluates screenshots across multiple design principles, generates evidence-based findings, assigns severity levels, and provides actionable recommendations to improve interface quality and usability.



## Features
* Screenshot Upload
* Design Principle Analysis
* Severity Classification
* Structured Audit Reports
* Evidence-Based Findings (Zero-Hallucination Approach)
* Side-by-Side Design Comparison
* Regression Detection
* Improvement Detection
* Comparative Reporting

---

## Design Principles Evaluated

* Visual Hierarchy
* Contrast
* Spacing
* Alignment
* Consistency
* Balance
* Emphasis
* Movement
* Pattern
* Rhythm
* Unity

---

## Architecture

```text
User Uploads Screenshot(s)
            │
            ▼
     Image Processing Layer
            │
            ▼
      Vision Analysis Engine
            │
            ▼
   Design Principle Evaluator
            │
            ▼
     Severity Classification
            │
            ▼
      Report Generation
            │
            ▼
         Streamlit UI
```

---

## Workflow

```text
Upload Screenshot
        │
        ▼
Image Processing
        │
        ▼
Vision-Based Analysis
        │
        ▼
Design Principle Evaluation
        │
        ▼
Evidence Validation
        │
        ▼
Severity Assignment
        │
        ▼
Report Generation
```

---

## Tech Stack

* Python
* Streamlit
* Vision Language Models
* JSON Reporting
* Prompt Engineering

---

## Sample Finding
<img width="1897" height="911" alt="Screenshot 2026-06-07 224434" src="https://github.com/user-attachments/assets/c264d711-ae23-4a95-b797-b5213824b437" />


<img width="1481" height="906" alt="Screenshot 2026-06-08 085531" src="https://github.com/user-attachments/assets/533705ab-865d-4d70-a5de-90943fb0a62a" />

---

## Zero-Hallucination Design

The agent follows an evidence-based analysis approach.

Every finding must be supported by visually verifiable elements present in the uploaded screenshot. The system does not generate findings based on assumptions or unavailable information.

---

## Future Improvements

* WCAG Accessibility Validation
* Confidence Scoring
* Automated Redesign Suggestions
* Multi-Screen Workflow Analysis
* Browser Extension Integration

---

## Author

Shobika
B.Tech Artificial Intelligence and Data Science
