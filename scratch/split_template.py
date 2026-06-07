import re
from pathlib import Path

# Paths
template_dir = Path("/home/eole/projects/papyconnect/papiconnect/app/templates")
index_path = template_dir / "index.html"
components_dir = template_dir / "components"
components_dir.mkdir(exist_ok=True)

# Read full index.html
content = index_path.read_text(encoding="utf-8")

# Let's locate landmarks using regex or simple search
# We can find landmarks in index.html and split the string:

def write_component(name, data):
    p = components_dir / name
    p.write_text(data, encoding="utf-8")
    print(f"Wrote component: {p.relative_to(template_dir)}")

# 1. Head (up to body start)
head_end_idx = content.find('<body')
head_content = content[:head_end_idx]
# Remove <!DOCTYPE html> and <html ...> and <head> to keep it clean, but let's keep everything inside <head>...</head>
# Let's extract between <head> and </head>
head_inner = re.search(r'<head>(.*?)</head>', head_content, re.DOTALL).group(1).strip()
write_component("head.html", head_inner)

# 2. Header
header_match = re.search(r'<!-- ══════════════ HEADER ══════════════ -->(.*?)<!-- ══════════════ MAIN ══════════════ -->', content, re.DOTALL)
header_content = header_match.group(1).strip()
write_component("header.html", header_content)

# 3. Toast (inside MAIN, search for x-show="toast")
toast_match = re.search(r'<!-- Toast / notification -->(.*?)<!-- Split Pane Layout -->', content, re.DOTALL)
toast_content = toast_match.group(1).strip()
write_component("toast.html", toast_content)

# 4. Wizard (left panel)
wizard_match = re.search(r'<!-- WIZARD \(Left Panel\) -->(.*?)<!-- CONFIGURED ACTIONS \(Right Panel\) -->', content, re.DOTALL)
# Keep the enclosing <section ...> for wizard
wizard_content = "<!-- WIZARD (Left Panel) -->\n" + wizard_match.group(1).strip()
write_component("wizard.html", wizard_content)

# 5. Actions (right panel)
actions_match = re.search(r'<!-- CONFIGURED ACTIONS \(Right Panel\) -->(.*?)<!-- IoT REGISTRY', content, re.DOTALL)
# Keep the enclosing <section ...> for actions
actions_content = "<!-- CONFIGURED ACTIONS (Right Panel) -->\n" + actions_match.group(1).strip()
write_component("actions.html", actions_content)

# 6. Registry (bottom pane)
registry_match = re.search(r'<!-- IoT REGISTRY \(Registry Bottom Pane\) -->(.*?)<!-- Device Details Modal', content, re.DOTALL)
registry_content = "<!-- IoT REGISTRY (Registry Bottom Pane) -->\n" + registry_match.group(1).strip()
write_component("registry.html", registry_content)

# 7. Modals (from Device Details Modal up to FOOTER)
modals_match = re.search(r'<!-- Device Details Modal.*?-->(.*?)<!-- ══════════════ FOOTER ══════════════ -->', content, re.DOTALL)
modals_content = modals_match.group(1).strip()
write_component("modals.html", modals_content)

# 8. Footer
footer_match = re.search(r'<!-- ══════════════ FOOTER ══════════════ -->(.*?)<!-- ══════════════ ALPINE.JS LOGIC ══════════════ -->', content, re.DOTALL)
footer_content = footer_match.group(1).strip()
write_component("footer.html", footer_content)

# 9. Scripts
scripts_match = re.search(r'<!-- ══════════════ ALPINE.JS LOGIC ══════════════ -->(.*?)$', content, re.DOTALL)
# Extract inner script content or keep everything including the script tag. Let's keep the script tag and script content.
scripts_content = scripts_match.group(1).strip()
# Let's clean the closing tags from scripts_content if any, actually it contains `</body>` and `</html>` at the very end
scripts_content = re.sub(r'</body>\s*</html>\s*$', '', scripts_content).strip()
write_component("scripts.html", scripts_content)

# Now, let's write the clean modular index.html
new_index = """<!DOCTYPE html>
<html lang="en" class="dark h-full">
<head>
  {% include 'components/head.html' %}
</head>
<body class="font-sans text-gray-100 min-h-screen" x-data="app()" x-init="init()">

  {% include 'components/header.html' %}

  <!-- ══════════════ MAIN ══════════════ -->
  <main class="max-w-6xl mx-auto px-6 py-10">
    {% include 'components/toast.html' %}

    <!-- Split Pane Layout -->
    <div class="grid gap-8 lg:grid-cols-12 mb-10">
      {% include 'components/wizard.html' %}
      {% include 'components/actions.html' %}
    </div>

    {% include 'components/registry.html' %}
  </main>

  {% include 'components/modals.html' %}
  {% include 'components/footer.html' %}
  {% include 'components/scripts.html' %}

</body>
</html>
"""

index_path.write_text(new_index, encoding="utf-8")
print("Successfully generated modular index.html!")
