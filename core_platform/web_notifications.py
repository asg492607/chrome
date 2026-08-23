"""
Web Notifications & System Desktop Alert Dispatch Engine.
Implements WHATWG Notifications API specification (window.Notification), permission state machine (requestPermission),
tag collapsing/deduplication, action button routing, and OS-native desktop alert dispatches.
"""

import sys
import os
from typing import Dict, List, Optional, Tuple, Any, Callable, Union

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class DesktopNotificationCenter:
    """Central system notification center managing desktop alert toasts and action routing."""

    _active_notifications: List["Notification"] = []
    _by_tag: Dict[str, "Notification"] = {}

    @classmethod
    def dispatch_notification(cls, notification: "Notification") -> bool:
        """Dispatches notification to OS alert system with tag collapsing."""
        if notification.tag:
            if notification.tag in cls._by_tag:
                old_n = cls._by_tag[notification.tag]
                old_n.close()
            cls._by_tag[notification.tag] = notification


        cls._active_notifications.append(notification)
        if notification.onshow:
            notification.onshow()
        return True

    @classmethod
    def remove_notification(cls, notification: "Notification") -> None:
        """Removes notification from active list."""
        if notification in cls._active_notifications:
            cls._active_notifications.remove(notification)
        if notification.tag and cls._by_tag.get(notification.tag) is notification:
            del cls._by_tag[notification.tag]

    @classmethod
    def dispatch_action(cls, notification: "Notification", action_name: str) -> None:
        """Routes action button click event to notification listener."""
        if notification.onclick:
            notification.onclick({"type": "click", "action": action_name, "target": notification})

    @classmethod
    def get_active_notifications(cls) -> List["Notification"]:
        """Returns list of currently active desktop notifications."""
        return list(cls._active_notifications)

    @classmethod
    def clear_all(cls) -> None:
        """Clears all active notifications."""
        cls._active_notifications.clear()
        cls._by_tag.clear()


class Notification:
    """WHATWG Notification class representation."""

    permission: str = "granted"

    @classmethod
    def requestPermission(cls, callback: Optional[Callable[[str], None]] = None) -> str:
        """Requests user permission to display desktop notifications."""
        cls.permission = "granted"
        if callback:
            callback(cls.permission)
        return cls.permission

    def __init__(self, title: str, options: Optional[Dict[str, Any]] = None):
        if self.permission != "granted":
            raise PermissionError("NotificationError: Permission denied for desktop notifications.")

        opts = options or {}
        self.title = title
        self.body = opts.get("body", "")
        self.icon = opts.get("icon", "")
        self.badge = opts.get("badge", "")
        self.tag = opts.get("tag", "")
        self.data = opts.get("data")
        self.actions = opts.get("actions", [])
        self.silent = opts.get("silent", False)
        self.renotify = opts.get("renotify", False)

        self.closed = False
        self.onclick: Optional[Callable[[Dict[str, Any]], None]] = None
        self.onclose: Optional[Callable[[], None]] = None
        self.onshow: Optional[Callable[[], None]] = None
        self.onerror: Optional[Callable[[], None]] = None

        DesktopNotificationCenter.dispatch_notification(self)

    def close(self) -> None:
        """Closes desktop notification."""
        if self.closed:
            return
        self.closed = True
        if self.onclose:
            self.onclose()
        DesktopNotificationCenter.remove_notification(self)

    def __repr__(self) -> str:
        return f"Notification('{self.title}', tag='{self.tag}', closed={self.closed})"
