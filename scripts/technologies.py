"""Verify portfolio technologies from pinned source. Repository evidence stays private."""
import base64
from collections import defaultdict
import json
from pathlib import PurePosixPath
import re
from urllib.parse import quote


REVISION = 2
PROFILE = "skill-aura-official/skill-aura-official"
GROUPS = (
    ("💻", "Languages"),
    ("🎨", "Frontend & UI"),
    ("🔌", "Backend & APIs"),
    ("🗄️", "Databases & Storage"),
    ("🧠", "AI, ML & Inference"),
    ("🎥", "Video & Camera Systems"),
    ("📦", "Infrastructure & Delivery"),
    ("🧪", "Development & Testing"),
)
LANGUAGES = {
    "Python": {".py"}, "JavaScript": {".js", ".jsx", ".cjs", ".mjs"},
    "TypeScript": {".ts", ".tsx"}, "HTML": {".html", ".htm"},
    "CSS": {".css"}, "SCSS": {".scss"}, "SQL": {".sql"},
    "PowerShell": {".ps1", ".psm1"}, "Shell": {".sh", ".bash"},
    "Batchfile": {".bat", ".cmd"}, "Go": {".go"}, "Rust": {".rs"},
    "Java": {".java"}, "Kotlin": {".kt", ".kts"}, "C": {".c", ".h"},
    "C++": {".cpp", ".cxx", ".hpp"}, "C#": {".cs"}, "PHP": {".php"},
    "Ruby": {".rb"}, "Swift": {".swift"}, "Dart": {".dart"},
}
RULES = {
    1: {
        "React": r"['\"]react(?:/[^'\"]+)?['\"]|\bReactDOM\.",
        "Next.js": r"from\s+['\"]next(?:/|['\"])|\bnext (?:build|start|dev)\b",
        "Vue": r"from\s+['\"]vue['\"]|<script setup",
        "Svelte": r"from\s+['\"]svelte(?:/|['\"])", "Angular": r"from\s+['\"]@angular/",
        "Vite": r"from\s+['\"]vite['\"]|\bvite (?:build|preview)\b",
        "Tailwind CSS": r"@tailwind (?:base|components|utilities)|@import ['\"]tailwindcss|@tailwindcss/(?:vite|postcss)",
        "Bootstrap": r"from\s+['\"]bootstrap|bootstrap(?:\.bundle)?(?:\.min)?\.css",
        "React Router": r"['\"]react-router(?:-dom)?['\"]",
        "Radix UI": r"['\"]@radix-ui/", "Lucide": r"['\"]lucide-(?:react|vue-next)['\"]",
        "Framer Motion": r"['\"](?:framer-motion|motion/react)['\"]",
        "Recharts": r"['\"]recharts['\"]", "Chart.js": r"['\"](?:react-chartjs-2|chart\.js(?:/auto)?)['\"]",
        "D3.js": r"['\"]d3(?:-[a-z-]+)?['\"]", "Leaflet": r"['\"](?:react-leaflet|leaflet)['\"]",
        "TanStack Query": r"['\"]@tanstack/(?:react|vue)-query['\"]",
        "Zustand": r"['\"]zustand(?:/[^'\"]+)?['\"]",
        "React Hook Form": r"['\"]react-hook-form['\"]",
        "React Icons": r"['\"]react-icons/[^'\"]+['\"]",
        "Three.js": r"['\"](?:three(?:/[^'\"]+)?|@react-three/fiber)['\"]",
        "Jinja": r"(?:from|import)\s+jinja2\b|\bJinja2Templates\(",
        "Streamlit": r"(?:from|import)\s+streamlit\b|\bstreamlit run\b",
    },
    2: {
        "Node.js": r"(?:from\s+|require\()['\"]node:|\bnode (?:--[\w-]+\s+)*[\w./-]+\.(?:js|cjs|mjs)\b",
        "Express": r"['\"]express['\"]\s*\)?[;\n]|\bexpress\.Router\(",
        "FastAPI": r"(?:from|import)\s+fastapi\b|\bFastAPI\(",
        "Flask": r"(?:from|import)\s+flask\b|\bFlask\(",
        "Django": r"(?:from|import)\s+django(?:\.|\s)", "Uvicorn": r"(?:from|import)\s+uvicorn\b|\buvicorn [\w.-]+:[\w.]+",
        "Fastify": r"['\"]fastify['\"]\s*\)?[;\n]", "NestJS": r"['\"]@nestjs/",
        "REST APIs": r"\b(?:app|router|api)\.(?:get|post|put|patch|delete)\(\s*['\"]/[^'\"]",
        "OpenAPI": r"(?m)^\s*(?:\"openapi\"|openapi):\s*['\"]?3\.[01]\.",
        "GraphQL": r"\bgraphql\s*`|['\"](?:graphql|@apollo/client)['\"]|(?:from|import)\s+(?:graphql|strawberry)\b|/graphql['\"]",
        "WebSockets": r"\b(?:new WebSocket|WebSocketServer|WebSocketRoute)\(|['\"]ws['\"]\s*\)?[;\n]|\.websocket\(",
        "Socket.IO": r"['\"]socket\.io(?:-client)?['\"]\s*\)?[;\n]|(?:from|import)\s+socketio\b",
        "gRPC": r"(?:from|import)\s+grpc\b|from\s+['\"]@grpc/",
        "Pydantic": r"(?:from|import)\s+pydantic(?:\b|_)",
        "Zod": r"['\"]zod['\"]\s*\)?[;\n]",
        "OAuth": r"\b(?:OAuth2PasswordBearer|OAuth2Session|OAuthProvider)\(|['\"](?:passport-oauth2|@auth/core)['\"]",
        "JWT": r"['\"]jsonwebtoken['\"]|(?:from|import)\s+(?:jwt|jose)\b",
        "Axios": r"(?:from\s+|require\()['\"]axios['\"]",
        "HTTPX": r"(?:from|import)\s+httpx\b",
        "Requests": r"(?:from|import)\s+requests\b",
        "aiohttp": r"(?:from|import)\s+aiohttp\b",
        "bcrypt": r"(?:from|import)\s+bcrypt\b|(?:from\s+|require\()['\"]bcrypt(?:js)?['\"]",
        "Python Cryptography": r"(?:from|import)\s+cryptography\b",
    },
    3: {
        "MySQL": r"['\"]mysql2(?:/promise)?['\"]\s*\)?[;\n]|(?:from|import)\s+(?:mysql\.connector|pymysql)\b|\bimage:\s*mysql:",
        "MariaDB": r"['\"]mariadb['\"]|\bimage:\s*mariadb:",
        "SQLite": r"(?:from|import)\s+sqlite3\b|['\"](?:better-sqlite3|node:sqlite|sqlite3)['\"]\s*\)?[;\n]",
        "PostgreSQL": r"['\"](?:pg|postgres)['\"]\s*\)?[;\n]|(?:from|import)\s+(?:psycopg2?|asyncpg)\b|\bimage:\s*postgres:",
        "Supabase": r"['\"]@supabase/(?:supabase-js|ssr)['\"]|(?:from|import)\s+supabase\b",
        "Redis": r"['\"](?:redis|ioredis)['\"]\s*\)?[;\n]|(?:from|import)\s+redis\b|\bimage:\s*redis:",
        "MongoDB": r"['\"](?:mongodb|mongoose)['\"]\s*\)?[;\n]|(?:from|import)\s+pymongo\b|\bimage:\s*mongo:",
        "Firebase": r"['\"]firebase(?:-admin)?/|(?:from|import)\s+firebase_admin\b",
        "Amazon S3": r"['\"]@aws-sdk/client-s3['\"]|\b(?:client|resource)\(['\"]s3['\"]",
        "SQLAlchemy": r"(?:from|import)\s+sqlalchemy\b", "Prisma": r"['\"]@prisma/client['\"]|(?m:^datasource\s+\w+\s*\{)",
        "Drizzle ORM": r"['\"]drizzle-orm(?:/[^'\"]+)?['\"]",
        "Microsoft Excel": r"['\"](?:exceljs|xlsx)['\"]\s*\)?[;\n]|(?:from|import)\s+(?:openpyxl|xlsxwriter)\b|spreadsheetml\.sheet",
    },
    4: {
        "PyTorch": r"(?:from|import)\s+torch\b",
        "ONNX Runtime": r"(?:from|import)\s+onnxruntime\b|['\"]onnxruntime-(?:node|web)['\"]",
        "NumPy": r"(?:from|import)\s+numpy\b", "Pandas": r"(?:from|import)\s+pandas\b",
        "Pillow": r"(?:from|import)\s+PIL\b", "scikit-learn": r"(?:from|import)\s+sklearn\b",
        "TensorFlow": r"(?:from|import)\s+(?:tensorflow|keras)\b",
        "YOLO": r"from\s+ultralytics\s+import[^\n]*\bYOLO\b|\bultralytics\.YOLO\(",
        "YOLOX": r"(?:from|import)\s+yolox\b|\byolox[-_]?[snmtlx]\b",
        "Qwen": r"\bQwen[23](?:[.-][\w.\-]+)+",
        "llama.cpp": r"\bllama-(?:server|cli)\b|(?:from|import)\s+llama_cpp\b",
        "OpenAI-compatible API": r"/v1/chat/completions\b",
        "OpenAI SDK": r"(?:from|import)\s+openai\b|(?:from\s+|require\()['\"]openai['\"]",
        "Anthropic SDK": r"(?:from|import)\s+anthropic\b|['\"]@anthropic-ai/sdk['\"]",
        "Hugging Face Transformers": r"(?:from|import)\s+transformers\b",
        "Ollama": r"(?:from|import)\s+ollama\b|\bollama (?:serve|run)\b",
        "Tesseract": r"(?:from|import)\s+pytesseract\b|\btesseract\s+.*?--psm",
        "EasyOCR": r"(?:from|import)\s+easyocr\b", "PaddleOCR": r"(?:from|import)\s+paddleocr\b",
    },
    5: {
        "OpenCV": r"(?:from|import)\s+cv2\b|\bcv2\.(?:imread|VideoCapture|dnn)\b",
        "FFmpeg": r"\bffmpeg\s+-(?:i|y|nostdin|hide_banner)\b|\bffmpeg\s+['\"-]|['\"]ffmpeg(?:\.exe)?['\"]",
        "MediaMTX": r"\bmediamtx(?:\.exe|\.ya?ml|\b.*?--)",
        "ONVIF": r"(?:from|import)\s+onvif\b|['\"](?:onvif|node-onvif)['\"]|www\.onvif\.org/ver",
        "RTSP": r"\brtsps?://|\b-rtsp_transport\b",
        "HLS": r"['\"]hls\.js['\"]|\b\.m3u8\b|application/vnd\.apple\.mpegurl",
        "WebRTC": r"\bRTCPeerConnection\b|\b(?:webrtc|WebRTC)(?:Address|LocalUDPAddress)\b|/whep\b",
        "PyAV": r"\bav\.open\(",
    },
    6: {
        "Docker": r"(?m:^\s*FROM\s+\S+)|\bdocker (?:build|run)\b",
        "Docker Compose": r"(?m:^services:\s*$)|\bdocker[- ]compose (?:up|down|build)\b",
        "GitHub Actions": r"(?m:^\s*- uses:\s+actions/)",
        "GitLab CI": r"(?m:^stages:\s*$)",
        "Nginx": r"\bproxy_pass\s+https?://|nginx:[\w.-]+",
        "Caddy": r"(?m:^\s*reverse_proxy\s+\S+)",
        "systemd": r"(?m:^\[Service\]\s*$)|\bsystemctl (?:enable|restart|start)\b",
        "SSH": r"\bssh(?:\.exe)?\s+(?:-[NL]|-o\s+)|\bStrictHostKeyChecking\b",
        "Tailscale": r"\btailscale (?:status|up|serve|ip)\b",
        "Vercel": r"\bvercel (?:deploy|build)\b|vercel\.com/schemas/vercel\.json",
        "Netlify": r"(?m:^\[build\]\s*$).*?publish\s*=",
        "Kubernetes": r"(?m:^apiVersion:\s+apps/v1)|\bkubectl (?:apply|get|rollout)\b",
        "Terraform": r"(?m:^\s*terraform\s*\{|^resource\s+\"[a-z]+_)",
        "Ansible": r"(?m:^\s*-\s+(?:name:.*\n\s+)?hosts:\s+\S+)",
    },
    7: {
        "Git": r"\bgit (?:rev-parse|clone|fetch|diff)\b",
        "npm": r"\bnpm (?:ci|install|run|test)\b", "pnpm": r"\bpnpm (?:install|run|test)\b",
        "Yarn": r"\byarn (?:install|build|test)\b",
        "pip": r"\bpip(?:3)? install\b|python(?:3)? -m pip\b",
        "pytest": r"(?:from|import)\s+pytest\b|\bpytest\s+(?:-|tests)",
        "Python unittest": r"(?:from|import)\s+unittest\b|python(?:3)? -m unittest\b",
        "Playwright": r"(?:from|import)\s+playwright\b|['\"](?:@playwright/test|playwright(?:-core)?)['\"]",
        "Vitest": r"['\"]vitest(?:/[^'\"]+)?['\"]\s*\)?[;\n]|\bvitest run\b",
        "Jest": r"['\"]@jest/globals['\"]|\bjest --",
        "Cypress": r"\bcy\.(?:visit|intercept)\(|\bcypress run\b",
        "Node.js test runner": r"['\"]node:test['\"]|\bnode --test\b",
        "Testing Library": r"['\"]@testing-library/",
        "ESLint": r"['\"](?:@eslint/js|eslint-config-[^'\"]+)['\"]|\beslint (?:\.|--)",
        "Ruff": r"\bruff (?:check|format)\b|(?m:^\[tool\.ruff\])",
        "PostCSS": r"['\"](?:postcss|autoprefixer)['\"]\s*\)?[;\n]",
        "Webpack": r"['\"]webpack['\"]\s*\)?[;\n]|\bwebpack --",
    },
}
PATTERNS = {
    name: re.compile(pattern, re.I)
    for rules in RULES.values()
    for name, pattern in rules.items()
}
CONFIG_ONLY = {
    "Docker Compose", "GitHub Actions", "GitLab CI", "Nginx", "Caddy",
    "Vercel", "Netlify", "Kubernetes", "Terraform", "Ansible",
}
ALLOWED = [{*LANGUAGES}, *(set(RULES[index]) for index in range(1, len(GROUPS)))]
EXTENSIONS = {extension for extensions in LANGUAGES.values() for extension in extensions}
CONFIG_NAMES = {
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "pyproject.toml",
    "uv.lock", "poetry.lock", "pipfile", "pipfile.lock", "go.mod", "cargo.toml",
    "gemfile", "composer.json", "pom.xml", "nginx.conf", "caddyfile",
    "vercel.json", "netlify.toml", ".gitlab-ci.yml", "makefile", "openapi.json",
}
SKIP = {
    ".git", ".venv", "node_modules", "vendor", "dist", "build", "coverage", "fixtures",
    "samples", "examples", "snapshots", "docs", "evidence", "recordings", "media",
}
CONFIG_SUFFIXES = {".yml", ".yaml", ".toml", ".ini", ".conf", ".service", ".tf"}
MANIFEST_NAMES = {"package.json", "pyproject.toml", "pipfile", "go.mod", "cargo.toml", "gemfile", "composer.json", "pom.xml"}
LOCK_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "pipfile.lock"}


