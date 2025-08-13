
def filter_duplicate_commands(commands):
    """
    Simple command deduplication function:
    1. For scripts with filenames, extract filename for matching
    2. For regular commands, remove spaces before comparison
    """
    import re
    
    unique_commands = []
    seen_filenames = set()  # Record seen filenames
    seen_shell_cmds = set() # Record seen shell commands
    
    for cmd_type, cmd_content in commands:
        # Check if it contains filename definition (# filename: xxx)
        filename_match = re.search(r'#\s*filename:\s*([\w.-]+)', cmd_content)
        # import pdb; pdb.set_trace()
        # 
        if filename_match:
            # Has filename, deduplicate by filename
            filename = filename_match.group(1)
            if filename not in seen_filenames:
                seen_filenames.add(filename)
                seen_shell_cmds.add(f"{cmd_type} {filename}")
                unique_commands.append([cmd_type, cmd_content])
        else:
            # Shell commands without filename, normalize before comparison
            # Normalize: remove leading/trailing spaces, replace multiple spaces with single space
            norm_content = re.sub(r'\s+', ' ', cmd_content.strip())            
            if norm_content not in seen_shell_cmds:
                seen_shell_cmds.add(norm_content)
                unique_commands.append([cmd_type, cmd_content])
    
    return unique_commands, seen_shell_cmds


def get_case_data():
  code_exec = [
    [
      "sh", "# filename: setup_environment.sh\npip install --quiet -v --no-cache-dir --global-option=\"--cpp_ext\" --global-option=\"--cuda_ext\" git+https://github.com/NVIDIA/apex\npip install git+https://github.com/mapillary/inplace_abn.git@v1.0.3"
    ],
    [
      "sh", "   sh setup_environment.sh"
    ],
    [
      "sh", "   python train_and_infer.py"
    ]
  ]
  return code_exec

if __name__ == "__main__":

  code_exec = get_case_data()
  # Use this function to filter commands
  filtered_commands, seen_shell_cmds = filter_duplicate_commands(code_exec)
  print(filtered_commands)
  print(seen_shell_cmds)
