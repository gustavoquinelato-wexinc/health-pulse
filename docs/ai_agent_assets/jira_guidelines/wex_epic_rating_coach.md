# AI Model Coaching Document: Jira Epic Quality Scoring for Product Innovation Velocity (ProdIV)

## 🎯 Objective

To accurately score Jira epics on a scale of **0-10**, reflecting their quality, clarity, and alignment with Product Innovation principles. This score will help teams improve their epics and provide a consistent measure for ProdIV.

## 🏗️ Core Principles for High-Quality Epics

Based on epic health coach and PI evaluation knowledge sources:

- **Value-Driven**: Clear customer and business value
- **Outcome-Oriented**: Focused on a specific, measurable outcome
- **Independent**: Can be delivered without hard dependencies on other epics (vertically sliced)
- **Well-Defined**: Clear description, scope, and robust acceptance criteria (ideally BDD-style)
- **Succinct & Clear**: Easily understood purpose and scope
- **Innovation-Focused**: Represents a new product/service or a significant enhancement, considering the delivery mechanism
- **Adherence to Standards**: Avoids anti-patterns like splitting by time, technology stack, or SDLC phase

## 📊 Scoring Scale (0-10)

### Score 0: No Information / Placeholder
- Epic description is missing, empty, or contains only placeholder text (e.g., "TBD," "New Epic")
- No discernible goal, value, or acceptance criteria

### Score 1: Minimal Information - Basic Idea
- A very brief title or a one-line, vague description
- Hints at a potential area but lacks any detail on what, why, or for whom
- No defined value, outcome, or acceptance criteria
- **Example**: "Improve user login."

### Score 2: Basic Description - Intent Stated
- A short description (1-2 sentences) stating a general intent or problem
- The "what" is vaguely mentioned, but "why" (value) and "how" (ACs) are missing
- Lacks clarity on specific outcomes or benefits
- **Example**: "Epic to make user login better because users complain it's slow."

### Score 3: Developing Description - Some Value Articulated
- Description provides some context about the problem or need
- Initial articulation of potential customer or business value, though not well-defined or measurable
- No clear acceptance criteria
- Scope is likely unclear
- **Example**: "As a user, I want to log in faster so I don't get frustrated. This will improve user satisfaction."

### Score 4: Fair Description - Clearer Value, Lacks ACs
- The epic description clearly outlines the problem and the target user
- A reasonable attempt to define customer and/or business value, though it might lack measurable metrics
- Missing formal or robust acceptance criteria
- Basic scope may be understood, but boundaries are not sharp
- **Example**: "As a frequent online shopper, I want a streamlined login process (e.g., saved username, biometric option) to reduce login time by 50% and decrease cart abandonment. This will improve user satisfaction and potentially increase conversion rates."

### Score 5: Good Foundation - Core Value & Scope Clear, Basic ACs Emerge
- Clear problem statement, target user, and defined primary value proposition (customer and business)
- Measurable success metrics for the value are attempted or partially present
- Initial, high-level acceptance criteria are present, though they may not be fully testable or cover all scenarios (e.g., not yet in BDD format)
- The epic is largely independent but dependencies might not be fully identified or mitigated
- **Example**: (Building on Score 4) Adds: "AC1: User can log in with saved username. AC2: User can log in using biometrics. AC3: Login time is under 3 seconds."

### Score 6: Solid Epic - Good Value, Scope, and Developing ACs
- Well-defined problem, user, and clearly articulated, measurable customer and business value
- Scope is reasonably well-defined and appears independent
- Acceptance criteria are present and cover main scenarios, starting to look like testable conditions (perhaps some BDD elements emerging)
- No obvious anti-patterns (like horizontal slicing)

### Score 7: Very Good Epic - Strong Value, Detailed ACs, Innovation Hinted
- All elements of Score 6 are met to a higher standard
- Acceptance criteria are detailed, clear, testable, and likely cover positive/negative paths (good candidates for BDD)
- Clear evidence that this is a new product/service or a significant enhancement
- Consideration for how the product/service is delivered is mentioned or implied
- The epic seems well-aligned with the "Definition of Ready" principles for its stage

