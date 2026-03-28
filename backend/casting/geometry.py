"""
Geometry processing - STEP/STL import, voxelization, and analysis
Ported from casting_geometric_toolsuite MATLAB code
"""
import numpy as np
import trimesh
from scipy import ndimage
from scipy.spatial.distance import edt
from typing import Dict, List, Tuple, Optional
import tempfile
import subprocess


class GeometryProcessor:
    """Process CAD files and extract casting-relevant features"""
    
    def __init__(self, voxel_resolution: int = 100):
        self.voxel_resolution = voxel_resolution
        
    def process(self, file_path: str) -> Dict:
        """
        Load and process a CAD file (STEP or STL)
        Returns voxelized geometry with analysis data
        """
        # Convert STEP to mesh if needed
        if file_path.lower().endswith('.step') or file_path.lower().endswith('.stp'):
            mesh = self._step_to_mesh(file_path)
        else:
            mesh = trimesh.load(file_path)
        
        # Voxelize
        voxels = self._voxelize_mesh(mesh)
        
        # Compute geometric features
        modulus_field = self._compute_modulus_field(voxels)
        thickness_field = self._compute_thickness_field(voxels)
        hotspots = self._detect_hotspots(modulus_field)
        feeding_zones = self._identify_feeding_zones(voxels, hotspots)
        
        return {
            "bounds": mesh.bounds.tolist(),
            "volume": float(mesh.volume),
            "surface_area": float(mesh.area),
            "voxels": voxels.shape,
            "voxel_size": self._get_voxel_size(mesh),
            "modulus_field": self._serialize_field(modulus_field),
            "thickness_field": self._serialize_field(thickness_field),
            "hotspots": hotspots,
            "feeding_zones": feeding_zones,
            "mesh_vertices": len(mesh.vertices),
            "mesh_faces": len(mesh.faces)
        }
    
    def _step_to_mesh(self, step_path: str) -> trimesh.Trimesh:
        """Convert STEP file to mesh using FreeCAD or OpenCASCADE"""
        # Try using FreeCAD's Python API if available
        try:
            import FreeCAD
            import Part
            import Mesh
            
            doc = FreeCAD.newDocument()
            Part.insert(step_path, doc.Name)
            
            # Get the shape and mesh it
            shape = doc.Objects[0].Shape
            mesh = Mesh.Mesh()
            mesh.addFacets(shape.tessellate(0.1))  # 0.1mm linear deflection
            
            # Convert to trimesh
            vertices = []
            faces = []
            for facet in mesh.Facets:
                base_idx = len(vertices)
                vertices.extend(facet.Points)
                faces.append([base_idx, base_idx+1, base_idx+2])
            
            return trimesh.Trimesh(vertices=vertices, faces=faces)
            
        except ImportError:
            # Fallback: use OpenCASCADE via pythonOCC
            try:
                from OCC.Core.STEPControl import STEPControl_Reader
                from OCC.Core.StlAPI import StlAPI_Writer
                from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
                
                reader = STEPControl_Reader()
                reader.ReadFile(step_path)
                reader.TransferRoots()
                shape = reader.OneShape()
                
                # Mesh the shape
                mesh = BRepMesh_IncrementalMesh(shape, 0.1)
                mesh.Perform()
                
                # Export to temporary STL
                with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as tmp:
                    writer = StlAPI_Writer()
                    writer.Write(shape, tmp.name)
                    return trimesh.load(tmp.name)
                    
            except ImportError:
                raise RuntimeError(
                    "STEP processing requires FreeCAD or pythonOCC. "
                    "Please install: pip install FreeCAD or pythonOCC"
                )
    
    def _voxelize_mesh(self, mesh: trimesh.Trimesh) -> np.ndarray:
        """Convert mesh to voxel grid"""
        # Use trimesh voxelization
        voxelized = mesh.voxelized(pitch=self._get_voxel_size(mesh))
        return voxelized.matrix
    
    def _get_voxel_size(self, mesh: trimesh.Trimesh) -> float:
        """Calculate appropriate voxel size based on mesh bounds"""
        bounds = mesh.bounds
        max_dim = np.max(bounds[1] - bounds[0])
        return max_dim / self.voxel_resolution
    
    def _compute_modulus_field(self, voxels: np.ndarray) -> np.ndarray:
        """
        Compute Chvorinov modulus (V/A) for each voxel neighborhood
        Based on casting_geometric_toolsuite approach
        """
        # Binary casting region
        casting = voxels > 0
        
        # Compute volume (local count)
        volume_kernel = np.ones((3, 3, 3))
        local_volume = ndimage.convolve(casting.astype(float), volume_kernel, mode='constant')
        
        # Compute surface area (gradient magnitude)
        grad_x = ndimage.sobel(casting.astype(float), axis=0)
        grad_y = ndimage.sobel(casting.astype(float), axis=1)
        grad_z = ndimage.sobel(casting.astype(float), axis=2)
        surface_area = np.sqrt(grad_x**2 + grad_y**2 + grad_z**2)
        
        # Modulus = V/A (avoid division by zero)
        modulus = np.zeros_like(local_volume)
        mask = surface_area > 0.01
        modulus[mask] = local_volume[mask] / surface_area[mask]
        
        return modulus
    
    def _compute_thickness_field(self, voxels: np.ndarray) -> np.ndarray:
        """
        Compute local thickness using Euclidean distance transform
        """
        # EDT from surface
        casting = voxels > 0
        surface = ndimage.binary_dilation(casting) ^ casting
        
        # Distance from surface
        distances = edt(~surface)
        
        # Thickness is 2x distance to nearest surface
        thickness = 2 * distances * casting
        
        return thickness
    
    def _detect_hotspots(self, modulus_field: np.ndarray, 
                         min_distance: int = 5) -> List[Dict]:
        """
        Detect hot spots (regional maxima in modulus field)
        These are last-to-freeze regions
        """
        from skimage.feature import peak_local_max
        
        # Find local maxima
        coordinates = peak_local_max(
            modulus_field,
            min_distance=min_distance,
            exclude_border=False
        )
        
        hotspots = []
        for i, (z, y, x) in enumerate(coordinates):
            if modulus_field[z, y, x] < 1.0:  # Filter small values
                continue
                
            hotspots.append({
                "id": i,
                "position": [int(x), int(y), int(z)],
                "modulus": float(modulus_field[z, y, x]),
                "severity": "high" if modulus_field[z, y, x] > 10 else "medium"
            })
        
        # Sort by modulus (highest first)
        hotspots.sort(key=lambda h: h["modulus"], reverse=True)
        
        return hotspots
    
    def _identify_feeding_zones(self, voxels: np.ndarray, 
                                 hotspots: List[Dict]) -> List[Dict]:
        """
        Identify zones that need feeding (based on hot spots)
        Uses watershed segmentation from hotspots
        """
        from skimage.segmentation import watershed
        from skimage.feature import peak_local_max
        
        casting = voxels > 0
        modulus = self._compute_modulus_field(voxels)
        
        # Create markers from hotspots
        markers = np.zeros_like(modulus, dtype=int)
        for i, hotspot in enumerate(hotspots[:10]):  # Limit to top 10
            x, y, z = hotspot["position"]
            if 0 <= z < markers.shape[0] and 0 <= y < markers.shape[1] and 0 <= x < markers.shape[2]:
                markers[z, y, x] = i + 1
        
        # Watershed segmentation
        # Invert modulus so high modulus = low value (basins)
        inverted = -modulus
        inverted[~casting] = -np.inf
        
        labels = watershed(inverted, markers, mask=casting)
        
        # Extract feeding zones
        zones = []
        for i in range(1, len(hotspots) + 1):
            zone_mask = labels == i
            if not zone_mask.any():
                continue
            
            # Calculate zone properties
            volume = zone_mask.sum()
            coords = np.argwhere(zone_mask)
            centroid = coords.mean(axis=0).tolist()
            
            zones.append({
                "id": i - 1,
                "hotspot_id": hotspots[i-1]["id"] if i-1 < len(hotspots) else None,
                "volume": int(volume),
                "centroid": [float(c) for c in centroid],
                "bounds": {
                    "min": [int(c) for c in coords.min(axis=0)],
                    "max": [int(c) for c in coords.max(axis=0)]
                }
            })
        
        return zones
    
    def analyze(self, geometry: Dict) -> Dict:
        """
        Full geometric analysis for casting design
        """
        hotspots = geometry.get("hotspots", [])
        feeding_zones = geometry.get("feeding_zones", [])
        
        # Generate recommendations
        recommendations = []
        
        if len(hotspots) == 0:
            recommendations.append("No critical hot spots detected. Simple casting.")
        else:
            recommendations.append(f"Detected {len(hotspots)} hot spots requiring risers.")
            
            for i, hotspot in enumerate(hotspots[:3]):
                recommendations.append(
                    f"  Hot spot {i+1}: Position {hotspot['position']}, "
                    f"Modulus {hotspot['modulus']:.2f}"
                )
        
        # Estimate required riser count
        estimated_risers = max(1, len([h for h in hotspots if h["severity"] == "high"]))
        
        return {
            "hotspots": hotspots,
            "feeding_zones": feeding_zones,
            "recommendations": recommendations,
            "estimated_riser_count": estimated_risers,
            "complexity": "high" if len(hotspots) > 3 else "medium" if len(hotspots) > 0 else "low"
        }
    
    def _serialize_field(self, field: np.ndarray) -> List:
        """Compress field for JSON serialization"""
        # Downsample for network transfer
        if field.size > 1000000:  # If larger than 1M elements
            from skimage.transform import downscale_local_mean
            factor = int(np.cbrt(field.size / 1000000)) + 1
            field = downscale_local_mean(field, (factor, factor, factor))
        
        # Return as sparse representation
        mask = field > 0.1
        coords = np.argwhere(mask)
        values = field[mask]
        
        return {
            "shape": field.shape,
            "coords": coords.tolist(),
            "values": values.tolist()
        }
