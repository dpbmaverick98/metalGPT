"""
Vercel AI SDK integration for MetalGPT
Unified AI interface with streaming and structured output
"""
import os
from typing import Optional, Dict, Any, AsyncGenerator, List
from pydantic import BaseModel

# Vercel AI SDK imports
from ai_sdk import generate_text, stream_text, generate_object
from ai_sdk import openai as ai_openai
from ai_sdk import anthropic as ai_anthropic


class DesignAction(BaseModel):
    """Structured design action from AI"""
    action_type: str  # "increase_riser_size", "add_riser", "add_chill", etc.
    target_id: Optional[int] = None
    parameters: Dict[str, float]
    reasoning: str


class ImprovementPlan(BaseModel):
    """AI-generated improvement plan"""
    analysis: str
    actions: List[DesignAction]
    confidence: float
    expected_outcome: str


class DefectAnalysis(BaseModel):
    """AI analysis of casting defects"""
    defect_type: str
    root_cause: str
    severity: str
    suggested_fixes: List[str]
    prevention_tips: List[str]


class AIProvider:
    """
    Unified AI provider using Vercel AI SDK
    """
    
    def __init__(self):
        self.model = None
        self.provider = None
        self._init_provider()
    
    def _init_provider(self):
        """Initialize AI provider from environment"""
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        
        # Prefer Anthropic for technical tasks
        if anthropic_key:
            self.model = ai_anthropic("claude-3-sonnet-20240229")
            self.provider = "anthropic"
            print("✅ Vercel AI SDK: Using Anthropic Claude 3 Sonnet")
        elif openai_key:
            self.model = ai_openai("gpt-4o-mini")
            self.provider = "openai"
            print("✅ Vercel AI SDK: Using OpenAI GPT-4o-mini")
        else:
            print("❌ No AI API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY")
    
    def is_available(self) -> bool:
        """Check if AI provider is available"""
        return self.model is not None
    
    def get_provider_name(self) -> str:
        """Get current provider name"""
        return self.provider or "none"
    
    async def generate(self, prompt: str, system: Optional[str] = None,
                      temperature: float = 0.7) -> str:
        """Generate text response"""
        if not self.model:
            raise RuntimeError("No AI provider available")
        
        result = await generate_text(
            model=self.model,
            system=system or "",
            prompt=prompt,
            temperature=temperature
        )
        return result.text
    
    async def stream(self, prompt: str, system: Optional[str] = None,
                    temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """Stream text response token by token"""
        if not self.model:
            raise RuntimeError("No AI provider available")
        
        result = await stream_text(
            model=self.model,
            system=system or "",
            prompt=prompt,
            temperature=temperature
        )
        
        async for chunk in result.text_stream:
            yield chunk
    
    async def generate_structured(self, prompt: str, schema: type[BaseModel],
                                  system: Optional[str] = None) -> BaseModel:
        """Generate structured output using Pydantic schema"""
        if not self.model:
            raise RuntimeError("No AI provider available")
        
        result = await generate_object(
            model=self.model,
            schema=schema,
            system=system or "",
            prompt=prompt
        )
        return result.object
    
    async def analyze_defects(self, defects: List[Dict], 
                             casting_info: Dict) -> List[DefectAnalysis]:
        """Use AI to analyze defects and suggest fixes"""
        if not self.model:
            return []
        
        system = """You are an expert metallurgist and casting engineer. 
Analyze the defects and provide detailed root cause analysis."""
        
        prompt = f"""Analyze these casting defects:

Casting Info:
- Material: {casting_info.get('material', 'unknown')}
- Volume: {casting_info.get('volume', 0):.0f} mm³
- Hot spots: {casting_info.get('hotspot_count', 0)}

Defects:
{defects}

Provide detailed analysis for each defect."""
        
        # For multiple items, we'd use a list schema
        # For now, analyze one by one
        analyses = []
        for defect in defects[:3]:  # Top 3 defects
            result = await self.generate_structured(
                prompt=f"Analyze this defect: {defect}",
                schema=DefectAnalysis,
                system=system
            )
            analyses.append(result)
        
        return analyses
    
    async def generate_improvement_plan(self, defects: List[Dict],
                                       current_design: Dict,
                                       geometry: Dict) -> ImprovementPlan:
        """Generate structured improvement plan"""
        if not self.model:
            raise RuntimeError("No AI provider available")
        
        system = """You are an expert casting optimization AI. 
Analyze defects and generate specific, actionable design improvements.

Available actions:
- increase_riser_size: Increase riser diameter/height (params: scale_factor)
- add_riser: Add new riser at position (params: x, y, z, radius)
- move_riser: Move existing riser (params: riser_id, x, y, z)
- add_chill: Add chill at position (params: x, y, z, thickness)
- increase_neck: Widen riser neck (params: riser_id, scale_factor)
- adjust_gating: Modify gating parameters (params: sprue_radius, sprue_height)

Rules:
- Riser modulus should be 1.2-1.5x casting modulus
- Place risers at last-to-freeze regions
- Use chills to accelerate solidification in thick sections"""
        
        prompt = f"""Current Design:
- Risers: {len(current_design.get('risers', []))}
- Gating: sprue r={current_design.get('gating', {}).get('sprue_radius', 0):.1f}mm
- Yield: {current_design.get('yield', 0):.1f}%

Geometry:
- Volume: {geometry.get('volume', 0):.0f} mm³
- Hot spots: {len(geometry.get('hotspots', []))}

Defects to fix:
{defects}

Generate improvement plan to eliminate these defects."""
        
        return await self.generate_structured(
            prompt=prompt,
            schema=ImprovementPlan,
            system=system
        )


# Singleton instance
_ai_provider: Optional[AIProvider] = None


def get_ai_provider() -> AIProvider:
    """Get or create AI provider singleton"""
    global _ai_provider
    if _ai_provider is None:
        _ai_provider = AIProvider()
    return _ai_provider
