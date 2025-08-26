# Work Decomposition Guide

**Tips for breaking down work to "small enough"**

## 📚 Learning Path Overview

1. **From Roadmap to User Story** - Aligning priorities and breaking down work
2. **Work Decomposition** - Effective breakdown into manageable units  
3. **Behavior Driven Development** - Collaborative process for defining behaviors
4. **Task Decomposition** - Breaking stories into development tasks
5. **Contract Driven Development** - Defining contracts between dependencies
6. **Defining Product Goals** - Turning vision into measurable objectives
7. **Definition of Ready** - Criteria for when work is ready to begin
8. **Spikes** - Exploration of potential solutions for uncertain work
9. **Story Slicing** - Splitting large stories into smaller deliveries

## 🎯 Why Reduce Batch Size?

Reducing the batch size of delivered work is one of the most important things we can do to drive improved workflow, quality, and outcomes. Here's why:

- **Fewer Assumptions**: We have fewer assumptions in acceptance criteria because we had to define how to test them. The act of defining them as tests brings out questions: "How can we validate that?"

- **Less Hope Creep**: We are less subject to hope creep. We can tell within a day that we bit off more than we thought and can communicate that.

- **Easier Pivoting**: When we deliver and discover the story was wrong, we've invested less in money, time, and emotional attachment so we can easily pivot.

- **Predictability**: It makes us predictable

- **Resets Perspective**: It helps to reset our brains on what "small" is. What many people consider small turns out to be massive once they see what small really is.

---

## 1️⃣ From Roadmap to User Story

**A guide to aligning priorities and breaking down work across multi-team products**

Aligning priorities across multi-team products can be challenging. This guide outlines how to effectively break down work from program-level roadmaps to team-level user stories.

### Program Roadmap

> **Key Point**: Establishing and understanding goals and priorities is crucial for an effective work breakdown process.

- Stakeholders and leadership teams must define high-level initiatives and their priorities
- Work can then be dispersed among product teams
- Leadership teams can be composed of a core group of product owners

### Product Roadmap

The program roadmap should break down into the product roadmap, which includes the prioritized list of epics for each product.

### Product Vision

The leadership team should define:
- **Product vision**
- **Roadmap** 
- **Dependencies** for each product

### Team Backlog

The team backlog should comprise the prioritized epics from the product roadmap.

### Effective Work Breakdown

The core group needed to effectively break down high-level requirements includes:
- **Product owners**
- **Tech leads** 
- **Project managers**

Product teams should use processes effective for Work Decomposition to break down epics into:
- **Smaller epics**
- **Stories**
- **Tasks**

---

## 2️⃣ Work Decomposition

**A guide to effectively breaking down work into manageable, deliverable units**

Effective work decomposition is crucial for delivering value faster with less rework. This guide outlines the process and best practices for breaking down work from ideas to tasks.

### Prerequisites

Before implementing the work breakdown flow, ensure your team has:
- **Definition of Ready**
- **Definition of Done**
- **Backlog refinement cadence** with appropriate team members and stakeholders

### Goal

**Decompose work into small batches that can be delivered frequently, multiple times a week.**

### Key Tips for Work Decomposition

- Known poor quality should not flow downstream
- Plan refinement meetings when people are mentally alert
- Good acceptance criteria come from good communication
- Focus on outcomes, not volume, during refinement

### Stages of Work Breakdown

#### 1. Intake/Product Ideas
- Ideas become epics with defined outcomes, clear goals, and value
- Epics become a list of features

**Common struggles:**
- Unclear requirements
- Unclear goals

#### 2. Refining Epics/Features into Stories
Stories are observable changes with clear acceptance criteria, completable in less than two days.

**Typical problems:**
- Stories are too big or complex
- Stories lack testable acceptance criteria
- Lack of dependency knowledge
- Managing research tasks

#### 3. Refining Stories into Development Tasks
- Tasks are independently deployable changes, mergeable to trunk daily
- Breaking stories into tasks allows teams to swarm work and deliver value faster
- Teams need to understand what makes a good task

### Measuring Success

> **Key Metric**: Track the team's Development Cycle Time to judge improvements in decomposition.

**Ideal characteristics:**
- Stories take 1-2 days to deliver
- No rework
- No delays waiting for explanations
- No dependencies on other stories or teams

---

## 3️⃣ Behavior Driven Development

Behavior Driven Development is the collaborative process where we discuss the intent and behaviors of a feature and document the understanding in a declarative, testable way. These testable acceptance criteria should be the Definition of Done for a user story. 

**BDD is not a technology or automated tool. BDD is the process of defining the behavior.** We can then automate tests for those behaviors.

### Example

