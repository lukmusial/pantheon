"""Parametric Pantheon (c. 126 AD) generator for Blender.

Run headless:
    blender -b --python blender/build_pantheon.py -- --preview renders/previews/blockout

which writes <prefix>_a.png (from the door towards the apse) and <prefix>_b.png
(from the apse side back towards the door).

Stage 2 blockout at real-world scale: drum with six exedrae, arched apse and
entrance bays, door wall, entablature, attic wall, coffered dome with stepped
coffers, oculus, column screens, eight aediculae, placeholder portico.

Axes: Z up, metres. The entrance is on +Y and the main apse on -Y. Azimuth is
measured counter-clockwise from +X. The real building's entrance bears 354.5
degrees (5.5 degrees west of north); the model keeps the axis on Y and the sun
direction is offset instead.

Dimensions come from reference/dimensions.md; see the notes in P.
"""

import math
import os
import random
import sys

import bpy
import numpy as np
from mathutils import Vector

P = {
    # Values follow reference/dimensions.md. Entries marked "scaled" were measured off
    # engravings there (about +/-3-5 %) and are not surveyed figures.
    # Rotunda
    "R": 21.72,              # inner radius (inner diameter and height 43.44 m)
    "wall_t": 6.2,           # drum wall thickness at the floor
    "spring_z": 21.72,       # height of the dome springing line (sphere centre)
    "oculus_r": 4.15,        # clear radius inside the bronze rim (structural opening 8.9 m)
    "shell_t": 1.5,          # dome shell thickness at the oculus
    # Lower order (Desgodetz 1682, converted)
    "col_h": 10.54,          # column height: base + shaft + capital
    "col_d": 1.11,           # column lower diameter
    "order_h": 13.05,        # top of the first cornice above the floor
    # Recesses on the eight axes
    "exedra_hw": 4.45,       # half of the 8.9 m clear opening
    "exedra_depth_semi": 4.3,   # scaled
    "exedra_depth_rect": 3.75,  # scaled
    "arch_crown": 19.5,      # crown of the apse and entrance arches above the floor (scaled, 19-20)
    "entrance_depth": 6.2,   # inner wall face to the door: the full wall, so the door wall closes the drum (scaled 6-7)
    "door_hw": 2.98,         # half of the 5.96 m clear doorway width
    "door_h": 11.73,         # clear doorway height
    # Aediculae (all scaled)
    "aed_width": 4.1,
    "aed_col_spacing": 3.2,
    "aed_podium_h": 2.15,
    "aed_entab_h": 0.75,
    "aed_ped_rise": 1.1,
    "aed_apex": 8.0,
    "aed_col_d": 0.45,
    "aed_projection": 1.1,
    # Original (pre-1747) attic: flat, pilasters and panels told apart only by stone colour.
    # 16 units, each one window plus three panel bays between four porphyry pilasters.
    "attic_dado_h": 2.05,
    "attic_entab_h": 1.75,
    "attic_pilaster_w": 0.37,
    "attic_win_w": 2.3,      # scaled
    "attic_win_sill": 15.5,  # scaled
    "attic_win_head": 19.4,  # scaled
    "attic_frame_w": 0.25,   # white marble window frame, estimate
    # Floor: orthogonal grid, squares between continuous bands, disc and square panels in checkerboard
    "floor_pitch": 3.96,
    "floor_square": 2.96,
    "floor_disc_d": 2.35,
    "floor_inner_square": 2.0,  # estimate
    # Coffers: band boundaries sit on the rib centre lines, so with a 0.95 m rib the
    # recesses span 3-13, 15.5-25.75, 28.25-37.5, 40-48.75 and 51.25-58 degrees (scaled)
    "coffer_count": 28,
    "coffer_el_deg": [1.75, 14.25, 27.0, 38.75, 50.0, 59.25],
    "coffer_steps": [4, 4, 4, 4, 3],                        # recess levels per ring
    "coffer_rib_el": 0.95,                                  # rib width between rings
    "coffer_rib_az": [1.01, 0.95, 0.88, 0.80, 0.72],        # rib width between coffers
    "coffer_step_inset": [0.33, 0.30, 0.26, 0.22, 0.20],    # mean inset of each level
    "coffer_step_depth": [0.18, 0.18, 0.18, 0.18, 0.20],    # total depth about 0.73
    # Step reveals are not concentric: the lower ones are narrower and the upper ones
    # broader, so every step shows from the floor centre. Factors are an estimate.
    "coffer_inset_low": 0.55,
    "coffer_inset_high": 1.45,
    # Portico (placeholders)
    "portico_front_y": 48.5,  # rear wall at about 33.4 plus the 15.5 portico depth (scaled)
    "portico_col_h": 14.15,
    "portico_col_d": 1.5,
    "portico_spacing": 4.54,
    # Outside of the drum (Moore): top of its middle cornice, and its full height to the top of the
    # crowning cornice, on which the dome's step rings stand
    "drum_mid": 22.1,
    "drum_top": 31.7,
    # Tessellation
    "segments": 448,         # 28 * 16, around the full circle
}

# The forecourt's paving, 1.4 below the portico floor: the portico stood on a podium reached by seven
# steps (en.wiki; Marder and Wilson Jones p. 59; reference/dimensions.md, portico). The 2020 sinkhole
# showed the Hadrianic travertine paving 2.5 m under today's piazza.
PLAZA_Z = -1.4

ENTRANCE_AZ = 90.0
APSE_AZ = 270.0
# axis azimuth -> recess kind
RECESSES = {
    0.0: "semi", 45.0: "rect", 90.0: "entrance", 135.0: "rect",
    180.0: "semi", 225.0: "rect", 270.0: "apse", 315.0: "rect",
}
# aedicula azimuth -> pediment type: triangular beside the door and the apse,
# segmental beside the east and west exedrae
AEDICULAE = {
    22.5: "segmental", 67.5: "triangular", 112.5: "triangular", 157.5: "segmental",
    202.5: "segmental", 247.5: "triangular", 292.5: "triangular", 337.5: "segmental",
}


def new_object(name, verts, faces, uvs=None):
    """uvs: optional list with one entry per face: a list of (u, v) per corner, or None."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    if uvs and any(uv is not None for uv in uvs):
        layer = mesh.uv_layers.new(name="UVMap")
        for poly in mesh.polygons:
            uv = uvs[poly.index] or [(0.0, 0.0)] * poly.loop_total
            for k, li in enumerate(poly.loop_indices):
                layer.data[li].uv = uv[k]
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


class Builder:
    """Collects vertices and faces for one object."""

    def __init__(self, name):
        self.name, self.verts, self.faces, self.uvs = name, [], [], []

    def add(self, verts, faces, uvs=None):
        base = len(self.verts)
        self.verts.extend(verts)
        self.faces.extend(tuple(base + i for i in f) for f in faces)
        self.uvs.extend(uvs if uvs is not None else [None] * len(faces))

    def quad(self, p0, p1, p2, p3, uv=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
        self.add([p0, p1, p2, p3], [(0, 1, 2, 3)], [list(uv)])

    def quad_out(self, p0, p1, p2, p3, out, uv=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
        """A quad that faces the direction out, whichever way its corners were listed (each corner
        keeps its UV). For painted sheets, which refine() does not orient: a sheet facing into the
        stone it lies on was drawn all the same (two-sided material), but its shadow rays started
        inside it, so its light was lost and soft shadows broke into jagged teeth (user, 2026-11-24,
        the sides of Jupiter's pedestal)."""
        n = (Vector(p1) - Vector(p0)).cross(Vector(p2) - Vector(p0))
        if n.dot(Vector(out)) < 0.0:
            self.quad(p1, p0, p3, p2, uv=(uv[1], uv[0], uv[3], uv[2]))
        else:
            self.quad(p0, p1, p2, p3, uv=uv)

    def finish(self):
        return new_object(self.name, self.verts, self.faces, self.uvs)


def frame(az_deg):
    """Local frame at an azimuth: returns a function (u, v, z) -> world xyz.

    u runs radially outwards, v tangentially (counter-clockwise).
    """
    a = math.radians(az_deg)
    ux, uy = math.cos(a), math.sin(a)
    return lambda u, v, z: (u * ux - v * uy, u * uy + v * ux, z)


def bay_half_angle():
    return math.asin(P["exedra_hw"] / P["R"])


def revolve(name, profile, closed=False, segments=None, skips=()):
    """Revolve (radius, z) points around Z. skips: (azimuth_deg, half_angle_rad) ranges left open."""
    n = segments or P["segments"]
    two_pi = 2.0 * math.pi
    angles = {two_pi * j / n for j in range(n)}
    for az, half in skips:
        angles.add((math.radians(az) - half) % two_pi)
        angles.add((math.radians(az) + half) % two_pi)
    angles = sorted(angles)
    n = len(angles)
    m = len(profile)

    def skipped(a):
        for az, half in skips:
            d = (a - math.radians(az) + math.pi) % two_pi - math.pi
            if abs(d) < half:
                return True
        return False

    verts = []
    for a in angles:
        ca, sa = math.cos(a), math.sin(a)
        verts.extend((r * ca, r * sa, z) for r, z in profile)
    flags = []
    for j in range(n):
        nxt = angles[(j + 1) % n] + (two_pi if j == n - 1 else 0.0)
        flags.append(skipped(0.5 * (angles[j] + nxt)))
    faces = []
    span = m if closed else m - 1
    for j in range(n):
        if flags[j]:
            continue
        j2 = (j + 1) % n
        for i in range(span):
            i2 = (i + 1) % m
            faces.append((j * m + i, j2 * m + i, j2 * m + i2, j * m + i2))
    if closed:
        for j in range(n):
            if flags[j] != flags[j - 1]:
                faces.append(tuple(j * m + i for i in range(m)))
    return new_object(name, verts, faces)


def cyl_into(builder, x, y, z0, h, d_bottom, d_top, segments=32):
    verts, faces = [], []
    for z, d in ((z0, d_bottom), (z0 + h, d_top)):
        for j in range(segments):
            a = 2.0 * math.pi * j / segments
            verts.append((x + 0.5 * d * math.cos(a), y + 0.5 * d * math.sin(a), z))
    for j in range(segments):
        j2 = (j + 1) % segments
        faces.append((j, j2, segments + j2, segments + j))
    faces.append(tuple(range(segments, 2 * segments)))
    faces.append(tuple(range(segments - 1, -1, -1)))
    builder.add(verts, faces)


def cylinder(name, x, y, z0, h, d_bottom, d_top, segments=32):
    b = Builder(name)
    cyl_into(b, x, y, z0, h, d_bottom, d_top, segments)
    return b.finish()


CAPITAL_SLOTS = []
CAPITAL_FBX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "architecture",
                           "capital", "capital.fbx")


def order_column(name, x, y, z0, h, d, segments=64, facing=None, cap_yaw=None):
    """Column with Attic base and a simplified capital (bell and abacus) as a separate white marble object.

    Proportions follow the main order: base about 0.5 and capital about 1.23 of a 10.54 column.
    The capital is a placeholder until a scanned Corinthian capital replaces it.

    facing: azimuth (degrees) the square plinth and capital are squared to, i.e. the direction
    perpendicular to the entablature the column carries (the recess or aedicula axis; 90 for the
    portico). Taken from the column's own position, the columns of a straight screen or of the
    portico were each turned a few degrees differently, so plinth and abacus corners stuck out from
    under the entablature (user, 2026-11-23). cap_yaw: the capital's yaw if not facing + 180.
    segments: 64 (was 32). Where the sun grazes a shaft, its shadow edge stepped from facet to facet
    in a visible sawtooth (user, 2026-11-23).
    """
    base_h, cap_h = 0.047 * h, 0.117 * h
    if facing is None:
        facing = math.degrees(math.atan2(y, x))
    fa = math.radians(facing)
    r = x * math.cos(fa) + y * math.sin(fa)              # position along the facing direction
    t = -x * math.sin(fa) + y * math.cos(fa)             # and across it
    to_world = frame(facing)
    orn = Builder("Orn_" + name)
    # square plinth, then the moulded Attic base
    box(orn, to_world, r - 0.7 * d, r + 0.7 * d, t - 0.7 * d, t + 0.7 * d, z0, z0 + 0.3 * base_h)
    lathe_into(orn, x, y, [(pr, z0 + pz) for pr, pz in attic_base_profile(d, base_h)], segments)
    # Scanned capital (blender/process_capital.py) placed by the UE level script. Its +X face is the
    # best preserved and its -X face is damaged, so +X is turned towards the room (yaw = azimuth + 180).
    CAPITAL_SLOTS.append({"column": name, "position": [x, y, z0 + h - cap_h], "height": cap_h,
                          "diameter": d * 0.86, "yaw": facing + 180.0 if cap_yaw is None else cap_yaw})
    zc = z0 + h - cap_h
    if os.path.exists(CAPITAL_FBX):
        orn.finish()
        return cylinder(name, x, y, z0 + base_h, h - base_h - cap_h, d, d * 0.86, segments)
    cyl_into(orn, x, y, zc, 0.85 * cap_h, 0.86 * d, 1.2 * d, segments)
    box(orn, to_world, r - 0.72 * d, r + 0.72 * d, t - 0.72 * d, t + 0.72 * d, zc + 0.85 * cap_h, z0 + h)
    orn.finish()
    return cylinder(name, x, y, z0 + base_h, h - base_h - cap_h, d, d * 0.86, segments)


def box(builder, to_world, u0, u1, v0, v1, z0, z1):
    c = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    verts = [to_world(u, v, z0) for u, v in c] + [to_world(u, v, z1) for u, v in c]
    builder.add(verts, [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])


def prism(builder, to_world, outline_vz, u0, u1):
    """Extrude a (v, z) outline along u."""
    n = len(outline_vz)
    verts = [to_world(u0, v, z) for v, z in outline_vz] + [to_world(u1, v, z) for v, z in outline_vz]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    builder.add(verts, faces)


def prism_v(builder, to_world, outline_uz, v0, v1):
    """Extrude a (u, z) moulding profile along v (closed outline, ends capped)."""
    n = len(outline_uz)
    verts = [to_world(u, v0, z) for u, z in outline_uz] + [to_world(u, v1, z) for u, z in outline_uz]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    builder.add(verts, faces)


def lathe_into(builder, x, y, profile, segments=32, cap=True):
    """Revolve a (radius, z) profile around a vertical axis at (x, y)."""
    m = len(profile)
    verts = []
    for j in range(segments):
        a = 2.0 * math.pi * j / segments
        ca, sa = math.cos(a), math.sin(a)
        verts.extend((x + r * ca, y + r * sa, z) for r, z in profile)
    faces = []
    for j in range(segments):
        j2 = (j + 1) % segments
        for i in range(m - 1):
            faces.append((j * m + i, j2 * m + i, j2 * m + i + 1, j * m + i + 1))
    if cap:
        faces.append(tuple(j * m for j in range(segments - 1, -1, -1)))
        faces.append(tuple(j * m + m - 1 for j in range(segments)))
    builder.add(verts, faces)


def strut(builder, p0, p1, w):
    """Square bar of width w between two points."""
    d = Vector(p1) - Vector(p0)
    a = d.orthogonal().normalized() * (0.5 * w)
    c = d.cross(a).normalized() * (0.5 * w)
    corners = [a + c, -a + c, -a - c, a - c]
    verts = [tuple(Vector(p0) + k) for k in corners] + [tuple(Vector(p1) + k) for k in corners]
    builder.add(verts, [(0, 1, 2, 3), (7, 6, 5, 4), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])


def attic_base_profile(d, b):
    """Attic base above its square plinth: torus, fillet, scotia, fillet, torus (radius, z) for
    lower shaft diameter d and total base height b; z runs from the plinth top (0.3 b)."""
    pts = [(0.0, 0.30), (0.62, 0.30), (0.66, 0.36), (0.67, 0.44), (0.64, 0.52), (0.58, 0.56),
           (0.56, 0.58), (0.52, 0.62), (0.50, 0.70), (0.52, 0.76), (0.56, 0.78), (0.58, 0.80),
           (0.59, 0.86), (0.57, 0.92), (0.52, 0.96), (0.50, 1.0), (0.0, 1.0)]
    return [(r * d, z * b) for r, z in pts]


# --------------------------------------------------------------------------
# Drum: plan outline with recesses, extruded upwards
# --------------------------------------------------------------------------

def recess_outline(kind):
    """Plan points (u, v) of one recess in its local frame, ordered by increasing azimuth.

    Returns (points, index of a segment left open or None).
    """
    R, hw = P["R"], P["exedra_hw"]
    u0 = math.sqrt(R * R - hw * hw)
    if kind == "entrance":
        # the end wall with the doorway is built separately
        ub = R + P["entrance_depth"]
        return [(u0, -hw), (ub, -hw), (ub, hw), (u0, hw)], 1
    if kind == "rect":
        ub = R + P["exedra_depth_rect"]
        return [(u0, -hw), (ub, -hw), (ub, hw), (u0, hw)], None
    uc = apse_centre_u()
    pts = [(u0, -hw)]
    steps = 32
    for k in range(steps + 1):
        t = -0.5 * math.pi + math.pi * k / steps
        pts.append((uc + hw * math.cos(t), hw * math.sin(t)))
    pts.append((u0, hw))
    return pts, None


def apse_centre_u():
    R, hw = P["R"], P["exedra_hw"]
    return max(math.sqrt(R * R - hw * hw), R + P["exedra_depth_semi"] - hw)


def arch_spring_z():
    return P["arch_crown"] - P["exedra_hw"]


def build_drum():
    R, h = P["R"], P["order_h"]
    axes = sorted(RECESSES)
    half = bay_half_angle()
    walls = Builder("Drum_Lower")
    ceilings = Builder("Recess_Ceilings")

    def strip(points, height, skip=None):
        verts = []
        for x, y, _ in points:
            verts += [(x, y, 0.0), (x, y, height)]
        faces = [(2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1)
                 for i in range(len(points) - 1) if i != skip]
        walls.add(verts, faces)

    for idx, az in enumerate(axes):
        kind = RECESSES[az]
        to_world = frame(az)
        local, gap = recess_outline(kind)
        pts = [to_world(u, v, 0.0) for u, v in local]
        arched = kind in ("apse", "entrance")
        strip(pts, arch_spring_z() if arched else h, gap)
        if arched:
            build_arched_bay(kind, az)
        else:
            # flat ceiling: recess outline plus the arc of the inner wall face
            a0, a1 = math.radians(az) - half, math.radians(az) + half
            arc = [(R * math.cos(a1 + (a0 - a1) * k / 16), R * math.sin(a1 + (a0 - a1) * k / 16), h)
                   for k in range(1, 16)]
            ring = [(x, y, h) for x, y, _ in pts] + arc
            ceilings.add(ring, [tuple(range(len(ring)))])
        # pier wall between this recess and the next one
        nxt = axes[(idx + 1) % len(axes)]
        start = math.radians(az) + half
        end = math.radians(nxt if nxt > az else nxt + 360.0) - half
        n = max(2, int(math.degrees(end - start)))
        strip([(R * math.cos(start + (end - start) * k / n),
                R * math.sin(start + (end - start) * k / n), 0.0) for k in range(n + 1)], h)

    walls.finish()
    ceilings.finish()

    arches = [(ENTRANCE_AZ, half), (APSE_AZ, half)]
    # the attic wall above the first cornice is built in build_attic()
    # Entablature ring carried by the columns across the exedra openings
    # Architrave with three fasciae and taenia, frieze, cornice with dentils, corona and sima.
    a0 = P["col_h"]
    f1 = a0 + 1.45
    revolve("Entablature", [
        (R + 1.0, a0), (R - 0.04, a0), (R - 0.04, a0 + 0.22), (R - 0.07, a0 + 0.22),
        (R - 0.07, a0 + 0.45), (R - 0.10, a0 + 0.45), (R - 0.10, a0 + 0.66), (R - 0.16, a0 + 0.66),
        (R - 0.16, a0 + 0.75), (R - 0.09, a0 + 0.75), (R - 0.09, f1), (R - 0.12, f1),
        (R - 0.12, f1 + 0.14), (R - 0.20, f1 + 0.14), (R - 0.20, f1 + 0.34), (R - 0.40, f1 + 0.34),
        (R - 0.40, f1 + 0.44), (R - 0.85, f1 + 0.44), (R - 0.85, f1 + 0.78), (R - 0.92, f1 + 0.78),
        (R - 0.98, f1 + 0.92), (R - 1.0, h), (R + 1.0, h),
    ], closed=True, skips=arches)
    # Porphyry frieze: a solid 1.5 cm slab on the frieze face, which now sits level with the top
    # fascia. Set 14 cm back under the 1 m cornice and made as a single sheet, it read as a dark,
    # glossy strip wedged between the architrave and the cornice (user, 2026-11-23)
    revolve("Entablature_Frieze", [(R - 0.09, a0 + 0.75), (R - 0.105, a0 + 0.75), (R - 0.105, f1),
                                   (R - 0.09, f1)], closed=True, skips=arches)
    # dentils along the bed of the cornice
    dent = Builder("Entablature_Dentils")
    step = 0.21 / R
    a = 0.0
    while a < 2.0 * math.pi:
        deg = math.degrees(a)
        if not any(abs(angle_diff(deg, ax)) < math.degrees(half) for ax, _ in arches):
            box(dent, frame(deg), R - 0.36, R - 0.19, -0.06, 0.06, f1 + 0.14, f1 + 0.34)
        a += step
    dent.finish()
    # Cornice at the springing line
    s = P["spring_z"]
    revolve("Spring_Cornice", [
        (R, s - 0.9), (R - 0.15, s - 0.6), (R - 0.55, s - 0.25), (R - 0.55, s), (R, s),
    ])


