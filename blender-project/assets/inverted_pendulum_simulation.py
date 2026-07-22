#!/usr/bin/env python3
"""
2-Wheel Inverted Pendulum Simulation GIF Generator
Generates an animated GIF (300x300 px, 6 FPS, 144 frames) mimicking the
Blender storyboard and PID dynamics simulated in InvertedPendulumSim.tsx.
https://note.com/joyous_eagle3768/n/n9c7ed1e49af1
"""

import os
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Circle, Rectangle, FancyArrow

# --- Parameters & Constants ---
WIDTH, HEIGHT = 300, 300
FPS = 6
TOTAL_FRAMES = 144  # 24 seconds at 6 FPS
DT = 1.0 / FPS      # 0.1667s per frame
SUB_STEPS = 10
S_DT = DT / SUB_STEPS

G = 9.81
L = 1.0           # Pendulum length
M = 1.0           # Chassis mass
WHEEL_RADIUS = 0.3
AXLE_WIDTH = 0.6

def math_sign(val):
    return 1.0 if val >= 0 else -1.0

# Storyboard phase definitions
PHASES = [
    {"name": "CONSTRUCTION", "range": (0, 24)},
    {"name": "NO CONTROL", "range": (25, 48)},
    {"name": "UNSTABLE PID", "range": (49, 84)},
    {"name": "STABLE PID", "range": (85, 143)}
]

# --- Pre-generate simulation data ---
states = []

# Phase 1: Construction (Frames 0 - 24)
# Model is static, being built in Blender
for f in range(25):
    states.append({
        "x": 0.0, "v": 0.0, "theta": 0.0, "omega": 0.0,
        "phase": "CONSTRUCTION", "p_progress": f / 24.0
    })

# Phase 2: No Control (Frames 25 - 48)
# Falling from initial tilt under gravity
s2 = {"x": 0.0, "v": 0.0, "theta": 0.12, "omega": 0.0}
for f in range(25, 49):
    for _ in range(SUB_STEPS):
        # Equations of motion under gravity without motor torque
        theta_accel = (G * math.sin(s2["theta"])) / L - 0.1 * s2["omega"]
        s2["omega"] += theta_accel * S_DT
        s2["theta"] += s2["omega"] * S_DT

        # Free-rolling wheels react to gravitational torque
        wheel_accel = -0.15 * G * math.sin(s2["theta"]) - 0.3 * s2["v"]
        s2["v"] += wheel_accel * S_DT
        s2["x"] += s2["v"] * S_DT

        # Ground collision
        if abs(s2["theta"]) >= math.pi / 2:
            s2["theta"] = math_sign(s2["theta"]) * (math.pi / 2)
            s2["omega"] = -s2["omega"] * 0.35
            s2["v"] *= 0.2

    states.append({**s2, "phase": "NO CONTROL", "p_progress": 1.0})

# Phase 3: Unstable PID (Frames 49 - 84)
# High Kp, low Kd, causes wild oscillations
s3 = {"x": 0.0, "v": 0.0, "theta": 0.12, "omega": 0.0, "integral": 0.0}
bad_kp, bad_ki, bad_kd = 7.5, 0.05, 0.1
for f in range(49, 85):
    for _ in range(SUB_STEPS):
        error = s3["theta"]
        s3["integral"] += error * S_DT
        u = bad_kp * error + bad_ki * s3["integral"] + bad_kd * s3["omega"]
        u = max(-15.0, min(15.0, u))

        # Physics simulation
        theta_accel = (G * math.sin(s3["theta"]) - math.cos(s3["theta"]) * u) / L - 0.05 * s3["omega"]
        s3["omega"] += theta_accel * S_DT
        s3["theta"] += s3["omega"] * S_DT

        s3["v"] += u * S_DT - 0.2 * s3["v"]
        s3["x"] += s3["v"] * S_DT

        if abs(s3["theta"]) >= math.pi / 2:
            s3["theta"] = math_sign(s3["theta"]) * (math.pi / 2)
            s3["omega"] = 0.0
            s3["v"] = 0.0

    states.append({**s3, "phase": "UNSTABLE PID", "p_progress": 1.0})

# Phase 4: Stable PID with Disturbance (Frames 85 - 144)
s4 = {"x": 0.0, "v": 0.0, "theta": 0.15, "omega": 0.0, "integral": 0.0, "target_x": 0.0}
kp, ki, kd = 14.5, 0.3, 4.2
pos_kp, pos_kd = 0.8, 1.2
for f in range(85, TOTAL_FRAMES):
    if f == 115:
        s4["omega"] += 1.6  # Punch force!
    if f >= 130:
        s4["target_x"] = 0.6  # Position command shift

    for _ in range(SUB_STEPS):
        # Cascade position control to angle target
        pos_err = s4["x"] - s4["target_x"]
        target_theta = -0.15 * math.tanh(pos_kp * pos_err + pos_kd * s4["v"])

        balance_err = s4["theta"] - target_theta
        s4["integral"] += balance_err * S_DT

        u = kp * balance_err + ki * s4["integral"] + kd * s4["omega"]
        u = max(-18.0, min(18.0, u))

        # Physics Integration
        theta_accel = (G * math.sin(s4["theta"]) - math.cos(s4["theta"]) * u) / L - 0.1 * s4["omega"]
        s4["omega"] += theta_accel * S_DT
        s4["theta"] += s4["omega"] * S_DT

        s4["v"] += u * S_DT - 0.4 * s4["v"]
        s4["x"] += s4["v"] * S_DT

        if abs(s4["theta"]) >= math.pi / 2:
            s4["theta"] = math_sign(s4["theta"]) * (math.pi / 2)
            s4["omega"] = 0.0

    states.append({**s4, "phase": "STABLE PID", "p_progress": 1.0})


