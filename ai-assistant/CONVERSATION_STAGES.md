# Multi-Stage Conversation Flow Implementation

## Overview

The AI Assistant now supports a **three-stage conversation flow** with dynamic prompt switching:

1. **GREETING** - Initial greeting and triage
2. **TRIAGE** - Problem scoping and details gathering
3. **FINALIZE** - Provider presentation and request completion

## Architecture

### Conversation Stages

```python
class ConversationStage:
    GREETING = "greeting"      # Initial greeting
    TRIAGE = "triage"          # Problem scoping
    FINALIZE = "finalize"      # Provider presentation
    COMPLETED = "completed"    # Conversation ended
```

### Stage Flow

```
┌──────────┐
│ GREETING │ Initial greeting, ask user's needs
└────┬─────┘
     │ User describes problem
     ▼
┌──────────┐
│ TRIAGE   │ Ask scoping questions (size, timing, etc.)
└────┬─────┘
     │ Agent detects "database durchsuchen" trigger
     ▼
┌──────────┐
│ FINALIZE │ Present providers, handle acceptance/rejection
└────┬─────┘
     │ User accepts or conversation ends
     ▼
┌──────────┐
│COMPLETED │ Thank user, goodbye
└──────────┘
```

## Key Components

### 1. Test Data (`test_data.py`)

**User Data:**
```python
USER_DATA = {
    "user_id": "user_123",
    "name": "Wolfgang",
    "email": "wolfgang@example.com",
    "address": "Hauptstraße 42, 10115 Berlin",
    "has_open_request": False,
}
```

**Service Providers:**
- 10 sample providers across different categories
- Categories: Gartenpflege, IT-Support, Handwerk, Elektrik, Sanitär, Malerei
- Each with: name, skills, rating, experience, price range, availability

**Helper Functions:**
- `search_providers(query, category, limit)` - Find matching providers
- `detect_category(text)` - Auto-detect service category from text

### 2. Conversation Context Tracking

```python
self.conversation_context = {
    "user_problem": "",              # Accumulated problem description
    "detected_category": None,       # Auto-detected category
    "providers_found": [],           # Matching providers
    "current_provider_index": 0,     # For iterating through providers
}
```

### 3. Dynamic Prompt Switching

Each stage uses a different prompt template:

**GREETING:**
- `GREETING_AND_TRIAGE_PROMPT`
- Greets user by name
- Asks if they have open request

**TRIAGE:**
- `TRIAGE_CONVERSATION_PROMPT`
- Acts as service coordinator
- Asks scoping questions (not diagnostic!)
- Summarizes requirements before transition

**FINALIZE:**
- `FINALIZE_SERVICE_REQUEST_PROMPT`
- Receives `provider_list_json` and `provider_count`
- Presents providers one by one
- Handles acceptance/rejection
- Falls back to "neighborhood search" if no providers

### 4. Stage Transition Detection

**TRIAGE → FINALIZE:**
Triggered when agent says transition keywords:
- "database durchsuchen"
- "datenbank durchsuchen"
- "einen moment"
- "please hold"

When detected:
1. Accumulates user's problem description
2. Detects category using keyword matching
3. Searches for matching providers
4. Updates prompt with provider data
5. Switches to FINALIZE stage

**FINALIZE → COMPLETED:**
Triggered when agent says closing keywords:
- "schönen tag"
- "auf wiedersehen"
- "vielen dank"

## Usage Example

```python
from ai_assistant.ai_assistant import AIAssistant

# Initialize
assistant = AIAssistant(
    gemini_api_key="your-api-key",
    session_id="user_session_123"
)

# Stage 1: Greeting
greeting_text, audio_stream = await assistant.get_greeting_audio()
# Agent greets user: "Hallo Wolfgang, schön dich zu sehen! Wie kann ich dir heute helfen?"
# Stage: GREETING → TRIAGE (automatic transition)

# Stage 2: Triage - User describes problem
user_msg = "Mein Drucker funktioniert nicht mehr"
async for chunk in assistant.generate_llm_response_stream(user_msg):
    print(chunk, end='')
# Agent asks scoping questions
# Stage: TRIAGE

# ... more triage conversation ...

# Stage 2→3: Agent confirms and triggers search
user_msg = "Ja, das stimmt alles"
async for chunk in assistant.generate_llm_response_stream(user_msg):
    print(chunk, end='')
# Agent: "Perfect. I just need a few seconds to search our database..."
# Stage: TRIAGE → FINALIZE (automatic transition)
# Providers searched and found automatically

# Stage 3: Finalize - Provider presentation
# Agent automatically presents first provider from search results
# Agent: "I've found a great match: TechFix IT-Support..."
# Stage: FINALIZE

# User accepts
user_msg = "Ja, bitte senden Sie die Anfrage"
async for chunk in assistant.generate_llm_response_stream(user_msg):
    print(chunk, end='')
# Agent confirms and says goodbye
# Stage: FINALIZE → COMPLETED
```