```gherkin
Feature: I need to smite a rabbit so that I can find the Holy Grail

Scenario: Use the Holy Hand Grenade of Antioch
  Given I have the Holy Hand Grenade of Antioch
  When I pull the pin
  And I count to 3
  But I do not count to 5
  And I lob it towards my foe
  And the foe is naughty in my sight
  Then my foe should snuff it
```

### Recommended Practices

Gherkin is the domain specific language that allows acceptance criteria to be expressed in "Arrange, Act, Assert" in a way that is understandable to all stakeholders.

#### Example: Time Clock System

```gherkin
Feature: As an hourly associate I want to be able to log my arrival time so that I can be paid correctly.

Scenario: Clocking in
  Given I am not clocked in
  When I enter my associate number
  Then my arrival time will be logged
  And I will be notified of the time

Scenario: Clocking out
  Given I am clocked in
  When I enter my associate number
  And I have been clocked in for more than 5 minutes
  Then I will be clocked out
  And I will be notified of the time

Scenario: Clocking out too little time
  Given I am clocked in
  When I enter my associate number
  And I have been clocked in for less than 5 minutes
  Then I will receive an error
```

### Using Acceptance Criteria to Negotiate and Split

With the above criteria, it may be acceptable to remove the time validation and accelerate the delivery of the time logging ability. After delivery, we may learn that the range validation isn't required. If true, we've saved money and time by NOT delivering unneeded features.

### Tips

- **Consumer Perspective**: Scenarios should be written from the point of view of the consumer (user, UI, or another service)
- **Single Function Focus**: Scenarios should be focused on a specific function and should not attempt to describe multiple behaviors
- **Story Splitting**: If a story has more than 6 acceptance criteria, it can probably be split
- **Condition Limit**: No acceptance test should contain more than 10 conditions. Much less is recommended
- **Flexibility**: Acceptance tests can describe full end-to-end user experiences or single component behaviors

### References

- Gherkin Reference
- BDD Primer - Liz Keogh
- Better Executable Specifications - Dave Farley
- A Real-world Example of BDD - Dave Farley
- ATDD - How to Guide - Dave Farley

---

## 4️⃣ Task Decomposition

### What does a good task look like?

**A development task is the smallest independently deployable change to implement acceptance criteria.**

### Recommended Practices

Create tasks that are meaningful and take less than two days to complete.

#### Example

```gherkin
Given I have data available for Integration Frequency
Then score entry for Integration Frequency will be updated for teams
```

**Tasks:**
- Task: Create Integration Frequency Feature Flag
- Task: Add Integration Frequency as Score Entry
- Task: Update Score Entry for Integration Frequency

Use Definition of Done as your checklist for completing a development task.

### Tips

- If a task includes integration to another dependency, add a simple contract mock to the task so that parallel development of the consumer and provider will result in minimal integration issues
- Decomposing stories into tasks allows teams to swarm stories and deliver value faster

---

## 5️⃣ Contract Driven Development

Contract Driven Development is the process of defining the contract changes between two dependencies during design and prior to construction. This allows the provider and consumer to work out how components should interact so that mocks and fakes can be created that allow the components to be developed and delivered asynchronously.

### Recommended Practices

For services, define the expected behavior changes for the affected verbs along with the payload. These should be expressed as contract tests, the unit test of an API, that both provider and consumer can use to validate the integration independently.

For more complicated interaction that require something more than simple canned responses, a common repository that represents a fake of the new service or tools like Mountebank or WireMock can be used to virtualize more complex behavior. It's important that both components are testing the same behaviors.

**Contract tests should follow Postel's Law**: *"Be conservative in what you do, be liberal in what you accept from others"*

### Tips

- For internal services, define the payload and responses in the developer task along with the expected functional test for that change
- For external services, use one of the open source tools that allow recording and replaying responses
- Always create contract tests before implementation of behavior

---

## 6️⃣ Defining Product Goals

### Product Goals

Product goals are a way to turn your vision for your product into easy to understand objectives that can be measured and achieved in a certain amount of time.

**Example**: Increased transparency into product metrics
**Measurable Outcome**: Increased traffic to product page

When generating product goals, you need to understand:
- **What problem** you are solving
- **Who** you are solving it for  
- **How** you measure that you achieved the goals

### Initiatives

Product goals can be broken down into initiatives, that when accomplished, deliver against the product strategy.

**Examples:**
- Provide one view for all product KPIs
- Ensure products have appropriate metrics associated with them

Initiatives can then be broken down into epics, stories, tasks, etc. among product teams, with high-level requirements associated.

### Epics

**An epic is a complete business feature with outcomes defined before stories are written. Epics should never be open ended buckets of work.**

**Example**: "I want to be able to review the CI metrics trends of teams who have completed a DevOps Dojo engagement."

### Tips

