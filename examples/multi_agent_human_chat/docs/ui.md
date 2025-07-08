# Chat UI Overview

## Introduction

The chat interface guides users by presenting support categories and example questions. This helps users quickly understand what the system can do and how to interact with it.

## Platform Service Access

The chat header provides quick-access links to key platform services. These links are collapsible to keep the interface clean.

- **Redpanda Console** – Message queue monitoring (`http://localhost:8082`)
- **Temporal UI** – Workflow management (`http://localhost:8081`)
- **Grafana** – Metrics and dashboards (`http://localhost:3000`)
- **MLflow** – Machine learning experiment tracking (`http://localhost:5001`)
- **Vespa Status** – Search engine status (`http://localhost:19071`)
- **Prometheus** – Metrics collection (`http://localhost:9090`)

## Welcome Screen

When users open the chat, the interface displays a welcome message followed by four support categories. Each category includes example questions that users can click to start a conversation.

## Support Categories

### Policy Inquiries

Covers questions about insurance coverage and policy details.

Example questions:

- What does my home insurance policy cover?
- Show me my policy details for policy H12345
- What's my deductible amount?
- Does my auto policy cover rental cars?

### Billing and Payments

Covers premium amounts, payment methods, and billing-related questions.

Example questions:

- What's my premium for policy B67890?
- When is my next payment due?
- How can I update my payment method?
- Can I see my billing history?

### Claims Support

Covers filing new claims or checking existing claim statuses.

Example questions:

- I want to file a claim for my car accident
- What's the status of claim CL789012?
- How do I submit claim documentation?
- Show me my claim history

### General Support

Covers other questions or issues not handled by the categories above.

Example questions:

- I need to speak with a manager
- I have a complaint about my service
- I'm having technical issues with my account
- I need help with something not listed here

## Interactive Features

- **Click-to-send**: Users can click example questions to populate and send a message.
- **Help button**: A button near the input toggles the category view.
- **Back navigation**: Users can return to the category selection during a conversation.
- **Auto-hide**: The category view hides automatically after sending a message.
- **Collapsible services**: Users can expand or collapse the platform service links in the header.

## Visual Design

The interface uses a clean, card-based layout that includes:

- Responsive design for desktop and mobile
- Light and dark mode support
- Hover states for interactive elements
- A 2x2 grid layout for category cards
- Clear visual hierarchy with titles and descriptions

## Implementation

### Data Structure

Support categories are defined as a list of objects in code:

```ts
const supportCategories = [
  {
    title: "Policy Inquiries",
    icon: "...",
    description: "Questions about your insurance coverage and policy details",
    examples: [ /* ... */ ]
  },
  // ...
];
```

### User Interaction Flow

1. New users see the category view on first load.
2. Returning users can toggle the category view using the help button.
3. Clicking an example immediately sends the message.
4. Users can reopen the categories view at any point in the conversation.

## Benefits

- Helps users quickly understand available capabilities
- Reduces confusion with clear options and examples
- Speeds up interactions through one-click suggestions
- Improves agent routing with well-structured queries
- Supports accessibility through structured content and clear labeling

## Future Improvements

- Update examples dynamically based on user history
- Add search within the category view
- Personalize categories based on user profile
- Track usage of examples and categories
- Add support for multiple languages

## How to Test

1. Start the system: `make start-all`
2. Open the interface at `http://localhost:8000`
3. Verify the welcome screen and category cards appear
4. Click an example question to send it
5. Use the help button to toggle categories
6. Test in both light and dark mode

## Visual Summary

The interface includes:

- A welcome message at the top
- Four category cards in a 2x2 grid layout
- Each card displays a title, description, and clickable example questions
- A help button near the input field
- Smooth transitions and consistent layout across screen sizes