def eligible(path):
    parts = PurePosixPath(path.lower()).parts
    return not (set(parts[:-1]) & SKIP or parts[-1].startswith(".env")
                or ".min." in parts[-1] or parts[-1].endswith(".d.ts"))


def bucket(path):
    name = PurePosixPath(path.lower()).name
    suffix = PurePosixPath(name).suffix
    if name in CONFIG_NAMES or name.startswith(("dockerfile", "requirements")) or suffix in CONFIG_SUFFIXES:
        return "configuration"
    if suffix in EXTENSIONS:
        group = "/".join(path.lower().split("/")[:2]) if "/" in path else "root"
        return suffix, group
    return None


def pick_files(entries):
    groups = defaultdict(list)
    for item in entries:
        key = bucket(item["path"])
        max_size = 524_288 if item["path"].lower().endswith(("openapi.json", "openapi.yaml", "openapi.yml")) else 128_000
        if key and 0 < item.get("size", 0) <= max_size:
            groups[key].append(item)
    config = groups.pop("configuration", [])
    chosen = sorted(config, key=lambda item: (item["path"].count("/"), item["path"]))[:56]
    for group in groups.values():
        group.sort(key=lambda item: (item["path"].count("/"), -item["size"], item["path"]))
    while groups and len(chosen) < 144:
        for key, items in list(groups.items()):
            chosen.append(items.pop(0))
            if not items:
                del groups[key]
            if len(chosen) >= 144:
                break
    return chosen


