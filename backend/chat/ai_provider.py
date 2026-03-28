"""
Vercel AI SDK integration for MetalGPT
Provides unified AI interface with streaming and structured output
"""
import os
from typing import Optional, Dict, Any, AsyncGenerator

# Try to import Vercel AI SDK
try:
    from ai_sdk import generate_text, stream_text, generate_object
    from ai_sdk import openai as ai_openai
    from ai_sdk import anthropic as ai_anthropic
    HAS_AI_SDK = True
except ImportError:
    HAS_AI_SDK = False

# Fallback to direct SDKs
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class AIProvider:
    """
    Unified AI provider using Vercel AI SDK or fallback to direct SDKs
    """
    
    def __init__(self):
        self.model = None
        self.provider = None
        self.use_ai_sdk = HAS_AI_SDK
        
        # Initialize with available provider
        self._init_provider()
    
    def _init_provider(self):
        """Initialize the best available AI provider"""
        
        if self.use_ai_sdk:
            # Try Vercel AI SDK first
            openai_key = os.getenv("OPENAI_API_KEY")
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
            
            if anthropic_key:
                self.model = ai_anthropic("claude-3-sonnet-20240229")
                self.provider = "anthropic"
                print("✅ Using Vercel AI SDK with Anthropic")
            elif openai_key:
                self.model = ai_openai("gpt-4o-mini")
                self.provider = "openai"
                print("✅ Using Vercel AI SDK with OpenAI")
        
        else:
            # Fallback to direct SDKs
            openai_key = os.getenv("OPENAI_API_KEY")
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
            
            if HAS_ANTHROPIC and anthropic_key:
                self.model = anthropic.AsyncAnthropic(api_key=anthropic_key)
                self.provider = "anthropic-direct"
                print("✅ Using Anthropic SDK directly")
            elif HAS_OPENAI and openai_key:
                self.model = openai.AsyncOpenAI(api_key=openai_key)
                self.provider = "openai-direct"
                print("✅ Using OpenAI SDK directly")
    
    async def generate(self, prompt: str, system: Optional[str] = None,
                      temperature: float = 0.7) -> str:
        """
        Generate text response
        
        Uses Vercel AI SDK if available, falls back to direct SDKs
        """
        if not self.model:
            raise RuntimeError("No AI provider available. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.")
        
        if self.use_ai_sdk:
            # Vercel AI SDK path
            result = await generate_text(
                model=self.model,
                system=system or "",
                prompt=prompt,
                temperature=temperature
            )
            return result.text
        
        else:
            # Direct SDK path
            if self.provider == "anthropic-direct":
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                
                response = await self.model.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=1000,
                    messages=messages
                )
                return response.content[0].text
            
            else:  # openai-direct
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                
                response = await self.model.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=temperature
                )
                return response.choices[0].message.content
    
    async def stream(self, prompt: str, system: Optional[str] = None,
                    temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """
        Stream text response token by token
        
        Yields tokens as they're generated for real-time display
        """
        if not self.model:
            raise RuntimeError("No AI provider available.")
        
        if self.use_ai_sdk:
            # Vercel AI SDK streaming
            result = await stream_text(
                model=self.model,
                system=system or "",
                prompt=prompt,
                temperature=temperature
            )
            
            async for chunk in result.text_stream:
                yield chunk
        
        else:
            # Direct SDK streaming (simplified - no true streaming)
            # In production, you'd implement proper streaming
            text = await self.generate(prompt, system, temperature)
            # Simulate streaming by yielding words
            words = text.split()
            for word in words:
                yield word + " "
    
    async def generate_structured(self, prompt: str, schema: Any,
                                  system: Optional[str] = None) -> Any:
        """
        Generate structured output using Pydantic schema
        
        Requires Vercel AI SDK. Falls back to JSON parsing if not available.
        """
        if self.use_ai_sdk:
            result = await generate_object(
                model=self.model,
                schema=schema,
                system=system or "",
                prompt=prompt
            )
            return result.object
        
        else:
            # Fallback: generate text and parse JSON
            import json
            import re
            
            schema_desc = self._describe_schema(schema)
            enhanced_prompt = f"""{prompt}

Respond with valid JSON matching this schema:
{schema_desc}

Return ONLY the JSON, no other text."""
            
            text = await self.generate(enhanced_prompt, system)
            
            # Extract JSON
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return schema(**data)
            else:
                raise ValueError("Could not parse structured output")
    
    def _describe_schema(self, schema_class) -> str:
        """Generate schema description for fallback parsing"""
        from pydantic import BaseModel
        
        if issubclass(schema_class, BaseModel):
            fields = []
            for name, field in schema_class.model_fields.items():
                field_type = field.annotation.__name__ if hasattr(field.annotation, '__name__') else str(field.annotation)
                fields.append(f"  {name}: {field_type}")
            return "{\n" + ",\n".join(fields) + "\n}"
        
        return str(schema_class)
    
    def is_available(self) -> bool:
        """Check if AI provider is available"""
        return self.model is not None
    
    def get_provider_name(self) -> str:
        """Get current provider name"""
        return self.provider or "none"


# Singleton instance
_ai_provider: Optional[AIProvider] = None


def get_ai_provider() -> AIProvider:
    """Get or create AI provider singleton"""
    global _ai_provider
    if _ai_provider is None:
        _ai_provider = AIProvider()
    return _ai_provider
