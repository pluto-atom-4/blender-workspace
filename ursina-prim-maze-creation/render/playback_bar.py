"""Bottom playback control bar: play/pause/rewind/forward buttons, frame counter, seek slider."""
from ursina import Entity, Text, camera, mouse
from ursina.prefabs.slider import Slider
from ursina.prefabs.button import Button

# Module-level UI elements
bar_root = None
frame_text = None
seek_slider = None


def build_bar(on_rewind, on_play_pause, on_forward, on_seek):
    """Build the playback control bar at the bottom of the screen.

    Args:
        on_rewind: Callable() - handle rewind button
        on_play_pause: Callable() - handle play/pause toggle button
        on_forward: Callable() - handle forward button
        on_seek: Callable(index: int) - handle seek slider

    Returns:
        Entity (bar_root) for the entire bottom bar
    """
    global bar_root, frame_text, seek_slider

    # Root bar positioned at bottom center
    bar_root = Entity(parent=camera.ui, x=0, y=-0.475)

    # Background quad for visual boundary (light semi-transparent)
    bg = Entity(
        parent=bar_root,
        model="quad",
        color=(0.2, 0.2, 0.2, 0.7),
        scale=(2.0, 0.05),
        z=0.01,  # Behind buttons
    )

    # Button scale for consistency
    button_scale = (0.06, 0.04)

    # === Rewind Button ===
    rewind_btn = Button(
        parent=bar_root,
        model="quad",
        scale=button_scale,
        x=-0.35,
        text="|<",
        text_size=0.5,
        on_click=on_rewind,
    )
    rewind_btn.color = (0.5, 0.5, 0.5, 1.0)

    # === Play/Pause Toggle Button ===
    play_pause_btn = Button(
        parent=bar_root,
        model="quad",
        scale=button_scale,
        x=-0.22,
        text="||",
        text_size=0.5,
        on_click=on_play_pause,
    )
    play_pause_btn.color = (0.5, 0.5, 0.5, 1.0)
    # Button() auto-creates play_pause_btn.text_entity from text= above —
    # update_play_pause_label() already does btn.text_entity.text = ... and keeps working.

    # === Forward Button ===
    forward_btn = Button(
        parent=bar_root,
        model="quad",
        scale=button_scale,
        x=-0.09,
        text=">|",
        text_size=0.5,
        on_click=on_forward,
    )
    forward_btn.color = (0.5, 0.5, 0.5, 1.0)

    # === Frame Counter Text ===
    frame_text = Text(
        parent=bar_root,
        text="0 / 0",
        x=0.15,
        scale=1.5,
    )

    # === Seek Slider ===
    seek_slider = Slider(
        min=0,
        max=100,
        default=0,
        text="",
        dynamic=False,  # Only fire on release
        parent=bar_root,
        x=0.65,
        scale=0.5,
    )
    seek_slider.on_value_changed = lambda: on_seek(int(seek_slider.value))

    # Store the play_pause_btn for external state updates
    bar_root.play_pause_btn = play_pause_btn

    return bar_root


def set_frame_text(current_index, total_steps):
    """Update frame counter display without triggering callbacks.

    Args:
        current_index: Current step index
        total_steps: Total number of steps
    """
    if frame_text:
        frame_text.text = f"{current_index} / {total_steps}"


def set_seek_slider(index, max_value=None, call_on_value_changed=False):
    """Update seek slider position without triggering callbacks.

    Args:
        index: Desired slider position (0 to max_value)
        max_value: Maximum slider value (if None, keep current)
        call_on_value_changed: If False, suppress callback during update
    """
    if seek_slider is None:
        return

    # Update max if provided
    if max_value is not None:
        seek_slider.max = max_value

    # Temporarily disable callback if requested
    if not call_on_value_changed:
        original_callback = seek_slider.on_value_changed
        seek_slider.on_value_changed = lambda: None
        seek_slider.value = index
        seek_slider.on_value_changed = original_callback
    else:
        seek_slider.value = index


def update_play_pause_label(is_playing):
    """Update play/pause button label based on current playback state.

    Args:
        is_playing: True if playback is active, False if paused
    """
    if bar_root and hasattr(bar_root, "play_pause_btn"):
        btn = bar_root.play_pause_btn
        if hasattr(btn, "text_entity"):
            btn.text_entity.text = ">" if is_playing else "||"
