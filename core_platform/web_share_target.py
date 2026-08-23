"""
Web Share Target & Native File Handling Registration Engine.
Implements W3C Web Share Target API Level 2 specification, Web App Manifest share_target registration,
OS file_handlers file extension association routing, and incoming share payload processing.
"""

import sys
import os
from typing import Dict, List, Optional, Tuple, Any, Union

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class SharedPayload:
    """Represents an incoming share payload containing text, URL, or binary file attachments."""

    def __init__(
        self,
        title: str = "",
        text: str = "",
        url: str = "",
        files: Optional[List[Dict[str, Any]]] = None
    ):
        self.title = title
        self.text = text
        self.url = url
        self.files = files or []


class WebShareTargetEngine:
    """Engine managing Web App Manifest share_target registrations and incoming payload dispatches."""

    _registered_targets: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register_share_target(cls, origin: str, manifest_entry: Dict[str, Any]) -> bool:
        """Registers manifest share_target configuration for specified web app origin."""
        action = manifest_entry.get("action", "/share-target")
        method = manifest_entry.get("method", "GET").upper()
        enctype = manifest_entry.get("enctype", "application/x-www-form-urlencoded")
        params = manifest_entry.get("params", {})

        cls._registered_targets[origin] = {
            "origin": origin,
            "action": action,
            "method": method,
            "enctype": enctype,
            "params": params
        }
        return True

    @classmethod
    def process_incoming_share(cls, origin: str, payload: SharedPayload) -> Dict[str, Any]:
        """Routes incoming share payload into target web app action endpoint."""
        if origin not in cls._registered_targets:
            raise ValueError(f"ShareTargetError: Origin '{origin}' has not registered a share_target manifest handler.")

        target = cls._registered_targets[origin]
        params = target["params"]
        form_data = {}

        if "title" in params and payload.title:
            form_data[params["title"]] = payload.title
        if "text" in params and payload.text:
            form_data[params["text"]] = payload.text
        if "url" in params and payload.url:
            form_data[params["url"]] = payload.url
        if "files" in params and payload.files:
            file_param_name = params["files"].get("name", "files") if isinstance(params["files"], dict) else "files"
            form_data[file_param_name] = payload.files

        return {
            "status": 200,
            "action": f"{origin}{target['action']}",
            "method": target["method"],
            "enctype": target["enctype"],
            "formData": form_data
        }

    @classmethod
    def get_share_targets(cls) -> Dict[str, Dict[str, Any]]:
        """Returns snapshot dictionary of registered share targets."""
        return dict(cls._registered_targets)

    @classmethod
    def clear_all(cls) -> None:
        """Clears all registrations."""
        cls._registered_targets.clear()


class NativeFileHandlerRegistry:
    """Registry managing Web App Manifest file_handlers OS extension associations and file launches."""

    _registered_handlers: Dict[str, List[Dict[str, Any]]] = {}
    _mime_to_origin_action: Dict[str, Tuple[str, str]] = {}
    _ext_to_mime: Dict[str, str] = {
        ".txt": "text/plain",
        ".pdf": "application/pdf",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg"
    }

    @classmethod
    def register_file_handlers(cls, origin: str, handlers_list: List[Dict[str, Any]]) -> bool:
        """Registers manifest file_handlers array with accept MIME/extension mappings for specified origin."""
        cls._registered_handlers[origin] = handlers_list
        for handler in handlers_list:
            action = handler.get("action", "/open-file")
            accept = handler.get("accept", {})
            for mime_type in accept.keys():
                cls._mime_to_origin_action[mime_type] = (origin, action)
        return True

    @classmethod
    def launch_with_file(cls, filename: str, file_bytes: bytes, mime_type: Optional[str] = None) -> Dict[str, Any]:
        """Launches target registered web app handler with OS opened file payload."""
        if not mime_type:
            ext = os.path.splitext(filename)[1].lower()
            mime_type = cls._ext_to_mime.get(ext, "application/octet-stream")

        if mime_type in cls._mime_to_origin_action:
            origin, action = cls._mime_to_origin_action[mime_type]
            return {
                "status": 200,
                "origin": origin,
                "action": f"{origin}{action}",
                "filename": filename,
                "mimeType": mime_type,
                "size": len(file_bytes)
            }

        raise FileNotFoundError(f"FileHandlerError: No registered web app file handler for MIME type '{mime_type}'.")

    @classmethod
    def clear_all(cls) -> None:
        """Clears all file handler registrations."""
        cls._registered_handlers.clear()
        cls._mime_to_origin_action.clear()
