# Vercel AI SDK Integration Plan for MetalGPT

## Overview

Vercel AI SDK now has a **Python re-implementation** (`ai-sdk-python`) that provides:
- Unified API across providers (OpenAI, Anthropic, Google, etc.)
- First-class streaming support
- Structured output with Pydantic
- Tool calling
- Tiny dependency footprint

## Current MetalGPT Architecture vs Vercel AI SDK

### Current Approach
```python
# Direct SDK usage - verbose and provider-specific
import openai
client = openai.AsyncOpenAI(api_key=...)
response = await client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...]
)
text = response.choices[0].message.content
```

### With Vercel AI SDK Python
```python
# Clean, provider-agnostic
from ai_sdk import generate_text, openai

# Can switch providers easily
model = openai("gpt-4o-mini")  # or anthropic("claude-3-sonnet")
result = await generate_text(model=model, prompt="...")
print(result.text)
```

## Key Improvements for MetalGPT

### 1. **Streaming Chat Responses**

Current: WebSocket with full message wait
```javascript
// Frontend waits for complete response
ws.send(JSON.stringify({text: message}))
const data = await ws.receive()  // Wait for full response
```

With AI SDK: True streaming
```python
# Backend - stream tokens as they're generated
from ai_sdk import stream_text

stream = await stream_text(model=model, prompt=...)
async for chunk in stream.text_stream:
    await websocket.send(json.dumps({"token": chunk}))
```

```javascript
// Frontend - display tokens as they arrive
useChat({
  api: '/api/chat',
  onStream: (token) => appendToMessage(token)
})
```

### 2. **Structured Output for Design Actions**

Current: Parse text for actions
```python
# Extract JSON from text with regex
text = ai_response
json_match = re.search(r'\[.*\]', text)
actions = json.loads(json_match.group())
```

With AI SDK: Type-safe structured output
```python
from ai_sdk import generate_object
from pydantic import BaseModel

class DesignAction(BaseModel):
    action: str  # "increase_riser_size", "add_chill", etc.
    target_id: int
    factor: float

class ImprovementPlan(BaseModel):
    analysis: str
    actions: list[DesignAction]
    confidence: float

result = await generate_object(
    model=model,
    schema=ImprovementPlan,
    prompt=f"Analyze defects: {defects} and suggest fixes"
)
# result.object is typed as ImprovementPlan
for action in result.object.actions:
    apply_fix(action)  # Type-safe!
```

### 3. **Tool Calling for Simulation Integration**

```python
from ai_sdk import tool, generate_text

# Define tools the AI can call
simulation_tool = tool({
    "description": "Run solidification simulation",
    "parameters": {
        "riser_positions": ["list of [x,y,z]"],
        "material": "string"
    },
    "execute": async (params) => {
        results = await run_simulation(params)
        return {"defects": results.defects}
    }
})

# AI decides when to call tools
result = await generate_text(
    model=model,
    tools={"simulate": simulation_tool},
    prompt="Optimize this casting design",
    max_tool_calls=10  # Allow iterative optimization
)
```

### 4. **Unified Provider Support**

Switch providers without code changes:
```python
from ai_sdk import generate_text, openai, anthropic, google

# Same API, different providers
providers = {
    "openai": openai("gpt-4o-mini"),
    "anthropic": anthropic("claude-3-sonnet"),
    "google": google("gemini-pro")
}

model = providers[os.getenv("AI_PROVIDER", "openai")]
result = await generate_text(model=model, prompt="...")
```

## Implementation Plan

### Phase 1: Basic Integration (1-2 hours)
1. Install `ai-sdk-python`
2. Replace direct SDK calls with `generate_text`
3. Add streaming support to chat handler

### Phase 2: Structured Output (2-3 hours)
1. Define Pydantic models for design actions
2. Use `generate_object` for improvement suggestions
3. Type-safe action parsing

### Phase 3: Tool Calling (3-4 hours)
1. Expose simulation as AI-callable tool
2. Allow AI to run iterative optimization
3. Frontend tool visualization

### Phase 4: Frontend SDK (2-3 hours)
1. Add `@ai-sdk/react` to frontend
2. Use `useChat` hook for streaming
3. Tool invocation UI components

## Code Changes Required

### Backend Changes

```python
# backend/chat/handler.py - New version
from ai_sdk import generate_text, stream_text, generate_object, openai, anthropic
from pydantic import BaseModel

class DesignAction(BaseModel):
    action_type: str
    riser_id: Optional[int]
    parameters: Dict[str, float]

class AIChatHandler:
    def __init__(self):
        # Unified model initialization
        self.model = openai("gpt-4o-mini") if os.getenv("OPENAI_API_KEY") else None
        if not self.model:
            self.model = anthropic("claude-3-sonnet") if os.getenv("ANTHROPIC_API_KEY") else None
    
    async def process_message_streaming(self, message: str, session_data: Dict):
        """Stream response token by token"""
        system_prompt = self._build_system_prompt(session_data)
        
        stream = await stream_text(
            model=self.model,
            system=system_prompt,
            messages=self.conversation_history,
        )
        
        async for chunk in stream.text_stream:
            yield {"token": chunk}
        
        yield {"done": True, "actions": self._extract_actions(stream.text)}
    
    async def generate_improvements_structured(self, defects: List[Defect]) -> ImprovementPlan:
        """Type-safe improvement generation"""
        return await generate_object(
            model=self.model,
            schema=ImprovementPlan,
            prompt=f"Analyze these defects and create improvement plan: {defects}"
        )
```

### Frontend Changes

```javascript
// frontend/app.js - New version with AI SDK
import { useChat } from '@ai-sdk/react';

function ChatComponent() {
  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
    api: '/api/chat',
    onFinish: (message) => {
      // Handle completed message with actions
      if (message.toolInvocations) {
        renderToolResults(message.toolInvocations);
      }
    }
  });

  return (
    <div>
      {messages.map(m => (
        <div key={m.id}>
          {m.content}
          {m.toolInvocations?.map(invocation => (
            <ToolResult key={invocation.toolCallId} invocation={invocation} />
          ))}
        </div>
      ))}
      <form onSubmit={handleSubmit}>
        <input value={input} onChange={handleInputChange} />
      </form>
    </div>
  );
}
```

## Benefits Summary

| Feature | Current | With Vercel AI SDK |
|---------|---------|-------------------|
| **Provider Switching** | Code changes required | Single config change |
| **Streaming** | Manual WebSocket | Built-in streaming |
| **Structured Output** | Regex parsing | Pydantic validation |
| **Tool Calling** | Custom implementation | Native support |
| **Frontend Integration** | Custom hooks | `useChat` hook |
| **Type Safety** | Manual validation | Full Pydantic types |
| **Dependencies** | Multiple SDKs | Single `ai-sdk-python` |

## Migration Effort

- **Low effort**: Basic `generate_text` replacement
- **Medium effort**: Add streaming to frontend
- **Higher effort**: Full tool calling with UI components

## Recommendation

**Start with Phase 1** - Basic integration gives immediate benefits:
- Cleaner code
- Easy provider switching
- Foundation for advanced features

Then gradually add structured output and tool calling as needed.

## Installation

```bash
pip install ai-sdk-python

# Optional: specific providers
pip install ai-sdk-python[openai,anthropic]
```

## Resources

- [Python AI SDK Docs](https://pythonaisdk.mintlify.app/)
- [GitHub: python-ai-sdk](https://github.com/python-ai-sdk/sdk)
- [Vercel AI Gateway](https://vercel.com/docs/ai-gateway)
