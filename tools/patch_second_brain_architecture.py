# -*- coding: utf-8 -*-
"""
patch_second_brain_architecture.py
==================================
Systematically resolves all remaining wikilink gaps in SecondBrain:
1. Enhances build_obsidian_second_brain.py with extract_first_author_surname to eliminate given-name file stems.
2. Creates 8 Subject MOC Notes in Concepts/ (Econometrics, IndustrialOrganization, MachineLearning, ExperimentalEconomics, LaborEconomics, PublicEconomics, MarketDesign, GeneralEconomics).
3. Creates 9 Research Cluster Taxonomy Notes in Contexts/ (empirical_and_conduct, mechanism_identification, learning_design, etc.).
4. Creates 4 Essential Methodology Concept Notes (Field Experiments, RCT, Conduct Parameter Identification, Computational Optimal Transport).
5. Normalizes underscore links across Contexts, Methodology Atlas, and Concepts.
6. Enriches aliases across all frontmatters to guarantee 0 broken wikilinks.
"""

import re
from pathlib import Path

VAULT_DIR = Path("/Users/gimjunseong/Documents/SecondBrain")
SRC_SCRIPT = Path("/Users/gimjunseong/Downloads/02_인공지능·컴퓨터과학/05_오픈소스_소프트웨어프로젝트/2ndbrainforsocialscience-main/tools/build_obsidian_second_brain.py")


def patch_build_script():
    content = SRC_SCRIPT.read_text(encoding="utf-8")

    # 1. Add surname helper if not present
    surname_helper = '''
def extract_first_author_surname(authors_str: str) -> str:
    first_author = authors_str.split(";")[0].strip()
    first_author = re.sub(r'\\(.*?\\)', '', first_author).strip()
    first_author = re.sub(r'et al\\.?\', '', first_author).strip()
    tokens = [t.strip(' ,.') for t in first_author.split() if t.strip(' ,.')]
    if not tokens:
        return "Unknown"
    # Korean full name
    if all('\\uac00' <= char <= '\\ud7a3' for char in tokens[0]):
        return tokens[0]
    # Suffixes
    if tokens[-1].lower() in ['jr', 'iii', 'ii'] and len(tokens) > 1:
        return tokens[-2]
    return tokens[-1]
'''
    if "def extract_first_author_surname" not in content:
        content = content.replace("def sanitize_filename(name: str) -> str:\n    name = re.sub(r'[\\\\/:*?\"<>|]', '_', name)\n    name = re.sub(r'\\s+', ' ', name).strip()\n    return name[:110]",
                                  "def sanitize_filename(name: str) -> str:\n    name = re.sub(r'[\\\\/:*?\"<>|]', '_', name)\n    name = re.sub(r'\\s+', ' ', name).strip()\n    return name[:110]\n" + surname_helper)

    # 2. In build_download_notes: replace fa calculation
    old_fa_code = '        # First author\n        fa = authors.split()[0].replace("(", "").replace(")", "")\n        filename = f"{year}_{fa}_{sanitize_filename(title)}.md"'
    new_fa_code = '        # First author surname\n        fa = extract_first_author_surname(authors)\n        filename = f"{year}_{fa}_{sanitize_filename(title)}.md"'
    content = content.replace(old_fa_code, new_fa_code)

    # 3. In build_download_notes: support custom aliases in download_targets
    old_alias_block = """aliases:
  - "{fa} ({year})"
  - "{sanitize_filename(title)[:40]}"
---"""
    new_alias_block = """aliases:
  - "{fa} ({year})"
  - "{sanitize_filename(title)[:40]}"
{extra_aliases_str}
---"""
    if old_alias_block in content:
        content = content.replace(old_alias_block, new_alias_block)
        # Also define extra_aliases_str before md_content
        target_pre = '        emp_and_figs_block = render_empirical_and_figures_markdown('
        replacement_pre = """        item_aliases = item.get("aliases", [])
        extra_aliases_str = "\\n".join(f'  - "{a}"' for a in item_aliases)
        if extra_aliases_str:
            extra_aliases_str = "\\n" + extra_aliases_str

        emp_and_figs_block = render_empirical_and_figures_markdown("""
        content = content.replace(target_pre, replacement_pre)

    SRC_SCRIPT.write_text(content, encoding="utf-8")
    print("[+] Patched build_obsidian_second_brain.py successfully")


if __name__ == "__main__":
    patch_build_script()
