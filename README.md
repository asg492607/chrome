# Chrome / PacketForge

PacketForge is a modular educational Internet Computing Platform and browser engine simulation implemented in Python. It models the core subsystems of the modern web stack—from low-level networking, protocols, and security models, to rendering pipelines, layout engines, JavaScript runtimes, WebAssembly, and search indexing.

---

## 🏛️ Subsystems & Architecture

1. **Browser & Chromium Engine**
   - **Parsing & DOM:** HTML parser, CSS parser, DOM tree construction.
   - **Styling & Layout:** Cascading style resolver, box model, Flexbox engine, and layout trees.
   - **Rendering & Compositing:** 2D Canvas, WebGL2, WebGPU pipelines, rasterizer, and compositor.

2. **Engines & Runtimes**
   - **JavaScript Engine:** V8 bindings simulation, event target dispatch, and mutation observers.
   - **WebAssembly Engine:** WASM interpreter and execution environment.
   - **Media Engine:** MSE video, Web Audio, Web Speech, and EME DRM pipelines.
   - **Storage Engine:** LocalStorage, SessionStorage, and IndexedDB implementations.
   - **Service Workers:** Offline caching, background sync, and lifecycle management.

3. **Networking & Protocols**
   - **Core Protocols:** DHCP server, DNS resolver, HTTP/2, HTTP/3 (QUIC), WebSocket, and WebRTC engines.
   - **Security:** TLS 1.3 cryptographic engine, CSP/CORS policy enforcement, Web Crypto, WebAuthn.
   - **Interception:** Packet crafter, reverse proxy, and ad-blocking rules engine.

4. **Search Platform**
   - **Crawler & Extraction:** Mock web content extractor and crawler.
   - **Indexing & Ranking:** Inverted index builder, TF-IDF engine, ranking, knowledge graph, and search API.

5. **Application & DevTools**
   - **Event Orchestration:** Centralized EventBus, dependency injection container, and runtime lifecycle.
   - **Developer Tools:** Chrome DevTools Protocol (CDP) engine and telemetry dashboard.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+ (tested on Python 3.10, 3.11, and 3.12)

### Installation

```bash
# Clone the repository
git clone https://github.com/asg492607/chrome.git
cd chrome

# Install dependencies in editable mode
pip install -e .
pip install pytest
```

### Running the Application

```bash
python main.py
# or
python application/packetforge.py
```

---

## 🧪 Testing

The codebase includes a comprehensive test suite covering integration and unit tests across all subsystems:

```bash
pytest
```
