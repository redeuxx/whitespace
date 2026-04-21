import json
import re

# Mapping from Pygments lexer aliases to highlight.js language names
PYGMENTS_TO_HLJS = {
    'python': 'python', 'python3': 'python', 'py': 'python',
    'javascript': 'javascript', 'js': 'javascript',
    'typescript': 'typescript', 'ts': 'typescript',
    'html': 'html', 'xml': 'xml',
    'css': 'css', 'scss': 'scss', 'sass': 'scss',
    'java': 'java', 'kotlin': 'kotlin',
    'c': 'c', 'cpp': 'cpp', 'c++': 'cpp',
    'csharp': 'csharp', 'c#': 'csharp',
    'go': 'go', 'golang': 'go',
    'rust': 'rust',
    'ruby': 'ruby', 'rb': 'ruby',
    'php': 'php',
    'swift': 'swift',
    'bash': 'shell', 'sh': 'shell', 'shell': 'shell',
    'powershell': 'powershell', 'ps1': 'powershell',
    'sql': 'sql',
    'json': 'json',
    'yaml': 'yaml', 'yml': 'yaml',
    'toml': 'ini',
    'markdown': 'markdown', 'md': 'markdown',
    'dockerfile': 'dockerfile',
    'makefile': 'makefile',
    'lua': 'lua',
    'perl': 'perl',
    'r': 'r',
    'scala': 'scala',
    'haskell': 'haskell',
    'elixir': 'elixir',
    'erlang': 'erlang',
    'clojure': 'clojure',
    'dart': 'dart',
    'vim': 'vim',
    'nginx': 'nginx',
    'apache': 'apache',
    'ini': 'ini', 'cfg': 'ini',
    'diff': 'diff', 'patch': 'diff',
    'latex': 'latex', 'tex': 'latex',
    'text': 'plaintext', 'plain': 'plaintext',
    'gas': 'x86asm', 'asm': 'x86asm', 'nasm': 'x86asm',
}

HLJS_LANGUAGES = sorted({
    'plaintext', 'python', 'javascript', 'typescript', 'html', 'xml',
    'css', 'scss', 'java', 'kotlin', 'c', 'cpp', 'csharp', 'go',
    'rust', 'ruby', 'php', 'swift', 'shell', 'powershell', 'sql',
    'json', 'yaml', 'ini', 'markdown', 'dockerfile', 'makefile',
    'lua', 'perl', 'r', 'scala', 'haskell', 'elixir', 'erlang',
    'clojure', 'dart', 'vim', 'nginx', 'apache', 'diff', 'latex',
    'x86asm',
})


def _pygments_detect(text):
    """Score curated Pygments lexers and return the best hljs name, or None."""
    from pygments.lexers import get_lexer_by_name
    from pygments.util import ClassNotFound

    best_score = 0.0
    best_hljs = None
    seen_classes = set()

    for pygments_name, hljs_name in PYGMENTS_TO_HLJS.items():
        if hljs_name == 'plaintext':
            continue
        try:
            lexer = get_lexer_by_name(pygments_name)
        except ClassNotFound:
            continue
        cls = type(lexer)
        if cls in seen_classes:
            continue
        seen_classes.add(cls)
        score = cls.analyse_text(text)

        # PythonLexer.analyse_text returns 1.0 for any content containing
        # 'import ', which causes false positives for Go, Java, Swift, etc.
        # Only trust its score when there is an actual Python shebang.
        if hljs_name == 'python' and score > 0:
            if not re.search(r'python', text[:50]):
                score = 0.0

        if score > best_score:
            best_score = score
            best_hljs = hljs_name

    return best_hljs if best_score >= 0.1 else None


