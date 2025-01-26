from rich.tree import Tree
from rich.console import Console
import os

def build_tree(root_path, tree):
    for item in sorted(os.listdir(root_path)):
        item_path = os.path.join(root_path, item)
        if os.path.isdir(item_path):
            branch = tree.add(f"[bold blue]{item}/[/bold blue]")
            build_tree(item_path, branch)
        else:
            tree.add(item)

if __name__ == "__main__":
    console = Console()
    root_directory = '.'  # You can change this to any directory you want
    tree = Tree(f"[bold green]{root_directory}[/bold green]")
    build_tree(root_directory, tree)
    console.print(tree)