def build_arched_bay(kind, az):
    """Vault, wall above the arch and (for the entrance) the door wall of an arched bay."""
    R, hw = P["R"], P["exedra_hw"]
    zs = arch_spring_z()
    to_world = frame(az)
    b = Builder("Bay_%s" % kind.capitalize())
    n = 32
    thetas = [math.pi * k / n for k in range(n + 1)]
    u_far = apse_centre_u() if kind == "apse" else R + P["entrance_depth"]

    # barrel vault from the inner wall face to the far end of the straight part
    verts = []
    for t in thetas:
        v, z = hw * math.cos(t), zs + hw * math.sin(t)
        verts += [to_world(math.sqrt(R * R - v * v), v, z), to_world(u_far, v, z)]
    b.add(verts, [(2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2) for k in range(n)])

    # Back of the vault: an outer shell 0.5 m out and end caps, so the vault is a closed solid. As a
    # single sheet with hairline gaps along its seams, Lumen rays escaped through it to the sunlit
    # exterior and came back as flickering spots along the top of the portal (user, 2026-11-23;
    # the attic had the same problem until it got a closed backing).
    t_out = 0.5
    ro = hw + t_out
    u_outer_far = u_far if kind == "apse" else u_far + 0.01
    verts = []
    for t in thetas:
        v, z = ro * math.cos(t), zs + ro * math.sin(t)
        verts += [to_world(math.sqrt(max(R * R - v * v, 0.0)) + 0.02, v, z), to_world(u_outer_far, v, z)]
    b.add(verts, [(2 * k + 2, 2 * k + 3, 2 * k + 1, 2 * k) for k in range(n)])
    ends = [("start", None)] + ([] if kind == "apse" else [("far", u_outer_far)])
    for which, uu in ends:
        verts = []
        for t in thetas:
            for rr in (hw, ro):
                v, z = rr * math.cos(t), zs + rr * math.sin(t)
                u = math.sqrt(max(R * R - v * v, 0.0)) + 0.02 if uu is None else uu
                verts.append(to_world(u, v, z))
        b.add(verts, [(2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2) for k in range(n)])

    # wall face between the arch and the dome springing
    verts = []
    for t in thetas:
        v, z = hw * math.cos(t), zs + hw * math.sin(t)
        u = math.sqrt(R * R - v * v)
        verts += [to_world(u, v, z), to_world(u, v, P["spring_z"])]
    b.add(verts, [(2 * k, 2 * k + 2, 2 * k + 3, 2 * k + 1) for k in range(n)])

    if kind == "apse":
        # semi-dome over the half-round end
        m = 12
        verts = []
        for i in range(m + 1):
            beta = 0.5 * math.pi * i / m
            for t in thetas:
                verts.append(to_world(u_far + hw * math.cos(beta) * math.sin(t),
                                      hw * math.cos(beta) * math.cos(t),
                                      zs + hw * math.sin(beta)))
        row = n + 1
        faces = [(i * row + k, i * row + k + 1, (i + 1) * row + k + 1, (i + 1) * row + k)
                 for i in range(m) for k in range(n)]
        b.add(verts, faces)
        # its back, closing the solid with the vault's outer shell
        verts = []
        for i in range(m + 1):
            beta = 0.5 * math.pi * i / m
            for t in thetas:
                verts.append(to_world(u_far + ro * math.cos(beta) * math.sin(t),
                                      ro * math.cos(beta) * math.cos(t),
                                      zs + ro * math.sin(beta)))
        b.add(verts, [(f[3], f[2], f[1], f[0]) for f in faces])
    else:
        # end wall with the doorway
        dhw, dh = P["door_hw"], P["door_h"]
        vs = sorted(set(np.linspace(-hw, hw, 33).tolist() + [-dhw, dhw]))
        for v0, v1 in zip(vs[:-1], vs[1:]):
            bottom = dh if abs(0.5 * (v0 + v1)) < dhw else 0.0
            top0 = zs + math.sqrt(max(0.0, hw * hw - v0 * v0))
            top1 = zs + math.sqrt(max(0.0, hw * hw - v1 * v1))
            b.add([to_world(u_far, v0, bottom), to_world(u_far, v1, bottom),
                   to_world(u_far, v1, top1), to_world(u_far, v0, top0)], [(0, 1, 2, 3)])
        # door reveal through the wall, reaching 1 cm into both wall faces so no hairline opens
        depth = 1.2
        box_pts = [(-dhw, 0.0), (-dhw, dh), (dhw, dh), (dhw, 0.0)]
        verts = []
        for v, z in box_pts:
            verts += [to_world(u_far - 0.01, v, z), to_world(u_far + depth + 0.01, v, z)]
        b.add(verts, [(2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2) for k in range(3)])
        # back face of the door wall: the wall is a closed solid, so the hairline joints between its
        # strips and the reveal no longer show the bright portico (user, 2026-11-23: light seeping
        # in between the door frame and the portal)
        for v0, v1 in zip(vs[:-1], vs[1:]):
            bottom = dh if abs(0.5 * (v0 + v1)) < dhw else 0.0
            top0 = zs + math.sqrt(max(0.0, hw * hw - v0 * v0))
            top1 = zs + math.sqrt(max(0.0, hw * hw - v1 * v1))
            ub = u_far + depth
            b.add([to_world(ub, v1, bottom), to_world(ub, v0, bottom),
                   to_world(ub, v0, top0), to_world(ub, v1, top1)], [(0, 1, 2, 3)])
    b.finish()


def build_columns():
    R, hw = P["R"], P["exedra_hw"]
    for az, kind in RECESSES.items():
        to_world = frame(az)
        if kind in ("semi", "rect"):
            u = math.sqrt(R * R - hw * hw) + 0.55
            offsets = (-hw / 3.0, hw / 3.0)
        elif kind == "apse":
            # the apse has no column screen: one column stands forward at each side
            u = R - 0.75
            offsets = (-hw - 0.65, hw + 0.65)
        else:
            continue
        for v in offsets:
            x, y, _ = to_world(u, v, 0.0)
            order_column("Column_%03d_%s" % (int(az), "L" if v < 0 else "R"), x, y, 0.0, P["col_h"], P["col_d"],
                         facing=az)


def build_aediculae():
    R = P["R"]
    width, spacing = P["aed_width"], P["aed_col_spacing"]
    podium, entab, rise, apex = P["aed_podium_h"], P["aed_entab_h"], P["aed_ped_rise"], P["aed_apex"]
    proj, col_d = P["aed_projection"], P["aed_col_d"]
    entab_z0 = apex - rise - entab
    for az, kind in AEDICULAE.items():
        to_world = frame(az)
        b = Builder("Aedicula_%04d_%s" % (int(az * 10), kind))
        u_front, u_back = R - proj, R + 0.05
        hwid = 0.5 * width
        # originally each column stood on its own pedestal, the niche running to the floor between
        for side in (-1.0, 1.0):
            vc = side * 0.5 * spacing
            box(b, to_world, u_front, u_back, vc - 0.45, vc + 0.45, 0.0, podium)
        e0, uf = entab_z0, u_front - 0.1
        # architrave (two fasciae), frieze, cornice; the scale follows the main order
        prism_v(b, to_world, [
            (u_back, e0), (uf + 0.06, e0), (uf + 0.06, e0 + 0.13), (uf + 0.02, e0 + 0.13),
            (uf + 0.02, e0 + 0.25), (uf + 0.06, e0 + 0.25), (uf + 0.06, e0 + 0.47), (uf - 0.02, e0 + 0.47),
            (uf - 0.02, e0 + 0.55), (uf - 0.18, e0 + 0.60), (uf - 0.18, e0 + 0.72), (uf - 0.20, e0 + entab),
            (u_back, e0 + entab)], -hwid - 0.1, hwid + 0.1)
        # painted frieze panel (UV 0..1 along the frieze)
        fz = Builder("Painted_AedFrieze_%04d" % int(az * 10))
        fz.quad(to_world(uf + 0.055, hwid, e0 + 0.25), to_world(uf + 0.055, -hwid, e0 + 0.25),
                to_world(uf + 0.055, -hwid, e0 + 0.47), to_world(uf + 0.055, hwid, e0 + 0.47))
        fz.finish()
        z0 = e0 + entab
        if kind == "triangular":
            tymp = [(-hwid, z0), (hwid, z0), (0.0, z0 + rise)]
            prism(b, to_world, tymp, uf + 0.08, u_back)
            # raking cornices
            for sgn in (-1.0, 1.0):
                band = [(sgn * (hwid + 0.15), z0 - 0.02), (0.0, z0 + rise + 0.2), (0.0, z0 + rise),
                        (sgn * hwid, z0)]
                if sgn > 0:
                    band.reverse()
                prism(b, to_world, band, uf - 0.18, u_back)
        else:
            rad = (hwid * hwid + rise * rise) / (2.0 * rise)
            ang = math.asin(hwid / rad)
            inner = [(rad * math.sin(-ang + 2.0 * ang * k / 16),
                      z0 + rise - rad + rad * math.cos(-ang + 2.0 * ang * k / 16)) for k in range(16, -1, -1)]
            prism(b, to_world, inner, uf + 0.08, u_back)
            outer = [((rad + 0.2) * math.sin(-ang + 2.0 * ang * k / 16) * (hwid + 0.15) / hwid,
                      z0 + rise - rad + (rad + 0.2) * math.cos(-ang + 2.0 * ang * k / 16)) for k in range(17)]
            prism(b, to_world, outer + inner, uf - 0.18, u_back)
        b.finish()
        for side in (-1.0, 1.0):
            x, y, _ = to_world(u_front + 0.5, side * 0.5 * spacing, 0.0)
            order_column("AedCol_%s_%04d_%s" % (kind, int(az * 10), "L" if side < 0 else "R"),
                         x, y, podium, entab_z0 - podium, col_d, segments=40, facing=az)


# Statue slots. Exedrae: Dio places Mars and Venus inside; the rest is informed reconstruction.
# kind -> statue key from blender/process_statues.py
EXEDRA_STATUES = {
    0.0: "venus_capitoline", 45.0: "apollo_belvedere", 135.0: "diana_gabii",
    180.0: "ares_ludovisi", 225.0: "athena_giustiniani", 315.0: "neptune_nimes",
}
AEDICULA_STATUES = {
    22.5: "apollo_lykeios", 67.5: "herakles_lansdowne", 112.5: "dionysus", 157.5: "hermes_logios",
    202.5: "ceres_louvre", 247.5: "augustus_jupiter_hermitage", 292.5: "hermes_farnese", 337.5: "caesar_borghese",
}
# statues that bring their own tall pedestal and need no added base
OWN_PEDESTAL = set()
STATUE_SLOTS = []


def build_statue_bases():
    """White marble bases, and the slot list (position, yaw) the UE level script places statues on.

    Processed statues face -Y; yaw = azimuth - 90 turns them to face the rotunda centre.
    """
    R = P["R"]
    b = Builder("Orn_StatueBases")
    painted = Builder("Painted_Pedestals")
    STATUE_SLOTS.clear()

    def slot(key, az, u, base_w, base_d, base_h):
        to_world = frame(az)
        if key in OWN_PEDESTAL:
            base_h = 0.0
        elif base_h > 0.0:
            hw, hd, m = 0.5 * base_w, 0.5 * base_d, 0.09
            # plinth, base moulding, die, cap moulding, top slab
            box(b, to_world, u - hd - m, u + hd + m, -hw - m, hw + m, 0.0, 0.16)
            box(b, to_world, u - hd - 0.5 * m, u + hd + 0.5 * m, -hw - 0.5 * m, hw + 0.5 * m, 0.16, 0.24)
            box(b, to_world, u - hd, u + hd, -hw, hw, 0.24, base_h - 0.24)
            box(b, to_world, u - hd - 0.5 * m, u + hd + 0.5 * m, -hw - 0.5 * m, hw + 0.5 * m,
                base_h - 0.24, base_h - 0.15)
            box(b, to_world, u - hd - m, u + hd + m, -hw - m, hw + m, base_h - 0.15, base_h)
            # painted panels on the die: front (towards the rotunda) and both sides
            z0, z1, e = 0.30, base_h - 0.30, 0.006
            painted.quad(to_world(u - hd - e, hw - 0.06, z0), to_world(u - hd - e, -hw + 0.06, z0),
                         to_world(u - hd - e, -hw + 0.06, z1), to_world(u - hd - e, hw - 0.06, z1))
            for sgn in (-1.0, 1.0):
                painted.quad_out(to_world(u - hd + 0.06, sgn * (hw + e), z0), to_world(u + hd - 0.06, sgn * (hw + e), z0),
                                 to_world(u + hd - 0.06, sgn * (hw + e), z1), to_world(u - hd + 0.06, sgn * (hw + e), z1),
                                 Vector(to_world(0.0, sgn, 0.0)) - Vector(to_world(0.0, 0.0, 0.0)))
        x, y, z = to_world(u, 0.0, base_h)
        STATUE_SLOTS.append({"statue": key, "azimuth": az, "position": [x, y, z], "yaw": az - 90.0})

    # hero in the apse on a tall pedestal
    slot("jupiter_smyrna", APSE_AZ, apse_centre_u() + 0.9, 3.0, 2.2, 2.0)
    for az, key in EXEDRA_STATUES.items():
        depth = P["exedra_depth_semi"] if RECESSES[az] == "semi" else P["exedra_depth_rect"]
        slot(key, az, R + 0.6 * depth, 1.9, 1.6, 1.2)
    for az, key in AEDICULA_STATUES.items():
        slot(key, az, R - 0.55, 1.6, 0.9, P["aed_podium_h"])
    b.finish()
    painted.finish()


def build_doors():
    """Bronze doorway: two open leaves, fluted bronze pilasters, bronze entablature, lattice transom.

    Sizes from reference/dimensions.md section 9; the leaves open inwards and stand
    against the side walls of the door reveal.
    """
    R = P["R"]
    to_world = frame(ENTRANCE_AZ)
    u_door = R + P["entrance_depth"]
    dhw, dh = P["door_hw"], P["door_h"]
    leaf_w, leaf_h, leaf_t = 0.5 * 4.45, 7.53, 0.2
    hinge_u = u_door + 0.35
    b = Builder("Bronze_Doors")
    # leaves swung fully open, so they stand along the passage
    for side in (-1.0, 1.0):
        v_in = side * (leaf_w - 0.05)
        box(b, to_world, hinge_u - leaf_w, hinge_u, min(v_in, v_in + side * leaf_t),
            max(v_in, v_in + side * leaf_t), 0.0, leaf_h)
        # raised panels on the face towards the passage: two per leaf, as on the surviving doors
        face_v = v_in
        for z0, z1 in ((0.6, 3.4), (3.9, 7.0)):
            box(b, to_world, hinge_u - leaf_w + 0.25, hinge_u - 0.25,
                min(face_v, face_v - side * 0.04), max(face_v, face_v - side * 0.04), z0, z1)
            # second, smaller step on each panel
            box(b, to_world, hinge_u - leaf_w + 0.45, hinge_u - 0.45,
                min(face_v, face_v - side * 0.07), max(face_v, face_v - side * 0.07), z0 + 0.2, z1 - 0.2)
        # rows of square bronze studs along the rails and stiles, as on the surviving leaves
        s, v_a, v_b = 0.035, min(face_v, face_v - side * 0.035), max(face_v, face_v - side * 0.035)
        u_lo, u_hi = hinge_u - leaf_w, hinge_u
        for zc in (0.3, 3.65, 7.26):
            for k in range(8):
                uc = u_lo + 0.125 + k * (leaf_w - 0.25) / 7.0
                box(b, to_world, uc - s, uc + s, v_a, v_b, zc - s, zc + s)
        for uc in (u_lo + 0.125, u_hi - 0.125):
            zc = 0.6
            while zc < 7.1:
                if abs(zc - 3.65) > 0.15:
                    box(b, to_world, uc - s, uc + s, v_a, v_b, zc - s, zc + s)
                zc += 0.3
    # fluted bronze pilasters filling the opening beside the leaves
    for side in (-1.0, 1.0):
        # 2 cm into the marble reveal, so no light line opens along the joint
        v0, v1 = sorted((side * leaf_w, side * (dhw + 0.02)))
        box(b, to_world, u_door + 0.25, u_door + 0.7, v0, v1, 0.0, leaf_h)
    # bronze entablature over the leaves
    ent_top = leaf_h + 0.7
    box(b, to_world, u_door + 0.2, u_door + 0.75, -dhw - 0.02, dhw + 0.02, leaf_h, ent_top)
    b.finish()

    # transom grille: six vertical panels of lattice filling the rest of the opening
    g = Builder("Bronze_Grille")
    bar = 0.06
    u0, u1 = u_door + 0.4, u_door + 0.47
    for k in range(7):
        v = -dhw + k * (2.0 * dhw / 6.0)
        box(g, to_world, u0 - 0.03, u1 + 0.03, v - 0.08, v + 0.08, ent_top, dh)
    step = 0.3
    v = -dhw + step
    while v < dhw - 0.05:
        box(g, to_world, u0, u1, v - 0.5 * bar, v + 0.5 * bar, ent_top, dh)
        v += step
    z = ent_top + step
    while z < dh - 0.05:
        box(g, to_world, u0, u1, -dhw - 0.02, dhw + 0.02, z - 0.5 * bar, z + 0.5 * bar)
        z += step
    g.finish()


# --------------------------------------------------------------------------
# Dome: inner surface as a spherical height field with stepped coffers
# --------------------------------------------------------------------------

def band(az, el, depth):
    """Vertices and quads for one elevation band. depth has shape (len(el), len(az))."""
    R, zc = P["R"], P["spring_z"]
    r = R + depth
    ce, se = np.cos(el)[:, None], np.sin(el)[:, None]
    x = r * ce * np.cos(az)[None, :]
    y = r * ce * np.sin(az)[None, :]
    z = zc + r * se
    verts = np.stack([x, y, z], axis=-1).reshape(-1, 3)
    n_el, n_az = len(el), len(az)
    i, j = np.meshgrid(np.arange(n_el - 1), np.arange(n_az), indexing="ij")
    j2 = (j + 1) % n_az
    quads = np.stack([i * n_az + j, i * n_az + j2, (i + 1) * n_az + j2, (i + 1) * n_az + j],
                     axis=-1).reshape(-1, 4)
    return verts, quads


def with_breaks(uniform, breaks, eps):
    extra = [b + s for b in breaks for s in (-eps, eps)]
    return np.unique(np.concatenate([uniform, np.array(extra)]))


