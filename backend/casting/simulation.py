"""
FDM Solidification Simulation
Ported from casting_geometric_toolsuite SolidificationKernel
"""
import numpy as np
from scipy import sparse
from scipy.sparse import linalg as sparse_linalg
from scipy.sparse.linalg import spsolve
from typing import Dict, List, Optional, Tuple
import numba
from dataclasses import dataclass


@dataclass
class MaterialProperties:
    """Thermal properties for casting materials"""
    density: float           # kg/m³
    specific_heat: float     # J/(kg·K)
    thermal_conductivity: float  # W/(m·K)
    liquidus_temp: float     # °C
    solidus_temp: float      # °C
    latent_heat: float       # J/kg
    initial_temp: float      # Pouring temperature, °C


# Material database
MATERIALS = {
    "aluminum_a356": MaterialProperties(
        density=2630,
        specific_heat=963,
        thermal_conductivity=137.5,
        liquidus_temp=595,
        solidus_temp=555,
        latent_heat=3.9e5,
        initial_temp=710
    ),
    "aluminum_a380": MaterialProperties(
        density=2760,
        specific_heat=963,
        thermal_conductivity=109.0,
        liquidus_temp=595,
        solidus_temp=540,
        latent_heat=3.9e5,
        initial_temp=700
    ),
    "steel_1045": MaterialProperties(
        density=7850,
        specific_heat=486,
        thermal_conductivity=51.9,
        liquidus_temp=1495,
        solidus_temp=1410,
        latent_heat=2.72e5,
        initial_temp=1600
    ),
    "cast_iron_gray": MaterialProperties(
        density=7200,
        specific_heat=544,
        thermal_conductivity=52.0,
        liquidus_temp=1200,
        solidus_temp=1150,
        latent_heat=2.1e5,
        initial_temp=1350
    )
}