def source_blobs(api, name, head, items):
    owner, repository = name.split("/", 1)
    for offset in range(0, len(items), 16):
        batch = items[offset:offset + 16]
        expressions = {
            f"file{index}": f"{head}:{item['path']}"
            for index, item in enumerate(batch)
        }
        fields = " ".join(f"{key}:object(expression:${key}){{...on Blob{{isBinary text}}}}" for key in expressions)
        variables = ", ".join(f"${key}:String!" for key in expressions)
        query = f"query($owner:String!, $name:String!, {variables}){{repository(owner:$owner,name:$name){{{fields}}}}}"
        try:
            blobs = api.graph(query, owner=owner, name=repository, **expressions)["repository"] or {}
        except Exception as exc:
            # Fine-grained credentials may permit REST Contents but restrict GraphQL.
            if getattr(exc, "status", None) not in (401, 403, "FORBIDDEN", "query error"):
                raise
            blobs = {}
        for index, item in enumerate(batch):
            blob = blobs.get(f"file{index}")
            if blob is None:
                encoded = api.request(f"repos/{name}/git/blobs/{item['sha']}")
                yield item["path"], base64.b64decode(encoded["content"]).decode("utf-8", errors="replace")
            elif not blob["isBinary"] and blob["text"] is not None:
                yield item["path"], blob["text"]