def build_dome():
    R = P["R"]
    n_cof = P["coffer_count"]
    cell = 2.0 * math.pi / n_cof
    per_cell = P["segments"] // n_cof
    bounds = [math.radians(d) for d in P["coffer_el_deg"]]
    el_oculus = math.acos(P["oculus_r"] / R)
    eps = 1.0e-4
    all_v, all_f, offset = [], [], 0

    def add(verts, quads):
        nonlocal offset
        all_v.append(verts)
        all_f.append(quads + offset)
        offset += len(verts)

    uniform_az = np.arange(P["segments"]) * (2.0 * math.pi / P["segments"])

    # plain band below the first coffer ring
    el = np.linspace(0.0, bounds[0], 5)
    add(*band(uniform_az, el, np.zeros((len(el), len(uniform_az)))))

    for ring in range(len(bounds) - 1):
        e0, e1 = bounds[ring], bounds[ring + 1]
        mid = 0.5 * (e0 + e1)
        steps = P["coffer_steps"][ring]
        g_az = 0.5 * P["coffer_rib_az"][ring] / (R * math.cos(mid))
        g_el = 0.5 * P["coffer_rib_el"] / R
        s_az = P["coffer_step_inset"][ring] / (R * math.cos(mid))
        s_lo = P["coffer_inset_low"] * P["coffer_step_inset"][ring] / R
        s_hi = P["coffer_inset_high"] * P["coffer_step_inset"][ring] / R
        d = P["coffer_step_depth"][ring]

        az_breaks = []
        for k in range(steps):
            az_breaks += [g_az + k * s_az, cell - g_az - k * s_az]
        local = with_breaks(np.arange(per_cell) * (cell / per_cell), az_breaks, eps)
        el_breaks = []
        for k in range(steps):
            el_breaks += [e0 + g_el + k * s_lo, e1 - g_el - k * s_hi]
        n_el = max(8, int(math.degrees(e1 - e0) * 2))
        el = with_breaks(np.linspace(e0, e1, n_el + 1), el_breaks, eps)

        depth_cell = np.zeros((len(el), len(local)))
        for k in range(steps):
            in_az = (local >= g_az + k * s_az) & (local <= cell - g_az - k * s_az)
            in_el = (el >= e0 + g_el + k * s_lo) & (el <= e1 - g_el - k * s_hi)
            depth_cell += d * np.outer(in_el, in_az)

        az = np.concatenate([c * cell + local for c in range(n_cof)])
        add(*band(az, el, np.tile(depth_cell, (1, n_cof))))

    # smooth zone between the last coffer ring and the oculus
    el = np.linspace(bounds[-1], el_oculus, 24)
    add(*band(uniform_az, el, np.zeros((len(el), len(uniform_az)))))

    new_object("Dome_Inner", np.concatenate(all_v).tolist(), np.concatenate(all_f).tolist())

    # Outside, the drum rises to 31.7 in three zones (cornices at 12.8, 21.8 and 31.7, Moore), seven
    # step rings stand on it (the first about 2.3 high and wide, the others about 0.8 high and 1.2
    # wide, Moore, estimated), and above them the dome shows only as a shallow cap up to the oculus
    # (Desgodetz pl. III; reference/dimensions.md). The model's drum used to stop at the springing
    # (21.7), so the whole hemisphere showed (user, 2026-11-25: proceed with the raised drum).
    zc, Ro = P["spring_z"], R + P["shell_t"]
    r_out = R + P["wall_t"]
    z_top = P["drum_top"]
    steps = [(r_out - 0.4, z_top - 0.05), (r_out - 0.4, z_top + 2.3), (r_out - 2.7, z_top + 2.3)]
    r, z = r_out - 2.7, z_top + 2.3
    for _ in range(6):
        steps += [(r, z + 0.8), (r - 1.2, z + 0.8)]
        r, z = r - 1.2, z + 0.8
    foot_r, foot_z = r, z
    # The cap: a sphere through the last tread's inner edge and the oculus rim, 1.5 above the inner
    # dome's edge there; it stays 2 m or more clear of the inner dome everywhere
    rim_z = zc + R * math.sin(el_oculus) + P["shell_t"]
    oc = P["oculus_r"]
    cz_cap = ((foot_r ** 2 + foot_z ** 2) - (oc ** 2 + rim_z ** 2)) / (2.0 * (foot_z - rim_z))
    r_cap = math.hypot(oc, rim_z - cz_cap)
    cap_z = lambda rr: cz_cap + math.sqrt(r_cap ** 2 - rr ** 2)
    # Gilded bronze tiles (the Hadrianic covering, stripped by Constans II in 663; user, 2026-11-25:
    # "dome in gilded bronze"): courses of tiles 0.6 m deep along the meridian, each lapping over the
    # next with a small lip, and cover strips running down over the joints between the columns of
    # tiles, as on a tiled roof
    n_course = 26
    rs = np.linspace(foot_r, oc, n_course + 1)
    profile = []
    for k in range(n_course):
        r0_, r1_ = rs[k], rs[k + 1]
        profile += [(r0_ + 0.025, cap_z(r0_) + 0.012), (r1_ + 0.012, cap_z(r1_) + 0.002)]
    profile.append((oc, rim_z))
    profile.insert(0, (foot_r - 0.05, foot_z))
    revolve("Dome_Outer", profile)
    ribs = Builder("Dome_Outer_Ribs")
    n_rib = 96
    for j in range(n_rib):
        a = 2.0 * math.pi * (j + 0.5) / n_rib
        ca, sa = math.cos(a), math.sin(a)
        ta = (-sa, ca)
        pts = [(rr, cap_z(rr)) for rr in np.linspace(foot_r, oc + 0.35, 24)]
        verts = []
        for rr, zz in pts:
            # a half-round cover strip, 12 cm wide, narrowing towards the oculus as the tiles do
            w = 0.06 * (0.55 + 0.45 * rr / foot_r)
            for dw, dz in ((-w, -0.01), (-0.6 * w, 0.045), (0.0, 0.06), (0.6 * w, 0.045), (w, -0.01)):
                verts.append((rr * ca + dw * ta[0], rr * sa + dw * ta[1], zz + dz))
        m = 5
        faces = []
        for i in range(len(pts) - 1):
            for q in range(m - 1):
                faces.append((i * m + q, (i + 1) * m + q, (i + 1) * m + q + 1, i * m + q + 1))
        faces.append(tuple(range(m - 1, -1, -1)))
        faces.append(tuple((len(pts) - 1) * m + q for q in range(m)))
        ribs.add(verts, faces)
    ribs.finish()
    # the bronze rim round the oculus, outside
    revolve("Dome_Outer_Rim", [(oc - 0.01, rim_z - 0.05), (oc - 0.01, rim_z + 0.35), (oc + 0.35, rim_z + 0.5), (oc + 0.8, rim_z + 0.42),
                               (oc + 1.1, cap_z(oc + 1.1) + 0.04), (oc + 1.1, cap_z(oc + 1.1) - 0.1),
                               (oc + 0.05, rim_z - 0.05)], closed=True)
    # (its inner face 1 cm inside the oculus ring's, which it overlaps for 5 cm)
    revolve("Oculus_Ring", [
        (P["oculus_r"], zc + R * math.sin(el_oculus)),
        (P["oculus_r"], rim_z),
    ])
    # The outer drum must leave no opening but the doorway: sunlight in the hollow between
    # the inner walls and this shell leaks into Lumen's indirect lighting. Below the
    # entrance arch springing the shell is open across the bay, which the bay side walls and
    # the door wall close; above it the shell runs unbroken.
    bay_gap = math.asin(P["exedra_hw"] / r_out)
    zs = arch_spring_z()
    # down to the forecourt's level, 1.4 below the floor (build_surroundings)
    revolve("Drum_Outer", [(r_out, PLAZA_Z), (r_out, zs)], skips=[(ENTRANCE_AZ, bay_gap)])
    # the drum's upper wall, its ledge 5 cm under the crowning cornice's top (the two used to share a
    # plane there), the seven step rings, and the last tread running in under the cap
    revolve("Drum_Outer_Upper", [(r_out, zs), (r_out, z_top - 0.05)] + steps + [(foot_r - 0.1, foot_z)])
    # Cornices round the outside of the drum (Moore: at 12.8, 21.8 and a crowning one at 31.7 with a
    # 1.1 m overhang), left out where the portico's block stands against the drum
    def cornice(z0, out, h):
        """(r, z) outline of a cornice whose top is at z0: fascia, cyma, corona, overhanging by out."""
        return [(r_out - 0.2, z0 - h), (r_out + 0.06, z0 - h), (r_out + 0.06, z0 - 0.75 * h),
                (r_out + 0.3 * out, z0 - 0.6 * h), (r_out + 0.75 * out, z0 - 0.35 * h), (r_out + out, z0 - 0.3 * h),
                (r_out + out, z0 - 0.06 * h), (r_out + out + 0.05, z0), (r_out - 0.2, z0)]
    block_hw = P["portico_spacing"] * 3.5 + 1.2 - 0.09
    corn = Builder("Drum_Outer_Cornices")
    for z0, out, h in ((12.8 + 0.3, 0.55, 0.65), (P["drum_mid"], 0.7, 0.8), (z_top, 1.1, 1.1)):
        skip = [(ENTRANCE_AZ, math.asin(block_hw / (r_out + out)))]
        ob = revolve("_cornice", cornice(z0, out, h), closed=True, skips=skip)
        corn.add([tuple(v.co) for v in ob.data.vertices], [tuple(f.vertices) for f in ob.data.polygons])
        bpy.data.objects.remove(ob)
    corn.finish()


# --------------------------------------------------------------------------
# Floor and portico placeholders
# --------------------------------------------------------------------------

EAGLE_HEIGHT_MAP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "eagle",
                                "eagle_height.npy")
EAGLE_ROUNDEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "eagle", "trellis",
                             "roundel_trellis2.glb")
# where the wreath sits in the height map's layout (13 m wide, its foot 0.25 above the cornice): centre
# and outer radius, from the photo's wreath at (1930, 960) px, radius 920 px, in the 3840 x 1806 crop
EAGLE_WIDTH = 13.0
EAGLE_WREATH = (0.5 - 1930.0 / 3840.0, 1.0 - (960.0 - 50.0) / 1806.0, 920.0 / 3840.0)


def build_pediment_eagle(face, zt, half_w, rise):
    """Gilded bronze relief on the tympanum: an eagle with spread wings in an oak wreath, ribbons
    either side.

    Nothing of the pediment's bronze survives; clamp holes in the tympanum show it carried a bronze
    relief, usually restored as an eagle in a wreath with ribbons (Desgodetz; de.wiki;
    reference/dimensions.md, lost finishes). The model is the Trajanic eagle in an oak wreath now in
    the portico of Santi Apostoli, Rome (probably from Trajan's Forum, so of the Pantheon's own years),
    from a photo by Sailko (CC BY 3.0, assets/eagle/photos/SOURCES.md):
      - the eagle in its wreath: a TRELLIS.2 model of the roundel (tools/eagle_trellis.py; user,
        2026-11-25: "why don't you model it properly in trellis"), turned to face the forecourt,
        scaled to the wreath, its depth flattened to a 0.55 m relief, and its flat ground set 4 cm
        behind the tympanum's face so that only the bird and the wreath stand out;
      - the ribbons either side: the photo's height map (tools/eagle_relief.py); the depth-estimated
        bird it once also gave read as a distorted lump.
    """
    width = EAGLE_WIDTH
    z0 = zt + 0.25
    cx_f, cz_f, r_f = EAGLE_WREATH
    if os.path.exists(EAGLE_HEIGHT_MAP):
        hm = np.load(EAGLE_HEIGHT_MAP)[::2, ::2]
        rows, cols = hm.shape
        height = width * (rows - 1) / (cols - 1)
        # the wreath's circle in the map's cells; the roundel model covers it
        rr, cc = np.mgrid[0:rows, 0:cols]
        wx = (0.5 - cc / (cols - 1)) * width
        wz = (1.0 - rr / (rows - 1)) * height
        inside = (hm > 0.0) & (np.hypot(wx - cx_f * width, wz - cz_f * height) > r_f * width * 1.02)
        keep = inside.copy()
        keep[1:, :] |= inside[:-1, :]
        keep[:-1, :] |= inside[1:, :]
        keep[:, 1:] |= inside[:, :-1]
        keep[:, :-1] |= inside[:, 1:]
        index = -np.ones(hm.shape, int)
        verts = []
        for r in range(rows):
            for c in range(cols):
                if keep[r, c]:
                    index[r, c] = len(verts)
                    # seen from the forecourt (looking towards -y), +x is on the left: the photo's
                    # columns run towards -x, or the relief comes out mirrored
                    verts.append(((0.5 - c / (cols - 1)) * width, face - 0.02 + 0.45 * float(hm[r, c]),
                                  z0 + (1.0 - r / (rows - 1)) * height))
        faces = []
        for r in range(rows - 1):
            for c in range(cols - 1):
                q = (index[r, c], index[r + 1, c], index[r + 1, c + 1], index[r, c + 1])
                if min(q) >= 0:
                    faces.append(q)               # wound to face +y, out of the tympanum
        obj = new_object("Portico_EagleRibbons", verts, faces)
        for poly in obj.data.polygons:
            poly.use_smooth = True
        centre = (cx_f * width, z0 + cz_f * height)
        diameter = 2.0 * r_f * width
    else:
        print("no eagle height map at %s: no ribbons" % EAGLE_HEIGHT_MAP)
        centre, diameter = (0.0, zt + 3.4), 6.2
    if not os.path.exists(EAGLE_ROUNDEL):
        print("no eagle roundel at %s: tympanum left without its eagle" % EAGLE_ROUNDEL)
        return
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=EAGLE_ROUNDEL)
    new = [o for o in set(bpy.data.objects) - before if o.type == "MESH"]
    pts, tris = [], []
    for o in new:
        o.data.calc_loop_triangles()
        m = o.matrix_world
        base = sum(len(p) for p in pts)
        pts.append(np.array([tuple(m @ v.co) for v in o.data.vertices]))
        tris += [tuple(base + i for i in t.vertices) for t in o.data.loop_triangles]
    for o in set(bpy.data.objects) - before:
        bpy.data.objects.remove(o)
    v = np.concatenate(pts)
    # the model: Z up, its relief facing -y with the head towards -x (the photo's view); turned half
    # round about Z it faces the forecourt (+y) with the head on the viewer's left (+x), as in the photo
    v[:, 0], v[:, 1] = -v[:, 0], -v[:, 1]
    mid = 0.5 * (v.min(0) + v.max(0))
    k = diameter / (v[:, 0].max() - v[:, 0].min())
    # the flat ground inside the wreath: the most common depth, finely binned
    hist, edges = np.histogram(v[:, 1], 400)
    ground = 0.5 * (edges[hist.argmax()] + edges[hist.argmax() + 1])
    squash = 0.55 / ((v[:, 1].max() - ground) * k)
    out = np.empty_like(v)
    out[:, 0] = centre[0] + (v[:, 0] - mid[0]) * k
    out[:, 2] = centre[1] + (v[:, 2] - mid[2]) * k
    out[:, 1] = face - 0.04 + (v[:, 1] - ground) * k * squash
    obj = new_object("Portico_Eagle", [tuple(p) for p in out], tris)
    # The glTF comes split at its texture seams (200 000 open edges): decimated as it was, the seams
    # opened into holes all over the bird (user, 2026-11-25: "the model appears to have holes in it").
    # Welded first it is all but watertight (85 open edges of 740 000), and stays whole (its back plate
    # lies behind the stone; dropping the faces that look backwards also took the feathers' undercuts);
    # the generated surface's crinkle is smoothed a little, which keeps the feathers' forms (user: "the
    # eagle should be smooth with feathers")
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.002)
    bm.to_mesh(obj.data)
    bm.free()
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    smooth = obj.modifiers.new("Smooth", "LAPLACIANSMOOTH")
    smooth.iterations = 3
    smooth.lambda_factor = 0.4
    smooth.use_volume_preserve = True
    bpy.ops.object.modifier_apply(modifier=smooth.name)
    # half a million triangles from TRELLIS: a third is plenty 25 m up
    dec = obj.modifiers.new("Decimate", "DECIMATE")
    dec.ratio = 0.33
    dec.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=dec.name)
    for poly in obj.data.polygons:
        poly.use_smooth = True


