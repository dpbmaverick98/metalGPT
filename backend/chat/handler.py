"""
Chat handler - Natural language interface for casting design
"""
import json
import re
from typing import Dict, Optional


class ChatHandler:
    """Handle natural language commands for casting optimization"""
    
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
        """
        Process a chat message and return response
        
        Args:
            message: User's natural language input
            session_data: Current session state
            websocket: Optional WebSocket for streaming responses
        
        Returns:
            Response dict with text, data, and actions
        """
        message_lower = message.lower()
        
        # Check for commands
        for pattern, handler_name in self.commands.items():
            if re.search(pattern, message_lower):
                handler = getattr(self, handler_name)
                return await handler(message, session_data, websocket)
        
        # Default: conversational response
        return await self.handle_conversation(message, session_data)
    
    async def handle_upload(self, message: str, session_data: Dict, 
                          websocket=None) -> Dict:
        """Handle file upload request"""
        return {
            "text": "Please upload your STEP or STL file using the upload button, or drag and drop it here.",
            "actions": [{"type": "prompt_upload"}],
            "session_updates": {}
        }
    
    async def handle_analyze(self, message: str, session_data: Dict,
                           websocket=None) -> Dict:
        """Handle geometry analysis request"""
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
        """Handle optimization request"""
        if not session_data.get("geometry"):
            return {
                "text": "Please upload a casting model first.",
                "actions": [{"type": "prompt_upload"}]
            }
        
        # Detect material from message
        material = self._detect_material(message) or session_data.get("material", "aluminum_a356")
        
        response = f"🔧 **Starting Optimization**\n\n"
        response += f"Material: {material.replace('_', ' ').title()}\n"
        response += "Running AI optimization to place risers and design gating...\n\n"
        
        # In real implementation, this would trigger the optimizer
        # and stream progress via WebSocket
        
        return {
            "text": response,
            "actions": [{"type": "start_optimization", "material": material}],
            "session_updates": {"material": material, "optimizing": True}
        }
    
    async def handle_add_risers(self, message: str, session_data: Dict,
                              websocket=None) -> Dict:
        """Handle riser addition request"""
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
        """Handle simulation request"""
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
        """Handle results display request"""
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
        """Handle material selection"""
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
        """Show help message"""
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
        """Handle general conversation"""
        # Check if we have a model loaded
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
        
        # We have a model - be helpful about next steps
        return {
            "text": "I see you have a casting loaded. I can:\n\n"
                    "1. **Analyze** - Check for hot spots and feeding zones\n"
                    "2. **Optimize** - AI designs risers and gating\n"
                    "3. **Simulate** - Run solidification analysis\n\n"
                    "What would you like to do?"
        }
    
    def _detect_material(self, message: str) -> Optional[str]:
        """Detect material from message text"""
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
