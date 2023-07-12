#!/usr/bin/env python3

"""
List distributions supported by neofetch
"""
from __future__ import annotations

import string
import textwrap
from pathlib import Path

import regex
from hypy_utils import write

from hyfetch.distros import AsciiArt

RE_SPLIT = regex.compile('EOF[ \n]*?;;')
RE_COLORS = regex.compile("""(?<=set_colors )[\"#a-z\\d ]+(?=\n)""")


def substr(s: str, start: str, end: str | None = None):
    """
    Get substring between start and end
    """
    start = s.index(start) + len(start)

    if end is None:
        return s[start:]

    return s[start:s.index(end, start)]


def parse_ascii_distros() -> list[AsciiArt]:
    """
    Parse ascii distros from neofetch script
    """
    nf = (Path(__file__).parent.parent / 'neofetch').read_text()

    # Get the content of "get_distro_ascii" function
    nf = nf[nf.index('get_distro_ascii() {\n'):]
    nf = nf[:nf.index('\n}\n')]

    # Remove trailing spaces
    while ' \n' in nf:
        nf = nf.replace(' \n', '\n')

    # Split by blocks
    blocks = [sub.strip() for b in regex.split('case .*? in\n', nf) for sub in RE_SPLIT.split(b)]

    # Parse blocks
    def parse_block(block: str) -> AsciiArt:
        try:
            # Get ascii art
            assert "'EOF'\n" in block
            art = substr(block, "'EOF'\n")

            # Join \
            block = block.replace('\\\n', ' ')

            # Get switch-case matching parameter
            match = block.split('\n')[0].strip()
            assert match.endswith(')')
            match = match[:-1]

            # Get colors
            color = RE_COLORS.findall(block)[0]
            if len(color) == 0:
                raise Exception(block)

            return AsciiArt(match, color, art)

        except AssertionError:
            pass

    out = [parse_block(block) for block in blocks]
    return [v for v in out if v]


def wrap(text: str, max_len: int, leading: str):
    length = max_len - len(leading)
    lines = [line for raw in text.split('\n') for line in textwrap.wrap(raw, length) or ['']]
    return '\n'.join(leading + line if line else line for line in lines)


def generate_help(max_len: int, leading: str):
    distros = sorted(list({a.get_friendly_name() for a in parse_ascii_distros()}), key=str.casefold)

    smalls = [d.replace('_small', '') for d in distros if d.endswith('_small')]
    olds = [d.replace('_old', '') for d in distros if d.endswith('_old')]
    distros = [d for d in distros if not d.endswith('_small') and not d.endswith('_old')]

    out = f"NOTE: {', '.join(distros)} have ascii logos.\n\n"\
          f"NOTE: {', '.join(olds)} have 'old' logo variants, use {{distro}}_old to use them.\n\n" \
          f"NOTE: {', '.join(smalls)} have 'small' logo variants, use {{distro}}_small to use them."

    return wrap(out, max_len, leading)


def match_condition(match: str) -> str:
    """
    Convert simple glob match condition to python
    """
    match = [s.strip() for s in match.split("|")]
    conds = []
    for m in match:
        stripped = m.strip("*'\"").lower()
        if '*' in stripped or '"' in stripped:
            print(f"TODO: Cannot properly parse: {m}")

        # Exact matches
        if m.strip("*") == m:
            conds.append(f"name == '{stripped}'")
            continue

        # Both sides are *
        if m.startswith("*") and m.endswith("*"):
            conds.append(f"(name.startswith('{stripped}') or name.endswith('{stripped}'))")
            continue

        # Ends with *
        if m.endswith("*"):
            conds.append(f"name.startswith('{stripped}')")
            continue

        # Starts with *
        if m.startswith("*"):
            conds.append(f"name.endswith('{stripped}')")
            continue

    return ' or '.join(conds)


def export_distro(d: AsciiArt) -> str:
    """
    Export distro to a python script
    """
    # Escape variable name
    varname = d.name.lower()
    for s in string.punctuation + ' ':
        varname = varname.replace(s, '_')

    # Escape/unescape ascii
    ascii = d.ascii.replace("\\\\", "\\")
    while '"""' in ascii:
        ascii = ascii.replace('"""', '"\\""')

    script = f"""# This file is automatically generated. Please do not modify.

from . import AsciiArt

{varname} = AsciiArt(match=r'''{d.match}''', color='{d.color}', ascii=r\"""
{ascii}
\""")
    """
    write(Path(__file__).parent.parent / f'hyfetch/distros/{varname}.py', script)

    # Generate python script for identifying the distro
    return f"""
    if {match_condition(d.match)}:
        from .{varname} import {varname}
        return {varname}
    """


def export_distros():
    distros = parse_ascii_distros()
    # print('\n'.join(d.match for d in distros))
    py = """# This file is automatically generated. Please do not modify.

from __future__ import annotations

from . import AsciiArt

def detect(name: str) -> AsciiArt | None:
    if not name:
        return None
    name = name.lower()
"""
    py += '\n'.join(export_distro(d).strip('\n') for d in distros)
    write(Path(__file__).parent.parent / f'hyfetch/distros/distro_detector.py', py)


if __name__ == '__main__':
    # print(generate_help(100, ' ' * 32))
    # print(generate_help(100, '# '))
    export_distros()