def build_entrance_floor(yb):
    """The floor through the entrance bay (from the rotunda's floor out to the door) and through the
    door passage to the portico. The ground plane used to stand in for it, at floor level; when the
    forecourt went down 1.4 m it left a pit at the doors (user, 2026-11-25: "the ground is lowered
    around the doors"). Slabs in the bay meet the rotunda's floor along its circle, 3 mm under its
    slabs' tops, so the two never share a plane where they overlap; a bedding under both closes the
    joints."""
    R = P["R"]
    r_door = R + P["entrance_depth"]
    bay_hw = P["exedra_hw"]
    pw = P["door_hw"] + 0.75
    top = SLAB_TOP - 0.003
    arc = lambda x: math.sqrt(max(R * R - x * x, 0.0))
    bay = Builder("Floor_Entrance")
    xs = [-bay_hw, -1.5, 1.5, bay_hw]
    ys = [R - 0.5, R + 1.6, R + 3.2, R + 4.7, r_door]
    g = 0.5 * SLAB_GAP
    for i in range(3):
        for j in range(4):
            x0, x1, y0, y1 = xs[i] + g, xs[i + 1] - g, ys[j] + g, ys[j + 1] - g
            low = [(x0 + (x1 - x0) * k / 8, max(y0, arc(x0 + (x1 - x0) * k / 8) + g)) for k in range(9)]
            if all(yv >= y1 for _, yv in low):
                continue
            outline = [(x, min(yv, y1)) for x, yv in low] + [(x1, y1), (x0, y1)]
            n = len(outline)
            verts = [(x, y, 0.0) for x, y in outline] + [(x, y, top) for x, y in outline]
            faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
            faces += [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
            bay.add(verts, faces)
    bay.finish()
    paving("Portico_Passage", -pw, pw, r_door, yb, row=1.4, length=2.0)
    bed = Builder("Floor_EntranceBedding")
    box(bed, FLAT, -bay_hw, bay_hw, R - 0.5, yb, -0.4, -0.004)
    bed.finish()


def build_recess_floor():
    """The floor of the exedrae and the apse, from the rotunda's floor out to their back walls. Like
    the entrance's, it used to be the ground plane at floor level, and it went down with the forecourt
    (user, 2026-11-25: "floor under statues inside is missing"). Pavonazzetto slabs clipped to the
    ring between the rotunda's circle and the drum's outer face (where no recess is, they lie inside
    the wall), 1 mm under the rotunda's slabs, so where the two overlap at the circle they never share
    a plane; the entrance bay has its own (build_entrance_floor). A bedding ring under them closes
    the joints."""
    R = P["R"]
    # 0.5 inside the drum's outer face (the deepest recess, the apse, ends 4.3 behind the circle): the
    # slabs are clipped in 0.4 m cells, and ending at the face itself some stuck out through it and cast
    # rows of triangular shadows down the outside of the drum (2026-11-25)
    r_out = R + P["wall_t"] - 0.5
    bay_hw = P["exedra_hw"]

    def inside(x, y):
        r = math.hypot(x, y)
        return R - 0.05 <= r <= r_out and not (abs(x) < bay_hw + 0.05 and y > 0.0)
    paving("Floor_Recesses", -r_out, r_out, -r_out, r_out, row=1.4, length=1.4, inside=inside,
           top=SLAB_TOP - 0.004)
    bed = Builder("Floor_RecessBedding")
    n = P["segments"]
    for j in range(n):
        a0, a1 = 2.0 * math.pi * j / n, 2.0 * math.pi * (j + 1) / n
        p = lambda r, a: (r * math.cos(a), r * math.sin(a), -0.004)
        bed.quad_out(p(R - 0.3, a0), p(r_out, a0), p(r_out, a1), p(R - 0.3, a1), (0.0, 0.0, 1.0))
    bed.finish()


def build_block_front(half_w, yb, y_low, rise):
    """Above the portico roof, the block's front carries a second, higher pediment over a cornice that
    continues the drum's middle one; the drum's crowning cornice runs on across the block's front and
    sides. Traces of the second pediment survive (reference/dimensions.md, transitional block) and
    Desgodetz draws it (pl. III); its pitch is the portico's."""
    b = Builder("Portico_BlockCornices")
    along_x = lambda u, v, z: (v, u, z)
    along_y = lambda u, v, z: (u, v, z)
    z_mid, z_top = P["drum_mid"], P["drum_top"]

    def section(face, sgn, z0, out, h):
        """The drum's cornice section, its face at face, projecting towards sgn."""
        o = lambda k: face + sgn * k
        return [(o(-0.2), z0 - h), (o(0.06), z0 - h), (o(0.06), z0 - 0.75 * h), (o(0.3 * out), z0 - 0.6 * h),
                (o(0.75 * out), z0 - 0.35 * h), (o(out), z0 - 0.3 * h), (o(out), z0 - 0.06 * h),
                (o(out + 0.05), z0), (o(-0.2), z0)]

    for z0, out, h in ((z_mid, 0.7, 0.8), (z_top, 1.1, 1.1)):
        reach = half_w + out + 0.05
        prism_v(b, along_x, section(yb, 1.0, z0, out, h), -reach, reach)
        for sgn in (-1.0, 1.0):
            # 1 cm lower than the front's, so their tops do not share a plane where they overlap
            prism_v(b, along_y, section(sgn * half_w, sgn, z0 - 0.01, out, h), y_low, yb + out + 0.05)
    # the second pediment's raking cornices, the portico's section, on the block's face
    base = lambda x: z_mid + rise * (1.0 - abs(x) / half_w)
    sec = [(-1.6, 0.0), (0.0, 0.0), (0.0, 0.22), (0.1, 0.27), (0.1, 0.42), (0.2, 0.47), (0.2, 0.52),
           (0.85, 0.52), (0.85, 0.82), (0.92, 0.86), (0.92, 0.92), (1.0, 1.0), (1.0, 1.1), (-1.6, 1.1)]
    end = half_w + 0.7
    ring = [[(x, yb + d, base(x) + hh) for d, hh in sec] for x in (-end, 0.0, end)]
    m = len(sec)
    faces = [tuple(range(m - 1, -1, -1)), tuple(2 * m + i for i in range(m))]
    for k in range(2):
        for i in range(m):
            i2 = (i + 1) % m
            faces.append((k * m + i, k * m + i2, (k + 1) * m + i2, (k + 1) * m + i))
    b.add([v for r in ring for v in r], faces)
    b.finish()


def build_floor_and_portico():
    """Ground, portico of 16 granite columns, entablature with the Agrippa inscription, pediment,
    gable roof on bronze tie-beams, and the transitional block with the passage to the bronze door.

    Model axes: x across the front, +y outwards from the rotunda. Sizes from reference/dimensions.md
    (portico 33.1 x 15.5, columns 14.15 high, shafts 1.5 diameter, axial spacing 4.54; door wall to
    portico rear wall about 5.5). Entablature and pediment heights were not found in open sources and
    are proportioned from the order (entablature about one fifth of the column, pediment 23 degrees).
    """
    # just below the forecourt's paving; out to the city's far edge (build_surroundings)
    s, g = 700.0, PLAZA_Z - 0.01
    new_object("Ground", [(-s, -s, g), (s, -s, g), (s, s, g), (-s, s, g)], [(0, 1, 2, 3)])
    R = P["R"]
    front = P["portico_front_y"]
    sp, h, d = P["portico_spacing"], P["portico_col_h"], P["portico_col_d"]
    xs = [(-3.5 + i) * sp for i in range(8)]
    half_w = xs[-1] + 1.2
    yb = R + P["wall_t"] + 5.5           # portico rear wall: front face of the transitional block
    E = 2.9                              # entablature height
    zt = h + E

    # columns: grey granite in front, pink granite behind
    for i, x in enumerate(xs):
        # squared to the portico; the scanned capitals' good face looks out to the forecourt
        order_column("Portico_Front_%d" % i, x, front, 0.0, h, d, facing=90.0, cap_yaw=90.0)
    for i in (0, 2, 5, 7):
        for row in (1, 2):
            order_column("Portico_Inner_%d_%d" % (i, row), xs[i], front - row * 4.6, 0.0, h, d,
                         facing=90.0, cap_yaw=90.0)

    along_x = lambda u, v, z: (v, u, z)   # profile in (y, z), extruded along x
    along_y = lambda u, v, z: (u, v, z)   # profile in (x, z), extruded along y

    def entab_profile(face, out):
        """Architrave (three fasciae), frieze, cornice; face = front plane, out = +1 or -1 outwards."""
        o = lambda k: face + out * k
        return [(o(-1.8), h), (o(0.0), h), (o(0.0), h + 0.3), (o(0.04), h + 0.3), (o(0.04), h + 0.6),
                (o(0.08), h + 0.6), (o(0.08), h + 0.9), (o(0.02), h + 0.9), (o(0.02), h + 1.75),
                (o(0.15), h + 1.75), (o(0.15), h + 1.95), (o(0.3), h + 1.95), (o(0.3), h + 2.1),
                (o(0.9), h + 2.15), (o(0.9), h + 2.6), (o(1.0), zt), (o(-1.8), zt)]

    ent = Builder("Portico_Entablature")
    prism_v(ent, along_x, entab_profile(front + 0.9, 1.0), -half_w, half_w)
    for sgn in (-1.0, 1.0):
        prism_v(ent, along_y, entab_profile(sgn * half_w, sgn), yb, front + 0.9)
    for i in (2, 5):  # beams over the inner rows, dividing the three aisles
        box(ent, along_y, xs[i] - 0.75, xs[i] + 0.75, yb, front - 0.9, h, zt - 0.6)
    ent.finish()

    # inscription in bronze letters on the frieze
    curve = bpy.data.curves.new("Inscription", "FONT")
    curve.body = "M\u00b7AGRIPPA\u00b7L\u00b7F\u00b7COS\u00b7TERTIVM\u00b7FECIT"
    curve.size = 0.62
    curve.extrude = 0.025
    curve.align_x = "CENTER"
    txt = bpy.data.objects.new("Bronze_Inscription", curve)
    bpy.context.scene.collection.objects.link(txt)
    txt.rotation_euler = (math.radians(90.0), 0.0, math.radians(180.0))
    txt.location = (0.0, front + 0.95, h + 1.08)
    bpy.context.view_layer.objects.active = txt
    bpy.ops.object.select_all(action="DESELECT")
    txt.select_set(True)
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Pediment: the tympanum, recessed behind moulded raking cornices with modillions under the
    # corona, as Desgodetz draws them (pl. III). The raking cornices used to be plain bands, and the
    # bronze roof showed through at the apex and the eaves (user, 2026-11-25). The tympanum is a
    # separate object for its ashlar joints; the gilded bronze eagle on it is build_pediment_eagle's.
    rise = half_w * math.tan(math.radians(23.0))
    face = front + 0.6                      # tympanum face
    base = lambda x: zt + rise * (1.0 - abs(x) / half_w)   # top edge of the tympanum
    tym = Builder("Portico_Tympanum")
    prism(tym, along_x, [(-half_w, zt), (half_w, zt), (0.0, zt + rise)], face, front - 1.0)
    tym.finish()
    ped = Builder("Portico_Pediment")
    # cornice section: (d, h) = forward of the tympanum face, above its top edge (vertical): bed
    # mouldings, a corona overhanging 1.05 and a sima, whose front meets the horizontal cornice's
    # (front + 1.9) at the corners. Its top stands 0.2-0.4 above the roof slabs everywhere.
    section = [(-1.6, 0.0), (0.0, 0.0), (0.0, 0.22), (0.1, 0.27), (0.1, 0.42), (0.2, 0.47), (0.2, 0.52),
               (1.05, 0.52), (1.05, 0.86), (1.12, 0.9), (1.12, 0.96), (1.24, 1.06), (1.3, 1.16), (1.3, 1.24),
               (-1.6, 1.24)]
    end = half_w + 1.0
    stations = [-end, 0.0, end]
    ring = [[(x, face + d, base(x) + h) for d, h in section] for x in stations]
    m = len(section)
    verts = [v for r in ring for v in r]
    faces = [tuple(range(m - 1, -1, -1)), tuple(2 * m + i for i in range(m))]
    for s in range(2):
        for i in range(m):
            i2 = (i + 1) % m
            faces.append((s * m + i, s * m + i2, (s + 1) * m + i2, (s + 1) * m + i))
    ped.add(verts, faces)
    # modillions: under the raking corona, along each slope, and under the horizontal cornice
    sheared = lambda u, v, z: (u, face + v, base(u) + z)
    x = 0.45
    while x < half_w - 0.3:
        for sgn in (-1.0, 1.0):
            box(ped, sheared, sgn * x - 0.1, sgn * x + 0.1, 0.25, 0.95, 0.3, 0.53)
        x += 0.7
    flat = lambda u, v, z: (u, v, z)
    x = -half_w + 0.35
    while x < half_w - 0.3:
        box(ped, flat, x - 0.1, x + 0.1, front + 1.2, front + 1.75, h + 1.92, h + 2.16)
        x += 0.7
    ped.finish()
    build_pediment_eagle(face, zt, half_w, rise)

    # gable roof of gilded bronze tiles, on bronze tie-beams (both lost; restored)
    roof = Builder("Bronze_Roof")
    ridge = zt + rise + 0.2
    eave = half_w + 0.9
    slab = 0.25
    # each slope is a closed slab: single-sided sheets were culled from below, so the sky showed
    # between the tie-beams when looking up in the portico (vertical film stills)
    # The slabs end 10 cm behind the tympanum face, inside the pediment: ending in the plane of the
    # old raking bands' front, the slab's end fought it at the apex, and lower down it showed as bronze
    # slivers under the cornice at the apex and above it at the eaves (user, 2026-11-25)
    roof_y = front + 0.5
    for sgn in (-1.0, 1.0):
        top = [(0.0, yb, ridge), (sgn * eave, yb, zt), (sgn * eave, roof_y, zt), (0.0, roof_y, ridge)]
        bottom = [(x, y, z - slab) for x, y, z in top]
        faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        if sgn < 0:
            faces = [tuple(reversed(f)) for f in faces]
        roof.add(top + bottom, faces)
        # bronze purlins along the slope, under the roof and resting on the tie-beam rafters
        for frac in (0.3, 0.62):
            x = sgn * frac * eave
            z = ridge - (ridge - zt) * frac - slab - 0.18
            strut(roof, (x, yb, z), (x, front + 0.5, z), 0.32)
    y = yb + 1.5
    while y < front - 0.5:
        box(roof, along_x, y - 0.25, y + 0.25, -half_w, half_w, zt - 0.6, zt)
        strut(roof, (-half_w, y, zt), (0.0, y, ridge - 0.3), 0.35)
        strut(roof, (half_w, y, zt), (0.0, y, ridge - 0.3), 0.35)
        y += 2.3
    # Bronze tiles: the slopes were bare sheets, "unrealistically smooth" (user, 2026-11-25). Cover tiles
    # (imbrices) run down each slope over the joints between the rows of flat tiles, every 0.6 m, with a
    # cap along the ridge; each a closed half-round-ish prism sunk 1 cm into the slab
    tiles = Builder("Bronze_RoofTiles")
    surf = lambda x: ridge - (ridge - zt) * abs(x) / eave          # the slope's top at x
    y = yb + 0.3
    while y < roof_y - 0.2:
        for sgn in (-1.0, 1.0):
            sec = []
            for x in (sgn * 0.35, sgn * (eave - 0.02)):
                z = surf(x)
                sec += [(x, y - 0.11, z - 0.01), (x, y - 0.07, z + 0.07), (x, y, z + 0.1), (x, y + 0.07, z + 0.07),
                        (x, y + 0.11, z - 0.01)]
            add_convex(tiles, sec, [(0, 1, 2, 3, 4), (9, 8, 7, 6, 5), (0, 5, 6, 1), (1, 6, 7, 2), (2, 7, 8, 3),
                                    (3, 8, 9, 4), (4, 9, 5, 0)])
        y += 0.6
    cap = []
    for yy in (yb + 0.05, roof_y - 0.05):
        cap += [(-0.45, yy, surf(0.45) - 0.01), (-0.25, yy, ridge + 0.12), (0.0, yy, ridge + 0.18),
                (0.25, yy, ridge + 0.12), (0.45, yy, surf(0.45) - 0.01)]
    add_convex(tiles, cap, [(0, 1, 2, 3, 4), (9, 8, 7, 6, 5), (0, 5, 6, 1), (1, 6, 7, 2), (2, 7, 8, 3),
                            (3, 8, 9, 4), (4, 9, 5, 0)])
    tiles.finish()
    roof.finish()

    # transitional block: marble front with the passage to the door, aisle niches for Augustus and Agrippa
    blk = Builder("Portico_Block")
    # as high as the drum, 3 cm under the top of its crowning cornice (which runs on round the block)
    # and 2 cm over the drum's ledge behind the cornice, so neither shares the block top's plane
    top = P["drum_top"] - 0.03
    pw, ph = P["door_hw"] + 0.75, P["door_h"] + 0.8       # passage with the marble door frame
    nx, nw, nd, nh = 0.5 * (xs[0] + xs[2]), 2.3, 2.0, 8.5  # niches at the ends of the side aisles
    cuts = sorted([(-nx - nw, -nx + nw, nh), (-pw, pw, ph), (nx - nw, nx + nw, nh)])
    xs_cut = [-half_w] + [c for a0, a1, _ in cuts for c in (a0, a1)] + [half_w]
    for k in range(len(xs_cut) - 1):
        x0, x1 = xs_cut[k], xs_cut[k + 1]
        z0 = 0.0
        for a0, a1, hh in cuts:
            if abs(x0 - a0) < 1e-6 and abs(x1 - a1) < 1e-6:
                z0 = hh
        blk.add([(x0, yb, z0), (x1, yb, z0), (x1, yb, top), (x0, yb, top)], [(0, 1, 2, 3)])
    for sgn in (-1.0, 1.0):  # passage side walls and ceiling
        blk.add([(sgn * pw, R + P["wall_t"] - 0.3, 0.0), (sgn * pw, yb, 0.0), (sgn * pw, yb, ph),
                 (sgn * pw, R + P["wall_t"] - 0.3, ph)], [(0, 1, 2, 3)])
    blk.add([(-pw, R + P["wall_t"] - 0.3, ph), (pw, R + P["wall_t"] - 0.3, ph), (pw, yb, ph), (-pw, yb, ph)],
            [(0, 1, 2, 3)])
    for sgn in (-1.0, 1.0):  # half-round niches, with a moulded statue base
        c = sgn * nx
        pts = [(c + nw * math.cos(math.pi * k / 16), yb - nd + 0.0 * k) for k in range(17)]
        ring = [(c + nw * math.cos(math.pi * k / 16), yb - nd * math.sin(math.pi * k / 16)) for k in range(17)]
        for k in range(16):
            (x0, y0), (x1, y1) = ring[k], ring[k + 1]
            blk.add([(x0, y0, 0.0), (x1, y1, 0.0), (x1, y1, nh), (x0, y0, nh)], [(0, 1, 2, 3)])
        blk.add([(x, y, nh) for x, y in ring], [tuple(range(17))])
        box(blk, along_y, c - 0.9, c + 0.9, yb - 1.6, yb - 0.3, 0.0, 1.6)
    # Block sides and top, running back into the masonry. They used to stop at y = R + 2, about 1.6 m
    # short of the drum at the block's corners: a slot from the ground to the top on both sides,
    # through which one could walk into the hollow block and behind the portico statues (user,
    # 2026-11-24). Each side now ends inside the drum wall (r = drum - 0.4) from the forecourt to the
    # top, the drum standing as high as the block (build_dome); the top's back edge follows an arc
    # under the first of the dome's step rings.
    r_wall = R + P["wall_t"] - 0.4
    y_low = math.sqrt(r_wall ** 2 - half_w ** 2)
    for sgn in (-1.0, 1.0):
        outline = [(sgn * half_w, y_low, PLAZA_Z), (sgn * half_w, yb, PLAZA_Z), (sgn * half_w, yb, top),
                   (sgn * half_w, y_low, top)]
        idx = list(range(len(outline)))
        blk.add(outline, [tuple(idx if sgn > 0 else reversed(idx))])
    r_top = R + P["wall_t"] - 0.5
    arc = [(half_w * (1.0 - 2.0 * k / 16), math.sqrt(max(r_top ** 2 - (half_w * (1.0 - 2.0 * k / 16)) ** 2, 0.0)), top)
           for k in range(17)]
    # wound anticlockwise seen from above, so it faces up (refine() cannot orient an open shell)
    blk.add([(-half_w, yb, top), (half_w, yb, top)] + arc, [tuple(reversed(range(19)))])
    blk.finish()
    build_block_front(half_w, yb, y_low, rise)
    PORTICO_NICHES[:] = [{"x": sgn * nx, "y": yb - 1.0, "z": 1.6, "yaw": 0.0} for sgn in (-1.0, 1.0)]
    # Augustus and Agrippa (Cassius Dio 53.27), facing out towards the portico front (+y)
    for sgn, key in ((1.0, "augustus_portico"), (-1.0, "agrippa_portico")):
        STATUE_SLOTS.append({"statue": key, "azimuth": 90.0, "position": [sgn * nx, yb - 0.95, 1.6], "yaw": 180.0})

    # portico paving as separate worn slabs; the forecourt, its steps and the city round it are
    # build_surroundings'
    paving("Portico_Floor", -half_w, half_w, yb, front + 1.6, row=1.5, length=2.2)
    build_entrance_floor(yb)
    build_surroundings(half_w, yb, front, math.sqrt(r_wall ** 2 - half_w ** 2))


# --------------------------------------------------------------------------
# Forecourt and city (user, 2026-11-25: "instead of blank canvas, the building should be placed in
# front of a plaza, surrounded by building facades from the period")
# --------------------------------------------------------------------------
# What is known: the Hadrianic forecourt was a travertine-paved square, larger than today's piazza and
# lower (2020 sinkhole; turismoroma.it), shared with the Basilica of Neptune behind the rotunda (Oxford
# ORA thesis on the Agrippan complex). Colonnades down its long sides and a gateway at the far end are
# the usual reconstruction; the evidence for them is thin. Agrippa's Basilica of Neptune stood against
# the rotunda's back, his baths beyond it, the Saepta Julia to the east. The rest is a plausible Roman
# city: brick-and-stucco apartment blocks (insulae) with shops on the ground floor and tiled roofs.
#
# Geometry: every solid here is either one closed prism (refine() orients and bevels it) or is wound
# outwards as it is built (add_convex, quad_out), and no two solids of one refined object share a
# vertex. The first version built the steps from boxes touching along their edges: refine() welded
# them into one non-manifold mesh, faces turned inside out, and the steps flickered as one flat wall
# (user, 2026-11-25).
COLONNADE = {"front": 24.2, "axis": 25.4, "back": 32.0, "wall": 0.6, "y0": 56.0, "y1": 150.0,
             "h": 7.2, "d": 0.8, "spacing": 3.6}
# Agrippa's Basilica of Neptune behind the rotunda: its walls' extent along y, height, gable rise, eaves
BASILICA = {"y0": -52.0, "y1": -28.4, "h": 22.0, "ridge": 5.5, "overhang": 0.6}
CITY_RNG = random.Random(4140)
CITY_COLOURS = ("Ochre", "Red", "Cream", "Brick")
FLAT = lambda u, v, z: (u, v, z)
BOX_FACES = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def add_convex(builder, verts, faces):
    """A convex solid, each face wound so that its normal points away from the solid's centre."""
    c = Vector(tuple(np.mean(np.array(verts, float), axis=0)))
    out = []
    for f in faces:
        pts = [Vector(verts[i]) for i in f]
        n = Vector((0.0, 0.0, 0.0))
        for k in range(len(pts)):                       # Newell's normal: sound for any polygon
            a, b = pts[k], pts[(k + 1) % len(pts)]
            n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
        mid = sum(pts, Vector()) / len(pts)
        out.append(tuple(reversed(f)) if n.dot(mid - c) < 0.0 else tuple(f))
    builder.add(verts, out)


def cbox(builder, x0, x1, y0, y1, z0, z1):
    """A closed box, wound outwards."""
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    add_convex(builder, [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], BOX_FACES)


def slab_between(builder, top, thickness):
    """A closed slab under a quad top (4 points), thickness straight down."""
    add_convex(builder, top + [(x, y, z - thickness) for x, y, z in top], BOX_FACES)


def roof_tiles(builder, face, spacing=0.42):
    """Cover tiles (imbrices) down one roof face: face is its outline, the eave edge first (two points),
    then the rest; a ridge every spacing along the eave, from the eave up to where the face ends (at the
    ridge or a hip), a low closed prism standing on the face (user, 2026-11-25: "real roof tiles")."""
    p0, p1 = Vector(face[0]), Vector(face[1])
    e1 = (p1 - p0).normalized()
    apex = sum((Vector(q) for q in face[2:]), Vector()) / (len(face) - 2)
    e2 = (apex - p0) - (apex - p0).dot(e1) * e1
    e2.normalize()
    n = e1.cross(e2)
    if n.z < 0.0:
        n = -n
    pts = [((Vector(q) - p0).dot(e1), (Vector(q) - p0).dot(e2)) for q in face]
    length = (p1 - p0).length
    a = 0.5 * spacing
    while a < length - 0.1:
        top = None
        for k in range(len(pts)):                       # where the line a = const leaves the face
            (a0, b0), (a1, b1) = pts[k], pts[(k + 1) % len(pts)]
            if (a0 - a) * (a1 - a) < 0.0 or (a0 == a and a1 != a):
                bb = b0 + (b1 - b0) * (a - a0) / (a1 - a0)
                top = bb if top is None else max(top, bb)
        if top is not None and top > 0.3:
            verts = []
            for b in (0.02, top - 0.05):
                o = p0 + e1 * a + e2 * b
                for da, dn in ((-0.08, -0.01), (0.0, 0.07), (0.08, -0.01)):
                    verts.append(tuple(o + e1 * da + n * dn))
            add_convex(builder, verts, [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)])
        a += spacing


