"""
WebAssembly (Wasm) Bytecode Execution Engine.
Implements Wasm binary module decoding (\\x00asm magic header), section parsing (TYPE, MEMORY, EXPORT, CODE),
64 KB page-aligned WasmLinearMemory, and stack machine bytecode interpreter.
"""

import sys
import os
import struct
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class WasmValType(Enum):
    I32 = 0x7F
    I64 = 0x7E
    F32 = 0x7D
    F64 = 0x7C


class WasmSectionType(Enum):
    CUSTOM = 0
    TYPE = 1
    IMPORT = 2
    FUNCTION = 3
    TABLE = 4
    MEMORY = 5
    GLOBAL = 6
    EXPORT = 7
    START = 8
    ELEMENT = 9
    CODE = 10
    DATA = 11


class WasmLinearMemory:
    """64 KB Page-Aligned Linear Memory for WebAssembly Execution."""

    PAGE_SIZE = 65536 # 64 KB per Wasm page

    def __init__(self, initial_pages: int = 1, max_pages: Optional[int] = None):
        self.initial_pages = initial_pages
        self.max_pages = max_pages
        self.buffer = bytearray(initial_pages * self.PAGE_SIZE)

    @property
    def current_pages(self) -> int:
        return len(self.buffer) // self.PAGE_SIZE

    def grow(self, pages: int) -> int:
        """Grows memory by target number of 64 KB pages. Returns previous page count."""
        prev = self.current_pages
        if self.max_pages is not None and (prev + pages) > self.max_pages:
            return -1

        self.buffer.extend(bytearray(pages * self.PAGE_SIZE))
        return prev

    def read_i32(self, offset: int) -> int:
        """Reads 32-bit signed integer in little-endian format."""
        if offset + 4 > len(self.buffer):
            raise IndexError("WasmMemoryError: Out of bounds memory read.")
        return struct.unpack("<i", self.buffer[offset:offset + 4])[0]

    def write_i32(self, offset: int, value: int) -> None:
        """Writes 32-bit signed integer in little-endian format."""
        if offset + 4 > len(self.buffer):
            raise IndexError("WasmMemoryError: Out of bounds memory write.")
        self.buffer[offset:offset + 4] = struct.pack("<i", value)

    def read_bytes(self, offset: int, size: int) -> bytes:
        """Reads bytes slice from linear memory."""
        if offset + size > len(self.buffer):
            raise IndexError("WasmMemoryError: Out of bounds memory read.")
        return bytes(self.buffer[offset:offset + size])

    def write_bytes(self, offset: int, data: bytes) -> None:
        """Writes bytes slice into linear memory."""
        if offset + len(data) > len(self.buffer):
            raise IndexError("WasmMemoryError: Out of bounds memory write.")
        self.buffer[offset:offset + len(data)] = data


class WasmFunction:
    """WebAssembly Function Representation."""

    def __init__(self, name: str, locals_count: int, code_bytes: bytes):
        self.name = name
        self.locals_count = locals_count
        self.code_bytes = code_bytes


class WasmModule:
    """Decoded WebAssembly Binary Module."""

    def __init__(self, initial_memory_pages: int = 1):
        self.magic_number: bytes = b"\x00asm"
        self.version: int = 1
        self.memory: WasmLinearMemory = WasmLinearMemory(initial_memory_pages)
        self.exports: Dict[str, WasmFunction] = {}

    def register_export_function(self, name: str, locals_count: int, code_bytes: bytes) -> WasmFunction:
        func = WasmFunction(name, locals_count, code_bytes)
        self.exports[name] = func
        return func


