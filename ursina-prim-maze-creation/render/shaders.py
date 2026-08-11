"""Custom lighting shader: parameterized version of ursina's basic_lighting_shader,
adjustable via light_dir / light_intensity / light_ambient uniforms instead of a
fixed normal->grey mapping."""
import math
from ursina.shader import Shader
from ursina import Vec3


dynamic_lighting_shader = Shader(
    name='dynamic_lighting_shader',
    language=Shader.GLSL,
    vertex='''
    #version 140
    uniform mat4 p3d_ModelViewProjectionMatrix;
    uniform mat4 p3d_ModelMatrix;
    in vec4 p3d_Vertex;
    in vec2 p3d_MultiTexCoord0;
    out vec2 texcoord;
    in vec3 p3d_Normal;
    out vec3 world_normal;
    void main() {
        gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
        texcoord = p3d_MultiTexCoord0;
        world_normal = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
    }
    ''',
    fragment='''
    #version 140
    uniform sampler2D p3d_Texture0;
    uniform vec4 p3d_ColorScale;
    uniform vec3 light_dir;
    uniform float light_intensity;
    uniform float light_ambient;
    in vec2 texcoord;
    in vec3 world_normal;
    out vec4 fragColor;
    void main() {
        float ndotl = max(dot(normalize(world_normal), light_dir), 0.0);
        float shade = light_ambient + (1.0 - light_ambient) * ndotl * light_intensity;
        shade = clamp(shade, 0.0, 1.5);
        vec4 tex = texture(p3d_Texture0, texcoord) * p3d_ColorScale;
        fragColor = vec4(tex.rgb * shade, tex.a);
    }
    ''',
    geometry=''
)


def _light_dir_from_angles(azimuth_deg, elevation_deg):
    """Convert azimuth/elevation (spherical coords in degrees) to a normalized light direction vector.

    Args:
        azimuth_deg: Rotation around Y axis (0=+X, 90=+Z, 180=-X, 270=-Z)
        elevation_deg: Angle from horizon (0=horizon, 90=zenith, -90=nadir)

    Returns:
        Normalized Vec3 light direction
    """
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    return Vec3(
        math.cos(el) * math.sin(az),
        math.sin(el),
        math.cos(el) * math.cos(az)
    ).normalized()
