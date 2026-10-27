"""DaVinci Resolve scripting tools for CortexFlow.

Provides video editing operations via DaVinci Resolve's Python API.
Falls back to mock mode when DaVinciResolveScript is unavailable.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_resolve = None
_project_manager = None
_mock_mode = False
_resolve_checked = False
_mock_state: dict[str, Any] = {
    "media_pool": [],
    "timelines": {},
    "current_timeline": None,
    "render_jobs": [],
}


def _get_resolve():
    global _resolve, _project_manager, _mock_mode, _resolve_checked
    if _resolve_checked:
        return _resolve
    _resolve_checked = True
    try:
        import DaVinciResolveScript as dvr
        _resolve = dvr.scriptapp("Resolve")
        if _resolve is None:
            raise RuntimeError("DaVinci Resolve is not running")
        _project_manager = _resolve.GetProjectManager()
        logger.info("Connected to DaVinci Resolve %s", _resolve.GetVersionString())
        return _resolve
    except (ImportError, RuntimeError) as e:
        logger.warning("DaVinci Resolve unavailable (%s), using mock mode", e)
        _mock_mode = True
        return None


def _get_project():
    _get_resolve()
    if _mock_mode:
        return None
    pm = _project_manager or _resolve.GetProjectManager()
    return pm.GetCurrentProject()


def _get_timeline(project=None):
    if project is None:
        project = _get_project()
    if project is None:
        return None
    return project.GetCurrentTimeline()


# ── Tool functions ────────────────────────────────────────────────

def resolve_connect(**kwargs) -> dict:
    """Connect to DaVinci Resolve and return version info."""
    _get_resolve()
    if _mock_mode:
        return {"connected": True, "mock": True, "version": "mock-19.0"}
    version = _resolve.GetVersionString()
    return {"connected": True, "mock": False, "version": version}

resolve_connect._tool_description = "Connect to DaVinci Resolve and return version info"


def resolve_import_media(file_paths: list[str] | str = None, **kwargs) -> dict:
    """Import media files into the DaVinci Resolve media pool."""
    if file_paths is None:
        file_paths = kwargs.get("paths", [])
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    _get_resolve()
    if _mock_mode:
        clips = [{"path": p, "id": f"mock_clip_{i}"} for i, p in enumerate(file_paths)]
        _mock_state["media_pool"].extend(clips)
        return {"imported": len(clips), "clips": clips, "mock": True}

    project = _get_project()
    media_pool = project.GetMediaPool()
    root_folder = media_pool.GetRootFolder()
    media_pool.SetCurrentFolder(root_folder)

    items = media_pool.ImportMedia([{"filePath": p} for p in file_paths])
    if not items:
        return {"imported": 0, "error": "Import failed", "paths": file_paths}

    clips = [{"path": p, "name": it.GetName(), "id": it.GetUniqueId()} for it, p in zip(items, file_paths)]
    return {"imported": len(clips), "clips": clips, "mock": False}

resolve_import_media._tool_description = "Import media files into DaVinci Resolve media pool"
resolve_import_media._tool_parameters = {
    "file_paths": {"type": "array", "description": "List of file paths to import"}
}


def resolve_create_timeline(name: str = "AutoEdit", **kwargs) -> dict:
    """Create a new timeline in the current project."""
    _get_resolve()
    if _mock_mode:
        timeline = {"name": name, "tracks": [], "duration": 0.0, "clips": []}
        _mock_state["timelines"][name] = timeline
        _mock_state["current_timeline"] = name
        return {"timeline": name, "created": True, "mock": True}

    project = _get_project()
    media_pool = project.GetMediaPool()
    timeline = media_pool.CreateTimelineFromClips(name, [])
    if timeline is None:
        return {"timeline": name, "created": False, "error": "Failed to create timeline"}

    media_pool.SetCurrentTimeline(timeline)
    return {
        "timeline": name,
        "created": True,
        "mock": False,
        "track_count": timeline.GetTrackCount("video"),
    }

resolve_create_timeline._tool_description = "Create a new timeline in DaVinci Resolve"
resolve_create_timeline._tool_parameters = {
    "name": {"type": "string", "description": "Timeline name"}
}


def resolve_add_clip_to_timeline(
    media_path: str = None,
    track_index: int = 1,
    position: float = None,
    **kwargs,
) -> dict:
    """Add a media clip to the current timeline."""
    if media_path is None:
        media_path = kwargs.get("path", "")

    _get_resolve()
    if _mock_mode:
        tl_name = _mock_state.get("current_timeline", "default")
        tl = _mock_state["timelines"].setdefault(tl_name, {"clips": [], "duration": 0.0})
        clip_info = {"path": media_path, "track": track_index, "position": position or tl["duration"]}
        tl["clips"].append(clip_info)
        tl["duration"] = clip_info["position"] + kwargs.get("duration", 10.0)
        return {"clip": clip_info, "timeline_duration": tl["duration"], "mock": True}

    project = _get_project()
    timeline = _get_timeline(project)
    if timeline is None:
        return {"error": "No active timeline"}

    media_pool = project.GetMediaPool()
    items = media_pool.ImportMedia([{"filePath": media_path}])
    if not items:
        return {"error": f"Failed to import {media_path}"}

    clip = items[0]
    if position is not None:
        timeline.SetClipProperty(clip, "Start", str(position))

    media_pool.AppendClipsToTimeline([clip])
    return {
        "clip_name": clip.GetName(),
        "track": track_index,
        "position": position,
        "mock": False,
    }

resolve_add_clip_to_timeline._tool_description = "Add a media clip to the current timeline"
resolve_add_clip_to_timeline._tool_parameters = {
    "media_path": {"type": "string", "description": "Path to media file"},
    "track_index": {"type": "integer", "description": "Video track index (1-based)"},
    "position": {"type": "number", "description": "Position on timeline in seconds"},
}


def resolve_trim_clip(
    clip_index: int = None,
    trim_start: float = 0,
    trim_end: float = 0,
    **kwargs,
) -> dict:
    """Trim a clip on the timeline by adjusting in/out points."""
    if clip_index is None:
        clip_index = kwargs.get("index", 1)

    _get_resolve()
    if _mock_mode:
        return {
            "clip_index": clip_index,
            "trim_start": trim_start,
            "trim_end": trim_end,
            "mock": True,
        }

    timeline = _get_timeline()
    if timeline is None:
        return {"error": "No active timeline"}

    clip = timeline.GetItemListInTrack("video", 1)
    if not clip or clip_index > len(clip):
        return {"error": f"Clip {clip_index} not found"}

    item = clip[clip_index - 1]
    if trim_start > 0:
        item.SetProperty("Start", str(float(item.GetProperty("Start")) + trim_start))
    if trim_end > 0:
        item.SetProperty("End", str(float(item.GetProperty("End")) - trim_end))

    return {
        "clip_index": clip_index,
        "trim_start": trim_start,
        "trim_end": trim_end,
        "mock": False,
    }

resolve_trim_clip._tool_description = "Trim a clip on the timeline"
resolve_trim_clip._tool_parameters = {
    "clip_index": {"type": "integer", "description": "1-based clip index on track"},
    "trim_start": {"type": "number", "description": "Seconds to trim from start"},
    "trim_end": {"type": "number", "description": "Seconds to trim from end"},
}


def resolve_add_transition(
    clip_index: int = None,
    transition_type: str = "Smooth Cut",
    duration_frames: int = 30,
    **kwargs,
) -> dict:
    """Add a transition effect before a clip on the timeline."""
    if clip_index is None:
        clip_index = kwargs.get("index", 1)

    _get_resolve()
    if _mock_mode:
        return {
            "clip_index": clip_index,
            "transition": transition_type,
            "duration_frames": duration_frames,
            "mock": True,
        }

    timeline = _get_timeline()
    if timeline is None:
        return {"error": "No active timeline"}

    clips = timeline.GetItemListInTrack("video", 1)
    if not clips or clip_index > len(clips):
        return {"error": f"Clip {clip_index} not found"}

    item = clips[clip_index - 1]
    success = item.AddTransition("Video", transition_type, duration_frames)
    return {
        "clip_index": clip_index,
        "transition": transition_type,
        "duration_frames": duration_frames,
        "success": success,
        "mock": False,
    }

resolve_add_transition._tool_description = "Add a video transition before a clip"
resolve_add_transition._tool_parameters = {
    "clip_index": {"type": "integer", "description": "1-based clip index"},
    "transition_type": {"type": "string", "description": "Transition name (e.g. Cross Dissolve, Smooth Cut)"},
    "duration_frames": {"type": "integer", "description": "Transition duration in frames"},
}


def resolve_delete_clip(clip_index: int = None, **kwargs) -> dict:
    """Delete a clip from the timeline (cut operation)."""
    if clip_index is None:
        clip_index = kwargs.get("index", 1)

    _get_resolve()
    if _mock_mode:
        return {"clip_index": clip_index, "deleted": True, "mock": True}

    timeline = _get_timeline()
    if timeline is None:
        return {"error": "No active timeline"}

    clips = timeline.GetItemListInTrack("video", 1)
    if not clips or clip_index > len(clips):
        return {"error": f"Clip {clip_index} not found"}

    item = clips[clip_index - 1]
    timeline.DeleteClip(item)
    return {"clip_index": clip_index, "deleted": True, "mock": False}

resolve_delete_clip._tool_description = "Delete a clip from the timeline"
resolve_delete_clip._tool_parameters = {
    "clip_index": {"type": "integer", "description": "1-based clip index to delete"},
}


def resolve_add_subtitles(
    srt_content: str = None,
    track_index: int = 1,
    **kwargs,
) -> dict:
    """Add subtitle track from SRT content to the timeline."""
    if srt_content is None:
        srt_content = kwargs.get("content", "")

    _get_resolve()
    if _mock_mode:
        return {"subtitles_added": True, "content_length": len(srt_content), "mock": True}

    import tempfile
    project = _get_project()
    timeline = _get_timeline(project)
    if timeline is None:
        return {"error": "No active timeline"}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False) as f:
        f.write(srt_content)
        srt_path = f.name

    try:
        media_pool = project.GetMediaPool()
        items = media_pool.ImportMedia([{
            "filePath": srt_path,
            "mediaPoolMetadata": {"Subtitle Format": "SRT"},
        }])
        if items:
            media_pool.AppendClipsToTimeline(items)
            return {"subtitles_added": True, "path": srt_path, "mock": False}
        return {"error": "Failed to import subtitles", "mock": False}
    finally:
        os.unlink(srt_path)

resolve_add_subtitles._tool_description = "Add SRT subtitles to the timeline"
resolve_add_subtitles._tool_parameters = {
    "srt_content": {"type": "string", "description": "SRT format subtitle content"},
    "track_index": {"type": "integer", "description": "Subtitle track index"},
}


def resolve_render(
    output_path: str = None,
    preset: str = "H.264 Master",
    **kwargs,
) -> dict:
    """Render the current timeline to a file."""
    if output_path is None:
        output_path = kwargs.get("output", "/tmp/rendered_video.mp4")

    _get_resolve()
    if _mock_mode:
        return {"output": output_path, "preset": preset, "rendered": True, "mock": True}

    project = _get_project()
    timeline = _get_timeline(project)
    if timeline is None:
        return {"error": "No active timeline"}

    render_job_id = project.SetRenderSettings({
        "TargetDir": os.path.dirname(output_path),
        "CustomName": os.path.splitext(os.path.basename(output_path))[0],
        "VideoQuality": 4,
    })

    project.AddRenderJob("current_timeline", render_job_id)
    project.StartRendering(render_job_id)

    return {
        "output": output_path,
        "preset": preset,
        "job_id": render_job_id,
        "rendering": True,
        "mock": False,
    }

resolve_render._tool_description = "Render the current timeline to a video file"
resolve_render._tool_parameters = {
    "output_path": {"type": "string", "description": "Output file path"},
    "preset": {"type": "string", "description": "Render preset name"},
}


def resolve_get_timeline_info(**kwargs) -> dict:
    """Get info about the current timeline (duration, track count, clips)."""
    _get_resolve()
    if _mock_mode:
        tl_name = _mock_state.get("current_timeline", "default")
        tl = _mock_state["timelines"].get(tl_name, {"duration": 0.0, "clips": []})
        return {
            "name": tl_name,
            "duration": tl.get("duration", 0.0),
            "clip_count": len(tl.get("clips", [])),
            "mock": True,
        }

    timeline = _get_timeline()
    if timeline is None:
        return {"error": "No active timeline"}

    video_clips = timeline.GetItemListInTrack("video", 1) or []
    return {
        "name": timeline.GetName(),
        "duration": timeline.GetEndFrame() - timeline.GetStartFrame(),
        "fps": timeline.GetSetting("timelineFrameRate"),
        "resolution": f"{timeline.GetSetting('timelineResolutionWidth')}x{timeline.GetSetting('timelineResolutionHeight')}",
        "video_tracks": timeline.GetTrackCount("video"),
        "audio_tracks": timeline.GetTrackCount("audio"),
        "clip_count": len(video_clips),
        "mock": False,
    }

resolve_get_timeline_info._tool_description = "Get current timeline info (duration, tracks, clips)"


def resolve_set_color_grade(
    clip_index: int = None,
    preset: str = "cinematic",
    **kwargs,
) -> dict:
    """Apply a color grade preset to a clip."""
    if clip_index is None:
        clip_index = kwargs.get("index", 1)

    _get_resolve()
    if _mock_mode:
        return {"clip_index": clip_index, "preset": preset, "mock": True}

    timeline = _get_timeline()
    if timeline is None:
        return {"error": "No active timeline"}

    clips = timeline.GetItemListInTrack("video", 1)
    if not clips or clip_index > len(clips):
        return {"error": f"Clip {clip_index} not found"}

    grade_presets = {
        "cinematic": {"contrast": 1.1, "saturation": 0.9, "temperature": -500},
        "vlog": {"contrast": 1.05, "saturation": 1.2, "temperature": 200},
        "tutorial": {"contrast": 1.0, "saturation": 1.0, "temperature": 0},
        "highlights": {"contrast": 1.2, "saturation": 1.3, "temperature": 100},
    }
    grade = grade_presets.get(preset, grade_presets["cinematic"])

    item = clips[clip_index - 1]
    for prop, val in grade.items():
        item.SetCDLProperty("Offset", prop, val)

    return {"clip_index": clip_index, "preset": preset, "applied": True, "mock": False}

resolve_set_color_grade._tool_description = "Apply a color grade preset to a timeline clip"
resolve_set_color_grade._tool_parameters = {
    "clip_index": {"type": "integer", "description": "1-based clip index"},
    "preset": {"type": "string", "description": "Grade preset: cinematic, vlog, tutorial, highlights"},
}
