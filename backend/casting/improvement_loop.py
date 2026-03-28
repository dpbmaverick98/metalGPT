"""
AI Improvement Loop - Automatic defect detection and iterative optimization
Uses Vercel AI SDK for structured output and streaming
"""
import asyncio
import numpy as np
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum

from chat.ai_provider import get_ai_provider, ImprovementPlan, DesignAction


class DefectType(Enum):
    SHRINKAGE_POROSITY = "shrinkage_porosity"
    HOT_TEAR = "hot_tear"
    COLD_SHUT = "cold_shut"
    MISRUN = "misrun"
    GAS_POROSITY = "gas_porosity"


@dataclass
class Defect:
    type: DefectType
    severity: str  # "low", "medium", "high", "critical"
    position: List[float]
    volume: float
    description: str
    suggested_fix: str


@dataclass
class DesignIteration:
    iteration: int
    risers: List[Dict]
    gating: Dict
    defects: List[Defect]
    yield_pct: float
    improvements: List[str]
    converged: bool


class AIImprovementLoop:
    """
    Automated improvement loop that:
    1. Runs simulation
    2. Detects defects
    3. AI analyzes root cause
    4. Suggests design changes
    5. Re-runs until converged
    """
    
    def __init__(self, max_iterations: int = 10, convergence_threshold: float = 0.05):
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self.iteration_history: List[DesignIteration] = []
        
    async def run_improvement_loop(
        self,
        geometry: Dict,
        material: str,
        simulator,
        optimizer,
        ai_client=None,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """
        Run the full AI improvement loop
        
        Returns:
            Final optimized design with iteration history
        """
        print(f"🚀 Starting AI Improvement Loop (max {self.max_iterations} iterations)")
        
        # Initial optimization
        current_design = optimizer.optimize(geometry, material)
        
        for iteration in range(1, self.max_iterations + 1):
            print(f"\n📊 Iteration {iteration}/{self.max_iterations}")
            
            if progress_callback:
                await progress_callback({
                    "iteration": iteration,
                    "max_iterations": self.max_iterations,
                    "phase": "simulating",
                    "message": f"Running simulation (iteration {iteration})..."
                })
            
            # Run simulation
            sim_results = simulator.run(
                geometry=geometry,
                risers=current_design["risers"],
                gating=current_design["gating"],
                material=material
            )
            
            # Detect and classify defects
            defects = self._analyze_defects(sim_results, geometry, current_design)
            
            print(f"   Found {len(defects)} defects")
            for d in defects:
                print(f"   - {d.type.value}: {d.severity} at {d.position}")
            
            # Check convergence
            if len(defects) == 0:
                print("✅ No defects detected! Design converged.")
                self._record_iteration(iteration, current_design, defects, [], True)
                break
            
            # AI analysis and improvement suggestions
            if progress_callback:
                await progress_callback({
                    "iteration": iteration,
                    "phase": "analyzing",
                    "message": f"AI analyzing defects and suggesting improvements..."
                })
            
            improvements = await self._generate_improvements(
                defects=defects,
                current_design=current_design,
                geometry=geometry,
                sim_results=sim_results,
                ai_client=ai_client
            )
            
            print(f"   AI suggests: {improvements}")
            
            # Apply improvements
            if progress_callback:
                await progress_callback({
                    "iteration": iteration,
                    "phase": "optimizing",
                    "message": f"Applying design improvements..."
                })
            
            new_design = self._apply_improvements(
                current_design, improvements, defects, geometry
            )
            
            # Record iteration
            self._record_iteration(
                iteration=iteration,
                design=current_design,
                defects=defects,
                improvements=improvements,
                converged=False
            )
            
            # Check for stagnation
            if self._is_stagnant():
                print("⚠️ Design stagnated. Trying alternative approach...")
                new_design = self._try_alternative_approach(current_design, geometry)
            
            current_design = new_design
            
            # Brief delay for UI updates
            await asyncio.sleep(0.1)
        
        else:
            print(f"⚠️ Reached max iterations ({self.max_iterations})")
        
        # Final simulation
        final_results = simulator.run(
            geometry=geometry,
            risers=current_design["risers"],
            gating=current_design["gating"],
            material=material
        )
        
        final_defects = self._analyze_defects(final_results, geometry, current_design)
        
        return {
            "final_design": current_design,
            "final_simulation": final_results,
            "final_defects": final_defects,
            "iteration_count": len(self.iteration_history),
            "converged": len(final_defects) == 0,
            "iteration_history": [
                {
                    "iteration": i.iteration,
                    "riser_count": len(i.risers),
                    "defect_count": len(i.defects),
                    "yield": i.yield_pct,
                    "improvements": i.improvements,
                    "converged": i.converged
                }
                for i in self.iteration_history
            ],
            "summary": self._generate_summary()
        }
    
    def _analyze_defects(self, sim_results: Dict, geometry: Dict, 
                        design: Dict) -> List[Defect]:
        """
        Analyze simulation results and classify defects
        """
        defects = []
        
        # Extract raw defects from simulation
        raw_defects = sim_results.get("defects", [])
        
        for raw in raw_defects:
            defect_type = self._classify_defect_type(raw)
            
            # Determine severity based on volume and location
            severity = self._calculate_severity(raw, geometry)
            
            # Generate suggested fix based on defect type
            suggested_fix = self._suggest_fix(defect_type, raw, design)
            
            defect = Defect(
                type=defect_type,
                severity=severity,
                position=raw.get("position", [0, 0, 0]),
                volume=raw.get("volume", 0),
                description=self._describe_defect(defect_type, raw),
                suggested_fix=suggested_fix
            )
            defects.append(defect)
        
        # Also check for potential issues not caught by simulation
        potential_defects = self._check_potential_issues(geometry, design)
        defects.extend(potential_defects)
        
        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        defects.sort(key=lambda d: severity_order.get(d.severity, 4))
        
        return defects
    
    def _classify_defect_type(self, raw_defect: Dict) -> DefectType:
        """Classify raw defect into DefectType"""
        defect_type_str = raw_defect.get("type", "").lower()
        
        if "shrinkage" in defect_type_str or "porosity" in defect_type_str:
            return DefectType.SHRINKAGE_POROSITY
        elif "tear" in defect_type_str or "crack" in defect_type_str:
            return DefectType.HOT_TEAR
        elif "cold" in defect_type_str or "shut" in defect_type_str:
            return DefectType.COLD_SHUT
        elif "misrun" in defect_type_str:
            return DefectType.MISRUN
        elif "gas" in defect_type_str or "blowhole" in defect_type_str:
            return DefectType.GAS_POROSITY
        else:
            return DefectType.SHRINKAGE_POROSITY  # Default
    
    def _calculate_severity(self, raw_defect: Dict, geometry: Dict) -> str:
        """Calculate defect severity based on size and location"""
        volume = raw_defect.get("volume", 0)
        max_porosity = raw_defect.get("max_porosity", 0)
        
        cast_volume = geometry.get("volume", 1000)
        volume_ratio = volume / cast_volume
        
        if volume_ratio > 0.05 or max_porosity > 0.15:
            return "critical"
        elif volume_ratio > 0.02 or max_porosity > 0.10:
            return "high"
        elif volume_ratio > 0.005 or max_porosity > 0.05:
            return "medium"
        else:
            return "low"
    
    def _suggest_fix(self, defect_type: DefectType, raw_defect: Dict, 
                    design: Dict) -> str:
        """Suggest fix based on defect type"""
        suggestions = {
            DefectType.SHRINKAGE_POROSITY: [
                "Increase riser size or add additional riser",
                "Move riser closer to defect location",
                "Add chill to accelerate local solidification",
                "Increase riser neck diameter for better feeding"
            ],
            DefectType.HOT_TEAR: [
                "Modify riser placement to reduce restraint",
                "Add fillets to sharp corners",
                "Improve directional solidification with chills",
                "Consider split risers for complex geometries"
            ],
            DefectType.COLD_SHUT: [
                "Increase pouring temperature",
                "Improve gating design for faster filling",
                "Add overflow at cold shut location",
                "Reduce section thickness variation"
            ],
            DefectType.MISRUN: [
                "Increase ingate area for faster filling",
                "Raise pouring temperature",
                "Add vents to improve air escape",
                "Consider multiple ingates"
            ],
            DefectType.GAS_POROSITY: [
                "Improve venting in mold design",
                "Reduce pouring turbulence",
                "Add filters to gating system",
                "Check for moisture in mold material"
            ]
        }
        
        return random.choice(suggestions.get(defect_type, ["Review design"]))
    
    def _describe_defect(self, defect_type: DefectType, raw_defect: Dict) -> str:
        """Generate human-readable defect description"""
        descriptions = {
            DefectType.SHRINKAGE_POROSITY: "Shrinkage cavity due to inadequate feeding during solidification",
            DefectType.HOT_TEAR: "Crack formed during solidification due to thermal stress",
            DefectType.COLD_SHUT: "Lack of fusion between metal streams",
            DefectType.MISRUN: "Incomplete filling of mold cavity",
            DefectType.GAS_POROSITY: "Porosity caused by trapped gas"
        }
        return descriptions.get(defect_type, "Unknown defect")
    
    def _check_potential_issues(self, geometry: Dict, design: Dict) -> List[Defect]:
        """Check for potential issues not caught by simulation"""
        issues = []
        
        # Check if risers cover all hot spots
        hotspots = geometry.get("hotspots", [])
        risers = design.get("risers", [])
        
        covered_hotspots = set()
        for riser in risers:
            r_pos = riser.get("position", [0, 0, 0])
            for i, hs in enumerate(hotspots):
                hs_pos = hs.get("position", [0, 0, 0])
                distance = np.linalg.norm(np.array(r_pos) - np.array(hs_pos))
                if distance < riser.get("radius", 20) * 3:  # Within feeding distance
                    covered_hotspots.add(i)
        
        uncovered = set(range(len(hotspots))) - covered_hotspots
        for idx in uncovered:
            hs = hotspots[idx]
            issues.append(Defect(
                type=DefectType.SHRINKAGE_POROSITY,
                severity="high",
                position=hs.get("position", [0, 0, 0]),
                volume=hs.get("modulus", 10) * 100,  # Estimate
                description="Hot spot not covered by any riser",
                suggested_fix="Add riser at this location"
            ))
        
        return issues
    
    async def _generate_improvements(
        self,
        defects: List[Defect],
        current_design: Dict,
        geometry: Dict,
        sim_results: Dict,
        ai_client=None
    ) -> List[str]:
        """
        Generate improvement suggestions using Vercel AI SDK structured output
        """
        provider = get_ai_provider()
        
        if provider.is_available():
            try:
                # Use structured output for type-safe improvements
                plan = await provider.generate_improvement_plan(
                    defects=[{
                        "type": d.type.value,
                        "severity": d.severity,
                        "position": d.position,
                        "suggested_fix": d.suggested_fix
                    } for d in defects],
                    current_design=current_design,
                    geometry=geometry
                )
                
                # Convert structured actions to improvement strings
                improvements = []
                for action in plan.actions:
                    if action.action_type == "increase_riser_size":
                        improvements.append(f"increase_riser_size:{action.target_id}:{action.parameters.get('scale_factor', 1.2)}")
                    elif action.action_type == "add_riser":
                        pos = [action.parameters.get('x', 0), action.parameters.get('y', 0), action.parameters.get('z', 0)]
                        improvements.append(f"add_riser_at:{pos}")
                    elif action.action_type == "move_riser":
                        pos = [action.parameters.get('x', 0), action.parameters.get('y', 0), action.parameters.get('z', 0)]
                        improvements.append(f"move_riser:{action.target_id}:{pos}")
                    elif action.action_type == "increase_neck":
                        improvements.append(f"increase_neck:{action.target_id}:{action.parameters.get('scale_factor', 1.2)}")
                    elif action.action_type == "add_chill":
                        pos = [action.parameters.get('x', 0), action.parameters.get('y', 0), action.parameters.get('z', 0)]
                        improvements.append(f"add_chill_at:{pos}")
                
                return improvements
                
            except Exception as e:
                print(f"Structured improvement generation failed: {e}")
                return self._rule_generate_improvements(defects, current_design, geometry)
        else:
            return self._rule_generate_improvements(defects, current_design, geometry)
    
    async def _ai_generate_improvements(
        self,
        defects: List[Defect],
        current_design: Dict,
        geometry: Dict,
        sim_results: Dict,
        ai_client
    ) -> List[str]:
        """Use AI to analyze defects and suggest improvements"""
        
        # Build prompt
        prompt = f"""You are an expert casting engineer analyzing simulation results.

CURRENT DESIGN:
- Risers: {len(current_design['risers'])}
- Gating: Sprue r={current_design['gating']['sprue_radius']:.1f}mm, h={current_design['gating']['sprue_height']:.1f}mm
- Yield: {current_design['yield']:.1f}%

DEFECTS DETECTED:
"""
        
        for d in defects[:5]:  # Top 5 defects
            prompt += f"\n- {d.type.value} ({d.severity}) at {d.position}\n"
            prompt += f"  Volume: {d.volume:.0f} mm³\n"
            prompt += f"  Suggested fix: {d.suggested_fix}\n"
        
        prompt += """

Suggest specific design changes to fix these defects. Return a JSON list of actions like:
[
  "increase_riser_size:0:1.2",  // Increase riser 0 size by 20%
  "add_riser_at:[100,50,80]",    // Add new riser at position
  "move_riser:0:[120,60,90]",    // Move riser 0 to new position
  "add_chill_at:[100,50,80]",    // Add chill at position
  "increase_neck:0:1.3"          // Increase riser 0 neck by 30%
]
"""
        
        try:
            # Call AI
            if hasattr(ai_client, 'messages'):  # Anthropic
                response = await ai_client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = response.content[0].text
            else:  # OpenAI
                response = await ai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500
                )
                text = response.choices[0].message.content
            
            # Extract JSON
            import json
            import re
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
        except Exception as e:
            print(f"AI improvement generation failed: {e}")
        
        # Fallback to rule-based
        return self._rule_generate_improvements(defects, current_design, geometry)
    
    def _rule_generate_improvements(
        self,
        defects: List[Defect],
        current_design: Dict,
        geometry: Dict
    ) -> List[str]:
        """Rule-based improvement generation"""
        improvements = []
        
        for defect in defects:
            if defect.type == DefectType.SHRINKAGE_POROSITY:
                # Find nearest riser
                nearest_riser_idx = self._find_nearest_riser(
                    defect.position, current_design["risers"]
                )
                
                if nearest_riser_idx is not None:
                    if defect.severity in ["critical", "high"]:
                        improvements.append(f"increase_riser_size:{nearest_riser_idx}:1.3")
                        improvements.append(f"increase_neck:{nearest_riser_idx}:1.2")
                    else:
                        improvements.append(f"increase_riser_size:{nearest_riser_idx}:1.15")
                else:
                    # No nearby riser - add one
                    improvements.append(f"add_riser_at:{defect.position}")
            
            elif defect.type == DefectType.HOT_TEAR:
                improvements.append(f"add_chill_at:{defect.position}")
            
            elif defect.type == DefectType.COLD_SHUT:
                improvements.append("increase_pouring_temp:20")
                improvements.append("increase_ingate_area:1.2")
            
            elif defect.type == DefectType.MISRUN:
                improvements.append("increase_ingate_area:1.3")
                improvements.append("increase_pouring_temp:30")
        
        return improvements
    
    def _find_nearest_riser(self, position: List[float], 
                           risers: List[Dict]) -> Optional[int]:
        """Find index of nearest riser to position"""
        if not risers:
            return None
        
        min_dist = float('inf')
        nearest_idx = None
        
        for i, riser in enumerate(risers):
            r_pos = riser.get("position", [0, 0, 0])
            dist = np.linalg.norm(np.array(position) - np.array(r_pos))
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i
        
        return nearest_idx
    
    def _apply_improvements(
        self,
        current_design: Dict,
        improvements: List[str],
        defects: List[Defect],
        geometry: Dict
    ) -> Dict:
        """Apply improvement actions to design"""
        new_design = {
            "risers": [r.copy() for r in current_design["risers"]],
            "gating": current_design["gating"].copy(),
            "yield": current_design["yield"]
        }
        
        for improvement in improvements:
            parts = improvement.split(":")
            action = parts[0]
            
            if action == "increase_riser_size" and len(parts) >= 3:
                idx = int(parts[1])
                factor = float(parts[2])
                if idx < len(new_design["risers"]):
                    new_design["risers"][idx]["radius"] *= factor
                    new_design["risers"][idx]["height"] *= factor
                    new_design["risers"][idx]["volume"] *= factor ** 3
            
            elif action == "increase_neck" and len(parts) >= 3:
                idx = int(parts[1])
                factor = float(parts[2])
                if idx < len(new_design["risers"]):
                    new_design["risers"][idx]["neck_diameter"] *= factor
            
            elif action == "move_riser" and len(parts) >= 3:
                idx = int(parts[1])
                # Parse position from string
                pos_str = parts[2]
                # Handle format like "[100,50,80]"
                pos = [float(x) for x in pos_str.strip("[]").split(",")]
                if idx < len(new_design["risers"]):
                    new_design["risers"][idx]["position"] = pos
            
            elif action == "add_riser_at" and len(parts) >= 2:
                pos_str = parts[1]
                pos = [float(x) for x in pos_str.strip("[]").split(",")]
                
                # Create new riser
                new_riser = {
                    "id": len(new_design["risers"]),
                    "position": pos,
                    "radius": 25,
                    "diameter": 50,
                    "height": 75,
                    "neck_diameter": 35,
                    "neck_height": 20,
                    "volume": np.pi * 25**2 * 75
                }
                new_design["risers"].append(new_riser)
            
            elif action == "add_chill_at":
                # Chills would be handled separately in simulation
                pass
            
            elif action == "increase_ingate_area" and len(parts) >= 2:
                factor = float(parts[1])
                new_design["gating"]["ingate_radius"] *= np.sqrt(factor)
        
        # Recalculate yield
        cast_volume = geometry.get("volume", 1000)
        riser_volume = sum(r["volume"] for r in new_design["risers"])
        gating_volume = new_design["gating"].get("volume", 200)
        new_design["yield"] = 100.0 * cast_volume / (cast_volume + riser_volume + gating_volume)
        
        return new_design
    
    def _record_iteration(self, iteration: int, design: Dict,
                         defects: List[Defect], improvements: List[str],
                         converged: bool):
        """Record iteration to history"""
        self.iteration_history.append(DesignIteration(
            iteration=iteration,
            risers=design["risers"],
            gating=design["gating"],
            defects=defects,
            yield_pct=design["yield"],
            improvements=improvements,
            converged=converged
        ))
    
    def _is_stagnant(self) -> bool:
        """Check if design is stagnating (no improvement)"""
        if len(self.iteration_history) < 3:
            return False
        
        # Check last 3 iterations
        recent = self.iteration_history[-3:]
        defect_counts = [len(i.defects) for i in recent]
        
        # If defect count not decreasing, might be stagnant
        return defect_counts[0] <= defect_counts[1] <= defect_counts[2]
    
    def _try_alternative_approach(self, current_design: Dict, 
                                   geometry: Dict) -> Dict:
        """Try different strategy when stagnating"""
        new_design = {
            "risers": [r.copy() for r in current_design["risers"]],
            "gating": current_design["gating"].copy(),
            "yield": current_design["yield"]
        }
        
        # Strategy: Merge small risers into larger ones
        if len(new_design["risers"]) > 2:
            # Keep only the 2 largest risers and make them bigger
            new_design["risers"].sort(key=lambda r: r["volume"], reverse=True)
            new_design["risers"] = new_design["risers"][:2]
            
            for riser in new_design["risers"]:
                riser["radius"] *= 1.3
                riser["height"] *= 1.2
                riser["volume"] = np.pi * riser["radius"]**2 * riser["height"]
        else:
            # Add exothermic sleeve effect (simulated by increasing size)
            for riser in new_design["risers"]:
                riser["radius"] *= 1.15
                riser["volume"] = np.pi * riser["radius"]**2 * riser["height"]
        
        return new_design
    
    def _generate_summary(self) -> str:
        """Generate human-readable summary of improvement process"""
        if not self.iteration_history:
            return "No iterations performed."
        
        first = self.iteration_history[0]
        last = self.iteration_history[-1]
        
        summary = f"**Improvement Summary**\n\n"
        summary += f"Iterations: {len(self.iteration_history)}\n"
        summary += f"Initial defects: {len(first.defects)}\n"
        summary += f"Final defects: {len(last.defects)}\n"
        summary += f"Yield change: {first.yield_pct:.1f}% → {last.yield_pct:.1f}%\n"
        summary += f"Status: {'✅ Converged' if last.converged else '⚠️ Max iterations reached'}\n\n"
        
        if last.converged:
            summary += "The design successfully eliminated all predicted defects."
        else:
            summary += f"Remaining defects: {len(last.defects)}. Consider manual review."
        
        return summary


# Import random for suggestion selection
import random
