"""
AI Chat handler with OpenAI/Anthropic integration
Falls back to rule-based system if no API key
"""
import json
import os
import re
from typing import Dict, Optional, List

# Try to import AI libraries
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


class AIChatHandler:
    """
    AI-powered chat handler for MetalGPT
    Uses OpenAI/Anthropic when available, falls back to rule-based
    """
    
    def __init__(self):
        self.openai_client = None
        self.anthropic_client = None
        self.use_ai = False
        self.conversation_history: List[Dict] = []
        
        # Initialize AI clients if keys available
        self._init_ai_clients()
        
        # Rule-based fallback
        self.rule_handler = RuleBasedHandler()
    
    def _init_ai_clients(self):
        """Initialize AI clients from environment"""
        # OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if HAS_OPENAI and openai_key:
            self.openai_client = openai.AsyncOpenAI(api_key=openai_key)
            self.use_ai = True
            print("✅ OpenAI client initialized")
        
        # Anthropic (Claude)
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if HAS_ANTHROPIC and anthropic_key:
            self.anthropic_client = anthropic.AsyncAnthropic(api_key=anthropic_key)
            self.use_ai = True
            print("✅ Anthropic client initialized")
        
        if not self.use_ai:
            print("⚠️ No AI API keys found. Using rule-based responses.")
            print("   Set OPENAI_API_KEY or ANTHROPIC_API_KEY for AI chat.")
    
    async def process_message(self, message: str, session_data: Dict,
                            websocket=None) -> Dict:
        """
        Process chat message with AI or rule-based fallback
        """
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": message})
        
        # Try AI first if available
        if self.use_ai:
            try:
                response = await self._get_ai_response(message, session_data)
                self.conversation_history.append({"role": "assistant", "content": response["text"]})
                return response
            except Exception as e:
                print(f"AI error: {e}. Falling back to rule-based.")
        
        # Fallback to rule-based
        response = await self.rule_handler.process_message(message, session_data, websocket)
        self.conversation_history.append({"role": "assistant", "content": response.get("text", "")})
        return response
    
    async def _get_ai_response(self, message: str, session_data: Dict) -> Dict:
        """Get response from AI model"""
        
        # Build system prompt with context
        system_prompt = self._build_system_prompt(session_data)
        
        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            *self.conversation_history[-10:]  # Last 10 messages for context
        ]
        
        # Try Anthropic first (better for technical tasks)
        if self.anthropic_client:
            return await self._call_anthropic(messages, session_data)
        
        # Fall back to OpenAI
        if self.openai_client:
            return await self._call_openai(messages, session_data)
        
        raise RuntimeError("No AI client available")
    
    def _build_system_prompt(self, session_data: Dict) -> str:
        """Build system prompt with current casting context"""
        
        prompt = """You are MetalGPT, an expert AI assistant for metal casting design and optimization.

Your capabilities:
1. Analyze casting geometry for hot spots and feeding requirements
2. Design optimal riser (feeder) placement and sizing
3. Design gating systems for mold filling
4. Run solidification simulations (FDM method)
5. Predict defects (shrinkage, porosity, cold shuts)
6. Recommend materials and process parameters

Key technical knowledge:
- Chvorinov's Rule: Solidification time ∝ (Volume/Surface Area)²
- Riser modulus must be 1.2-1.5× casting modulus to feed properly
- Directional solidification: castings should freeze from thin to thick sections
- Gating ratios: sprue:runner:ingate typically 1:2:4 or 1:4:4
- Materials: Aluminum A356 (common), Steel (high shrinkage), Gray Iron (graphite expansion)

When responding:
- Be concise but technically accurate
- Suggest specific actions the user can take
- Reference the current casting data when available
- Use markdown formatting for clarity
"""
        
        # Add current session context
        if session_data.get("geometry"):
            geom = session_data["geometry"]
            prompt += f"\n\nCURRENT CASTING:\n"
            prompt += f"- Volume: {geom.get('volume', 0):.0f} mm³\n"
            prompt += f"- Hot spots detected: {len(geom.get('hotspots', []))}\n"
            prompt += f"- Complexity: {geom.get('complexity', 'unknown')}\n"
        
        if session_data.get("material"):
            prompt += f"- Material: {session_data['material']}\n"
        
        if session_data.get("risers"):
            prompt += f"- Risers placed: {len(session_data['risers'])}\n"
        
        prompt += "\nAvailable actions: analyze, optimize, simulate, set_material, upload"
        
        return prompt
    
    async def _call_anthropic(self, messages: List[Dict], session_data: Dict) -> Dict:
        """Call Anthropic Claude API"""
        
        # Convert to Anthropic format
        system_msg = None
        chat_messages = []
        
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                chat_messages.append({
                    "role": m["role"],
                    "content": m["content"]
                })
        
        response = await self.anthropic_client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            system=system_msg,
            messages=chat_messages
        )
        
        text = response.content[0].text
        return self._parse_ai_response(text, session_data)
    
    async def _call_openai(self, messages: List[Dict], session_data: Dict) -> Dict:
        """Call OpenAI API"""
        
        response = await self.openai_client.chat.completions.create(
            model="gpt-4o-mini",  # or gpt-4o for better quality
            messages=messages,
            max_tokens=1000,
            temperature=0.7
        )
        
        text = response.choices[0].message.content
        return self._parse_ai_response(text, session_data)
    
    def _parse_ai_response(self, text: str, session_data: Dict) -> Dict:
        """
        Parse AI response and extract actions
        Looks for special markers in the response
        """
        response = {"text": text, "actions": [], "session_updates": {}}
        
        # Check for action markers like [ACTION:optimize] or [ACTION:simulate]
        action_pattern = r'\[ACTION:(\w+)\]'
        actions = re.findall(action_pattern, text)
        
        for action in actions:
            if action == "optimize":
                response["actions"].append({
                    "type": "button",
                    "label": "Optimize Design",
                    "action": "optimize"
                })
            elif action == "simulate":
                response["actions"].append({
                    "type": "button", 
                    "label": "Run Simulation",
                    "action": "simulate"
                })
            elif action == "analyze":
                response["actions"].append({
                    "type": "button",
                    "label": "Analyze",
                    "action": "analyze"
                })
        
        # Remove action markers from displayed text
        response["text"] = re.sub(action_pattern, '', text).strip()
        
        return response
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []


class RuleBasedHandler:
    """Original rule-based handler as fallback"""
    
    def __init__(self):
        self.commands = {
            r"upload|load|import.*file": "handle_upload",
            r"analyze|check|inspect": "handle_analyze",
            r"optimize|improve|better.*design": "handle_optimize",
            r"add.*riser|place.*riser|riser.*needed": "handle_add_risers",
            r"simulate|run.*simulation|check.*solidification": "handle_simulate",
            r"show.*result|display|visualize": "handle_show_results",
            r"set.*material|use.*material|aluminum|steel|iron": "handle_set_material",
            r"help|what.*can.*do|commands": "handle_help",
        }
    
    async def process_message(self, message: str, session_data: Dict,
                            websocket=None) -> Dict:
        """Process message with regex patterns"""
        message_lower = message.lower()
        
        for pattern, handler_name in self.commands.items():
            if re.search(pattern, message_lower):
                handler = getattr(self, handler_name)
                return await handler(message, session_data, websocket)
        
        return await self.handle_conversation(message, session_data)
    
    async def handle_upload(self, message: str, session_data: Dict, 
                          websocket=None) -> Dict:
        return {
            "text": "Please upload your STEP or STL file using the upload button, or drag and drop it here.",
            "actions": [{"type": "prompt_upload"}]
        }
    
    async def handle_analyze(self, message: str, session_data: Dict,
                           websocket=None) -> Dict:
        if not session_data.get("geometry"):
            return {
                "text": "Please upload a casting model first so I can analyze it.",
                "actions": [{"type": "prompt_upload"}]
            }
        
        geometry = session_data["geometry"]
        hotspots = geometry.get("hotspots", [])
        
        response = f"📊 **Analysis Complete**\n\n"
        response += f"**Casting Volume:** {geometry.get('volume', 0):.0f} mm³\n"
        response += f"**Surface Area:** {geometry.get('surface_area', 0):.0f} mm²\n"
        response += f"**Hot Spots Detected:** {len(hotspots)}\n\n"
        
        if hotspots:
            response += "**Critical Areas:**\n"
            for i, hs in enumerate(hotspots[:3]):
                response += f"  {i+1}. Position {hs['position']} - Modulus {hs['modulus']:.2f} ({hs['severity']})\n"
        else:
            response += "No critical hot spots detected. This is a relatively simple casting.\n"
        
        response += "\nWould you like me to optimize the riser design?"
        
        return {
            "text": response,
            "data": {"hotspots": hotspots},
            "actions": [
                {"type": "button", "label": "Optimize Design", "action": "optimize"},
                {"type": "button", "label": "Run Simulation", "action": "simulate"}
            ]
        }
    
    async def handle_optimize(self, message: str, session_data: Dict,
                            websocket=None) -> Dict:
        if not session_data.get("geometry"):
            return {
                "text": "Please upload a casting model first.",
                "actions": [{"type": "prompt_upload"}]
            }
        
        material = self._detect_material(message) or session_data.get("material", "aluminum_a356")
        
        response = f"🔧 **Starting Optimization**\n\n"
        response += f"Material: {material.replace('_', ' ').title()}\n"
        response += "Running AI optimization to place risers and design gating...\n\n"
        
        return {
            "text": response,
            "actions": [{"type": "start_optimization", "material": material}],
            "session_updates": {"material": material, "optimizing": True}
        }
    
    async def handle_add_risers(self, message: str, session_data: Dict,
                              websocket=None) -> Dict:
        if not session_data.get("geometry"):
            return {
                "text": "Please upload a casting model first.",
                "actions": [{"type": "prompt_upload"}]
            }
        
        hotspots = session_data["geometry"].get("hotspots", [])
        
        if not hotspots:
            return {
                "text": "No hot spots detected. A single top riser should be sufficient.\n\nWould you like me to add it?",
                "actions": [{"type": "button", "label": "Add Top Riser", "action": "add_riser"}]
            }
        
        response = f"📍 **Riser Placement**\n\n"
        response += f"I'll place {len(hotspots)} riser(s) at the detected hot spots:\n\n"
        
        for i, hs in enumerate(hotspots[:3]):
            response += f"  **Riser {i+1}:** At position {hs['position']}\n"
            response += f"  - Target modulus: {hs['modulus']:.2f}\n"
            response += f"  - Will be sized to solidify after this region\n\n"
        
        return {
            "text": response,
            "actions": [
                {"type": "button", "label": "Auto-Place Risers", "action": "place_risers"},
                {"type": "button", "label": "Customize", "action": "customize_risers"}
            ]
        }
    
    async def handle_simulate(self, message: str, session_data: Dict,
                            websocket=None) -> Dict:
        if not session_data.get("geometry"):
            return {
                "text": "Please upload a casting model first.",
                "actions": [{"type": "prompt_upload"}]
            }
        
        if not session_data.get("risers"):
            return {
                "text": "No risers placed yet. Would you like me to optimize the design first?",
                "actions": [
                    {"type": "button", "label": "Optimize Design", "action": "optimize"},
                    {"type": "button", "label": "Add Risers Manually", "action": "add_risers"}
                ]
            }
        
        response = "🔥 **Running Solidification Simulation**\n\n"
        response += "Simulating heat flow and solidification with current design...\n\n"
        response += "This will predict:\n"
        response += "- Solidification time\n"
        response += "- Hot spot formation\n"
        response += "- Shrinkage porosity\n"
        response += "- Feeding effectiveness\n"
        
        return {
            "text": response,
            "actions": [{"type": "start_simulation"}]
        }
    
    async def handle_show_results(self, message: str, session_data: Dict,
                                websocket=None) -> Dict:
        results = session_data.get("simulation_results")
        
        if not results:
            return {
                "text": "No simulation results yet. Run a simulation first?",
                "actions": [{"type": "button", "label": "Run Simulation", "action": "simulate"}]
            }
        
        response = "📈 **Simulation Results**\n\n"
        response += f"**Solidification Time:** {results.get('solidification_time', 0):.1f} seconds\n"
        response += f"**Estimated Yield:** {results.get('yield_estimate', 0):.1f}%\n\n"
        
        defects = results.get("defects", [])
        if defects:
            response += f"**⚠️ Defects Detected:** {len(defects)}\n\n"
            for d in defects[:3]:
                response += f"  - {d['type'].replace('_', ' ').title()}: {d['severity']}\n"
                response += f"    Position: {d['position']}\n\n"
            response += "\nWould you like me to optimize to fix these defects?"
        else:
            response += "✅ **No defects predicted!**\n\n"
            response += "The design looks good. Ready for production."
        
        return {
            "text": response,
            "data": results,
            "actions": [
                {"type": "button", "label": "View 3D Results", "action": "view_3d"},
                {"type": "button", "label": "Export Report", "action": "export"}
            ] if not defects else [
                {"type": "button", "label": "Re-optimize", "action": "optimize"}
            ]
        }
    
    async def handle_set_material(self, message: str, session_data: Dict,
                                websocket=None) -> Dict:
        material = self._detect_material(message)
        
        if material:
            material_name = material.replace('_', ' ').title()
            return {
                "text": f"✅ Material set to **{material_name}**\n\n"
                        f"Thermal properties loaded:\n"
                        f"- Density, specific heat, conductivity\n"
                        f"- Liquidus/solidus temperatures\n"
                        f"- Latent heat of fusion\n\n"
                        f"Ready to optimize for this alloy.",
                "session_updates": {"material": material}
            }
        else:
            return {
                "text": "Available materials:\n"
                        "- Aluminum A356 (common sand casting alloy)\n"
                        "- Aluminum A380 (die casting)\n"
                        "- Steel 1045 (carbon steel)\n"
                        "- Gray Cast Iron\n\n"
                        "Which would you like to use?",
                "actions": [
                    {"type": "button", "label": "Aluminum A356", "action": "set_material_a356"},
                    {"type": "button", "label": "Steel 1045", "action": "set_material_steel"},
                    {"type": "button", "label": "Cast Iron", "action": "set_material_iron"}
                ]
            }
    
    async def handle_help(self, message: str, session_data: Dict,
                        websocket=None) -> Dict:
        response = "🤖 **MetalGPT Help**\n\n"
        response += "I can help you optimize metal casting designs. Here's what I can do:\n\n"
        
        response += "**📁 File Operations:**\n"
        response += "- 'Upload a STEP file' - Import your CAD model\n\n"
        
        response += "**🔍 Analysis:**\n"
        response += "- 'Analyze this casting' - Find hot spots and thick sections\n\n"
        
        response += "**⚙️ Optimization:**\n"
        response += "- 'Optimize for aluminum' - AI designs risers and gating\n"
        response += "- 'Add risers automatically' - Place risers at hot spots\n\n"
        
        response += "**🔥 Simulation:**\n"
        response += "- 'Run simulation' - Predict solidification and defects\n"
        response += "- 'Show results' - View porosity and yield estimates\n\n"
        
        response += "**⚗️ Materials:**\n"
        response += "- 'Use steel' / 'Set material to aluminum A356'\n\n"
        
        response += "What would you like to do?"
        
        return {"text": response}
    
    async def handle_conversation(self, message: str, session_data: Dict) -> Dict:
        if not session_data.get("geometry"):
            return {
                "text": "Hello! I'm MetalGPT, your AI casting assistant.\n\n"
                        "Upload a STEP or STL file of your casting, and I'll help you:\n"
                        "- Analyze for hot spots\n"
                        "- Design optimal risers\n"
                        "- Simulate solidification\n"
                        "- Predict and prevent defects\n\n"
                        "What casting are you working on?"
            }
        
        return {
            "text": "I see you have a casting loaded. I can:\n\n"
                    "1. **Analyze** - Check for hot spots and feeding zones\n"
                    "2. **Optimize** - AI designs risers and gating\n"
                    "3. **Simulate** - Run solidification analysis\n\n"
                    "What would you like to do?"
        }
    
    def _detect_material(self, message: str) -> Optional[str]:
        message_lower = message.lower()
        
        materials = {
            "aluminum_a356": ["a356", "aluminum a356", "al 356"],
            "aluminum_a380": ["a380", "aluminum a380", "al 380"],
            "steel_1045": ["steel", "1045", "carbon steel", "mild steel"],
            "cast_iron_gray": ["iron", "gray iron", "grey iron", "cast iron"]
        }
        
        for material, keywords in materials.items():
            for kw in keywords:
                if kw in message_lower:
                    return material
        
        return None


# Backwards compatibility - use AI handler as default
ChatHandler = AIChatHandler
