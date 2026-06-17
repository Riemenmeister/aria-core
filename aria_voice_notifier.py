"""
Voice Notifier for Aria Core with Rate-Limiting and Voice Profiles
Prevents audio spam during error loops by enforcing minimum time between identical error messages.
Supports custom voice profiles for different error types with configurable TTS properties.
"""

import logging
import time
from enum import Enum
from typing import Optional, Dict

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

logger = logging.getLogger('aria_voice_notifier')


class VoiceProfile(Enum):
    """Predefined voice profiles for different message types."""
    INFO = 'info'
    WARNING = 'warning'
    CRITICAL = 'critical'
    SUCCESS = 'success'


class VoiceProfileConfig:
    """Configuration for a voice profile."""
    
    def __init__(self, name: str, rate: int = 160, volume: float = 1.0, cooldown: int = 30):
        """
        Initialize a voice profile configuration.
        
        Args:
            name: Profile name.
            rate: Speech rate (50-300, default 160).
            volume: Volume level (0.0-1.0, default 1.0).
            cooldown: Cooldown between identical messages in seconds (default 30).
        """
        self.name = name
        self.rate = max(50, min(300, rate))  # Clamp between 50 and 300
        self.volume = max(0.0, min(1.0, volume))  # Clamp between 0 and 1
        self.cooldown = max(1, cooldown)  # Minimum 1 second


# Predefined profile configurations
DEFAULT_PROFILES: Dict[VoiceProfile, VoiceProfileConfig] = {
    VoiceProfile.INFO: VoiceProfileConfig('INFO', rate=160, volume=1.0, cooldown=30),
    VoiceProfile.WARNING: VoiceProfileConfig('WARNING', rate=140, volume=1.0, cooldown=20),
    VoiceProfile.CRITICAL: VoiceProfileConfig('CRITICAL', rate=120, volume=1.0, cooldown=60),
    VoiceProfile.SUCCESS: VoiceProfileConfig('SUCCESS', rate=180, volume=1.0, cooldown=15),
}


