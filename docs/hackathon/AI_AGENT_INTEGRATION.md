# AI Agent Dashboard Integration

## Overview

This document describes the new AI Agent Dashboard page that merges the GUS AI agent functionality with Alan's card-based UI design pattern, featuring a Matrix-style collapsible chat interface.

## Features

### 1. Card-Based Dashboard
- **AI Analysis Cards**: Display AI responses in interactive cards similar to Alan's design
- **KPI Cards**: Show key metrics extracted from AI analysis
- **Recommendations Cards**: Present AI recommendations in an organized format
- **Chart Cards**: Visualize data insights from AI responses

### 2. Matrix-Style Chat Interface
- **Collapsible Panel**: Chat interface slides up from the bottom of the screen
- **Dark Theme**: Black background with green text styling reminiscent of The Matrix
- **Terminal Aesthetics**: Monospace font and command-line style prompts
- **Resizable**: Users can adjust the height of the chat panel

### 3. Real AI Integration
- **GUS AI Service**: Connected to the existing Strategic Business Intelligence Agent
- **Live Responses**: Real-time AI analysis and recommendations
- **Suggested Prompts**: Pre-built queries for BEX project analysis
- **Metadata Display**: Shows confidence scores, data sources, and analysis types

## File Structure

```
services/frontend/src/
├── pages/
│   └── AIAgent.jsx                 # Main AI Agent dashboard page
├── components/
│   ├── ai/
│   │   ├── AIResponseCard.jsx      # Enhanced card component for AI responses
│   │   └── AIResponseParser.jsx    # Parses AI responses into cards
│   └── alan/                       # Existing Alan components (reused)
│       ├── KPICard.jsx
│       └── ChartCard.jsx
```

## Navigation

The AI Agent page is accessible via:
- **URL**: `/ai-agent`
- **Sidebar**: "AI Agent" menu item with CPU chip icon
- **Position**: Between "Alan" and "GUS" in the navigation menu

## Usage

### Starting a Conversation
1. Navigate to the AI Agent page
2. Click the "AI TERMINAL" button at the bottom to open the chat panel
3. Use suggested prompts or type your own queries
4. AI responses will appear as interactive cards in the dashboard above

### Interacting with Cards
- **Share**: Copy shareable links for specific analysis cards
- **Remove**: Delete cards from the dashboard
- **Get Recommendations**: Request AI recommendations for specific data
- **Resize/Move**: Drag and resize cards using the grid layout

### Chat Interface Features
- **Matrix Styling**: Dark background with green terminal text
- **Resizable Panel**: Drag the top border to adjust height
- **Suggested Prompts**: Toggle visibility of pre-built queries
- **Real-time Responses**: Live AI analysis with metadata

## Technical Implementation

### AI Response Processing
The system automatically converts AI responses into dashboard cards:

1. **Main Analysis**: Creates an analysis card with the full AI response
2. **KPI Extraction**: Parses executive summary for numerical metrics
3. **Recommendations**: Displays AI recommendations in a dedicated card
4. **Visualizations**: Generates chart cards for data insights

### Card Types
- `ai-analysis`: Main AI response content
- `ai-kpi`: Key performance indicators
- `ai-recommendations`: AI-generated recommendations
- `ai-chart`: Data visualizations

### Styling
- **Cards**: Follow Alan's design pattern with hover effects and shadows
- **Chat**: Matrix-inspired dark theme with green accents
- **Layout**: Responsive grid system with drag-and-drop functionality

## Integration Points

### Backend Services
- **GUS AI Service** (port 5002): Strategic Business Intelligence Agent
- **Backend API** (port 5001): Authentication and data access
- **Frontend** (port 5010): React application

### Shared Components
- Reuses Alan's `KPICard` and `ChartCard` components
- Extends with new `AIResponseCard` for AI-specific content
- Maintains consistent styling and interaction patterns

## Future Enhancements

1. **Real Chart Data**: Replace mock chart data with actual AI-generated visualizations
2. **Card Persistence**: Save dashboard layouts and card configurations
3. **Export Features**: Export analysis results and visualizations
4. **Advanced Filtering**: Filter cards by analysis type, confidence score, etc.
5. **Collaboration**: Share dashboards with team members

## Testing

To test the integration:

1. Ensure all services are running:
   - Frontend: `npm run dev` (port 5010)
   - Backend: `python main.py` (port 5001)
   - GUS AI: `python main.py` (port 5002)

2. Navigate to `http://localhost:5010/ai-agent`

3. Test the chat interface with sample queries:
   - "Which BEX components have the highest defect rates?"
   - "What is BEX's Product Innovation Velocity?"
   - "Show me team performance metrics"

4. Verify that responses appear as interactive cards in the dashboard

## Troubleshooting

### Common Issues
- **Port Conflicts**: Ensure ports 5001, 5002, and 5010 are available
- **Service Dependencies**: All three services must be running for full functionality
- **Authentication**: Valid JWT token required for AI service access

### Debug Mode
Enable debug logging in the browser console to see:
- AI service requests and responses
- Card creation and layout updates
- Chat interface state changes