def inspect_repo(api, repo, head):
    name = repo["full_name"]
    prefix = f"repos/{name}"
    tree = api.request(prefix + "/git/trees/" + quote(head, safe=""), {"recursive": "1"})
    languages = api.request(prefix + "/languages")
    entries = [item for item in tree["tree"] if item["type"] == "blob" and eligible(item["path"])]
    evidence = defaultdict(set)
    hints = defaultdict(set)
    for language, extensions in LANGUAGES.items():
        paths = [item["path"] for item in entries if PurePosixPath(item["path"].lower()).suffix in extensions]
        if paths and (languages.get(language) or language in {"SQL", "Shell", "PowerShell", "HTML", "CSS"}):
            evidence[language].update(paths[:3])
    selected = pick_files(entries)
    for path, source in source_blobs(api, name, head, selected):
        filename = PurePosixPath(path.lower()).name
        if filename == "package.json":
            try:
                package = json.loads(source)
            except (ValueError, TypeError):
                continue
            for field in ("dependencies", "devDependencies", "optionalDependencies"):
                hints[path].update(package.get(field, {}).keys())
            source = "\n".join(package.get("scripts", {}).values())
        elif filename in MANIFEST_NAMES or filename.startswith("requirements"):
            hints[path].update(re.findall(r"(?m)^\s*([A-Za-z][\w.-]{1,48})\s*(?:[=<>~!]|\[)", source))
            continue
        elif filename in LOCK_NAMES:
            continue
        for technology, pattern in PATTERNS.items():
            if technology == "Docker" and not filename.startswith("dockerfile") and not re.search(r"\bdocker (?:build|run)\b", source):
                continue
            if technology in CONFIG_ONLY and bucket(path) != "configuration":
                continue
            if pattern.search(source):
                evidence[technology].add(path)
    return {
        "commit": head, "status": "PARTIAL" if tree.get("truncated") else "VERIFIED",
        "archived": repo.get("archived", False), "languages": languages,
        "eligible_paths": len(entries), "sampled_paths": len(selected),
        "technology_paths": {key: sorted(paths) for key, paths in sorted(evidence.items())},
        "manifest_candidates": {path: sorted(names) for path, names in sorted(hints.items())},
        "lockfiles": {item["path"]: item["sha"] for item in entries if PurePosixPath(item["path"].lower()).name in LOCK_NAMES},
    }


