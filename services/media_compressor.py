"""
Services wrapper for media compressor.
Re-exports SmartAudioCompressor, SmartVideoCompressor, and convert_audio_to_mp3_if_needed
from media.compressor with full compatibility.
"""

from media.compressor import (
    SmartAudioCompressor,
    SmartVideoCompressor,
    convert_audio_to_mp3_if_needed
)

__all__ = [
    "SmartAudioCompressor",
    "SmartVideoCompressor",
    "convert_audio_to_mp3_if_needed"
]