class FDMSimulator:
    """Finite Difference Method solidification simulator"""
    
    def __init__(self, ambient_temp: float = 25.0):
        self.ambient_temp = ambient_temp
        self.heat_transfer_coeff = 500.0  # W/(m²·K) casting-mold interface
        
    def run(self, geometry: Dict, risers: List[Dict], 
            gating: Optional[Dict], material: str = "aluminum_a356") -> Dict:
        """
        Run solidification simulation
        
        Args:
            geometry: Voxelized geometry data
            risers: List of riser definitions
            gating: Gating system parameters
            material: Material key from MATERIALS
        
        Returns:
            Simulation results including defect predictions
        """
        props = MATERIALS.get(material, MATERIALS["aluminum_a356"])
        
        # Reconstruct voxel grid
        voxel_shape = tuple(geometry["voxels"])
        
        # Create material ID field
        material_ids = self._create_material_field(
            voxel_shape, geometry, risers, gating
        )
        
        # Initial temperature field
        temperature = self._initialize_temperature(material_ids, props)
        
        # Run time-stepping simulation
        results = self._solve_transient(
            temperature, material_ids, props, geometry["voxel_size"]
        )
        
        # Analyze results for defects
        defects = self._detect_defects(results, material_ids, props)
        
        return {
            "solidification_time": float(results["final_time"]),
            "temperature_history": results["temperature_history"],
            "solidification_front": results["solidification_front"],
            "defects": defects,
            "porosity_map": results["porosity_map"],
            "yield_estimate": self._estimate_yield(geometry, risers, gating)
        }
    
    def _create_material_field(self, shape: Tuple[int, ...], 
                               geometry: Dict,
                               risers: List[Dict],
                               gating: Optional[Dict]) -> np.ndarray:
        """Create material ID field (0=ambient, 1=mold, 2=casting, 3=riser)"""
        material_ids = np.ones(shape, dtype=np.int32)  # Start with mold
        
        # Mark casting region (from geometry)
        # This would use the actual voxel data from geometry
        center = tuple(s // 2 for s in shape)
        radius = min(shape) // 3
        
        # Simple sphere for casting (replace with actual geometry)
        z, y, x = np.ogrid[:shape[0], :shape[1], :shape[2]]
        casting_mask = ((x - center[2])**2 + 
                       (y - center[1])**2 + 
                       (z - center[0])**2) < radius**2
        material_ids[casting_mask] = 2  # Casting
        
        # Mark risers
        for riser in risers:
            pos = riser.get("position", [0, 0, 0])
            r = riser.get("radius", 10)
            
            # Scale to voxel coordinates
            vx = int(pos[0] / geometry["voxel_size"])
            vy = int(pos[1] / geometry["voxel_size"])
            vz = int(pos[2] / geometry["voxel_size"])
            vr = int(r / geometry["voxel_size"])
            
            riser_mask = ((x - vx)**2 + (y - vy)**2 + (z - vz)**2) < vr**2
            material_ids[riser_mask] = 3  # Riser
        
        return material_ids
    
    def _initialize_temperature(self, material_ids: np.ndarray,
                                props: MaterialProperties) -> np.ndarray:
        """Set initial temperatures"""
        temp = np.full_like(material_ids, self.ambient_temp, dtype=float)
        
        # Casting and risers start at pouring temperature
        temp[material_ids >= 2] = props.initial_temp
        
        return temp
    
    def _solve_transient(self, temperature: np.ndarray,
                         material_ids: np.ndarray,
                         props: MaterialProperties,
                         voxel_size: float,
                         max_time: float = 10000.0,
                         save_interval: float = 100.0) -> Dict:
        """
        Solve transient heat conduction with phase change
        
        Uses implicit time stepping with enthalpy method for latent heat
        """
        shape = temperature.shape
        n_cells = np.prod(shape)
        
        # Flatten for matrix operations
        T = temperature.flatten()
        
        # Build system matrix (sparse)
        # This is a simplified version - full version would use proper FVM discretization
        
        # Time step (adaptive based on stability)
        alpha = props.thermal_conductivity / (props.density * props.specific_heat)
        dt = 0.5 * voxel_size**2 / alpha  # CFL condition
        
        # Enthalpy for phase tracking
        enthalpy = self._temperature_to_enthalpy(T, props)
        
        # History for analysis
        history = []
        solidification_front = []
        
        t = 0.0
        step = 0
        
        while t < max_time and T[material_ids.flatten() >= 2].max() > props.solidus_temp:
            # Build and solve system
            A, b = self._build_system(T, material_ids, props, voxel_size, dt)
            
            # Solve: A*T_new = b
            try:
                T_new = spsolve(A, b)
            except:
                # Fallback to iterative solver
                T_new, _ = sparse_linalg.bicgstab(A, b, x0=T, tol=1e-8)
            
            # Update enthalpy and handle phase change
            enthalpy_new = enthalpy + props.specific_heat * (T_new - T)
            T = self._enthalpy_to_temperature(enthalpy_new, props)
            enthalpy = enthalpy_new
            
            # Record history
            if step % int(save_interval / dt) == 0:
                history.append({
                    "time": t,
                    "temperature": T.copy(),
                    "liquid_fraction": self._liquid_fraction(T, props)
                })
                
                # Track solidification front
                liquid_frac = self._liquid_fraction(T, props)
                casting_mask = material_ids.flatten() >= 2
                if casting_mask.any():
                    avg_liquid = liquid_frac[casting_mask].mean()
                    solidification_front.append({
                        "time": t,
                        "avg_liquid_fraction": float(avg_liquid)
                    })
            
            T = T_new
            t += dt
            step += 1
            
            if step > 100000:  # Safety limit
                break
        
        # Final analysis
        final_temp = T.reshape(shape)
        liquid_frac = self._liquid_fraction(T, props).reshape(shape)
        
        # Detect potential shrinkage (regions that solidified without feeding)
        porosity_map = self._estimate_porosity(
            final_temp, liquid_frac, material_ids, props
        )
        
        return {
            "final_time": t,
            "final_temperature": final_temp,
            "temperature_history": history,
            "solidification_front": solidification_front,
            "porosity_map": porosity_map,
            "liquid_fraction": liquid_frac
        }
    
    def _build_system(self, T: np.ndarray, material_ids: np.ndarray,
                      props: MaterialProperties, dx: float, dt: float):
        """Build linear system for implicit time stepping"""
        shape = material_ids.shape
        n = np.prod(shape)
        
        # Material properties at each cell
        rho = np.where(material_ids.flatten() >= 2, props.density, 1600)  # sand mold
        cp = np.where(material_ids.flatten() >= 2, props.specific_heat, 800)
        k = np.where(material_ids.flatten() >= 2, props.thermal_conductivity, 0.5)
        
        # Thermal mass
        thermal_mass = rho * cp * dx**3
        
        # Build sparse matrix
        # Simplified: 7-point stencil for 3D
        diagonals = []
        offsets = []
        
        # Main diagonal
        main_diag = thermal_mass / dt
        
        # Neighbor connections (simplified)
        # Full implementation would properly handle boundaries and interfaces
        
        A = sparse.diags(main_diag, 0, format='csr')
        b = thermal_mass / dt * T
        
        # Add boundary conditions (ambient)
        ambient_mask = material_ids.flatten() == 0
        b[ambient_mask] = self.ambient_temp
        
        return A, b
    
    def _temperature_to_enthalpy(self, T: np.ndarray, 
                                  props: MaterialProperties) -> np.ndarray:
        """Convert temperature to enthalpy including latent heat"""
        h = props.specific_heat * T
        
        # Add latent heat in freezing range
        freezing = (T >= props.solidus_temp) & (T <= props.liquidus_temp)
        fraction_solid = (props.liquidus_temp - T[freezing]) / (props.liquidus_temp - props.solidus_temp)
        h[freezing] += props.latent_heat * (1 - fraction_solid)
        
        # Fully liquid
        h[T > props.liquidus_temp] += props.latent_heat
        
        return h
    
    def _enthalpy_to_temperature(self, h: np.ndarray,
                                  props: MaterialProperties) -> np.ndarray:
        """Convert enthalpy back to temperature"""
        # Check if in freezing range
        h_solid = props.specific_heat * props.solidus_temp
        h_liquid = h_solid + props.latent_heat
        
        T = np.zeros_like(h)
        
        # Solid
        solid_mask = h <= h_solid
        T[solid_mask] = h[solid_mask] / props.specific_heat
        
        # Liquid
        liquid_mask = h >= h_liquid
        T[liquid_mask] = (h[liquid_mask] - props.latent_heat) / props.specific_heat
        
        # Freezing range - interpolate
        freezing = ~solid_mask & ~liquid_mask
        fraction_liquid = (h[freezing] - h_solid) / props.latent_heat
        T[freezing] = props.solidus_temp + fraction_liquid * (props.liquidus_temp - props.solidus_temp)
        
        return T
    
    def _liquid_fraction(self, T: np.ndarray, props: MaterialProperties) -> np.ndarray:
        """Calculate liquid fraction (0=solid, 1=liquid)"""
        frac = np.ones_like(T)
        frac[T <= props.solidus_temp] = 0.0
        frac[T >= props.liquidus_temp] = 1.0
        
        freezing = (T > props.solidus_temp) & (T < props.liquidus_temp)
        frac[freezing] = (T[freezing] - props.solidus_temp) / (props.liquidus_temp - props.solidus_temp)
        
        return frac
    
    def _estimate_porosity(self, T: np.ndarray, liquid_frac: np.ndarray,
                           material_ids: np.ndarray, props: MaterialProperties) -> np.ndarray:
        """
        Estimate porosity from solidification pattern
        
        Simple model: porosity occurs where:
        1. Solidification completed
        2. No feeding path to riser
        3. High modulus (last to freeze)
        """
        porosity = np.zeros_like(T)
        
        # Casting and riser regions
        casting_mask = material_ids >= 2
        
        # Regions that are now solid but were isolated
        solid_mask = liquid_frac < 0.1
        
        # Estimate based on solidification time (simplified)
        # In reality, this requires tracking feeding paths
        porosity[casting_mask & solid_mask] = 0.02  # 2% baseline porosity
        
        return porosity
    
    def _detect_defects(self, results: Dict, material_ids: np.ndarray,
                        props: MaterialProperties) -> List[Dict]:
        """Analyze simulation results for casting defects"""
        defects = []
        
        porosity = results["porosity_map"]
        casting_mask = material_ids >= 2
        
        # Find high porosity regions
        high_porosity = porosity > 0.05
        
        if high_porosity.any():
            from scipy import ndimage
            labeled, num_features = ndimage.label(high_porosity)
            
            for i in range(1, num_features + 1):
                region = labeled == i
                coords = np.argwhere(region)
                centroid = coords.mean(axis=0).tolist()
                volume = region.sum()
                
                defects.append({
                    "type": "shrinkage_porosity",
                    "severity": "high" if porosity[region].max() > 0.1 else "medium",
                    "position": [float(c) for c in centroid],
                    "volume": int(volume),
                    "max_porosity": float(porosity[region].max())
                })
        
        return defects
    
    def _estimate_yield(self, geometry: Dict, risers: List[Dict],
                        gating: Optional[Dict]) -> float:
        """Estimate casting yield percentage"""
        cast_volume = geometry.get("volume", 1000)
        
        riser_volume = sum(
            np.pi * r.get("radius", 10)**2 * r.get("height", 30)
            for r in risers
        )
        
        gating_volume = 200 if gating else 0  # Estimate
        
        total = cast_volume + riser_volume + gating_volume
        return 100.0 * cast_volume / total if total > 0 else 0.0