class VoiceNotifier:
    """
    Manages TTS output with rate-limiting and voice profiles.
    
    Each voice profile has its own TTS settings (rate, volume, cooldown).
    Messages can be routed to different profiles based on severity/type.
    Rate-limiting is per-message per-profile to prevent audio spam during error loops.
    """
    
    def __init__(self, profiles: Optional[Dict[VoiceProfile, VoiceProfileConfig]] = None, enabled: bool = True):
        """
        Initialize VoiceNotifier with custom or default profiles.
        
        Args:
            profiles: Custom profile configurations. If None, uses DEFAULT_PROFILES.
            enabled: Whether to enable TTS output (default: True).
        """
        self.enabled = enabled and TTS_AVAILABLE
        self.engine = None
        self.profiles = profiles or DEFAULT_PROFILES.copy()
        self.last_message_time: Dict[str, float] = {}  # Track last speak time per message
        self.current_profile = VoiceProfile.INFO
        
        if self.enabled:
            try:
                self.engine = pyttsx3.init()
                logger.info('VoiceNotifier TTS-Engine erfolgreich initialisiert.')
                self._apply_profile(self.current_profile)
            except Exception as e:
                logger.warning('VoiceNotifier: TTS-Engine konnte nicht initialisiert werden: %s', e)
                self.enabled = False
    
    def _apply_profile(self, profile: VoiceProfile) -> None:
        """Apply TTS settings from a voice profile."""
        if not self.enabled or profile not in self.profiles:
            return
        
        config = self.profiles[profile]
        try:
            self.engine.setProperty('rate', config.rate)
            self.engine.setProperty('volume', config.volume)
            self.current_profile = profile
            logger.debug('VoiceProfile "%s" angewendet: rate=%d, volume=%.1f', config.name, config.rate, config.volume)
        except Exception as e:
            logger.warning('Fehler beim Anwenden des Profils "%s": %s', config.name, e)
    
    def add_profile(self, profile_enum: VoiceProfile, config: VoiceProfileConfig) -> None:
        """Add or update a voice profile."""
        self.profiles[profile_enum] = config
        logger.info('VoiceProfile "%s" hinzugefügt: rate=%d, volume=%.1f, cooldown=%d',
                    config.name, config.rate, config.volume, config.cooldown)
    
    def speak(self, text: str, profile: VoiceProfile = VoiceProfile.INFO, force: bool = False) -> bool:
        """
        Speak a message with rate-limiting per profile.
        
        Args:
            text: The message to speak.
            profile: Voice profile to use (default: INFO).
            force: If True, bypass rate-limiting and speak immediately.
        
        Returns:
            True if message was spoken, False if rate-limited.
        """
        if not self.enabled:
            logger.info('[ARIA SPRICHT (ohne Audio)]: %s', text)
            return False
        
        if profile not in self.profiles:
            logger.warning('Unbekanntes VoiceProfile: %s', profile)
            return False
        
        config = self.profiles[profile]
        current_time = time.time()
        
        # Use profile + text as cache key for per-message-per-profile cooldown
        cache_key = f"{profile.value}:{text}"
        last_time = self.last_message_time.get(cache_key, 0)
        time_since_last = current_time - last_time
        
        # Check rate-limit
        if not force and time_since_last < config.cooldown:
            logger.debug(
                '[RATE-LIMITED] [%s]: "%s" (%.1fs bis zur nächsten Ausgabe)',
                config.name,
                text,
                config.cooldown - time_since_last
            )
            return False
        
        # Apply profile and speak the message
        try:
            self._apply_profile(profile)
            logger.info('[ARIA SPRICHT] [%s]: %s', config.name, text)
            self.engine.say(text)
            self.engine.runAndWait()
            self.last_message_time[cache_key] = current_time
            return True
        except Exception as e:
            logger.warning('Fehler bei TTS-Ausgabe: %s', e)
            return False
    
    def reset_cooldown(self, text: Optional[str] = None, profile: Optional[VoiceProfile] = None) -> None:
        """
        Reset the cooldown timer for a specific message/profile or all messages.
        
        Args:
            text: Specific message to reset. If None, resets all messages for the profile.
            profile: Profile to reset. If None, resets all profiles.
        """
        if text is None and profile is None:
            self.last_message_time.clear()
            logger.info('Alle Cooldown-Timer zurückgesetzt.')
        elif text is not None and profile is not None:
            cache_key = f"{profile.value}:{text}"
            if cache_key in self.last_message_time:
                del self.last_message_time[cache_key]
                logger.info('Cooldown für "%s" [%s] zurückgesetzt.', text, profile.value)
        elif profile is not None:
            prefix = f"{profile.value}:"
            keys_to_delete = [k for k in self.last_message_time if k.startswith(prefix)]
            for key in keys_to_delete:
                del self.last_message_time[key]
            logger.info('Alle Cooldowns für Profil "%s" zurückgesetzt.', profile.value)
        else:
            logger.warning('reset_cooldown: Mindestens text oder profile erforderlich.')
    
    def set_cooldown(self, profile: VoiceProfile, cooldown_seconds: int) -> None:
        """Update the cooldown duration for a specific profile."""
        if profile not in self.profiles:
            logger.warning('Unbekanntes VoiceProfile: %s', profile)
            return
        self.profiles[profile].cooldown = max(1, cooldown_seconds)
        logger.info('Cooldown für Profil "%s" auf %d Sekunden aktualisiert.', profile.value, cooldown_seconds)
    
    def set_profile_settings(self, profile: VoiceProfile, rate: Optional[int] = None,
                            volume: Optional[float] = None) -> None:
        """Update rate and/or volume for a specific profile."""
        if profile not in self.profiles:
            logger.warning('Unbekanntes VoiceProfile: %s', profile)
            return
        
        config = self.profiles[profile]
        if rate is not None:
            config.rate = max(50, min(300, rate))
        if volume is not None:
            config.volume = max(0.0, min(1.0, volume))
        
        logger.info('Profil "%s" aktualisiert: rate=%d, volume=%.1f', config.name, config.rate, config.volume)
        
        # Reapply if this is the current profile
        if profile == self.current_profile:
            self._apply_profile(profile)


# Global notifier instance
_notifier: Optional[VoiceNotifier] = None


def initialize_notifier(profiles: Optional[Dict[VoiceProfile, VoiceProfileConfig]] = None,
                       enabled: bool = True) -> VoiceNotifier:
    """Initialize the global VoiceNotifier instance with optional custom profiles."""
    global _notifier
    _notifier = VoiceNotifier(profiles=profiles, enabled=enabled)
    return _notifier


def get_notifier() -> VoiceNotifier:
    """Get the global VoiceNotifier instance, initializing with defaults if needed."""
    global _notifier
    if _notifier is None:
        _notifier = VoiceNotifier()
    return _notifier


def aria_speak(text: str, profile: VoiceProfile = VoiceProfile.INFO, force: bool = False) -> bool:
    """
    Convenience function to speak via the global notifier.
    
    Args:
        text: The message to speak.
        profile: Voice profile to use (default: INFO).
        force: If True, bypass rate-limiting.
    
    Returns:
        True if message was spoken, False if rate-limited.
    """
    return get_notifier().speak(text, profile=profile, force=force)