# --- Visualization / Plotting Setup ---
# Setup high contrast dark theme matching Blender viewport
plt.rcParams['text.color'] = '#e4e4e7'
plt.rcParams['axes.labelcolor'] = '#a1a1aa'
plt.rcParams['xtick.color'] = '#71717a'
plt.rcParams['ytick.color'] = '#71717a'

fig, ax = plt.subplots(figsize=(5, 5), dpi=60, facecolor='#18181b')
fig.subplots_adjust(left=0, right=1, bottom=0, top=1)

# Frame function for Matplotlib FuncAnimation
def update(frame):
    ax.clear()
    ax.set_facecolor('#2e2e2e')
    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(-1.0, 4.0)
    ax.axis('off')

    state = states[frame]
    phase = state["phase"]
    p_prog = state["p_progress"]

    # Calculate scale factor for physical offsets
    scale = 1.3
    x_pos = state["x"] * scale
    theta = state["theta"]

    # Ground line & Grid lines
    ax.axhline(0, color='#555555', linewidth=2, zorder=1)
    for g_x in np.arange(-5, 6, 0.5):
        # Moving floor pattern
        shift = (state["x"] * scale) % 0.5
        ax.plot([g_x - shift, g_x - shift], [-0.1, 0], color='#444444', linewidth=1, zorder=0)

    # Blender Coordinate Guides
    ax.plot([0.2, 1.2], [0.2, 0.2], color='#ff6b6b', linewidth=2, zorder=10) # Red X Axis
    ax.text(1.3, 0.15, 'X', color='#ff6b6b', fontfamily='monospace', fontsize=9, fontweight='bold')
    ax.plot([0.2, 0.2], [0.2, 1.2], color='#326ba8', linewidth=2, zorder=10) # Blue Z Axis
    ax.text(0.1, 1.3, 'Z', color='#6be0ff', fontfamily='monospace', fontsize=9, fontweight='bold')

    # Draw disturbance arrow (force impulse) at frame 115-118
    if 115 <= frame <= 118:
        arrow = FancyArrow(x_pos - 1.5, 1.5, 0.8, 0, width=0.1, head_width=0.25,
                           head_length=0.25, color='#ef4444', zorder=20)
        ax.add_patch(arrow)
        ax.text(x_pos - 1.8, 1.8, 'PUSH FORCE!', color='#ef4444',
                fontfamily='monospace', fontsize=8, fontweight='bold')

    # Draw Wheels & Chassis
    wheel_y = WHEEL_RADIUS
    chassis_len = 1.8

    # Construction Animation offsets
    chassis_alpha = min(1.0, p_prog * 1.5) if phase == "CONSTRUCTION" else 1.0
    wheel_alpha = min(1.0, (p_prog - 0.4) * 2.0) if phase == "CONSTRUCTION" else 1.0

    # Draw Wheels
    if phase != "CONSTRUCTION" or p_prog > 0.4:
        # Drawing 2 Wheels as overlapping circles for isometric segway look
        for offset in [-0.4, 0.4]:
            w_x = x_pos + offset
            is_selected = (phase == "CONSTRUCTION" and frame >= 15)
            edge_col = '#f97316' if is_selected else '#e4e4e7'
            fill_col = (0.97, 0.45, 0.08, 0.25) if is_selected else '#1e293b'

            # Draw Wheel base Circle
            wheel_patch = Circle((w_x, wheel_y), WHEEL_RADIUS, edgecolor=edge_col,
                                 facecolor=fill_col, linewidth=2, alpha=wheel_alpha, zorder=4)
            ax.add_patch(wheel_patch)

            # Wheel Spoke rotation
            rot = state["x"] * 3.5
            spoke_dx = math.cos(rot) * WHEEL_RADIUS
            spoke_dy = math.sin(rot) * WHEEL_RADIUS
            ax.plot([w_x - spoke_dx, w_x + spoke_dx], [wheel_y - spoke_dy, wheel_y + spoke_dy],
                    color='#71717a' if not is_selected else '#ea580c', linewidth=1.5, alpha=wheel_alpha, zorder=5)

    # Draw Pendulum Chassis
    if phase != "CONSTRUCTION" or p_prog > 0.1:
        # Pivot point
        pivot_x = x_pos
        pivot_y = wheel_y

        # Top of the chassis
        top_x = pivot_x + chassis_len * math.sin(theta)
        top_y = pivot_y + chassis_len * math.cos(theta)

        is_selected = (phase == "CONSTRUCTION" and frame >= 15)
        chassis_color = '#cbd5e1'
        fill_color = '#475569'
        if is_selected:
            chassis_color = '#f97316'
            fill_color = '#ea580c'

        # Chassis Beam
        ax.plot([pivot_x, top_x], [pivot_y, top_y], color=chassis_color, linewidth=8,
                alpha=chassis_alpha, solid_capstyle='round', zorder=3)

        # Draw Sensor Board on top
        cap_size = 0.2
        cap_x = top_x + 0.1 * math.sin(theta)
        cap_y = top_y + 0.1 * math.cos(theta)
        led_color = '#22c55e'
        if abs(theta) > 0.4:
            led_color = '#ef4444'
        elif phase == "UNSTABLE PID":
            led_color = '#f59e0b'
        elif phase == "CONSTRUCTION":
            led_color = '#3b82f6'

        sensor_patch = Circle((cap_x, cap_y), cap_size, color='#f97316', alpha=chassis_alpha, zorder=6)
        ax.add_patch(sensor_patch)

        # Blinking LED
        led_patch = Circle((cap_x, cap_y), 0.08, color=led_color, alpha=chassis_alpha, zorder=7)
        ax.add_patch(led_patch)

        # Center of Mass indicator
        com_y = pivot_y + (chassis_len * 0.6) * math.cos(theta)
        com_x = pivot_x + (chassis_len * 0.6) * math.sin(theta)
        ax.scatter([com_x], [com_y], marker='x', color='#ef4444', s=40, zorder=8, alpha=chassis_alpha)

    # Info HUD Overlay (Blender Viewport Mock)
    ax.text(-2.3, 3.7, '[CAM] Blender Viewport', color='#a1a1aa', fontfamily='monospace', fontsize=9, fontweight='bold')
    ax.text(-2.3, 3.4, f'Frame: {frame:03d} / 144', color='#e4e4e7', fontfamily='monospace', fontsize=8)
    ax.text(-2.3, 3.1, f'Phase: {phase}', color='#ea580c', fontfamily='monospace', fontsize=8, fontweight='bold')
    ax.text(-2.3, 2.8, f'Angle: {math.degrees(theta):.1f}°', color='#e4e4e7', fontfamily='monospace', fontsize=8)
    ax.text(-2.3, 2.5, f'X-Pos: {state["x"]:.2f} m', color='#e4e4e7', fontfamily='monospace', fontsize=8)

    # Status Badge
    badge_bg = '#22c55e'
    badge_text = 'STABLE'
    if abs(theta) >= 1.4:
        badge_bg = '#ef4444'
        badge_text = 'CRASHED'
    elif phase == "CONSTRUCTION":
        badge_bg = '#3b82f6'
        badge_text = 'BUILDING'
    elif phase == "UNSTABLE PID":
        badge_bg = '#f59e0b'
        badge_text = 'VIBRATING'

    ax.text(1.3, 3.7, f' {badge_text} ', color='#ffffff', bbox=dict(facecolor=badge_bg, edgecolor='none', boxstyle='round,pad=0.3'),
            fontfamily='monospace', fontsize=8, fontweight='bold', horizontalalignment='center')

    # Draw mini oscilloscope at bottom right
    graph_box = Rectangle((0.8, -0.8), 1.5, 0.8, edgecolor='#475569', facecolor='#0f172a', zorder=15, alpha=0.9)
    ax.add_patch(graph_box)
    ax.text(0.9, -0.2, 'Angle θ', color='#94a3b8', fontfamily='monospace', fontsize=7)

    # Plot wave
    plot_frames = 30
    plot_x = np.linspace(0.85, 2.25, plot_frames)
    plot_y = []
    for p_idx in range(plot_frames):
        target_f = max(0, frame - plot_frames + p_idx)
        past_val = states[target_f]["theta"]
        # Normalize to graph box height
        norm_y = -0.4 + (past_val * 0.3)
        plot_y.append(max(-0.75, min(-0.05, norm_y)))

    line_col = '#22c55e' if phase == "STABLE PID" else '#ef4444' if phase == "UNSTABLE PID" else '#f59e0b'
    ax.plot(plot_x, plot_y, color=line_col, linewidth=1.5, zorder=16)

    # Crop boundary to 300x300 canvas shape representation
    ax.set_position([0, 0, 1, 1])

# --- Save Animation as GIF ---
output_filename = "inverted_pendulum.gif"
print(f"Creating animation ({TOTAL_FRAMES} frames, {FPS} FPS)...")
ani = FuncAnimation(fig, update, frames=TOTAL_FRAMES, repeat=False)

# Saving
writer = PillowWriter(fps=FPS)
ani.save(output_filename, writer=writer)
plt.close()

print(f"Animation saved successfully as '{output_filename}'!")