def hip_roof(builder, x0, x1, y0, y1, z, rise, overhang=0.6, tiles=None):
    """A tiled hip roof over a rectangle, its eaves overhanging by overhang; with tiles, cover tiles
    run down each face (roof_tiles)."""
    x0, x1, y0, y1 = x0 - overhang, x1 + overhang, y0 - overhang, y1 + overhang
    w, d = x1 - x0, y1 - y0
    zr = z + rise
    if w >= d:
        r0, r1 = (x0 + 0.5 * d, 0.5 * (y0 + y1)), (x1 - 0.5 * d, 0.5 * (y0 + y1))
        faces = [(0, 1, 5, 4), (2, 3, 4, 5), (1, 2, 5), (3, 0, 4), (3, 2, 1, 0)]
    else:
        r0, r1 = (0.5 * (x0 + x1), y0 + 0.5 * w), (0.5 * (x0 + x1), y1 - 0.5 * w)
        faces = [(1, 2, 5, 4), (3, 0, 4, 5), (0, 1, 4), (2, 3, 5), (3, 2, 1, 0)]
    verts = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z), (r0[0], r0[1], zr), (r1[0], r1[1], zr)]
    add_convex(builder, verts, faces)
    if tiles is not None:
        for f in faces[:4]:
            # each sloping face, its eave edge first (the two corners at eave height), wound either way
            eave = [i for i in f if i < 4]
            rest = [i for i in f if i >= 4]
            tiles_face = [verts[i] for i in eave] + [verts[i] for i in rest]
            roof_tiles(tiles, tiles_face)


def gable_prism(builder, x0, x1, y0, y1, z, ridge, along="x"):
    """A gable roof as a triangular prism, its ridge along x or y."""
    if along == "x":
        tri = [(y0, z), (y1, z), (0.5 * (y0 + y1), z + ridge)]
        verts = [(x0, v, zz) for v, zz in tri] + [(x1, v, zz) for v, zz in tri]
    else:
        tri = [(x0, z), (x1, z), (0.5 * (x0 + x1), z + ridge)]
        verts = [(u, y0, zz) for u, zz in tri] + [(u, y1, zz) for u, zz in tri]
    add_convex(builder, verts, [(0, 1, 2), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)])


def facade(parts, wall, axis, plane, out, a0, a1, z_lo, z_hi, rows, reveal=0.25, depth=1.2, trims=True):
    """A wall face with openings that look into darkness: the face itself, tiled round the openings;
    for each opening, reveals in the wall's own finish, then a dark recess (Void) to depth behind
    the face, and an invisible blocker in the opening (Blockers), so that one can look in but not
    walk or fly in (user, 2026-11-25: they "can open into darkness but not allow to walk in").

    axis "x": the face lies in the plane x = plane and runs along y from a0 to a1; axis "y": in y =
    plane, along x. out (+1 or -1): the way it looks. rows: (zb, zt, [(c0, c1), ...], kind) per row of
    openings, kind "shop" or "window" (travertine frames over shops and sills under windows when
    trims)."""
    if axis == "x":
        P_ = lambda a, z, o: (plane + out * o, a, z)
        N, A = (out, 0.0, 0.0), (0.0, 1.0, 0.0)
    else:
        P_ = lambda a, z, o: (a, plane + out * o, z)
        N, A = (0.0, out, 0.0), (1.0, 0.0, 0.0)
    neg = lambda v: tuple(-c for c in v)
    up, down = (0.0, 0.0, 1.0), (0.0, 0.0, -1.0)

    def quad(b, a_0, a_1, z_0, z_1, o, normal):
        b.quad_out(P_(a_0, z_0, o), P_(a_1, z_0, o), P_(a_1, z_1, o), P_(a_0, z_1, o), normal)

    z = z_lo
    for zb, zt, opens, kind in sorted((r for r in rows if r[0] >= z_lo and r[1] <= z_hi), key=lambda r: r[0]):
        if zb > z + 1e-6:
            quad(wall, a0, a1, z, zb, 0.0, N)
        edges = [a0] + [c for c0, c1 in sorted(opens) for c in (c0, c1)] + [a1]
        for k in range(0, len(edges), 2):
            if edges[k + 1] - edges[k] > 1e-6:
                quad(wall, edges[k], edges[k + 1], zb, zt, 0.0, N)
        for c0, c1 in opens:
            dep = depth if kind == "window" else max(depth, 2.4)
            for b, oa, ob in ((wall, 0.0, reveal), (parts["Void"], reveal, dep)):
                # the reveals' sides, sill and head, each facing into the opening (o runs inwards)
                b.quad_out(P_(c0, zb, -oa), P_(c0, zb, -ob), P_(c0, zt, -ob), P_(c0, zt, -oa), A)
                b.quad_out(P_(c1, zb, -oa), P_(c1, zb, -ob), P_(c1, zt, -ob), P_(c1, zt, -oa), neg(A))
                b.quad_out(P_(c0, zb, -oa), P_(c1, zb, -oa), P_(c1, zb, -ob), P_(c0, zb, -ob), up)
                b.quad_out(P_(c0, zt, -oa), P_(c1, zt, -oa), P_(c1, zt, -ob), P_(c0, zt, -ob), down)
            quad(parts["Void"], c0, c1, zb, zt, -dep, N)                    # the back, in the dark
            quad(parts["Blockers"], c0, c1, zb, zt, -0.05, N)
            if trims:
                if kind == "shop":
                    p0, p1 = P_(c0 - 0.2, zt, -0.12), P_(c1 + 0.2, zt + 0.25, 0.02)
                else:
                    p0, p1 = P_(c0 - 0.15, zb - 0.1, -0.12), P_(c1 + 0.15, zb, 0.02)
                cbox(parts["Trim"], p0[0], p1[0], p0[1], p1[1], p0[2], p1[2])
        z = zt
    if z_hi > z + 1e-6:
        quad(wall, a0, a1, z, z_hi, 0.0, N)