## Testing

Run the test script:

```bash
cd ai-assistant
python test_conversation_stages.py
```

This simulates a complete conversation flow from greeting to provider acceptance.

## How It Works

### 1. Initialization
- Creates LLM instance with streaming support
- Initializes empty conversation context
- Sets initial stage to GREETING
- Creates initial chain for TRIAGE (used after greeting)

### 2. Greeting Generation
```python
async def get_greeting_audio():
    # Temporarily switch to GREETING stage
    # Generate personalized greeting using USER_DATA
    # Add greeting to chat history
    # Switch to TRIAGE stage
    # Return greeting text and audio
```

### 3. Response Generation with Stage Management
```python
async def generate_llm_response_stream(prompt):
    # If in TRIAGE stage: accumulate problem description
    # Stream response using current prompt template
    # After complete response: check for stage transitions
    # If transition detected: update chain with new prompt
```

### 4. Problem Accumulation (TRIAGE stage)
```python
def _accumulate_problem_description(user_input):
    # Append user input to context
    # Detect category from accumulated text
    # Search for matching providers
    # Store results in context
```

### 5. Stage Transition Detection
```python
def _detect_stage_transition(user_input, ai_response):
    # Check for transition keywords in AI response
    # TRIAGE→FINALIZE: "database durchsuchen"
    # FINALIZE→COMPLETED: "schönen tag"
    # Return new stage if transition detected
```

### 6. Chain Update
```python
def _update_chain_for_stage(stage):
    # Create new prompt template for stage
    # For FINALIZE: inject provider data into prompt
    # Recreate LangChain chain with new prompt
    # Update current stage
```

## Prompt Template Placeholders

### GREETING_AND_TRIAGE_PROMPT
- `{agent_name}` - Agent's name (Elin)
- `{company_name}` - Company name (FidesConnect)
- `{user_name}` - User's name from USER_DATA
- `{has_open_request}` - "YES" or "NO"

### TRIAGE_CONVERSATION_PROMPT
- `{agent_name}` - Agent's name (Elin)

### FINALIZE_SERVICE_REQUEST_PROMPT
- `{agent_name}` - Agent's name (Elin)
- `{provider_list_json}` - JSON array of providers
- `{provider_count}` - Number of providers found

## Provider Search Logic

### Category Detection
Matches keywords in user's accumulated problem description:
- **Gartenpflege**: rasen, mähen, garten, hecke...
- **IT-Support**: drucker, computer, pc, netzwerk...
- **Handwerk**: reparatur, kaputt, defekt...
- **Elektrik**: elektrik, strom, lampe...
- **Sanitär**: wasser, rohr, toilette...
- **Malerei**: malen, streichen, farbe...

### Provider Scoring
Providers scored based on:
1. Category match (50 points)
2. Skills match (20 points per skill)
3. Category in query (15 points)
4. Rating bonus (rating × 2)
5. Experience bonus (up to 10 points)

Top 3 providers returned, sorted by score.

## Conversation Context Example

After a complete TRIAGE conversation:

```python
{
    "user_problem": "Mein Drucker funktioniert nicht mehr HP etwa 3 Jahre alt Fehlermeldung morgen vormittags",
    "detected_category": "IT-Support",
    "providers_found": [
        {
            "id": "provider_002",
            "name": "TechFix IT-Support",
            "category": "IT-Support",
            "skills": ["Drucker-Reparatur", "Netzwerk-Installation", "PC-Wartung"],
            "rating": 4.9,
            "experience_years": 8,
            "price_range": "€€€",
            "availability": "Mo-Fr",
            "description": "Zertifizierte IT-Spezialisten für alle technischen Probleme"
        },
        {
            "id": "provider_004",
            "name": "PrintMaster Solutions",
            // ... more provider data
        }
    ],
    "current_provider_index": 0
}
```

## Benefits

1. **Clear Separation**: Each stage has its own behavior and prompt
2. **Automatic Transitions**: No manual stage switching needed
3. **Context Preservation**: All conversation context maintained
4. **Provider Integration**: Automatic search and matching
5. **Flexible**: Easy to add new stages or modify behavior
6. **LangChain Compatible**: Works with any LangChain-supported LLM

## Future Enhancements

- Persistent storage for conversation context
- Multi-provider iteration in FINALIZE stage
- User preference learning
- Calendar integration for scheduling
- Real provider API integration
- A/B testing different prompts per stage
