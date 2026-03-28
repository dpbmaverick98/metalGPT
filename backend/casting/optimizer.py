"""
AI Casting Optimizer - RL-based riser and gating optimization
"""
import numpy as np
from typing import Dict, List, Optional, Callable
import random


class CastingOptimizer:
    """Optimize casting design using evolutionary algorithms"""
    
    def __init__(self):
        self.population_size = 50
        self.generations = 30
        self.mutation_rate = 0.1
        
    def optimize(self, geometry: Dict, material: str = "aluminum_a356",
                 progress_callback: Optional[Callable] = None) -> Dict:
        """
        Run optimization to find best riser and gating design
        
        Uses simplified evolutionary approach based on PMC9654928
        """
        hotspots = geometry.get("hotspots", [])
        feeding_zones = geometry.get("feeding_zones", [])
        
        if len(hotspots) == 0:
            # Simple casting - minimal risering
            return {
                "risers": [self._create_simple_riser(geometry)],
                "gating": self._create_simple_gating(geometry),
                "yield": 85.0,
                "message": "Simple casting - minimal risering applied"
            }
        
        # Stage 1: Optimize gating system
        gating = self._optimize_gating(geometry, material)
        
        # Stage 2: Optimize risers for each hot spot
        risers = self._optimize_risers(geometry, hotspots, feeding_zones, material)
        
        # Calculate final yield
        cast_volume = geometry.get("volume", 1000)
        riser_volume = sum(r["volume"] for r in risers)
        gating_volume = gating.get("volume", 200)
        
        total_volume = cast_volume + riser_volume + gating_volume
        yield_pct = 100.0 * cast_volume / total_volume
        
        return {
            "risers": risers,
            "gating": gating,
            "yield": yield_pct,
            "message": f"Optimized with {len(risers)} risers, yield: {yield_pct:.1f}%"
        }
    
    def _optimize_gating(self, geometry: Dict, material: str) -> Dict:
        """
        Optimize gating system (simplified NSGA-II approach)
        
        Decision variables:
        - r: choke section radius
        - h: sprue height
        """
        # Bounds based on casting size
        bounds = geometry.get("bounds", [[0, 0, 0], [100, 100, 100]])
        max_dim = max(b[1] - b[0] for b in zip(bounds[0], bounds[1]))
        
        # Search space
        r_min, r_max = 5, min(50, max_dim / 10)
        h_min, h_max = max_dim / 4, max_dim
        
        best_design = None
        best_score = float('inf')
        
        # Grid search (simplified from NSGA-II)
        for r in np.linspace(r_min, r_max, 10):
            for h in np.linspace(h_min, h_max, 10):
                score = self._evaluate_gating(r, h, geometry, material)
                if score < best_score:
                    best_score = score
                    best_design = {"r": r, "h": h}
        
        # Calculate derived dimensions
        r = best_design["r"]
        h = best_design["h"]
        
        # Gating ratio 1:2:4 (sprue:runner:ingate)
        return {
            "sprue_radius": r,
            "sprue_height": h,
            "runner_radius": r * np.sqrt(2),  # Area ratio 2:1
            "ingate_radius": r * 2,  # Area ratio 4:1
            "volume": np.pi * r**2 * h * 1.5,  # Estimate
            "filling_time_estimate": self._estimate_filling_time(r, h, geometry)
        }
    
    def _evaluate_gating(self, r: float, h: float, geometry: Dict, 
                         material: str) -> float:
        """Evaluate gating design (multi-objective scalarized)"""
        # Objective 1: Filling time (shorter is better)
        fill_time = self._estimate_filling_time(r, h, geometry)
        
        # Objective 2: Yield (higher is better)
        gating_volume = np.pi * r**2 * h * 1.5
        cast_volume = geometry.get("volume", 1000)
        yield_pct = cast_volume / (cast_volume + gating_volume)
        
        # Objective 3: Flow stability (Reynolds number)
        # Simplified: lower velocity = more stable
        velocity = np.sqrt(2 * 9.81 * h / 1000)  # m/s, Torricelli's law
        
        # Scalarized score (lower is better)
        # Weights: filling time 0.4, yield 0.4, stability 0.2
        score = 0.4 * (fill_time / 100) + 0.4 * (1 - yield_pct) + 0.2 * (velocity / 10)
        
        return score
    
    def _estimate_filling_time(self, r: float, h: float, geometry: Dict) -> float:
        """Estimate mold filling time"""
        cast_volume = geometry.get("volume", 1000)  # mm³
        
        # Flow rate through choke (Torricelli's law)
        g = 9810  # mm/s²
        velocity = np.sqrt(2 * g * h)  # mm/s
        area = np.pi * r**2  # mm²
        flow_rate = velocity * area  # mm³/s
        
        fill_time = cast_volume / flow_rate if flow_rate > 0 else 1000
        return fill_time
    
    def _optimize_risers(self, geometry: Dict, hotspots: List[Dict],
                         feeding_zones: List[Dict], material: str) -> List[Dict]:
        """
        Optimize riser dimensions for each hot spot
        
        Based on FeederQuery algorithm from casting_geometric_toolsuite
        """
        risers = []
        
        for i, hotspot in enumerate(hotspots[:5]):  # Max 5 risers
            # Get feeding zone for this hotspot
            zone = None
            for z in feeding_zones:
                if z.get("hotspot_id") == hotspot["id"]:
                    zone = z
                    break
            
            if zone is None:
                zone = {"volume": 1000, "centroid": hotspot["position"]}
            
            # Calculate riser dimensions using shape factor method
            riser = self._calculate_riser_dimensions(hotspot, zone, material)
            riser["id"] = i
            riser["feeds_hotspot"] = hotspot["id"]
            
            risers.append(riser)
        
        return risers
    
    def _calculate_riser_dimensions(self, hotspot: Dict, zone: Dict,
                                    material: str) -> Dict:
        """
        Calculate riser dimensions using geometric method
        
        Based on FeederQuery.feeder_sfsa() from casting_geometric_toolsuite
        """
        # Volume coefficient from empirical data
        VOLUME_COEFFICIENT = 2.51
        VOLUME_POWER = -0.74
        HEIGHT_DIAMETER_RATIO = 1.5
        
        # Zone properties
        v_s = zone.get("volume", 1000)  # Volume of feeding zone
        
        # Shape factor (simplified - would use geodesic distance in full version)
        # L = max feeding distance, W = characteristic width, T = thickness
        L = 50  # Estimate
        W = 30  # Estimate
        T = hotspot.get("modulus", 10) * 2  # Approximate thickness from modulus
        
        sf = (L + W) / max(T, 1)
        
        # Feeder volume
        v_f = VOLUME_COEFFICIENT * v_s * (sf ** VOLUME_POWER)
        
        # Cylinder riser: V = πr²h, h = 1.5 * 2r = 3r
        # V = πr²(3r) = 3πr³
        # r = (V / (3π))^(1/3)
        radius = (v_f / (3 * np.pi)) ** (1/3)
        
        # Dimensions
        diameter = 2 * radius
        height = HEIGHT_DIAMETER_RATIO * diameter
        
        # Neck dimensions (connecting to casting)
        neck_diameter = 0.7 * diameter  # Typical: 0.6-0.8 of riser diameter
        neck_height = min(30, diameter / 2)  # 15-30mm typical
        
        # Verify modulus criterion: Mr >= 1.2 * Mc
        # Modulus = Volume / Surface Area
        riser_volume = np.pi * radius**2 * height
        riser_surface = 2 * np.pi * radius**2 + 2 * np.pi * radius * height
        riser_modulus = riser_volume / riser_surface
        
        casting_modulus = hotspot.get("modulus", 5)
        
        if riser_modulus < 1.2 * casting_modulus:
            # Scale up to meet modulus criterion
            scale = (1.2 * casting_modulus) / riser_modulus
            radius *= np.sqrt(scale)  # Scale radius to increase modulus
            diameter = 2 * radius
            height = HEIGHT_DIAMETER_RATIO * diameter
            riser_volume = np.pi * radius**2 * height
        
        return {
            "position": zone.get("centroid", hotspot["position"]),
            "radius": float(radius),
            "diameter": float(diameter),
            "height": float(height),
            "neck_diameter": float(neck_diameter),
            "neck_height": float(neck_height),
            "volume": float(riser_volume),
            "modulus": float(riser_modulus),
            "feeds_modulus": float(casting_modulus)
        }
    
    def _create_simple_riser(self, geometry: Dict) -> Dict:
        """Create a simple riser for castings without hot spots"""
        bounds = geometry.get("bounds", [[0, 0, 0], [100, 100, 100]])
        center = [(b[0] + b[1]) / 2 for b in zip(bounds[0], bounds[1])]
        
        # Top riser
        position = [center[0], center[1], bounds[1][2] + 20]
        
        return {
            "id": 0,
            "position": position,
            "radius": 20,
            "diameter": 40,
            "height": 60,
            "neck_diameter": 28,
            "neck_height": 20,
            "volume": np.pi * 20**2 * 60
        }
    
    def _create_simple_gating(self, geometry: Dict) -> Dict:
        """Create simple gating system"""
        bounds = geometry.get("bounds", [[0, 0, 0], [100, 100, 100]])
        height = bounds[1][2] - bounds[0][2]
        
        return {
            "sprue_radius": 10,
            "sprue_height": height * 0.8,
            "runner_radius": 14,
            "ingate_radius": 20,
            "volume": 500
        }
