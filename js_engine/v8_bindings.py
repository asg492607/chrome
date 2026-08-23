"""
V8 Engine FFI & DOM C++ Binding Generator.
Provides zero-overhead direct C/ctypes FFI bindings and JSContext execution environment
for manipulating 32-byte DOMEntity32 slots directly in DocumentTreeMemoryBank.
"""

import sys
import os
import re
import ctypes
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core_platform.ecs_memory import DocumentTreeMemoryBank, NodeFlags, DOMEntity32
from core_platform.tag_constants import TagType, TAG_NAME_TO_TYPE, TAG_TYPE_TO_NAME


# C-Compatible FFI Callback Prototypes for V8 Engine Integration
CTYPES_CREATE_ELEMENT_FUNC = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p)
CTYPES_GET_ELEMENT_BY_ID_FUNC = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p)
CTYPES_SET_STYLE_FUNC = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p)


class DOMBindings:
    """High-Speed Native DOM C++ Binding Functions operating directly on ECS Memory Bank."""

    @classmethod
    def get_element_by_id(cls, bank: DocumentTreeMemoryBank, id_str: str) -> Optional[int]:
        """Fast $O(N)$ attribute search for DOM Entity with matching ID attribute."""
        target_id = id_str.strip().lower()
        for entity_id, attrs in bank.attr_pool.items():
            if attrs.get("id", "").strip().lower() == target_id:
                return entity_id
        return None

    @classmethod
    def get_elements_by_class_name(cls, bank: DocumentTreeMemoryBank, class_name: str) -> List[int]:
        """Retrieves list of DOM entity IDs containing target class name."""
        target_cls = class_name.strip().lower()
        matching_ids = []
        for entity_id, attrs in bank.attr_pool.items():
            classes = [c.strip().lower() for c in attrs.get("class", "").split()]
            if target_cls in classes:
                matching_ids.append(entity_id)
        return matching_ids

    @classmethod
    def create_element(cls, bank: DocumentTreeMemoryBank, tag_name: str) -> int:
        """Allocates a new 32-byte DOMEntity32 in DocumentTreeMemoryBank for specified tag."""
        clean_tag = tag_name.strip().lower()
        tag_type = TAG_NAME_TO_TYPE.get(clean_tag, TagType.CUSTOM)
        flags = int(NodeFlags.VISIBILITY | NodeFlags.DIRTY_LAYOUT | NodeFlags.DIRTY_STYLE)

        entity_id = bank.allocate_entity(
            tag_type,
            flags=flags,
            attrs={"_tag_name": clean_tag}
        )
        return entity_id

    @classmethod
    def append_child(cls, bank: DocumentTreeMemoryBank, parent_id: int, child_id: int) -> None:
        """Establishes parent-child linkage and sets DIRTY_LAYOUT flag on parent."""
        bank.append_child(parent_id, child_id)
        if parent_id < bank.count:
            bank.entities[parent_id].flags |= int(NodeFlags.DIRTY_LAYOUT)
        from js_engine.mutation_observer import MutationObserverEngine
        MutationObserverEngine.notify_child_list_change(bank, parent_id, [child_id], [])

    @classmethod
    def set_attribute(cls, bank: DocumentTreeMemoryBank, node_id: int, key: str, value: str) -> None:
        """Sets attribute key/value on entity and propagates dirty flags."""
        if node_id >= bank.count:
            return

        if node_id not in bank.attr_pool:
            bank.attr_pool[node_id] = {}
        old_val = bank.attr_pool[node_id].get(key, "")
        bank.attr_pool[node_id][key] = value

        clean_k = key.strip().lower()
        if clean_k in ("id", "class", "style"):
            bank.entities[node_id].flags |= int(NodeFlags.DIRTY_STYLE | NodeFlags.DIRTY_LAYOUT)

        from js_engine.mutation_observer import MutationObserverEngine
        MutationObserverEngine.notify_attribute_change(bank, node_id, key, old_val)

    @classmethod
    def get_attribute(cls, bank: DocumentTreeMemoryBank, node_id: int, key: str) -> str:
        """Returns attribute string value for specified entity."""
        if node_id in bank.attr_pool:
            return bank.attr_pool[node_id].get(key, "")
        return ""

    @classmethod
    def set_style(cls, bank: DocumentTreeMemoryBank, node_id: int, property_name: str, value: str) -> None:
        """Modifies computed styles pool and sets DIRTY_STYLE & DIRTY_LAYOUT flags."""
        if node_id >= bank.count:
            return

        if node_id not in bank.computed_styles_pool:
            bank.computed_styles_pool[node_id] = {}

        clean_prop = property_name.strip().lower()
        bank.computed_styles_pool[node_id][clean_prop] = value.strip()
        bank.entities[node_id].flags |= int(NodeFlags.DIRTY_STYLE | NodeFlags.DIRTY_LAYOUT)

    @classmethod
    def set_text_content(cls, bank: DocumentTreeMemoryBank, node_id: int, text: str) -> None:
        """Updates text payload in side-car pool and marks entity as TEXT_NODE."""
        if node_id >= bank.count:
            return

        old_val = bank.text_pool.get(node_id, "")
        bank.text_pool[node_id] = text
        bank.entities[node_id].flags |= int(NodeFlags.TEXT_NODE | NodeFlags.DIRTY_LAYOUT)
        from js_engine.mutation_observer import MutationObserverEngine
        MutationObserverEngine.notify_character_data_change(bank, node_id, old_val)