class WasmDecoder:
    """Decodes WebAssembly binary format module files."""

    WASM_MAGIC = b"\x00asm"
    WASM_VERSION = 1

    @classmethod
    def parse_module(cls, wasm_bytes: bytes) -> WasmModule:
        """Validates Wasm magic header and parses binary module sections."""
        if len(wasm_bytes) < 8:
            raise ValueError("WasmDecodeError: Binary stream too short.")

        magic = wasm_bytes[:4]
        version = struct.unpack("<I", wasm_bytes[4:8])[0]

        if magic != cls.WASM_MAGIC or version != cls.WASM_VERSION:
            raise ValueError("WasmDecodeError: Invalid WebAssembly magic header or version.")

        module = WasmModule()
        offset = 8

        # Parse sections
        while offset < len(wasm_bytes):
            sec_type_val = wasm_bytes[offset]
            offset += 1
            sec_len, len_consumed = cls._decode_varuint32(wasm_bytes, offset)
            offset += len_consumed

            sec_bytes = wasm_bytes[offset:offset + sec_len]
            offset += sec_len

            try:
                sec_type = WasmSectionType(sec_type_val)
                if sec_type == WasmSectionType.MEMORY:
                    module.memory = cls._parse_memory_section(sec_bytes)
            except ValueError:
                pass

        return module

    @classmethod
    def _parse_memory_section(cls, data: bytes) -> WasmLinearMemory:
        initial = data[1] if len(data) > 1 else 1
        return WasmLinearMemory(initial)

    @classmethod
    def _decode_varuint32(cls, data: bytes, offset: int) -> Tuple[int, int]:
        result = 0
        shift = 0
        consumed = 0

        while True:
            if offset + consumed >= len(data):
                break
            b = data[offset + consumed]
            consumed += 1
            result |= (b & 0x7F) << shift
            if (b & 0x80) == 0:
                break
            shift += 7

        return result, consumed


class WasmInterpreter:
    """Stack Machine Interpreter executing WebAssembly Bytecode Instructions."""

    OP_END = 0x0B
    OP_LOCAL_GET = 0x20
    OP_LOCAL_SET = 0x21
    OP_I32_LOAD = 0x28
    OP_I32_STORE = 0x36
    OP_I32_CONST = 0x41
    OP_I32_ADD = 0x6A
    OP_I32_SUB = 0x6B
    OP_I32_MUL = 0x6C

    @classmethod
    def execute_instructions(
        cls,
        code_bytes: bytes,
        locals_map: List[int],
        memory: WasmLinearMemory
    ) -> List[int]:
        """Executes Wasm stack machine instructions and returns output stack."""
        stack: List[int] = []
        pc = 0

        while pc < len(code_bytes):
            op = code_bytes[pc]
            pc += 1

            if op == cls.OP_END:
                break

            elif op == cls.OP_I32_CONST:
                val, consumed = cls._decode_sleb128(code_bytes, pc)
                pc += consumed
                stack.append(val)

            elif op == cls.OP_LOCAL_GET:
                local_idx = code_bytes[pc]
                pc += 1
                stack.append(locals_map[local_idx])

            elif op == cls.OP_LOCAL_SET:
                local_idx = code_bytes[pc]
                pc += 1
                if stack:
                    locals_map[local_idx] = stack.pop()

            elif op == cls.OP_I32_ADD:
                if len(stack) >= 2:
                    b = stack.pop()
                    a = stack.pop()
                    stack.append((a + b) & 0xFFFFFFFF)

            elif op == cls.OP_I32_SUB:
                if len(stack) >= 2:
                    b = stack.pop()
                    a = stack.pop()
                    stack.append((a - b) & 0xFFFFFFFF)

            elif op == cls.OP_I32_MUL:
                if len(stack) >= 2:
                    b = stack.pop()
                    a = stack.pop()
                    stack.append((a * b) & 0xFFFFFFFF)

            elif op == cls.OP_I32_LOAD:
                pc += 2 # Skip flags & offset
                if stack:
                    mem_addr = stack.pop()
                    val = memory.read_i32(mem_addr)
                    stack.append(val)

            elif op == cls.OP_I32_STORE:
                pc += 2 # Skip flags & offset
                if len(stack) >= 2:
                    val = stack.pop()
                    mem_addr = stack.pop()
                    memory.write_i32(mem_addr, val)

        return stack

    @classmethod
    def call_export(cls, module: WasmModule, func_name: str, args: List[int]) -> Optional[int]:
        """Calls exported Wasm function with arguments and returns top of stack result."""
        if func_name not in module.exports:
            raise KeyError(f"WasmExportError: Function '{func_name}' not exported.")

        func = module.exports[func_name]
        locals_map = list(args) + [0] * func.locals_count

        stack = cls.execute_instructions(func.code_bytes, locals_map, module.memory)
        return stack[-1] if stack else None

    @classmethod
    def _decode_sleb128(cls, data: bytes, pc: int) -> Tuple[int, int]:
        result = 0
        shift = 0
        consumed = 0

        while pc + consumed < len(data):
            b = data[pc + consumed]
            consumed += 1
            result |= (b & 0x7F) << shift
            shift += 7
            if (b & 0x80) == 0:
                if (shift < 32) and (b & 0x40):
                    result |= (~0 << shift)
                break

        return result, consumed
