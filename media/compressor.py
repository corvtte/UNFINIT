# -*- coding: utf-8 -*-
"""
ماژول سازگاری بهینه‌ساز رسانه (Media Compressor Compatibility Wrapper)
انعکاس کامل کلاس‌های SmartAudioCompressor، SmartVideoCompressor و SmartVideoSplitter از services.compressor.
"""

from services.compressor import (
    SAFE_BALE_PART_LIMIT_MB,
    SmartAudioCompressor,
    SmartVideoCompressor,
    SmartVideoSplitter,
    convert_audio_to_mp3_if_needed,
    _format_video_progress_msg
)

__all__ = [
    "SAFE_BALE_PART_LIMIT_MB",
    "SmartAudioCompressor",
    "SmartVideoCompressor",
    "SmartVideoSplitter",
    "convert_audio_to_mp3_if_needed",
    "_format_video_progress_msg"
]