### Score 8: Excellent Epic - Meets Most ProdIV Criteria
- Compelling customer and business value, with clear, measurable outcomes
- Clearly independent and vertically sliced
- Robust, comprehensive, and testable acceptance criteria, ideally in BDD format ("Given/When/Then")
- Explicitly addresses a customer need/pain point AND contributes to strategic business goals
- Clearly a new product/service or a significant enhancement, with delivery aspects considered
- No anti-patterns. Adheres to good agile work decomposition principles

### Score 9: Outstanding Epic - Fully ProdIV Compliant, Minor Polish Possible
- All criteria for Score 8 are exceptionally well met
- The epic is a model example of a Product Innovation
- The value proposition is strong, and impact is clearly articulated
- Acceptance criteria are exemplary – comprehensive, unambiguous, and perfectly formatted for BDD
- All aspects of the "Epic Health Coach" definition of a "good epic" and "Product Innovation" are clearly evident
- Any improvements would be very minor (e.g., slight wording refinements)

### Score 10: Perfect Epic - Exemplar of Product Innovation
- Flawlessly meets all criteria for a Score 9
- The epic is perfectly defined, leaving no room for ambiguity
- It clearly articulates a significant, valuable, and innovative change for both the customer and the business
- Serves as a benchmark for other epics

## 📈 Weighting Based on Epic Status (Increasing Rigor)

The AI should apply increasing levels of scrutiny as an epic progresses through its lifecycle. An epic that is "good enough" for the Backlog may not be "good enough" once it's "In Progress."

### Backlog
- **Focus**: Core idea, problem statement, initial value proposition
- **Expected Scores**: 2-5. A Score 5 here would mean a good description, clear problem/user, and some thought on value and high-level scope. Detailed ACs are not expected
- **Rigor**: Lowest. The goal is to capture ideas and potential value

### Refinement
- **Focus**: Clarifying value (customer/business), defining scope more sharply, beginning to draft acceptance criteria, identifying potential dependencies
- **Expected Scores**: 4-7. To reach a 6-7, the epic should have clearly defined value, measurable outcomes becoming apparent, and initial (possibly BDD-style) acceptance criteria
- **Rigor**: Moderate. The epic should be solidifying and meeting more "Definition of Ready" criteria

### To Do (Ready for Development)
- **Focus**: Epic should be fully defined, meeting the team's "Definition of Ready." This implies clear, testable acceptance criteria, defined scope, and value
- **Expected Scores**: 6-9. A Score below 6 should be a flag. Epics here should have robust ACs and clearly demonstrate their value and independence
- **Rigor**: High. The team is about to commit to building this. Ambiguity should be minimal

### In Progress
- **Focus**: This is the most critical stage for epic quality as active development is underway. The epic must be well-defined
- **Expected Scores**: 7-10. An epic "In Progress" scoring below 7 indicates a potential problem (e.g., scope creep, misunderstood requirements, poor initial definition)
- **Rigor**: Very High. The definition should be stable and guiding development accurately. Changes should be managed formally

### Ready for QA Testing / Ready for Prod
- **Focus**: The epic should represent a completed, valuable, and innovative increment that has met its acceptance criteria
- **Expected Scores**: 8-10. The epic (and the work it represents) should fully embody the principles of a Product Innovation. A score below 8 at this stage suggests that what was delivered might not have fully met the initial ProdIV intent or quality bar
- **Rigor**: Highest. The epic serves as a record of what was achieved and its innovative value

## 🔍 Guidance for AI Assessment

When assessing, explicitly check for elements like:
- **Problem Statement**
- **User Persona** (if applicable)
- **Customer Value**
- **Business Value**
- **Measurable Outcomes/KPIs**
- **Acceptance Criteria** (and their format/testability)
- **Independence**
- **Adherence to ProdIV principles** (new/enhanced, delivery)

### Red Flags
Pay attention to keywords that indicate missing information (e.g., "TBD," "clarify," "discuss") which might lower the score, especially in later statuses.

### Green Flags
Conversely, look for strong indicators of BDD ("Given/When/Then") or clear metrics to support higher scores.