def _manual_detect(text):
    """
    Pattern-based fallback for languages Pygments has no heuristics for.
    Each check requires multiple independent signals to reduce false positives.
    Ordered from most-specific to least-specific within ambiguous language groups.
    """
    M = re.MULTILINE

    # JSON — parse-based, unambiguous
    stripped = text.strip()
    if stripped and stripped[0] in ('{', '['):
        try:
            json.loads(stripped)
            return 'json'
        except (ValueError, json.JSONDecodeError):
            pass

    # SQL — require compound statement starters anchored to line beginnings;
    # bare keywords like SELECT/FROM/TABLE are common React/MUI component names in TSX
    if re.search(
        r'^\s*(SELECT\s+[\w*]|INSERT\s+INTO\s+\w|DELETE\s+FROM\s+\w|'
        r'CREATE\s+TABLE\s+\w|DROP\s+TABLE\s+\w|ALTER\s+TABLE\s+\w|'
        r'UPDATE\s+\w+\s+SET\s+\w)',
        text, re.IGNORECASE | re.MULTILINE
    ):
        return 'sql'

    # Dockerfile
    if re.search(r'^FROM\s+\S+', text, M) and \
       re.search(r'^(RUN|CMD|COPY|ADD|EXPOSE|ENV|ENTRYPOINT)\b', text, M):
        return 'dockerfile'

    # Python (no shebang) — requires Python-specific patterns not shared with other languages
    if (re.search(r'\bdef\s+\w+\s*\(self[,)]', text) or
        re.search(r'if\s+__name__\s*==\s*["\']__main__["\']', text) or
        re.search(r'@(classmethod|staticmethod|property)\b', text)) and \
       re.search(r'\bdef\s+\w+\s*\(', text):
        return 'python'

    # Assembly — must run before C/C++ because GAS-syntax assembly files often
    # use #include for macro headers (e.g. RISC-V/ARM test suites).
    # .section/.globl at line-start are essentially exclusive to assemblers;
    # two or more GAS pseudo-op directives is a reliable signal.
    _ASM_DIRECTIVES = r'^\s*\.(section|text|data|bss|global|globl|macro|endm|align|balign|byte|word|long|quad|fill|skip|space|zero|equ|set|type|size|string|asciz|ascii)\b'
    if re.search(_ASM_DIRECTIVES, text, M):
        if re.search(r'^\s*\.(macro|endm)\b', text, M) or \
           len(re.findall(_ASM_DIRECTIVES, text, M)) >= 2:
            return 'x86asm'

    # C / C++ — #include is unique to the C family; check before CSS/SCSS
    if re.search(r'^#include\s*[<"]', text, M):
        if re.search(r'\b(cout\b|cin\b|std::|namespace\s+\w|template\s*<|#include\s*<(iostream|vector|string|map|algorithm)>)', text):
            return 'cpp'
        return 'c'

    # Go — `package` declaration is unique to Go
    if re.search(r'^package\s+\w+', text, M) and \
       re.search(r'\bfunc\s+\w+', text):
        return 'go'

    # Rust — fn + at least one Rust-specific token
    if re.search(r'\bfn\s+\w+\s*[(<]', text) and \
       re.search(r'\b(let\s+mut|println!|impl\s+\w|use\s+std::|#\[derive)', text):
        return 'rust'

    # C# — before Java since both use `public class`
    if re.search(r'\busing\s+System[\s;]', text) or \
       (re.search(r'\bnamespace\s+\w+', text) and
        re.search(r'\bpublic\s+(class|interface|enum)\s+\w+', text)):
        return 'csharp'

    # Java — public class/interface + Java stdlib imports or System.out
    if re.search(r'\bpublic\s+(class|interface|enum)\s+\w+', text) and \
       (re.search(r'\bimport\s+java\.', text) or
        re.search(r'System\.out\.|System\.err\.', text)):
        return 'java'

    # Kotlin — `fun` keyword + val/var with type or data class
    if re.search(r'\bfun\s+\w+\s*[(<(]', text) and \
       re.search(r'\b(val|var)\s+\w+\s*[:=]|data\s+class\s+\w+', text):
        return 'kotlin'

    # Scala
    if re.search(r'\bdef\s+\w+[^:\n]*:', text) and \
       re.search(r'\b(object|trait|case\s+class)\s+\w+', text):
        return 'scala'

    # Swift — func + Swift-specific patterns
    # (?:<[^>]*>)? allows for generic type parameters between name and (
    if re.search(r'\bfunc\s+\w+(?:<[^>]*>)?\s*\(', text) and \
       re.search(r'\b(guard\s+let|if\s+let|@\w+\b|var\s+\w+\s*[:=])', text) and \
       not re.search(r'^package\s+\w+', text, M):
        return 'swift'

    # TypeScript — before JS; requires type annotations or TS-specific keywords
    if re.search(r'\b(interface|type)\s+\w+[\s{<]', text) and \
       re.search(r':\s*(string|number|boolean|any|void|never|unknown)\b', text):
        return 'typescript'
    if re.search(r':\s*(string|number|boolean)\b', text) and \
       re.search(r'\b(const|let|var)\s+\w+\s*:', text) and \
       re.search(r'\b(import|export)\b', text):
        return 'typescript'
    # TSX: React-specific TS types or JSX return with TS annotations
    if re.search(r':\s*React\.(FC|Component|ReactNode|ReactElement|CSSProperties)\b', text) or \
       (re.search(r'\b(React\.FC|JSX\.Element)\b', text) and
        re.search(r'\b(const|let|function)\s+\w+', text)):
        return 'typescript'

    # JavaScript / JSX — const/let/var + JS-specific patterns or React JSX
    if re.search(r'\b(const|let|var)\s+\w+\s*=', text) and \
       re.search(r'\b(function\s*\(|=>\s*\{|require\s*\(|module\.exports|console\.)', text):
        return 'javascript'
    # JSX without TS: React import + JSX syntax
    if re.search(r'\bfrom\s+["\']react["\']', text, re.IGNORECASE) and \
       re.search(r'return[\s(]*<[A-Z]\w*[\s/>]', text):
        return 'javascript'

    # Elixir — defmodule is unique; must come before Ruby (both use def/end)
    if re.search(r'\bdefmodule\s+\w+', text) and \
       re.search(r'\bdef\s+\w+', text):
        return 'elixir'

    # Ruby — def + end (Lua uses function, not def)
    if re.search(r'\bdef\s+\w+', text) and \
       re.search(r'\bend\b', text) and \
       re.search(r'\b(puts|require|attr_|do\s*\|)', text):
        return 'ruby'

    # Lua
    if re.search(r'\bfunction\s+\w+\s*\(', text) and \
       re.search(r'\bend\b', text) and \
       re.search(r'\b(local\s+\w+|require\s*[("\'"]|print\s*\()', text):
        return 'lua'

    # Haskell — type signatures and do-notation
    if re.search(r'::\s*\w+(\s+->\s*\w+)+', text) and \
       re.search(r'\b(module\s+\w+|import\s+Data\.|where\b)', text):
        return 'haskell'

    # Erlang — -module declaration
    if re.search(r'^-module\s*\(', text, M) and \
       re.search(r'^-export\s*\(', text, M):
        return 'erlang'

    # Clojure — S-expression with defn/def
    if re.search(r'^\s*\(def(n|module|record|protocol)?\s+', text, M):
        return 'clojure'

    # Dart
    if re.search(r'\bvoid\s+main\s*\(\s*\)', text) and \
       re.search(r'\b(print\s*\(|import\s+["\']dart:)', text):
        return 'dart'

    # PowerShell — cmdlet syntax or $variable declarations
    if re.search(r'\$\w+\s*=', text) and \
       re.search(r'\b(Write-Host|Get-|Set-|New-|Remove-|Invoke-|-Param\b|\[Parameter)', text):
        return 'powershell'

    # nginx config — before SCSS (nested braces trigger SCSS's nested-rule check)
    if re.search(r'\b(server|location|upstream)\s*\{', text) and \
       re.search(r'\b(listen|proxy_pass|root|index)\s+', text):
        return 'nginx'

    # Apache config — before Pygments fallback (Pygments scores apache config as XML)
    if re.search(r'<(VirtualHost|Directory|Location|Files)\b', text) and \
       re.search(r'\b(ServerName|DocumentRoot|AllowOverride|RewriteRule)\b', text):
        return 'apache'

    # SCSS — $variable: value syntax is the only unambiguous SCSS signal;
    # nested braces alone match C/C++/nginx/etc. so that heuristic is dropped
    if re.search(r'^\s*\$\w+\s*:', text, M):
        return 'scss'

    # CSS — selector block + at least one recognisable CSS property
    _CSS_PROPS = r'\b(color|font|margin|padding|border|background|display|width|height|position|top|left|right|bottom|flex|grid|overflow|opacity|cursor|z-index|text-|list-|box-|align-|justify-)\b'
    if re.search(r'[^\s{]+[ \t]*\{', text) and \
       re.search(_CSS_PROPS, text) and \
       re.search(r':\s*[\w#"\'(]', text) and \
       re.search(r';\s*\}', text):
        return 'css'

    # Shell/Bash — check before Markdown because backticks in shell scripts
    # (command substitution) would otherwise trigger the Markdown backtick heuristic.
    _SHELL_SHEBANG = r'^#!\s*/\S*(sh|bash|zsh|ksh|dash)\b'
    _SHELL_KEYWORDS = r'\b(fi|esac|elif|done)\b'
    _SHELL_CONSTRUCTS = r'(if\s+\[\[?|for\s+\w+\s+in\s+|while\s+\[\[?|case\s+\S+\s+in\b|\bdo\b)'
    if re.search(_SHELL_SHEBANG, text, M) or \
       (re.search(_SHELL_KEYWORDS, text) and re.search(_SHELL_CONSTRUCTS, text)):
        return 'shell'

    # Markdown — headings or list + emphasis
    if re.search(r'^#{1,6}\s+\S', text, M) and \
       re.search(r'(\*\*|__|`|\[[^\[\]]+\]\([^()]+\))', text):
        return 'markdown'

    # Makefile — tab-indented recipes
    if re.search(r'^\w[\w.\-/ ]*:', text, M) and \
       re.search(r'^\t\S', text, M):
        return 'makefile'

    # VimScript — use function! (with !) to avoid matching PHP/JS/Lua `function`;
    # plain `set`/`let g:`/mapping commands are unambiguous on their own
    if re.search(r'^(set\s+\w|let\s+[gslbwt]:\w|function!\s+\w|syntax\s+(enable|on|off)|colorscheme\s+\w)', text, M) or \
       re.search(r'^(nnoremap|vnoremap|inoremap|xnoremap|noremap|map)\b', text, M):
        return 'vim'

    # Perl
    if re.search(r'\buse\s+strict\b|\buse\s+warnings\b', text) or \
       (re.search(r'\bsub\s+\w+\s*\{', text) and
        re.search(r'\b(my|local|our)\s+[\$@%]', text)):
        return 'perl'

    # YAML — key: value structure (last resort; many config formats look like YAML)
    if re.search(r'^---', text, M) or \
       (re.search(r'^\w[\w\s]*:\s+\S', text, M) and
        re.search(r'^\s+-\s+\S', text, M)):
        return 'yaml'

    return None


def detect_language(content):
    if not content or len(content.strip()) < 10:
        return None
    text = content[:4000]

    # Assembly files often open with large comment blocks (copyright headers,
    # test-case descriptions) that push directives past the 4000-char window.
    # Scan a wider slice specifically for assembly before running other checks.
    _ASM_DIR = r'^\s*\.(section|text|data|bss|global|globl|macro|endm|align|balign|byte|word|long|quad|fill|skip|space|zero|equ|set|type|size|string|asciz|ascii)\b'
    extended = content[:16000]
    M = re.MULTILINE
    if re.search(_ASM_DIR, extended, M):
        if re.search(r'^\s*\.(macro|endm)\b', extended, M) or \
           len(re.findall(_ASM_DIR, extended, M)) >= 2:
            return 'x86asm'

    # Manual patterns run first — they are more targeted and avoid Pygments
    # false positives (e.g. Pygments scores Apache config as XML).
    # Pygments covers languages with strong textual markers (shebangs, <?php, etc.)
    # that manual detection doesn't handle.
    return _manual_detect(text) or _pygments_detect(text)
