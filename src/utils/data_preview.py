"""
Contains functions to manually generate a textual preview of some common file types (.csv, .json,..) for the agent.
"""

import json
from pathlib import Path

import humanize
import pandas as pd
from genson import SchemaBuilder
from pandas.api.types import is_numeric_dtype

# these files are treated as code (e.g. markdown wrapped)
code_files = {".py", ".sh", ".yaml", ".yml", ".md", ".html", ".xml", ".log", ".rst"}
# we treat these files as text (rather than binary) files
plaintext_files = {".txt", ".csv", ".json", ".tsv"} | code_files


def get_file_len_size(f: Path) -> tuple[int, str]:
    """
    Calculate the size of a file (#lines for plaintext files, otherwise #bytes)
    Also returns a human-readable string representation of the size.
    """
    if f.suffix in plaintext_files:
        num_lines = sum(1 for _ in open(f))
        return num_lines, f"{num_lines} lines"
    else:
        s = f.stat().st_size
        return s, humanize.naturalsize(s)


def file_tree(path, depth=0, max_depth=3, show_size=True) -> str:
    """Generate a tree structure of files in a directory"""
    result = []
    files = [p for p in Path(path).iterdir() if not p.is_dir()]
    dirs = [p for p in Path(path).iterdir() if p.is_dir()]
    
    # Reduce the number of files and directories displayed level by level based on depth
    if depth == 0:
        max_n = 10 if len(files) > 30 else  15
        max_dirs = 8 if len(dirs) > 30 else 10
    elif depth == 1:
        max_n = 6 if len(files) > 30 else 6
        max_dirs = 4 if len(dirs) > 15 else 4
    elif depth == 2:
        max_n = 4 if len(files) > 30 else 4
        max_dirs = 2 if len(dirs) > 10 else 2
    else:
        max_n = 4 if len(files) > 30 else 4
        max_dirs = 2 if len(dirs) > 8 else 2
    
    
    for p in sorted(files)[:max_n]:
        if show_size:
            result.append(f"{' '*depth*4}{p.name} ({get_file_len_size(p)[1]})")
        else:
            result.append(f"{' '*depth*4}{p.name}")
    if len(files) > max_n:
        result.append(f"{' '*depth*4}... and {len(files)-max_n} other files")

    for p in sorted(dirs)[:max_dirs]:
        result.append(f"{' '*depth*4}{p.name}/")
        if depth <= max_depth:
            result.append(file_tree(p, depth + 1, max_depth, show_size))
    if len(dirs) > max_dirs:
        result.append(f"{' '*depth*4}... and {len(dirs)-max_dirs} other directories")

    return "\n".join(result)


def _walk(path: Path):
    """Recursively walk a directory (analogous to os.walk but for pathlib.Path)"""
    for p in sorted(Path(path).iterdir()):
        if p.is_dir():
            yield from _walk(p)
            continue
        yield p


def preview_csv(p: Path, file_name: str, simple=True) -> str:
    """Generate a textual preview of a csv file

    Args:
        p (Path): the path to the csv file
        file_name (str): the file name to use in the preview
        simple (bool, optional): whether to use a simplified version of the preview. Defaults to True.

    Returns:
        str: the textual preview
    """
    df = pd.read_csv(p)

    out = []

    out.append(f"-> {file_name} has {df.shape[0]} rows and {df.shape[1]} columns.")

    if simple:
        cols = df.columns.tolist()
        sel_cols = 15
        cols_str = ", ".join(cols[:sel_cols])
        res = f"The columns are: {cols_str}"
        if len(cols) > sel_cols:
            res += f"... and {len(cols)-sel_cols} more columns"
        out.append(res)
    else:
        out.append("Here is some information about the columns:")
        for col in sorted(df.columns):
            dtype = df[col].dtype
            name = f"{col} ({dtype})"

            nan_count = df[col].isnull().sum()

            if dtype == "bool":
                v = df[col][df[col].notnull()].mean()
                out.append(f"{name} is {v*100:.2f}% True, {100-v*100:.2f}% False")
            elif df[col].nunique() < 10:
                out.append(
                    f"{name} has {df[col].nunique()} unique values: {df[col].unique().tolist()}"
                )
            elif is_numeric_dtype(df[col]):
                out.append(
                    f"{name} has range: {df[col].min():.2f} - {df[col].max():.2f}, {nan_count} nan values"
                )
            elif dtype == "object":
                out.append(
                    f"{name} has {df[col].nunique()} unique values. Some example values: {df[col].value_counts().head(4).index.tolist()}"
                )

    return "\n".join(out)


def preview_json(p: Path, file_name: str):
    """Generate a textual preview of a json file using a generated json schema"""
    builder = SchemaBuilder()
    with open(p) as f:
        builder.add_object(json.load(f))
    return f"-> {file_name} has auto-generated json schema:\n" + builder.to_json(
        indent=2
    )


def generate_preview(base_path, include_file_details=True, simple=False, max_depth=3):
    """
    Generate a textual preview of a directory, including an overview of the directory
    structure and previews of individual files
    """
    tree = f"```\n{file_tree(base_path, max_depth=max_depth)}```"
    out = [tree]

    if include_file_details:
        for fn in _walk(base_path):
            file_name = str(fn.relative_to(base_path))

            if fn.suffix == ".csv":
                out.append(preview_csv(fn, file_name, simple=simple))
            elif fn.suffix == ".json":
                out.append(preview_json(fn, file_name))
            elif fn.suffix in plaintext_files:
                if get_file_len_size(fn)[0] < 30:
                    with open(fn) as f:
                        content = f.read()
                        if fn.suffix in code_files:
                            content = f"```\n{content}\n```"
                        out.append(f"-> {file_name} has content:\n\n{content}")

    result = "\n\n".join(out)

    # if the result is very long we generate a simpler version
    if len(result) > 6000 and not simple:
        return generate_preview(
            base_path, include_file_details=include_file_details, simple=True, max_depth=max_depth
        )

    return result

def _parse_ipynb_file(file_path):
    """Parse .ipynb file, extract code cells, remove outputs
    
    Args:
        file_path: .ipynb file path
        
    Returns:
        Extracted Python code content string
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            notebook = json.load(f)
        
        code_cells = []
        
        # Extract all code cell contents
        if 'cells' in notebook:
            for cell in notebook['cells']:
                if cell.get('cell_type') == 'code':
                    # Only extract source code from code cells, ignore outputs
                    source = cell.get('source', [])
                    if isinstance(source, list):
                        code_cells.append(''.join(source))
                    else:
                        code_cells.append(source)
        
        return '\n\n'.join(code_cells)
    except Exception as e:
        return f"Unable to parse .ipynb file {file_path}: {str(e)}"

if __name__ == '__main__':
    res = generate_preview('/mnt/ceph/huacan/Code/Tasks/CodeAgent/data/mle-bench-data/data/dog-breed-identification')
    print(res)
