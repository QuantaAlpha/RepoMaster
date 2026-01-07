from src.core.tool_code_explorer import CodeExplorerTools
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test GlobalCodeTreeBuilder")
    parser.add_argument("repo_path", type=str, help="Path to the repository to parse")
    parser.add_argument("--tool", type=str, help="Tool to use for code exploration", default="find_dependencies")
    parser.add_argument("--entity-id", type=str, help="Specific entity ID to focus on", default=None)
    parser.add_argument("--entity-type", type=str, help="Type of the entity (class, function, module)", default=None)
    
    args = parser.parse_args()

    tools = CodeExplorerTools(args.repo_path)
    if args.tool == "find_dependencies":
        print("=== find_dependencies results ===")
        print(tools.find_dependencies(args.entity_id, args.entity_type))
    elif args.tool == "find_references":
        print("=== find_references results ===")
        print(tools.find_references(args.entity_id, args.entity_type))