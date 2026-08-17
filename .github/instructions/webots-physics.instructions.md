---
applyTo: "blender-project/physics/**"
description: "Conventions for Webots robot simulation files"
---

# Webots physics configuration

- Export geometry as OBJ, not DAE. This Blender build has no Collada exporter; DAE attempts will fail silently in the export step.
- Name `Gyro` and `Accelerometer` nodes exactly `"gyro"` and `"accelerometer"` (lowercase, no suffix). Webots IDE uses the device name as the key to look it up in robot controller code; a mismatch means the sensor data never arrives in `robot.device["accelerometer"]`.
- Follow `.wbt` conventions: proto definitions in `protos/`, instantiation in the main world file. A proto file for a custom robot part must be self-contained (all geometry references, material defs, joint limits, mass properties declared inside the proto, not inherited from the world).
- Collision geometry must be explicit; Webots doesn't auto-compute bounding boxes from visual meshes. A dynamic body with visual geometry but no collision `Shape` node will fall through the plane.