- Product goals need a description and key results needed to achieve them
- Initiatives need enough information to help the team understand the expected value, the requirements, measure of success, and the time frame associated to completion

---

## 7️⃣ Definition of Ready

**Is it REALLY Ready?**

A Definition of Ready is a set of criteria decided by the team that defines when work is ready to begin. The goal of the Definition of Ready is to help the team decide on the level of uncertainty that they are comfortable with taking on with respect to their work. Without that guidance, any work is fair game. That is a recipe for confusion and disaster.

### Recommended Practices

When deciding on a Definition of Ready, there are certain minimum criteria that should always be there:

**Minimum Criteria:**
- **Description of the value** the work provides (Why do we want to do this?)
- **Testable Acceptance Criteria** (When do we know we've done what we need to?)
- **Team Review and Agreement** (Has the team seen it?)

**Additional Context-Specific Criteria:**
- Wireframes for new UI components
- Contracts for APIs/services we depend on
- All relevant test types identified for subtasks
- Team estimate of the story size is no more than 2 days

### Key Points

- The Definition of Ready is a **living document** that should evolve over time
- The most important thing is to **actually enforce** the Definition of Ready
- If any work in "Ready to Start" does not meet the Definition of Ready, **move it back to the Backlog** until it is refined
- Any work that is planned for a sprint/iteration **must meet the Definition of Ready**
- If work needs to be expedited, it needs to go through the same process (unless there is immediate production impact)

### Tips

- Using Behavior Driven Development is one of the best ways to define testable acceptance criteria
- Definition of Ready is also useful for support tickets or other types of work that the team can be responsible for
- It's up to everyone on the team, including the Product Owner, to make sure that non-ready work is refined appropriately
- **Recommended DoR for CD**: Any story can be completed, either by the team or a single developer, in 2 days or less

---

## 8️⃣ Spikes

Spikes are an exploration of potential solutions for work or research items that cannot be estimated. They should be **time-boxed in short increments (1-3 days)**.

### Recommended Practices

Since all work has some amount of uncertainty and risk, spikes should be used **infrequently** when the team has no idea on how to proceed with a work item. They should result in information that can be used to better refine work into something valuable, for some iteration in the future.

**Key Guidelines:**
- Spikes should follow a **Definition of Done**, with acceptance criteria, that can be demoed at the end of its timebox
- A spike should have a **definite timebox** with frequent feedback to the team on what's been learned so far
- The best way to learn is to learn using the problem in front of us right now
- **Batching learning is worse** than batching other kinds of work because effective learning requires applying the learning immediately or it's lost

### Tips

- Use spikes **sparingly**, only when high uncertainty exists
- Spikes should be focused on **discovery and experimentation**
- **Stay within the parameters** of the spike. Anything else is considered a waste

---

## 9️⃣ Story Slicing

Story slicing is the activity of taking large stories and splitting them into smaller, more predictable deliveries. This allows the team to deliver higher priority changes more rapidly instead of tying those changes to others that may be of lower relative value.

### Recommended Practices

**Stories should be sliced vertically.** That is, the story should be aligned such that it fulfills a consumer request without requiring another story being deployed. After slicing, they should still meet the **INVEST principle**.

#### Example Stories

```
As an hourly associate I want to be able to log my arrival time so that I can be paid correctly.

As a consumer of item data, I want to retrieve item information by color so that I can find all red items.
```

### What NOT to Do

**Do not slice by tech stack layer:**
- ❌ UI "story"
- ❌ Service "story"
- ❌ Database "story"

**Do not slice by activity:**
- ❌ Coding "story"
- ❌ Review "story"
- ❌ Testing "story"

### Tips

- If you're unsure if a story can be sliced thinner, look at the acceptance tests from the BDD activity and see if it makes sense to defer some of the tests to a later release
- While stories should be sliced vertically, it's quite possible that multiple developers can work the story with each developer picking up a task that represents a layer of the slice
- **Minimize hard dependencies** in a story. The odds of delivering on time for any activity are 1 in 2^n where n is the number of hard dependencies

---

## 📈 Summary

The following playbooks have proven useful in helping teams achieve the outcome of reducing batch size and improving delivery:

1. **From Roadmap to User Story** - Alignment across teams
2. **Work Decomposition** - Systematic breakdown approach
3. **Behavior Driven Development** - Clear, testable criteria
4. **Task Decomposition** - Independently deployable changes
5. **Contract Driven Development** - Managing dependencies
6. **Defining Product Goals** - Vision to measurable objectives
7. **Definition of Ready** - Quality gates for work
8. **Spikes** - Managing uncertainty
9. **Story Slicing** - Vertical decomposition for value

By following these practices, teams can deliver value more frequently, reduce risk, and maintain high quality standards throughout the development process.