def city_rows(a0, a1, z0, h, shops=True, z_lo=None):
    """Rows of openings for a block face: shops on the ground floor, then windows on every floor, a
    few left shuttered (no opening)."""
    rows = []
    length = a1 - a0
    if shops:
        n = max(1, int((length - 1.2) // 4.2))
        pitch = length / n
        rows.append((z0, z0 + 3.3, [(a0 + (k + 0.5) * pitch - 1.25, a0 + (k + 0.5) * pitch + 1.25)
                                    for k in range(n)], "shop"))
    n = max(1, int((length - 0.8) // 2.5))
    pitch = length / n
    z = z0 + 4.2 + 0.9
    while z + 1.4 < z0 + h - 0.6:
        opens = [(a0 + (k + 0.5) * pitch - 0.45, a0 + (k + 0.5) * pitch + 0.45) for k in range(n)
                 if CITY_RNG.random() >= 0.12]
        if opens and (z_lo is None or z >= z_lo + 0.2):
            rows.append((z, z + 1.35, opens, "window"))
        z += 3.1
    return rows


SIDES = {"-x": ("x", -1.0), "+x": ("x", 1.0), "-y": ("y", -1.0), "+y": ("y", 1.0)}


def block(parts, x0, x1, y0, y1, h, detail=None, colour=None, z0=PLAZA_Z, omit=(), roof=True):
    """A city block (insula): four stucco walls under a tiled hip roof. detail: {side: options} for
    the faces seen from the forecourt and the lanes, with openings (city_rows); options: shops (bool,
    default True) and from_z (the face starts that high above z0: below it another wall stands
    against it). omit: faces left out (another wall is there)."""
    colour = colour or CITY_RNG.choice(CITY_COLOURS)
    wall = parts[colour]
    for side, (axis, out) in SIDES.items():
        if side in omit:
            continue
        plane = (x1 if out > 0 else x0) if axis == "x" else (y1 if out > 0 else y0)
        a0, a1 = (y0, y1) if axis == "x" else (x0, x1)
        opts = (detail or {}).get(side)
        from_z = (opts or {}).get("from_z", 0.0)
        z_lo = z0 + from_z
        rows = []
        if opts is not None:
            rows = city_rows(a0, a1, z0, h, opts.get("shops", True) and from_z == 0.0, z_lo)
        facade(parts, wall, axis, plane, out, a0, a1, z_lo, z0 + h, rows)
        if opts is not None:
            # string courses at the floors, between the rows of openings
            z = z0 + 4.2
            while z < z0 + h - 1.5:
                if z - 0.18 >= z_lo:
                    p0, p1 = (plane - out * 0.05, plane + out * 0.1)
                    if axis == "x":
                        cbox(parts["Trim"], p0, p1, a0, a1, z - 0.18, z)
                    else:
                        cbox(parts["Trim"], a0, a1, p0, p1, z - 0.18, z)
                z += 3.1
    if roof:
        hip_roof(parts["Roofs"], x0, x1, y0, y1, z0 + h, min(x1 - x0, y1 - y0) * 0.2, 0.5,
                 tiles=parts["RoofTiles"] if math.hypot(0.5 * (x0 + x1), 0.5 * (y0 + y1) - 60.0) < 160.0 else None)


def temple(parts, cx, cy, w, d, h, facing_y=1.0, z0=PLAZA_Z):
    """A temple on the skyline: podium, cella, six columns across the front, gable roof."""
    cbox(parts["Trim"], cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2, z0, z0 + 3.0)
    porch = 6.0
    c0, c1 = (cy - d / 2 + 1.0, cy + d / 2 - porch) if facing_y > 0 else (cy - d / 2 + porch, cy + d / 2 - 1.0)
    cbox(parts["Cream"], cx - w / 2 + 1.0, cx + w / 2 - 1.0, c0, c1, z0 + 3.0, z0 + 3.0 + h)
    front = cy + facing_y * (d / 2 - 1.5)
    for k in range(6):
        cyl_into(parts["Trim"], cx - w / 2 + 1.5 + (w - 3.0) * k / 5, front, z0 + 3.01, h - 0.02, 1.0, 0.86, 12)
    gable_prism(parts["Roofs"], cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2, z0 + 3.0 + h,
                0.5 * w * math.tan(math.radians(20.0)), along="y")


TEMPLES = ((-150.0, 110.0, 22.0, 36.0, 12.0, 1.0), (170.0, -60.0, 18.0, 30.0, 10.0, 1.0),
           (60.0, 262.0, 26.0, 40.0, 14.0, -1.0))


def build_surroundings(half_w, yb, front, y_low):
    """The podium and its steps, the forecourt with its colonnades and gateway, the Basilica of
    Neptune against the rotunda's back, and the city round them to the horizon."""
    PZ = PLAZA_Z
    C = COLONNADE
    r_drum = P["R"] + P["wall_t"]
    steps_end = front + 1.6 + 6 * 0.4
    along_y = FLAT

    # podium under the portico: one prism, its section with a crown and a plinth moulding; behind the
    # portico's rear wall the block's own sides come down to the forecourt and only the mouldings run
    # on along them (2 mm into the podium, so that no vertex of theirs meets one of its)
    pod = Builder("Forecourt_Podium")
    hw = half_w
    section = [(-hw - 0.15, PZ), (hw + 0.15, PZ), (hw + 0.15, PZ + 0.3), (hw, PZ + 0.3), (hw, -0.24),
               (hw + 0.12, -0.24), (hw + 0.12, -0.005), (-hw - 0.12, -0.005), (-hw - 0.12, -0.24),
               (-hw, -0.24), (-hw, PZ + 0.3), (-hw - 0.15, PZ + 0.3)]
    prism_v(pod, along_y, section, yb, front + 1.6)
    for sgn in (-1.0, 1.0):
        for zz0, zz1, wdt in ((-0.24, -0.005, 0.12), (PZ, PZ + 0.3, 0.15)):
            cbox(pod, sgn * hw, sgn * (hw + wdt), y_low, yb + 0.002, zz0, zz1)
    pod.finish()
    # seven risers across the portico's whole width down to the forecourt: one stepped prism
    st = Builder("Forecourt_Steps")
    stair = [(front + 1.6, PZ), (steps_end, PZ)]
    for k in range(5, -1, -1):
        y1 = front + 1.6 + 0.4 * (k + 1)
        stair += [(y1, -0.2 * (k + 1)), (y1 - 0.4, -0.2 * (k + 1))]
    prism(st, FLAT, stair, -hw, hw)               # the (y, z) outline extruded along x
    st.finish()

    # colonnades down both long sides
    stylo, shafts, bases = Builder("Forecourt_Stylobate"), Builder("Forecourt_Columns"), Builder("Forecourt_ColBases")
    ent, ceil = Builder("Forecourt_ColEntab"), Builder("Forecourt_Ceiling")
    walls, ends = Builder("Forecourt_Walls"), Builder("Forecourt_WallEnds")
    parts = {c: Builder("Forecourt_City_" + c) for c in CITY_COLOURS}
    parts.update({"Roofs": Builder("Forecourt_Roofs"), "RoofTiles": Builder("Forecourt_RoofTiles"),
                  "Void": Builder("Forecourt_Void"),
                  "Trim": Builder("Forecourt_Trim"), "Blockers": Builder("Forecourt_Blockers")})
    roofs = parts["Roofs"]
    d, h = C["d"], C["h"]
    base_h, cap_h = 0.047 * h, 0.117 * h
    z0 = PZ + 0.6
    zt0 = z0 + h
    wa, wb = C["back"], C["back"] + C["wall"]
    a_e, z_e = C["axis"] - 1.3, zt0 + 1.45                 # eave over the cornice
    a_r = wb + 0.3
    slope = math.tan(math.radians(17.0))
    z_r = z_e + (a_r - a_e) * slope
    ztop = z_e + (wb - a_e) * slope + 0.3                  # the back wall stands just above the roof
    for sgn in (-1.0, 1.0):
        X = lambda a: sgn * a
        # stylobate: a step and the platform, one prism
        prof = [(X(C["front"]), PZ), (X(wa + 0.1), PZ), (X(wa + 0.1), z0), (X(C["front"] + 0.4), z0),
                (X(C["front"] + 0.4), PZ + 0.3), (X(C["front"]), PZ + 0.3)]
        prism_v(stylo, along_y, prof, C["y0"], C["y1"])
        y, k = C["y0"] + 2.0, 0
        while y <= C["y1"] - 2.0 + 1e-6:
            x = X(C["axis"])
            cbox(bases, x - 0.7 * d, x + 0.7 * d, y - 0.7 * d, y + 0.7 * d, z0, z0 + 0.3 * base_h)
            lathe_into(bases, x, y, [(pr, z0 + 0.001 + pz) for pr, pz in attic_base_profile(d, base_h)], 32)
            cyl_into(shafts, x, y, z0 + base_h, h - base_h - cap_h, d, 0.86 * d, 32)
            # the scanned capital's good face looks out over the forecourt
            CAPITAL_SLOTS.append({"column": "Forecourt_%s_%02d" % ("E" if sgn > 0 else "W", k),
                                  "position": [x, y, zt0 - cap_h], "height": cap_h, "diameter": 0.86 * d,
                                  "yaw": 180.0 if sgn > 0 else 0.0})
            y, k = y + C["spacing"], k + 1
        # architrave, frieze and cornice over the columns, a flat ceiling behind
        o = lambda kk: X(C["axis"] - 0.45 - kk)
        prof = [(o(-0.9), zt0), (o(0.0), zt0), (o(0.0), zt0 + 0.85), (o(0.12), zt0 + 0.95), (o(0.12), zt0 + 1.1),
                (o(0.5), zt0 + 1.25), (o(0.55), zt0 + 1.45), (o(-0.9), zt0 + 1.45)]
        prism_v(ent, along_y, prof, C["y0"], C["y1"])
        cbox(ceil, X(C["axis"] + 0.46), X(wa - 0.001), C["y0"] + 0.6, C["y1"] - 0.6, zt0 + 0.85, zt0 + 1.05)
        # lean-to roof of tiles, cover tiles running down the slope
        top = [(X(a_e), C["y0"] - 0.3, z_e), (X(a_r), C["y0"] - 0.3, z_r), (X(a_r), C["y1"] + 0.3, z_r),
               (X(a_e), C["y1"] + 0.3, z_e)]
        slab_between(roofs, top, 0.22)
        yy = C["y0"] - 0.1
        while yy < C["y1"] + 0.2:
            ridge = []
            for a, z in ((a_e, z_e), (a_r, z_r)):
                ridge += [(X(a), yy - 0.08, z - 0.01), (X(a), yy + 0.08, z - 0.01), (X(a), yy, z + 0.09)]
            add_convex(roofs, ridge, [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)])
            yy += 0.45
        # the back wall, its face to the forecourt with a shop (taberna) behind every other bay: the
        # doors look through the wall's thickness into dark rooms
        doors = [C["y0"] + 2.0 + C["spacing"] * (2 * j + 0.5) for j in range(13)]
        facade(parts, walls, "x", X(wa), -sgn, C["y0"] + 0.6, C["y1"] - 0.6, PZ, ztop,
               [(z0, z0 + 3.6, [(c - 1.2, c + 1.2) for c in doors], "shop")], reveal=C["wall"], depth=2.6,
               trims=False)
        walls.quad_out((X(wa), C["y0"] + 0.6, ztop), (X(wb), C["y0"] + 0.6, ztop), (X(wb), C["y1"] - 0.6, ztop),
                       (X(wa), C["y1"] - 0.6, ztop), (0.0, 0.0, 1.0))
        # end walls under the roof's slope
        end = [(C["front"], PZ), (wb, PZ), (wb, ztop), (C["front"], z_e + 0.25)]
        for e0 in (C["y0"], C["y1"] - 0.6):
            prism(ends, lambda u, v, z: (X(v), u, z), end, e0, e0 + 0.6)

    # gateway at the far end: one arch, half-columns, an entablature and an attic
    gate = Builder("Forecourt_Gate")
    g0, g1 = C["y1"], C["y1"] + 3.0
    W, aw, spring, gtop = wb, 3.6, PZ + 7.2, PZ + 15.0
    cbox(gate, -W, -aw, g0, g1, PZ, gtop)
    cbox(gate, aw, W, g0, g1, PZ, gtop)
    arc = [(aw * math.cos(math.pi * k / 16), spring + aw * math.sin(math.pi * k / 16)) for k in range(17)]
    prism(gate, lambda u, v, z: (v, u, z), arc + [(-aw - 0.002, gtop - 0.002), (aw + 0.002, gtop - 0.002)],
          g0 + 0.002, g1 - 0.002)
    cbox(gate, -W, W, g0 - 0.6, g0, PZ + 9.0, PZ + 10.55)                       # entablature
    cbox(gate, -W - 0.2, W + 0.2, g0 - 0.95, g0 - 0.6, PZ + 10.2, PZ + 10.55)   # its cornice
    cbox(gate, -14.0, 14.0, g0 - 0.3, g0 - 0.001, PZ + 10.56, PZ + 14.2)        # attic
    cbox(gate, -14.3, 14.3, g0 - 0.5, g0 - 0.002, PZ + 14.21, PZ + 14.6)
    cbox(gate, -5.5, 5.5, g0 - 0.42, g0 - 0.3, PZ + 11.2, PZ + 13.6)            # inscription panel
    for nx_ in (-16.5, -12.5, 12.5, 16.5):                                      # blind niches
        cbox(parts["Void"], nx_ - 1.0, nx_ + 1.0, g0 - 0.015, g0 + 0.05, PZ + 1.2, PZ + 5.6)
        cbox(gate, nx_ - 1.25, nx_ + 1.25, g0 - 0.12, g0 - 0.001, PZ + 5.6, PZ + 5.85)
    gd, gh = 1.0, 9.0
    for gx in (-9.5, -5.0, 5.0, 9.5):
        bh, ch = 0.047 * gh, 0.117 * gh
        cbox(bases, gx - 0.7 * gd, gx + 0.7 * gd, g0 - 0.7 * gd, g0 - 0.001, PZ, PZ + 0.3 * bh)
        lathe_into(bases, gx, g0, [(pr, PZ + 0.001 + pz) for pr, pz in attic_base_profile(gd, bh)], 32)
        cyl_into(shafts, gx, g0, PZ + bh, gh - bh - ch, gd, 0.86 * gd, 32)
        CAPITAL_SLOTS.append({"column": "Forecourt_G_%+.0f" % gx, "position": [gx, g0, PZ + gh - ch],
                              "height": ch, "diameter": 0.86 * gd, "yaw": 270.0})
    for b in (stylo, shafts, bases, ent, ceil, walls, ends, gate):
        b.finish()

    # paving: the forecourt, the flanks of the portico and the lanes beside the rotunda; worn slabs,
    # lifted and tilted more than the portico's (user, 2026-11-25: "too ideal")
    # Every slab is laid, including those that run on under a wall, a step or the drum (there hidden in
    # the solid): leaving out whole slabs whose centres fell inside left empty rectangles along those
    # edges (user, 2026-11-25). Only the rotunda's own floor area is left out.
    def keep(x, y):
        return math.hypot(x, y) > P["R"] + 1.0
    paving("Forecourt_Paving", -40.0, 40.0, -28.4, 175.0, row=1.5, length=2.2, z0=PZ, keep=keep, cell=4.0,
           tilt=0.004, lift=0.006)

    # the city: blocks closing the forecourt and the lanes, then rows of blocks to the horizon.
    # Basilica of Neptune against the rotunda's back: a tall hall under a gable roof, its long side to
    # the rotunda, with pilasters and big windows high up
    bas_y0, bas_y1 = BASILICA["y0"], BASILICA["y1"]
    block(parts, -32.0, 32.0, bas_y0, bas_y1, BASILICA["h"], colour="Brick", omit=("+y",), roof=False)
    facade(parts, parts["Brick"], "y", bas_y1, 1.0, -32.0, 32.0, PZ, PZ + 22.0,
           [(PZ + 12.0, PZ + 19.0, [(-28.0 + 8.0 * k - 1.6, -28.0 + 8.0 * k + 1.6) for k in range(8)], "window")],
           depth=2.0, trims=False)
    for k in range(7):
        cx = -24.0 + 8.0 * k
        cbox(parts["Trim"], cx - 0.35, cx + 0.35, bas_y1 - 0.05, bas_y1 + 0.25, PZ, PZ + 21.0)
    cbox(parts["Trim"], -32.0, 32.0, bas_y1 - 0.05, bas_y1 + 0.5, PZ + 21.0, PZ + 22.0)
    ov = BASILICA["overhang"]
    gable_prism(roofs, -32.6, 32.6, bas_y0 - ov, bas_y1 + ov, PZ + BASILICA["h"], BASILICA["ridge"], along="x")
    for sgn in (-1.0, 1.0):
        block(parts, sgn * 32.0, sgn * 40.0, bas_y0, bas_y1, 16.0, detail={"+y": {}}, colour="Ochre")
    # beside the lanes (x = +-40, facing in) and behind the colonnades up to the gateway
    for sgn in (-1.0, 1.0):
        side = "-x" if sgn > 0 else "+x"
        for y0, y1, hh in ((-52.0, -12.0, 17.0), (-12.0, 22.0, 20.0), (22.0, 56.6, 15.5)):
            block(parts, *sorted((sgn * 40.0, sgn * 62.0)), y0, y1, hh, detail={side: {}})
        # over the colonnade roofs their upper floors look into the forecourt (below, the colonnade's
        # back wall stands against them); the first block's south face closes the lane
        a0, a1 = sorted((sgn * wb, sgn * 62.0))
        block(parts, a0, a1, 56.6, 103.0, 18.0, detail={"-y": {}, side: {"from_z": ztop - PZ}})
        block(parts, a0, a1, 103.0, 153.0, 21.0, detail={side: {"from_z": ztop - PZ}})
        # the street running on behind the gateway
        block(parts, *sorted((sgn * 7.0, sgn * wb)), 153.0, 190.0, 17.0, detail={side: {}})
    block(parts, -7.0, 7.0, 175.0, 195.0, 18.0, detail={"-y": {}})
    for cx, cy, w, dd, hh, fy in TEMPLES:
        temple(parts, cx, cy, w, dd, hh, fy)
    # rows of blocks out to about 430 m, streets between; facades only within about 130 m
    pitch = 36.0
    for i in range(-12, 13):
        for j in range(-12, 13):
            cx, cy = i * pitch, j * pitch + 60.0
            if -70.0 < cx < 70.0 and -60.0 < cy < 205.0:
                continue
            if any(abs(tx - cx) < 30.0 and abs(ty - cy) < 32.0 for tx, ty, *_ in TEMPLES):
                continue
            if CITY_RNG.random() < 0.12:
                continue                          # an open space, a garden
            w, dd = CITY_RNG.uniform(20.0, 29.0), CITY_RNG.uniform(20.0, 29.0)
            hh = CITY_RNG.uniform(11.0, 23.0)
            detail = {}
            if math.hypot(cx, cy - 60.0) < 130.0:
                detail = {s: {"shops": False} for s, ok in (("-x", cx > 0), ("+x", cx < 0), ("-y", cy > 60.0),
                                                            ("+y", cy < 60.0)) if ok}
            block(parts, cx - w / 2, cx + w / 2, cy - dd / 2, cy + dd / 2, hh, detail=detail)
    for b in parts.values():
        if b.faces:
            b.finish()


PORTICO_NICHES = []


APSE_AEDICULAE = (247.5, 292.5)   # the aediculae either side of the apse


def build_panelling():
    """Pier walls beside the aediculae: dark marble panels with giallo antico insets and porphyry
    roundels (Desgodetz; reference/dimensions.md, aediculae)."""
    R = P["R"]
    dark, gia, por = Builder("Panel_Dark"), Builder("Panel_Giallo"), Builder("Panel_Porphyry")
    for az in AEDICULAE:
        for sgn in (-1.0, 1.0):
            # each panel is flat, so it is set tangent to the wall at its own centre
            to_world = frame(az + math.degrees(sgn * 3.2 / R))
            lo, hi = -0.65, 0.65
            box(dark, to_world, R - 0.03, R + 0.01, lo, hi, 0.45, 9.9)
            box(gia, to_world, R - 0.04, R - 0.02, lo + 0.18, hi - 0.18, 0.75, 4.15)
            # framed panel picture (tabula), 1.24 x 1.60 m; seen from the room +v is on the left
            tab = Builder("Painted_Tab_%04d_%s" % (int(az * 10), "L" if sgn > 0 else "R"))
            # Beside the apse the pier towards the apse stands behind the apse-mouth column, so its
            # picture could not be seen (user, 2026-11-23). It moves to the open pier on the other
            # side of the aedicula, into the giallo field under that pier's own picture.
            hidden = az in APSE_AEDICULAE and (az + sgn * 10.0 - 270.0) ** 2 < (az - 270.0) ** 2
            place = frame(az - math.degrees(sgn * 3.2 / R)) if hidden else to_world
            z0 = 2.2 if hidden else 4.4
            tab.quad(place(R - 0.06, 0.62, z0), place(R - 0.06, -0.62, z0),
                     place(R - 0.06, -0.62, z0 + 1.6), place(R - 0.06, 0.62, z0 + 1.6))
            tab.finish()
            box(gia, to_world, R - 0.04, R - 0.02, lo + 0.18, hi - 0.18, 8.2, 9.6)
            circle = [(0.42 * math.cos(2 * math.pi * k / 32), 6.9 + 0.42 * math.sin(2 * math.pi * k / 32))
                      for k in range(32)]
            prism(por, to_world, circle, R - 0.05, R - 0.02)
    for b in (dark, gia, por):
        b.finish()
    # black Third Style ground behind each aedicula statue
    for az in AEDICULAE:
        to_world = frame(az)
        nb = Builder("Painted_NicheBack_%04d" % int(az * 10))
        nb.quad(to_world(R - 0.04, 1.15, 0.0), to_world(R - 0.04, -1.15, 0.0),
                to_world(R - 0.04, -1.15, P["aed_apex"] - P["aed_ped_rise"] - P["aed_entab_h"]),
                to_world(R - 0.04, 1.15, P["aed_apex"] - P["aed_ped_rise"] - P["aed_entab_h"]))
        nb.finish()
    # painted wall field with the god's picture on each exedra back wall, above the statue
    for az, kind in RECESSES.items():
        if kind not in ("semi", "rect"):
            continue
        to_world = frame(az)
        fb = Builder("Painted_Field_%03d" % int(az))
        z0, z1 = 5.0, 8.0
        if kind == "rect":
            u = R + P["exedra_depth_rect"] - 0.02
            fb.quad(to_world(u, 2.0, z0), to_world(u, -2.0, z0), to_world(u, -2.0, z1), to_world(u, 2.0, z1))
        else:
            hw = P["exedra_hw"] - 0.02
            uc = apse_centre_u()
            n = 16
            span = 4.0 / hw
            for k in range(n):
                a0 = span * (0.5 - k / n)
                a1 = span * (0.5 - (k + 1) / n)
                p = lambda a, z: to_world(uc + hw * math.cos(a), hw * math.sin(a), z)
                fb.quad(p(a0, z0), p(a1, z0), p(a1, z1), p(a0, z1),
                        uv=((k / n, 0.0), ((k + 1) / n, 0.0), ((k + 1) / n, 1.0), (k / n, 1.0)))
        fb.finish()


# --------------------------------------------------------------------------
# Coffer rosettes
# --------------------------------------------------------------------------

def build_rosettes():
    """A gilded bronze rosette at the centre of each of the 140 coffers (5 rings x 28).

    Francesco Piranesi records stucco rosettes on bronze pins; the gilded bronze finish is the
    conventional restoration (reference/dimensions.md, coffers)."""
    R = P["R"]
    zc = P["spring_z"]
    bounds = [math.radians(d) for d in P["coffer_el_deg"]]
    cell = 2.0 * math.pi / P["coffer_count"]
    b = Builder("Gilded_Rosettes")
    for ring in range(len(bounds) - 1):
        e0, e1 = bounds[ring], bounds[ring + 1]
        steps = P["coffer_steps"][ring]
        g_el = 0.5 * P["coffer_rib_el"] / R
        s_lo = P["coffer_inset_low"] * P["coffer_step_inset"][ring] / R
        s_hi = P["coffer_inset_high"] * P["coffer_step_inset"][ring] / R
        lo = e0 + g_el + (steps - 1) * s_lo
        hi = e1 - g_el - (steps - 1) * s_hi
        el = 0.5 * (lo + hi)
        inner_h = R * (hi - lo)
        rr = max(0.12, 0.3 * inner_h)
        depth = steps * P["coffer_step_depth"][ring]
        for c in range(P["coffer_count"]):
            az = (c + 0.5) * cell
            n = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
            centre = Vector((0.0, 0.0, zc)) + n * (R + depth - 0.02)
            if (ring, c) == INVADER_COFFER:
                # no rosette here: a tile mosaic takes its place (build_invaders)
                INVADER_DOME.update(centre=centre, normal=n, radius=rr)
                continue
            t1 = Vector((-math.sin(az), math.cos(az), 0.0))
            t2 = n.cross(t1).normalized()
            verts = [tuple(centre - n * 0.07)]
            for k in range(16):
                a = 2.0 * math.pi * k / 16
                rad = rr if k % 2 == 0 else 0.55 * rr
                lift = 0.025 if k % 2 == 0 else 0.0
                verts.append(tuple(centre + (t1 * math.cos(a) + t2 * math.sin(a)) * rad - n * lift))
            b.add(verts, [(0, 1 + k, 1 + (k + 1) % 16) for k in range(16)])
    b.finish()


# --------------------------------------------------------------------------
# Easter egg: three small tile mosaics of pixel creatures (user, 2026-11-24)
# --------------------------------------------------------------------------
# In the manner of the street mosaics of pixel-art aliens set on city walls: square glazed tiles, one
# per pixel, in a bed of grout. The three creatures are drawn for this project. One takes the place
# of a coffer rosette, one is on a side of the old altar by the door (its left as it stands facing the
# rotunda: the side turned away from the way in, user 2026-11-24), one on the back wall of the
# north-east exedra, behind the statue.

# ring from the springing, coffer: the rosette that gives way. On the dome's right as one faces the apse
# from the door (user, 2026-11-24; it was first coffer 22, beside the apse)
INVADER_COFFER = (1, 13)
INVADER_DOME = {}              # filled by build_rosettes: centre, normal, radius of that rosette
INVADER_ALTAR_AZ = 78.75       # the scanned plinth by the door (ue/scripts/build_scene.py, PROPS)
INVADER_ALTAR_R = 19.4               # where it stands, and how far its left face is from its middle
INVADER_ALTAR_SIDE = 0.346           # (26.6 cm in the scan, at the prop's scale 1.3)
INVADER_EXEDRA_AZ = 45.0
TILE_COLOURS = {"W": "#F2EFE6", "K": "#141416", "R": "#C8281E", "Y": "#F2C230", "G": "#2E8B3A",
                "P": "#6A2C91", "B": "#2456B4", "grout": "#8F8C84"}
INVADERS = {
    # one eye, feelers and feet tipped with gold: among the gilded stars of the dome
    "Dome": ["Y.........Y", ".W.......W.", "..WWWWWWW..", ".WWWRRRWWW.", "WWWWRKRWWWW", "WWWWRRRWWWW",
             "WWWWWWWWWWW", ".WW.WWW.WW.", ".W..W.W..W.", "Y..Y...Y..Y"],
    # crowned with laurel
    "Altar": [".GG......GG.", "G..RRRRRR..G", "G.RRRRRRRR.G", ".RRWWRRWWRR.", ".RRWKRRKWRR.", "RRRRRRRRRRRR",
              "RRR.RRRR.RRR", ".RR..RR..RR.", "RR...RR...RR"],
    # under a centurion's crest
    # (yellow: in the firelight of the exedra a blue or green tile goes dull)
    # Jupiter's: the purple of a triumphator, crowned in gold
    "Jupiter": ["..Y.Y.Y.Y..", "..YYYYYYY..", ".PPPPPPPPP.", "PPWKPPPWKPP", "PPKKPPPKKPP", "PPPPPPPPPPP",
                ".P.PPPPP.P.", "P.P.....P.P", ".P.......P."],
    "Exedra": ["R.R.R.R.R.R", ".RRRRRRRRR.", "...YYYYY...", ".YYYYYYYYY.", "YYKKYYYKKYY", "YYWKYYYWKYY",
               "YYYYYYYYYYY", ".Y.YYYYY.Y.", "Y..Y...Y..Y", ".Y...Y...Y."],
    # Outside (user, 2026-11-26: "one should be on the wall on the far side of the building. one should
    # be hidden in the collonades in the plaza. one should be only accessible in the flight mode, a
    # bigger one on one of the building roofs in the area").
    # On the back of the drum, in the narrow gap by the Basilica of Neptune: in Neptune's blue
    "Drum": ["..B.....B..", "...B...B...", "..BBBBBBB..", ".BBKBBBKBB.", "BBBBBBBBBBB", "B.BBBBBBB.B",
             "B.B.....B.B", "...BB.BB..."],
    # in a shop doorway of the west colonnade, on the far jamb: seen only from inside the colonnade
    "Colonnade": ["...GG...", "..GGGG..", ".GGGGGG.", "GGKGGKGG", "GGGGGGGG", "..G..G..", ".G.GG.G.",
                  "G.G..G.G"],
    # on the basilica's roof, on the slope that faces the rotunda: below the roof's plane from every
    # street and hidden from the forecourt by the rotunda, so it is seen only from the air. Crowned
    "Basilica": ["..Y.YYYY.Y..", "....WWWW....", ".WWWWWWWWWW.", "WWWWWWWWWWWW", "WWWKKWWKKWWW",
                 "WWWWWWWWWWWW", "...WW..WW...", "..WW.WW.WW..", "WW........WW"],
}
INVADER_DRUM_AZ = 298.0          # behind the rotunda, 3.7 m from the basilica's wall
INVADER_COLONNADE_DOOR = 8       # the west colonnade's ninth shop doorway from the portico


def mosaic(name, rows, centre, right, up, pitch, seed):
    """A tile mosaic as a mesh: one glazed tile (a low, slightly pillowed block) per letter of rows,
    on a bed of grout, about centre in the plane of right and up (as the viewer sees it). pitch is
    the spacing of the tiles in metres. The colours go into the vertex colours as sRGB values, which
    the material /Game/Materials/M_InvaderTile turns into linear ones."""
    centre, right, up = Vector(centre), Vector(right).normalized(), Vector(up).normalized()
    out = right.cross(up)
    rng = random.Random(seed)
    thick = 0.22 * pitch
    verts, faces, colours = [], [], []

    def block(cx, cy, half, z0, z1, inset, colour):
        base = len(verts)
        for z, h in ((z0, half), (z1, half - inset)):
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                verts.append(tuple(centre + right * (cx + sx * h) + up * (cy + sy * h) + out * z))
        faces.append((base + 4, base + 5, base + 6, base + 7))
        for k in range(4):
            faces.append((base + k, base + (k + 1) % 4, base + 4 + (k + 1) % 4, base + 4 + k))
        colours.extend([colour] * 5)

    def rgb(key, vary=0.0):
        h = TILE_COLOURS[key]
        f = 1.0 + rng.uniform(-vary, vary)
        return tuple(min(1.0, f * int(h[i:i + 2], 16) / 255.0) for i in (1, 3, 5))

    w, h = len(rows[0]), len(rows)
    for r, row in enumerate(rows):
        for c, key in enumerate(row):
            if key == ".":
                continue
            cx, cy = (c - 0.5 * (w - 1)) * pitch, (0.5 * (h - 1) - r) * pitch
            block(cx, cy, 0.5 * pitch, 0.0, 0.45 * thick, 0.0, rgb("grout"))
            # set by hand: no two tiles quite in line or quite the same shade
            block(cx + rng.uniform(-0.025, 0.025) * pitch, cy + rng.uniform(-0.025, 0.025) * pitch,
                  0.455 * pitch, 0.3 * thick, thick * rng.uniform(0.92, 1.08), 0.07 * pitch, rgb(key, 0.06))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    attr = mesh.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="CORNER")
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            attr.data[li].color = (*colours[poly.index], 1.0)
    mesh.color_attributes.active_color = attr
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def build_invaders():
    up = Vector((0.0, 0.0, 1.0))
    # in the coffer: as wide as the rosette it replaces, seen from the floor (up is towards the oculus)
    d = INVADER_DOME
    az = math.atan2(d["normal"].y, d["normal"].x)
    t1 = Vector((-math.sin(az), math.cos(az), 0.0))
    rows = INVADERS["Dome"]
    mosaic("Invader_Dome", rows, d["centre"] + d["normal"] * 0.008, -t1, d["normal"].cross(t1),
           2.2 * d["radius"] / len(rows[0]), 1)
    # on the altar by the door: the face that looks along the wall, away from the doorway's axis.
    # Not seen on coming in; seen from inside, from the side of the first aedicula
    a = math.radians(INVADER_ALTAR_AZ)
    radial, tangent = Vector((math.cos(a), math.sin(a), 0.0)), Vector((-math.sin(a), math.cos(a), 0.0))
    mosaic("Invader_Altar", INVADERS["Altar"],
           radial * INVADER_ALTAR_R - tangent * (INVADER_ALTAR_SIDE + 0.002) + up * 0.6, radial, up, 0.03, 2)
    # on the exedra's back wall, behind the statue: hidden from the middle of the rotunda by the
    # figure, seen from either side through the columns
    a = math.radians(INVADER_EXEDRA_AZ)
    radial, tangent = Vector((math.cos(a), math.sin(a), 0.0)), Vector((-math.sin(a), math.cos(a), 0.0))
    # on the right-hand side of Jupiter's pedestal, seen from the rotunda (user, 2026-11-24): over the
    # painted panel, towards the front, so it shows from the apse's side
    to_world = frame(APSE_AZ)
    u = apse_centre_u() + 0.9
    side = -(0.5 * 3.0 + 0.012)          # the die's side face (base_w 3.0 in build_statue_base), past its panel
    cx, cy, _ = to_world(u - 0.35, side, 0.0)
    ox, oy, _ = to_world(u - 0.35, side - 1.0, 0.0)
    outward = Vector((ox - cx, oy - cy, 0.0)).normalized()
    mosaic("Invader_Jupiter", INVADERS["Jupiter"], Vector((cx, cy, 1.0)), outward.cross(up) * -1.0, up, 0.035, 4)
    mosaic("Invader_Exedra", INVADERS["Exedra"],
           radial * (P["R"] + P["exedra_depth_rect"] - 0.003) + tangent * 0.3 + up * 1.75, -tangent, up, 0.035, 3)

    # outside. On the drum, 2 m above the forecourt, facing out (its edges stand 2 mm further off the
    # curved wall than its middle)
    a = math.radians(INVADER_DRUM_AZ)
    radial, tangent = Vector((math.cos(a), math.sin(a), 0.0)), Vector((-math.sin(a), math.cos(a), 0.0))
    mosaic("Invader_Drum", INVADERS["Drum"], radial * (P["R"] + P["wall_t"] + 0.004) + up * (PLAZA_Z + 2.0),
           tangent, up, 0.06, 5)
    # on the far jamb of a shop doorway in the west colonnade's back wall (build_surroundings: the jamb
    # runs through the wall's thickness, x from -back to -(back + wall), and faces back to the portico)
    C = COLONNADE
    door = C["y0"] + 2.0 + C["spacing"] * (2 * INVADER_COLONNADE_DOOR + 0.5)
    mosaic("Invader_Colonnade", INVADERS["Colonnade"],
           Vector((-(C["back"] + 0.5 * C["wall"]), door + 1.2 - 0.004, PLAZA_Z + 0.6 + 1.7)),
           Vector((1.0, 0.0, 0.0)), up, 0.05, 6)
    # on the north slope of the basilica's gable roof, half way up, big enough to read from the air
    B = BASILICA
    run, rise = 0.5 * (B["y1"] - B["y0"]) + B["overhang"], B["ridge"]
    slope_up = Vector((0.0, -run, rise)).normalized()
    normal = Vector((0.0, rise, run)).normalized()
    mid = Vector((0.0, B["y1"] + B["overhang"] - 0.5 * run, PLAZA_Z + B["h"] + 0.5 * rise))
    mosaic("Invader_Basilica", INVADERS["Basilica"], mid + normal * 0.01, Vector((-1.0, 0.0, 0.0)), slope_up, 0.3, 7)


# --------------------------------------------------------------------------
# Fire light: candelabra with fire bowls, tripod braziers, the altar before Jupiter
# --------------------------------------------------------------------------

LIGHT_SLOTS = []


def flame_cards(builder, x, y, z, w, h, n=3):
    """Crossed vertical cards for an animated flame material (UV v runs from base to tip)."""
    for k in range(n):
        a = math.pi * k / n
        dx, dy = 0.5 * w * math.cos(a), 0.5 * w * math.sin(a)
        builder.quad((x - dx, y - dy, z), (x + dx, y + dy, z), (x + dx, y + dy, z + h), (x - dx, y - dy, z + h))


def candelabrum(bronze, flames, x, y, H, bowl_r=0.13, flame_h=0.32, name=""):
    """Bronze stand on three lion-paw legs, fluted shaft with knops, fire bowl on top."""
    for k in range(3):
        a = 2.0 * math.pi * k / 3 + 0.3
        top = (x + 0.05 * math.cos(a), y + 0.05 * math.sin(a), 0.2 * H)
        foot = (x + 0.26 * math.cos(a), y + 0.26 * math.sin(a), 0.05)
        strut(bronze, top, foot, 0.035)
        lathe_into(bronze, foot[0], foot[1], [(0.0, 0.0), (0.045, 0.0), (0.05, 0.04), (0.03, 0.07), (0.0, 0.07)], 10)
    shaft = [(0.0, 0.18 * H), (0.08, 0.18 * H), (0.09, 0.22 * H), (0.05, 0.25 * H), (0.026, 0.27 * H),
             (0.024, 0.42 * H), (0.045, 0.43 * H), (0.024, 0.45 * H), (0.022, 0.62 * H), (0.042, 0.63 * H),
             (0.022, 0.65 * H), (0.02, 0.86 * H), (0.04, 0.88 * H), (0.03, 0.9 * H),
             (bowl_r * 0.4, 0.93 * H), (bowl_r, 0.98 * H), (bowl_r + 0.015, H), (bowl_r * 0.85, H),
             (0.0, 0.985 * H)]
    lathe_into(bronze, x, y, shaft, 24)
    flame_cards(flames, x, y, 0.985 * H, 1.5 * bowl_r, flame_h)
    LIGHT_SLOTS.append({"name": name, "kind": "stand", "position": [x, y, H + 0.25 * flame_h],
                        "flame_height": flame_h})


def tripod_brazier(bronze, flames, x, y, H=1.0, bowl_r=0.34, name=""):
    """Bronze tripod with a shallow fire bowl."""
    for k in range(3):
        a = 2.0 * math.pi * k / 3
        strut(bronze, (x + 0.85 * bowl_r * math.cos(a), y + 0.85 * bowl_r * math.sin(a), H - 0.05),
              (x + 1.15 * bowl_r * math.cos(a), y + 1.15 * bowl_r * math.sin(a), 0.06), 0.04)
        lathe_into(bronze, x + 1.15 * bowl_r * math.cos(a), y + 1.15 * bowl_r * math.sin(a),
                   [(0.0, 0.0), (0.05, 0.0), (0.06, 0.05), (0.035, 0.09), (0.0, 0.09)], 10)
    lathe_into(bronze, x, y, [(0.0, 0.42 * H), (0.03, 0.42 * H), (0.03, 0.44 * H), (0.0, 0.44 * H)], 12)
    for k in range(3):
        a = 2.0 * math.pi * k / 3
        strut(bronze, (x, y, 0.43 * H), (x + bowl_r * math.cos(a), y + bowl_r * math.sin(a), 0.43 * H), 0.025)
    lathe_into(bronze, x, y, [(0.0, H - 0.16), (0.3 * bowl_r, H - 0.16), (0.8 * bowl_r, H - 0.1),
                              (bowl_r, H - 0.02), (bowl_r + 0.03, H), (bowl_r * 0.92, H), (0.0, H - 0.06)], 32)
    flame_cards(flames, x, y, H - 0.06, 1.3 * bowl_r, 0.75)
    LIGHT_SLOTS.append({"name": name, "kind": "brazier", "position": [x, y, H + 0.3], "flame_height": 0.75})


def build_fixtures():
    R, hw = P["R"], P["exedra_hw"]
    LIGHT_SLOTS.clear()
    bronze = Builder("Bronze_Fixtures")
    flames = Builder("Flames")
    altar = Builder("Orn_Altar")
    painted = Builder("Painted_AltarFront")
    painted_sides = Builder("Painted_AltarSides")

    # braziers just inside the doorway, one each side of the passage
    to_world = frame(ENTRANCE_AZ)
    for side in (-1.0, 1.0):
        x, y, _ = to_world(R + 1.4, side * 3.4, 0.0)
        tripod_brazier(bronze, flames, x, y, 1.05, name="door_%s" % ("L" if side < 0 else "R"))

    # tall stands flanking Jupiter, braziers at the apse mouth
    to_world = frame(APSE_AZ)
    for side in (-1.0, 1.0):
        x, y, _ = to_world(apse_centre_u() + 0.6, side * 2.6, 0.0)
        candelabrum(bronze, flames, x, y, 2.8, 0.16, 0.42, name="apse_%s" % ("L" if side < 0 else "R"))
        x, y, _ = to_world(R + 0.3, side * 3.5, 0.0)
        tripod_brazier(bronze, flames, x, y, 1.05, name="apse_mouth_%s" % ("L" if side < 0 else "R"))

    # the altar of Jupiter on the main axis, with its fire
    u, w, d = R - 2.2, 1.7, 1.1
    hwa, hda = 0.5 * w, 0.5 * d
    box(altar, to_world, u - hda - 0.12, u + hda + 0.12, -hwa - 0.12, hwa + 0.12, 0.0, 0.14)
    box(altar, to_world, u - hda - 0.06, u + hda + 0.06, -hwa - 0.06, hwa + 0.06, 0.14, 0.22)
    box(altar, to_world, u - hda, u + hda, -hwa, hwa, 0.22, 0.92)
    box(altar, to_world, u - hda - 0.06, u + hda + 0.06, -hwa - 0.06, hwa + 0.06, 0.92, 1.0)
    box(altar, to_world, u - hda - 0.12, u + hda + 0.12, -hwa - 0.12, hwa + 0.12, 1.0, 1.1)
    for side in (-1.0, 1.0):  # pulvini: bolsters along the top edges
        circle = [(side * (hwa - 0.02) + 0.11 * math.cos(2 * math.pi * k / 16), 1.2 + 0.11 * math.sin(2 * math.pi * k / 16))
                  for k in range(16)]
        prism(altar, to_world, circle, u - hda - 0.1, u + hda + 0.1)
    e = 0.006
    painted.quad(to_world(u - hda - e, hwa - 0.05, 0.27), to_world(u - hda - e, -hwa + 0.05, 0.27),
                 to_world(u - hda - e, -hwa + 0.05, 0.87), to_world(u - hda - e, hwa - 0.05, 0.87))
    for sgn in (-1.0, 1.0):
        painted_sides.quad_out(to_world(u - hda + 0.05, sgn * (hwa + e), 0.27), to_world(u + hda - 0.05, sgn * (hwa + e), 0.27),
                               to_world(u + hda - 0.05, sgn * (hwa + e), 0.87), to_world(u - hda + 0.05, sgn * (hwa + e), 0.87),
                               Vector(to_world(0.0, sgn, 0.0)) - Vector(to_world(0.0, 0.0, 0.0)))
    ax, ay, _ = to_world(u, 0.0, 0.0)
    flame_cards(flames, ax, ay, 1.1, 0.8, 0.9, n=4)
    LIGHT_SLOTS.append({"name": "altar", "kind": "altar", "position": [ax, ay, 1.6], "flame_height": 0.9})

    # stands flanking each exedra statue
    for az, kind in RECESSES.items():
        if kind not in ("semi", "rect"):
            continue
        depth = P["exedra_depth_semi"] if kind == "semi" else P["exedra_depth_rect"]
        to_world = frame(az)
        for side in (-1.0, 1.0):
            x, y, _ = to_world(R + 0.6 * depth - 0.3, side * 1.75, 0.0)
            candelabrum(bronze, flames, x, y, 1.9, name="exedra_%03d_%s" % (int(az), "L" if side < 0 else "R"))

    # a stand before each aedicula, on the side away from the nearer exedra opening
    for az in AEDICULAE:
        to_world = frame(az)
        x, y, _ = to_world(R - 1.7, 0.0, 0.0)
        candelabrum(bronze, flames, x, y, 1.6, 0.11, 0.26, name="aedicula_%04d" % int(az * 10))

    for bld in (bronze, flames, altar, painted, painted_sides):
        bld.finish()


# --------------------------------------------------------------------------
# Attic (original flat design) and floor paving
# --------------------------------------------------------------------------

def angle_diff(a_deg, b_deg):
    return (a_deg - b_deg + 180.0) % 360.0 - 180.0


ATTIC_STATUES = {
    22.5: "attic_mars", 67.5: "attic_mercury", 112.5: "attic_vulcan", 157.5: "attic_aesculapius",
    202.5: "attic_ceres", 247.5: "attic_augustus_jupiter", 292.5: "attic_nerva_jupiter", 337.5: "attic_juno",
}


def build_attic():
    R, z0, z1 = P["R"], P["order_h"], P["spring_z"]
    dado_top = z0 + P["attic_dado_h"]
    ent_bot = z1 - P["attic_entab_h"]
    sill, head = P["attic_win_sill"], P["attic_win_head"]
    frame_w = P["attic_frame_w"]
    win_half = math.degrees(math.asin(0.5 * P["attic_win_w"] / R))
    arch_half = math.degrees(bay_half_angle())
    arch_axes = (ENTRANCE_AZ, APSE_AZ)
    windows = [k * 22.5 for k in range(16) if k * 22.5 not in arch_axes]
    # real openings over the six lateral exedrae; the eight over the aediculae are blind
    real = {0.0, 45.0, 135.0, 180.0, 225.0, 315.0}

    def in_arch(a, margin=0.0):
        return any(abs(angle_diff(a, ax)) < arch_half + margin for ax in arch_axes)

    def window_at(a):
        for w in windows:
            if abs(angle_diff(a, w)) < win_half:
                return w
        return None

    # wall surface with window openings
    wall = Builder("Attic_Wall")
    angles = {360.0 * j / P["segments"] for j in range(P["segments"])}
    for ax in arch_axes:
        angles |= {(ax - arch_half) % 360.0, (ax + arch_half) % 360.0}
    for w in windows:
        angles |= {(w - win_half) % 360.0, (w + win_half) % 360.0}
    angles = sorted(angles)
    for a0, a1 in zip(angles, angles[1:] + [angles[0] + 360.0]):
        mid = 0.5 * (a0 + a1)
        if in_arch(mid):
            continue
        spans = [(z0, sill), (head, z1)] if window_at(mid) is not None else [(z0, z1)]
        r0, r1 = math.radians(a0), math.radians(a1)
        # closed 10 cm slabs rather than single-sided sheets: Lumen lights an open sheet wrongly
        # (too bright with a sunlit shell behind it, too dark with a closed void)
        Rb = R + 0.1
        for zb, zt in spans:
            wall.add([(R * math.cos(r0), R * math.sin(r0), zb), (R * math.cos(r1), R * math.sin(r1), zb),
                      (R * math.cos(r1), R * math.sin(r1), zt), (R * math.cos(r0), R * math.sin(r0), zt),
                      (Rb * math.cos(r0), Rb * math.sin(r0), zb), (Rb * math.cos(r1), Rb * math.sin(r1), zb),
                      (Rb * math.cos(r1), Rb * math.sin(r1), zt), (Rb * math.cos(r0), Rb * math.sin(r0), zt)],
                     [(0, 1, 2, 3), (7, 6, 5, 4), (4, 5, 1, 0), (3, 2, 6, 7), (4, 0, 3, 7), (1, 5, 6, 2)])
    wall.finish()

    # window reveals and white marble frames
    reveals, frames = Builder("Attic_Reveals"), Builder("Attic_Frames")
    hw = 0.5 * P["attic_win_w"]
    for w in windows:
        to_world = frame(w)
        depth = 1.6 if w in real else 1.0
        u_in = math.sqrt(R * R - hw * hw)
        # sides, sill, head and back as closed 10 cm slabs (see the wall above). Each reaches 1 cm
        # into the opening past the wall, and each frame 2 cm past the reveals: flush, the giallo
        # wall's cut ends and the white reveals fought at the niche's head, a gold line flickering
        # along its top (user, 2026-11-24)
        t, ub, o = 0.1, R + depth, 0.01
        box(reveals, to_world, u_in, ub, -hw - t, -hw + o, sill - t, head + t)
        box(reveals, to_world, u_in, ub, hw - o, hw + t, sill - t, head + t)
        box(reveals, to_world, u_in, ub, -hw, hw, sill - t, sill + o)
        box(reveals, to_world, u_in, ub, -hw, hw, head - o, head + t)
        box(reveals, to_world, ub, ub + t, -hw - t, hw + t, sill - t, head + t)
        u_f, f = u_in - 0.06, 2 * o
        box(frames, to_world, u_f, R, -hw - frame_w, -hw + f, sill - frame_w, head + frame_w)
        box(frames, to_world, u_f, R, hw - f, hw + frame_w, sill - frame_w, head + frame_w)
        box(frames, to_world, u_f, R, -hw, hw, sill - frame_w, sill + f)
        box(frames, to_world, u_f, R, -hw, hw, head - f, head + frame_w)
    # gilded bronze lattice grilles in the six real windows (reference/attic_niches.md)
    grille = Builder("Gilded_AtticGrilles")
    for w in windows:
        if w not in real:
            continue
        to_world = frame(w)
        u0 = R + 0.35
        v = -hw
        while v <= hw + 1e-6:
            box(grille, to_world, u0, u0 + 0.05, v - 0.025, v + 0.025, sill, head)
            v += hw / 4.0
        z = sill
        while z <= head + 1e-6:
            box(grille, to_world, u0, u0 + 0.05, -hw, hw, z - 0.025, z + 0.025)
            z += (head - sill) / 7.0
        for k in range(-4, 5):  # diagonal lattice
            strut(grille, to_world(u0 + 0.025, k * hw / 4.0 - hw, sill), to_world(u0 + 0.025, k * hw / 4.0 + hw, head), 0.03)
    grille.finish()
    # small statues in the eight blind niches (reconstruction after Palladio and Ligorio)
    for w in windows:
        key = ATTIC_STATUES.get(w)
        if key:
            to_world = frame(w)
            x, y, z = to_world(R + 0.5, 0.0, sill + 0.02)
            STATUE_SLOTS.append({"statue": key, "azimuth": w, "position": [x, y, z], "yaw": w - 90.0})
    reveals.finish()
    frames.finish()

    # four porphyry pilasters with three panel bays between neighbouring window frames
    pil = Builder("Attic_Pilasters")
    pw = P["attic_pilaster_w"]
    pw_deg = math.degrees(pw / R)
    frame_deg = math.degrees((hw + frame_w) / R)
    for k in range(16):
        start = k * 22.5 + frame_deg
        end = (k + 1) * 22.5 - frame_deg
        panel = (end - start - 4.0 * pw_deg) / 3.0
        for i in range(4):
            c = start + 0.5 * pw_deg + i * (panel + pw_deg)
            if in_arch(c, margin=pw_deg):
                continue
            box(pil, frame(c), R - 0.03, R + 0.01, -0.5 * pw, 0.5 * pw, dado_top, ent_bot)
    pil.finish()
    # a raised pavonazzetto panel in each bay, leaving a giallo border: the bays were plain flat
    # sheets of one stone before, which read as painted card
    panels = Builder("Attic_Panels")
    for k in range(16):
        start = k * 22.5 + frame_deg
        end = (k + 1) * 22.5 - frame_deg
        panel = (end - start - 4.0 * pw_deg) / 3.0
        half_w = 0.5 * math.radians(panel) * R - 0.2
        for i in range(3):
            c = start + pw_deg + 0.5 * panel + i * (panel + pw_deg)
            if in_arch(c, margin=0.5 * panel):
                continue
            box(panels, frame(c), R - 0.03, R + 0.01, -half_w, half_w, dado_top + 0.3, ent_bot - 0.3)
    panels.finish()

    skips = [(ax, math.radians(arch_half)) for ax in arch_axes]
    revolve("Attic_Dado", [(R, z0), (R - 0.04, z0), (R - 0.04, dado_top), (R, dado_top)], skips=skips)
    revolve("Attic_Entablature", [(R, ent_bot), (R - 0.05, ent_bot), (R - 0.05, z1 - 0.9), (R, z1 - 0.9)],
            skips=skips)
    # Closed backing behind the single-sided attic wall and window reveals. Without it Lumen's
    # rays, which start just behind these surfaces, reached the back faces of the sunlit outer
    # shell and lit the giallo wall and the niche interiors far brighter than the solid panels
    # and pilasters in front of them.
    b0, b1 = R + 0.02, R + 1.8
    revolve("Attic_Backing", [(b0, z0), (b1, z0), (b1, z1), (b0, z1), (b0, z1 - 0.1), (b1 - 0.1, z1 - 0.1),
                              (b1 - 0.1, z0 + 0.1), (b0, z0 + 0.1)], closed=True, skips=skips)


SLAB_GAP = 0.004        # metres between neighbouring slabs
SLAB_TOP = 0.02         # top of the paving above the bedding at z = 0
SLAB_RNG = random.Random(126)


def slab_into(builder, x0, x1, y0, y1, z0, z1, inside=None, cell=0.4, tilt=0.0012, lift=0.0012):
    """One paving slab as a closed solid with a SLAB_GAP joint all round. Its top is set slightly
    high or low and tilted (lift metres, tilt metres per metre), so neighbouring slabs meet with
    small lips as on worn real paving. inside(x, y): cells whose centre fails it are left out
    (slabs that run under the wall); the slab stays one piece, with side faces only on its outline."""
    g = 0.5 * SLAB_GAP
    x0, x1, y0, y1 = x0 + g, x1 - g, y0 + g, y1 - g
    nx, ny = max(1, int(math.ceil((x1 - x0) / cell))), max(1, int(math.ceil((y1 - y0) / cell)))
    keep = [[inside is None or inside(x0 + (a + 0.5) * (x1 - x0) / nx, y0 + (b + 0.5) * (y1 - y0) / ny)
             for b in range(ny)] for a in range(nx)]
    if not any(any(r) for r in keep):
        return
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    h = SLAB_RNG.uniform(-lift, lift)
    sx, sy = SLAB_RNG.uniform(-tilt, tilt), SLAB_RNG.uniform(-tilt, tilt)
    verts = []
    for a in range(nx + 1):
        for b in range(ny + 1):
            x, y = x0 + a * (x1 - x0) / nx, y0 + b * (y1 - y0) / ny
            verts.append((x, y, z1 + h + sx * (x - cx) + sy * (y - cy)))
    top = len(verts)
    verts += [(x, y, z0) for x, y, _ in verts]

    def vi(a, b, bottom=False):
        return a * (ny + 1) + b + (top if bottom else 0)

    def kept(a, b):
        return 0 <= a < nx and 0 <= b < ny and keep[a][b]

    faces = []
    for a in range(nx):
        for b in range(ny):
            if not keep[a][b]:
                continue
            faces.append((vi(a, b), vi(a + 1, b), vi(a + 1, b + 1), vi(a, b + 1)))
            faces.append((vi(a, b + 1, True), vi(a + 1, b + 1, True), vi(a + 1, b, True), vi(a, b, True)))
            for (da, db), (p, q) in (((0, -1), ((a, b), (a + 1, b))), ((1, 0), ((a + 1, b), (a + 1, b + 1))),
                                     ((0, 1), ((a + 1, b + 1), (a, b + 1))), ((-1, 0), ((a, b + 1), (a, b)))):
                if not kept(a + da, b + db):
                    faces.append((vi(*p), vi(*q), vi(*q, True), vi(*p, True)))
    builder.add(verts, faces)


def disc_slab_into(builder, cx, cy, r, z0, z1, m=48, tilt=0.0012):
    """Round inlay as a closed solid, tilted slightly like slab_into."""
    r -= 0.5 * SLAB_GAP
    sx, sy = SLAB_RNG.uniform(-tilt, tilt), SLAB_RNG.uniform(-tilt, tilt)
    ring = [(cx + r * math.cos(2 * math.pi * k / m), cy + r * math.sin(2 * math.pi * k / m)) for k in range(m)]
    verts = ([(cx, cy, z1)] + [(x, y, z1 + sx * (x - cx) + sy * (y - cy)) for x, y in ring]
             + [(cx, cy, z0)] + [(x, y, z0) for x, y in ring])
    faces = [(0, 1 + k, 1 + (k + 1) % m) for k in range(m)]
    faces += [(m + 1, m + 2 + (k + 1) % m, m + 2 + k) for k in range(m)]
    faces += [(1 + k, m + 2 + k, m + 2 + (k + 1) % m, 1 + (k + 1) % m) for k in range(m)]
    builder.add(verts, faces)


def build_floor():
    """Rotunda paving as separate slabs: squares, the bands between them cut at every crossing,
    and the roundels and inner squares let into the squares, each with a joint and a slight lip.
    A dark bedding disc under the whole floor shows in the joints."""
    R = P["R"]
    pitch, sq = P["floor_pitch"], P["floor_square"]
    disc_r, inner = 0.5 * P["floor_disc_d"], P["floor_inner_square"]
    bw = pitch - sq
    parts = {name: Builder("Floor_" + name)
             for name in ("Bedding", "Bands", "Giallo", "Pavonazzetto", "Porphyry", "Granite")}

    n = P["segments"]
    ring = [(R * math.cos(2 * math.pi * j / n), R * math.sin(2 * math.pi * j / n), 0.0) for j in range(n)]
    parts["Bedding"].add([(0.0, 0.0, 0.0)] + ring, [(0, 1 + j, 1 + (j + 1) % n) for j in range(n)])

    def inside(x, y):
        return math.hypot(x, y) < R

    def rect(builder, cx, cy, w, d, z0=0.0, z1=SLAB_TOP):
        if math.hypot(abs(cx) - 0.5 * w, abs(cy) - 0.5 * d) < R:
            slab_into(builder, cx - 0.5 * w, cx + 0.5 * w, cy - 0.5 * d, cy + 0.5 * d, z0, z1, inside)

    half = int(math.ceil(R / pitch)) + 1
    inlay = (0.01, SLAB_TOP + 0.0025)        # inlays sit in the square, 2.5 mm proud
    for i in range(-half, half + 1):
        for j in range(-half, half + 1):
            cx, cy = i * pitch, j * pitch
            # bands: the run beside this square on two sides, and the crossing piece
            rect(parts["Bands"], cx, cy + 0.5 * pitch, sq, bw)
            rect(parts["Bands"], cx + 0.5 * pitch, cy, bw, sq)
            rect(parts["Bands"], cx + 0.5 * pitch, cy + 0.5 * pitch, bw, bw)
            if math.hypot(abs(cx) - 0.5 * sq, abs(cy) - 0.5 * sq) > R and math.hypot(cx, cy) > R:
                continue
            if (i + j) % 2 == 0:
                # disc in a square
                rect(parts["Giallo" if i % 2 == 0 else "Pavonazzetto"], cx, cy, sq, sq)
                if math.hypot(cx, cy) + disc_r < R:
                    disc_slab_into(parts["Porphyry" if ((i - j) // 2) % 2 == 0 else "Granite"],
                                   cx, cy, disc_r, *inlay)
            else:
                # porphyry frame around a square of pavonazzetto or giallo
                rect(parts["Porphyry"], cx, cy, sq, sq)
                if math.hypot(abs(cx) + 0.5 * inner, abs(cy) + 0.5 * inner) < R:
                    rect(parts["Pavonazzetto" if i % 2 else "Giallo"], cx, cy, inner, inner, *inlay)
    for b in parts.values():
        if b.faces:
            b.finish()


def paving(name, x0, x1, y0, y1, row=1.2, length=1.8, seed_shift=0.0, z0=0.0, keep=None, cell=0.4,
           tilt=0.002, lift=0.002, inside=None, top=SLAB_TOP):
    """Exterior travertine paving: rows of slabs in running bond, each row offset by half a slab.
    keep(x, y): slabs whose centre fails it are left out (whole slabs: over a large area the cell
    clipping of slab_into would multiply the faces)."""
    b = Builder(name)
    y, k = y0, 0
    while y < y1 - 1e-6:
        y_next = min(y1, y + row)
        x = x0 - (0.5 * length if k % 2 else 0.0) - seed_shift
        while x < x1 - 1e-6:
            xa, xb = max(x0, x), min(x1, x + length)
            if xb - xa > 0.05 and (keep is None or keep(0.5 * (xa + xb), 0.5 * (y + y_next))):
                slab_into(b, xa, xb, y, y_next, z0, z0 + top, inside=inside, cell=cell, tilt=tilt, lift=lift)
            x += length
        y, k = y_next, k + 1
    b.finish()


# --------------------------------------------------------------------------
# Materials: one slot per stone type; UE replaces these with its master materials
# --------------------------------------------------------------------------

MATERIALS = {
    # name: (base colour, metallic, roughness)
    "WhiteMarble": ((0.82, 0.80, 0.75), 0.0, 0.25),
    "Pavonazzetto": ((0.76, 0.70, 0.72), 0.0, 0.2),
    "GialloAntico": ((0.72, 0.45, 0.18), 0.0, 0.2),
    "Porphyry": ((0.22, 0.04, 0.05), 0.0, 0.2),
    "GreyGranite": ((0.30, 0.30, 0.31), 0.0, 0.3),
    "PinkGranite": ((0.50, 0.32, 0.28), 0.0, 0.3),
    "Stucco": ((0.78, 0.76, 0.72), 0.0, 0.7),
    "Bronze": ((0.55, 0.36, 0.14), 1.0, 0.35),
    "Concrete": ((0.50, 0.47, 0.43), 0.0, 0.9),
    "Travertine": ((0.70, 0.65, 0.56), 0.0, 0.6),
    "Gilded": ((0.95, 0.75, 0.35), 1.0, 0.28),
    "DarkMarble": ((0.06, 0.055, 0.05), 0.0, 0.25),
    "Painted": ((0.55, 0.12, 0.08), 0.0, 0.65),
    "Flame": ((1.0, 0.55, 0.15), 0.0, 1.0),
    "InvaderTile": ((0.8, 0.1, 0.08), 0.0, 0.2),
    # the city round the forecourt (build_surroundings)
    "Terracotta": ((0.55, 0.28, 0.17), 0.0, 0.75),
    "Void": ((0.025, 0.022, 0.02), 0.0, 0.95),
    "StuccoOchre": ((0.70, 0.52, 0.32), 0.0, 0.8),
    "StuccoRed": ((0.56, 0.27, 0.19), 0.0, 0.8),
    "StuccoCream": ((0.80, 0.74, 0.62), 0.0, 0.8),
    "Brick": ((0.52, 0.30, 0.21), 0.0, 0.85),
}

# first matching name prefix wins
MATERIAL_RULES = [
    ("Orn_", "WhiteMarble"), ("Bronze_Inscription", "Gilded"), ("Bronze_", "Bronze"), ("Gilded_", "Gilded"), ("Painted_", "Painted"),
    ("Flames", "Flame"), ("Invader_", "InvaderTile"), ("Entablature_Frieze", "Porphyry"), ("Entablature_Dentils", "WhiteMarble"),
    ("Panel_Dark", "DarkMarble"), ("Panel_Giallo", "GialloAntico"), ("Panel_Porphyry", "Porphyry"),
    ("Portico_Entablature", "WhiteMarble"), ("Portico_Pediment", "WhiteMarble"), ("Portico_Tympanum", "WhiteMarble"), ("Portico_Eagle", "Gilded"), ("Portico_BlockCornices", "WhiteMarble"), ("Portico_Block", "WhiteMarble"),
    ("Portico_Floor", "Travertine"),
    ("Floor_Bedding", "Concrete"), ("Floor_EntranceBedding", "Concrete"), ("Floor_RecessBedding", "Concrete"), ("Floor_Recesses", "Pavonazzetto"),
    ("Forecourt_Roofs", "Terracotta"), ("Forecourt_RoofTiles", "Terracotta"), ("Forecourt_Void", "Void"), ("Forecourt_City_Ochre", "StuccoOchre"),
    ("Forecourt_City_Red", "StuccoRed"), ("Forecourt_City_Cream", "StuccoCream"), ("Forecourt_City_Brick", "Brick"),
    ("Forecourt_Columns", "GreyGranite"), ("Forecourt_ColBases", "WhiteMarble"), ("Forecourt_ColEntab", "WhiteMarble"),
    ("Forecourt_Ceiling", "Stucco"), ("Forecourt_Walls", "Stucco"), ("Forecourt_WallEnds", "Stucco"),
    ("Forecourt_Blockers", "Void"), ("Forecourt_Gate", "WhiteMarble"), ("Floor_Entrance", "Pavonazzetto"),
    ("Portico_Passage", "Travertine"),
    ("Forecourt_", "Travertine"), ("Floor_Bands", "Pavonazzetto"), ("Floor_Giallo", "GialloAntico"), ("Floor_Pavonazzetto", "Pavonazzetto"),
    ("Floor_Porphyry", "Porphyry"), ("Floor_Granite", "GreyGranite"),
    ("Drum_Lower", "Pavonazzetto"), ("Recess_Ceilings", "WhiteMarble"),
    ("Attic_Wall", "GialloAntico"), ("Attic_Dado", "Pavonazzetto"), ("Attic_Pilasters", "Porphyry"),
    ("Attic_Panels", "Pavonazzetto"),
    ("Attic_", "WhiteMarble"), ("Entablature", "WhiteMarble"), ("Spring_Cornice", "WhiteMarble"),
    ("Bay_", "WhiteMarble"),
    # curved exedrae and apse: pavonazzetto; diagonal exedrae: giallo antico
    ("Column_000", "Pavonazzetto"), ("Column_180", "Pavonazzetto"), ("Column_270", "Pavonazzetto"),
    ("Column_", "GialloAntico"),
    ("AedCol_triangular", "GialloAntico"), ("AedCol_segmental", "Porphyry"), ("Aedicula_", "WhiteMarble"),
    ("Dome_Inner", "Stucco"), ("Oculus_Ring", "Bronze"), ("Dome_Outer", "Gilded"), ("Drum_Outer", "Concrete"),
    ("Ground", "Travertine"),
    ("Portico_Front", "GreyGranite"), ("Portico_Inner", "PinkGranite"), ("Portico_", "Concrete"),
]


def apply_materials():
    mats = {}
    for name, (color, metallic, rough) in MATERIALS.items():
        m = bpy.data.materials.new("M_" + name)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*color, 1.0)
            bsdf.inputs["Metallic"].default_value = metallic
            bsdf.inputs["Roughness"].default_value = rough
        m.diffuse_color = (*color, 1.0)
        mats[name] = m
    missing = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        for prefix, mat in MATERIAL_RULES:
            if obj.name.startswith(prefix):
                obj.data.materials.append(mats[mat])
                break
        else:
            missing.append(obj.name)
    if missing:
        print("No material rule for:", ", ".join(missing))


# --------------------------------------------------------------------------
# Preview renders
# --------------------------------------------------------------------------

def setup_preview(samples=96):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for dev in prefs.devices:
            dev.use = True
        scene.cycles.device = "GPU"
    except Exception as exc:  # falls back to CPU rendering
        print("GPU setup failed, using CPU:", exc)
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.view_settings.exposure = 3.0

    world = bpy.data.worlds.new("Sky")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.55, 0.70, 1.0, 1.0)
        bg.inputs[1].default_value = 1.0
    scene.world = world

    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 6.0
    sun_data.angle = math.radians(0.53)
    sun = bpy.data.objects.new("Sun", sun_data)
    scene.collection.objects.link(sun)
    # midday, late April in Rome: sun due south at about 62 degrees elevation. The building
    # axis is 5.5 degrees west of north, so in model space the sun is turned by that much.
    elev, skew = math.radians(62.0), math.radians(5.5)
    travel = Vector((math.cos(elev) * math.sin(skew), math.cos(elev) * math.cos(skew), -math.sin(elev)))
    sun.rotation_euler = travel.to_track_quat("-Z", "Y").to_euler()

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def render_view(cam, path, position, target, lens=16.0):
    cam.data.lens = lens
    cam.location = position
    direction = Vector(target) - Vector(position)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# Objects left as built: flat painted panels (UV-mapped pictures), flame cards, the ground plane.
NO_REFINE = ("Painted_", "Flames", "Ground", "Invader_", "Portico_Eagle", "Floor_RecessBedding", "Forecourt_Paving", "Forecourt_City_",
             "Forecourt_Roofs", "Forecourt_RoofTiles", "Forecourt_Void", "Forecourt_Trim", "Forecourt_Walls",
             "Forecourt_Blockers")
# Of those, the paving's slabs (slab_into) are oriented at export, as refine() would (thousands of
# them: the bevels refine() adds would multiply their faces), and given a colour each for the stone
# material's variation from slab to slab. The rest are wound outwards as they are built
# (build_surroundings).
ORIENT = ("Forecourt_Paving",)
BEVEL_WIDTH = 0.006      # metres: real stone arrises are never knife-sharp
BEVEL_ANGLE = 30.0       # degrees between faces above which an edge is bevelled


def island_colours(bm, rng):
    """Give every separate block or slab of a bmesh its own random vertex colour (R, G)."""
    col = bm.loops.layers.color.new("Col")
    seen = set()
    for start in bm.verts:
        if start in seen:
            continue
        stack, island = [start], []
        seen.add(start)
        while stack:
            v = stack.pop()
            island.append(v)
            for e in v.link_edges:
                o = e.other_vert(v)
                if o not in seen:
                    seen.add(o)
                    stack.append(o)
        c = (rng.random(), rng.random(), 0.0, 1.0)
        for v in island:
            for loop in v.link_loops:
                loop[col] = c


def refine(obj, rng):
    """Make a generated mesh read as cut stone: weld, give every separate block or slab its own
    random vertex colour (R, G; used by the stone material for slight colour, roughness and vein
    variation), bevel the hard edges, triangulate and smooth-shade with area-weighted normals."""
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    island_colours(bm, rng)
    edges = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0.0) > math.radians(BEVEL_ANGLE)]
    if edges:
        bmesh.ops.bevel(bm, geom=edges, offset=BEVEL_WIDTH, offset_type="OFFSET", segments=2, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    for f in bm.faces:
        f.smooth = True
    # Hard corners the bevel did not take (open shells, T-junctions) stay sharp. Smoothed across, a
    # wall's corner normals tilted up or down and the world-aligned stone texture blended in its
    # top-down projection, which shows on a vertical wall as streaks pulled straight down (user,
    # 2026-11-23, the exterior walls by the entrance).
    cos_hard = math.cos(math.radians(BEVEL_ANGLE))
    for e in bm.edges:
        fs = e.link_faces
        if len(fs) >= 2 and any(fs[i].normal.dot(fs[j].normal) < cos_hard
                                for i in range(len(fs)) for j in range(i + 1, len(fs))):
            e.smooth = False
    bm.to_mesh(obj.data)
    bm.free()
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    mod.mode = "FACE_AREA"
    mod.weight = 50
    mod.keep_sharp = True
    bpy.ops.object.modifier_apply(modifier=mod.name)


def export_fbx(out_dir, only=None):
    """One FBX per object, in world position, plus a manifest for the UE import script.

    only: a list of object names to export alone, leaving the other FBX files and the manifest as
    they are (refine() hands out random block colours in object order, so a full export after a
    change to one object would reshuffle the colours of every object after it).

    Blender is Z-up right-handed in metres; the FBX importer in UE converts to its
    Z-up left-handed centimetre space (Blender +Y becomes UE -Y).
    """
    import bmesh
    import json
    import os

    import random

    os.makedirs(out_dir, exist_ok=True)
    manifest = []
    rng = random.Random(126)
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH" or (only and obj.name not in only):
            continue
        refined = not obj.name.startswith(NO_REFINE)
        if refined:
            refine(obj, rng)
        else:
            # triangulate here so concave n-gons are split correctly before UE sees them
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            if obj.name.startswith(ORIENT):
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
                island_colours(bm, rng)
            bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
            bm.to_mesh(obj.data)
            bm.free()
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        path = os.path.join(out_dir, obj.name + ".fbx")
        # refined meshes carry their own (area-weighted) normals; the rest are flat-shaded
        bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_scale_options="FBX_SCALE_UNITS",
                                 mesh_smooth_type="OFF" if refined else "FACE", add_leaf_bones=False,
                                 bake_anim=False, colors_type="LINEAR")
        mat = obj.data.materials[0].name if obj.data.materials else None
        manifest.append({"name": obj.name, "file": obj.name + ".fbx", "material": mat,
                         "triangles": len(obj.data.polygons)})
    if only:
        # the other objects' entries stay; these objects' entries, the materials and the slots (all
        # generated the same on every run) are brought up to date
        path = os.path.join(out_dir, "manifest.json")
        old = json.load(open(path))
        names = {m["name"] for m in manifest}
        old["objects"] = [o for o in old["objects"] if o["name"] not in names] + manifest
        old["materials"] = {"M_" + k: {"base_color": v[0], "metallic": v[1], "roughness": v[2]}
                            for k, v in MATERIALS.items()}
        old.update({"statue_slots": STATUE_SLOTS, "light_slots": LIGHT_SLOTS, "capital_slots": CAPITAL_SLOTS})
        with open(path, "w") as fh:
            json.dump(old, fh, indent=1)
        print("exported %s to %s (manifest entries updated)" % (", ".join(m["name"] for m in manifest), out_dir))
        return
    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        json.dump({"units": "metres, Blender axes (Z up, +Y towards the entrance)",
                   "materials": {"M_" + k: {"base_color": v[0], "metallic": v[1], "roughness": v[2]}
                                 for k, v in MATERIALS.items()},
                   "objects": manifest, "statue_slots": STATUE_SLOTS, "light_slots": LIGHT_SLOTS,
                   "capital_slots": CAPITAL_SLOTS}, fh, indent=1)
    print("exported %d objects to %s" % (len(manifest), out_dir))


