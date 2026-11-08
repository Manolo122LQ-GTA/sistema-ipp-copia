import os
import re
import sys
import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'IPP1'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'IPP1.settings')
django.setup()

from django.urls import reverse, NoReverseMatch

template_dir = os.path.join(os.path.dirname(__file__), 'IPP1', 'template')

# Pattern to match {% url 'name' arg1 arg2 %} or {% url "name" arg1 arg2 %}
url_pattern = re.compile(
    r"{%\s*url\s+['\"]([^'\"]+)['\"]\s*([^%]*?)\s*%}",
    re.DOTALL
)

issues = []

for root, dirs, files in os.walk(template_dir):
    for f in files:
        if f.endswith('.html'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
            for m in url_pattern.finditer(content):
                name = m.group(1)
                args_str = m.group(2).strip()
                # Parse args: simple space-separated, may include filters like |filter
                args = []
                if args_str:
                    # Simple split by whitespace, removing Django filters for arg resolution
                    # We'll just try with the raw args first
                    for arg in args_str.split():
                        # Remove leading/trailing quotes
                        arg_clean = arg.strip("'\"")
                        # If it looks like a variable name (no spaces, no operators), use it
                        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', arg_clean):
                            args.append(arg_clean)
                        else:
                            # It's a literal or expression - skip for now
                            pass
                try:
                    if args:
                        reverse(name, args=args)
                    else:
                        reverse(name)
                except NoReverseMatch as e:
                    issues.append((path, name, args, str(e)))

print('URL names usados en templates que NO se pueden reversar (con argumentos parseados):')
for path, name, args, err in issues:
    print(f'  {os.path.relpath(path, template_dir)}: {name} args={args} -> {err}')