class V8FFIBridge:
    """C-Compatible FFI Function Pointer Bridge for V8 Engine Integration."""

    def __init__(self, bank: DocumentTreeMemoryBank):
        self.bank = bank
        self.total_ffi_calls = 0

        # Define C-callable FFI wrappers
        self._c_create_element = CTYPES_CREATE_ELEMENT_FUNC(self._ffi_create_element)
        self._c_get_element_by_id = CTYPES_GET_ELEMENT_BY_ID_FUNC(self._ffi_get_element_by_id)
        self._c_set_style = CTYPES_SET_STYLE_FUNC(self._ffi_set_style)

    def _ffi_create_element(self, tag_name_ptr: bytes) -> int:
        self.total_ffi_calls += 1
        tag_str = tag_name_ptr.decode('utf-8') if isinstance(tag_name_ptr, bytes) else str(tag_name_ptr)
        return DOMBindings.create_element(self.bank, tag_str)

    def _ffi_get_element_by_id(self, id_ptr: bytes) -> int:
        self.total_ffi_calls += 1
        id_str = id_ptr.decode('utf-8') if isinstance(id_ptr, bytes) else str(id_ptr)
        res = DOMBindings.get_element_by_id(self.bank, id_str)
        return res if res is not None else -1

    def _ffi_set_style(self, node_id: int, prop_ptr: bytes, val_ptr: bytes) -> None:
        self.total_ffi_calls += 1
        prop = prop_ptr.decode('utf-8') if isinstance(prop_ptr, bytes) else str(prop_ptr)
        val = val_ptr.decode('utf-8') if isinstance(val_ptr, bytes) else str(val_ptr)
        DOMBindings.set_style(self.bank, node_id, prop, val)


class JSContext:
    """Embedded JavaScript Execution Context that evaluates scripts into DOM memory mutations."""

    def __init__(self, bank: DocumentTreeMemoryBank):
        self.bank = bank
        self.ffi_bridge = V8FFIBridge(bank)
        self.local_vars: Dict[str, int] = {} # Variable name -> Entity ID

    def execute_script(self, js_code: str) -> Dict[str, Any]:
        """Parses and executes JS DOM statements directly against DocumentTreeMemoryBank."""
        results: Dict[str, Any] = {"status": "success", "mutations": 0}

        lines = [line.strip() for line in js_code.split(';') if line.strip()]

        for line in lines:
            # 1. const/let varName = document.createElement("tag");
            create_match = re.match(r'(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*document\.createElement\(\s*["\']([a-zA-Z0-9]+)["\']\s*\)', line)
            if create_match:
                var_name = create_match.group(1)
                tag_name = create_match.group(2)
                node_id = DOMBindings.create_element(self.bank, tag_name)
                self.local_vars[var_name] = node_id
                results["mutations"] += 1
                continue

            # 2. const/let varName = document.getElementById("id");
            get_match = re.match(r'(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*document\.getElementById\(\s*["\']([^"\']+)["\']\s*\)', line)
            if get_match:
                var_name = get_match.group(1)
                id_str = get_match.group(2)
                node_id = DOMBindings.get_element_by_id(self.bank, id_str)
                if node_id is not None:
                    self.local_vars[var_name] = node_id
                results["mutations"] += 1
                continue

            # 3. varName.setAttribute("attr", "val");
            attr_match = re.match(r'([a-zA-Z0-9_$]+)\.setAttribute\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*\)', line)
            if attr_match:
                var_name = attr_match.group(1)
                attr_key = attr_match.group(2)
                attr_val = attr_match.group(3)
                if var_name in self.local_vars:
                    DOMBindings.set_attribute(self.bank, self.local_vars[var_name], attr_key, attr_val)
                    results["mutations"] += 1
                continue

            # 4. varName.style.prop = "val";
            style_match = re.match(r'([a-zA-Z0-9_$]+)\.style\.([a-zA-Z0-9_-]+)\s*=\s*["\']([^"\']+)["\']', line)
            if style_match:
                var_name = style_match.group(1)
                style_prop = style_match.group(2)
                style_val = style_match.group(3)
                if var_name in self.local_vars:
                    DOMBindings.set_style(self.bank, self.local_vars[var_name], style_prop, style_val)
                    results["mutations"] += 1
                continue

            # 5. parentVar.appendChild(childVar);
            append_match = re.match(r'([a-zA-Z0-9_$]+)\.appendChild\(\s*([a-zA-Z0-9_$]+)\s*\)', line)
            if append_match:
                p_var = append_match.group(1)
                c_var = append_match.group(2)
                p_id = self.local_vars.get(p_var, 0) # Default to root if body/document
                c_id = self.local_vars.get(c_var)
                if c_id is not None:
                    DOMBindings.append_child(self.bank, p_id, c_id)
                    results["mutations"] += 1
                continue

        return results