def place_statues():
    """Preview only: bring the processed statue FBX files into the slots (UE does this itself)."""
    import os
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    marble = bpy.data.materials.get("M_WhiteMarble")
    for s in STATUE_SLOTS:
        path = os.path.join(root, "assets", "statues", "processed", s["statue"] + ".fbx")
        if not os.path.exists(path):
            print("missing statue", path)
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=path)
        for o in set(bpy.data.objects) - before:
            if o.type == "MESH":
                o.location = s["position"]
                o.rotation_euler = (0.0, 0.0, math.radians(s["yaw"]))
                o.data.materials.clear()
                if marble:
                    o.data.materials.append(marble)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    with_statues = "--with-statues" in argv
    preview = argv[argv.index("--preview") + 1] if "--preview" in argv else None
    save = argv[argv.index("--save") + 1] if "--save" in argv else None
    export = argv[argv.index("--export") + 1] if "--export" in argv else None
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None

    bpy.ops.wm.read_factory_settings(use_empty=True)
    build_drum()
    build_columns()
    build_aediculae()
    build_doors()
    build_statue_bases()
    build_fixtures()
    build_attic()
    build_floor()
    build_recess_floor()
    build_dome()
    build_rosettes()
    build_invaders()
    build_floor_and_portico()
    build_panelling()
    apply_materials()

    total = 0
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            total += len(obj.data.polygons)
    print("objects=%d faces=%d" % (len(bpy.context.scene.objects), total))

    if save:
        bpy.ops.wm.save_as_mainfile(filepath=save)
    if export:
        export_fbx(export, only)
    if preview:
        if with_statues:
            place_statues()
        cam = setup_preview()
        # just inside the door, looking across to the apse and up into the dome
        render_view(cam, preview + "_a.png", (0.0, 17.0, 1.7), (0.0, -14.0, 14.0))
        # near the apse, looking back to the door past the aediculae
        render_view(cam, preview + "_b.png", (7.0, -15.0, 1.7), (-5.0, 21.0, 9.0))
        # close on the doorway and an exedra column screen
        render_view(cam, preview + "_c.png", (-3.0, 12.0, 1.7), (1.0, 28.0, 6.0), lens=24.0)
        # final shot: Zeus in the apse
        render_view(cam, preview + "_d.png", (0.0, -8.0, 2.2), (0.0, -23.0, 5.0), lens=35.0)
        # the opening shot: the portico and the door
        render_view(cam, preview + "_e.png", (6.0, 58.0, 1.7), (0.0, 36.0, 9.0), lens=20.0)
        # a pier with its aedicula and panelling
        render_view(cam, preview + "_f.png", (-8.0, 2.0, 1.7), (-19.0, 8.5, 5.0), lens=24.0)


if __name__ == "__main__":
    main()