def collect(sources, previous=None):
    previous = previous or {}
    old = previous.get("repositories", {})
    result = {}
    for repo, api in sources:
        ident = str(repo["id"])
        prior = old.get(ident, {})
        head = repo.get("branch_heads", {}).get(repo.get("default_branch"))
        if repo["full_name"].casefold() == PROFILE:
            # Exclude the profile collector and generated snapshots from portfolio technology.
            continue
        if (previous.get("revision") == REVISION and api is not None and head
                and prior.get("status") == "VERIFIED" and prior["commit"] == head):
            result[ident] = {**prior, "archived": repo.get("archived", False)}
        elif api is None or not head:
            result[ident] = {**prior, "status": "UNKNOWN"}
        else:
            try:
                result[ident] = inspect_repo(api, repo, head)
            except Exception as exc:
                status = getattr(exc, "status", None)
                if status is None:
                    raise
                result[ident] = {**prior, "status": "UNKNOWN", "failure": str(status)}
    return {"revision": REVISION, "repositories": result}


def public_rows(inventory):
    repositories = (inventory or {}).get("repositories", {})
    current, archived = set(), set()
    for repo in repositories.values():
        target = archived if repo.get("archived") else current
        target.update(repo.get("technology_paths", {}))
    rows = [f"**{icon} {title}**<br>\n" + " ".join(f"`{name}`" for name in sorted(known & current, key=str.casefold))
            for (icon, title), known in zip(GROUPS, ALLOWED) if known & current]
    historical = sorted(set().union(*ALLOWED) & (archived - current), key=str.casefold)
    if historical:
        rows.extend(["<details><summary>Technologies verified in archived projects</summary>", "",
                     " ".join(f"`{name}`" for name in historical), "", "</details>"])
    if not repositories:
        rows.append("Technology verification is pending.")
    elif any(repo["status"] != "VERIFIED" for repo in repositories.values()):
        rows.append("Some repository evidence is unavailable. Previously verified technologies remain listed.")
    return rows
